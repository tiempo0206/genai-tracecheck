"""Generate the versioned fixture compatibility matrix.

Every committed OTLP fixture is analyzed with the same default TraceCheck
policy. The output records only metadata, counts, rule IDs, and attribute
presence; it never copies captured prompt or response values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from genai_tracecheck.batch import analyze_batch
from genai_tracecheck.loader import load_otlp_json
from genai_tracecheck.models import BatchFileResult, Finding, Policy, Severity

ROOT = Path(__file__).parents[2]
OUTPUT_PATH = ROOT / "compatibility" / "compatibility-matrix.json"
FRAMEWORK_MANIFEST_PATH = ROOT / "tools" / "framework-fixtures" / "manifest.json"
SNAPSHOT_DATE = "2026-09-25"
GENERATED_AT = datetime(2026, 9, 25, tzinfo=UTC)

SEMCONV_REVISION = "e57c543b4889619eb2a05702471937db5119165d"
SEMCONV_URL = (
    "https://github.com/open-telemetry/semantic-conventions-genai/blob/"
    f"{SEMCONV_REVISION}/model/gen-ai/spans.yaml"
)

FIXTURES = (
    {
        "path": "examples/framework/langchain-chat.otlp.json",
        "kind": "framework_generated",
        "expected_gate": "pass",
        "purpose": "Observe LangChain instrumentation output from an in-process fake model.",
    },
    {
        "path": "examples/framework/openai-chat.otlp.json",
        "kind": "framework_generated",
        "expected_gate": "pass",
        "purpose": "Observe OpenAI instrumentation output from an HTTP mock response.",
    },
    {
        "path": "examples/graph-issues.otlp.json",
        "kind": "synthetic_negative",
        "expected_gate": "fail",
        "purpose": "Exercise duplicate span, cycle, and parent containment findings.",
    },
    {
        "path": "examples/inconsistent-usage.otlp.json",
        "kind": "synthetic_negative",
        "expected_gate": "fail",
        "purpose": "Exercise latency, token subset, and tool-token findings.",
    },
    {
        "path": "examples/latency-tokens.otlp.json",
        "kind": "synthetic_positive",
        "expected_gate": "pass",
        "purpose": "Verify valid latency and token aggregation.",
    },
    {
        "path": "examples/malformed-content.otlp.json",
        "kind": "synthetic_negative",
        "expected_gate": "fail",
        "purpose": "Exercise structured content schema findings.",
    },
    {
        "path": "examples/partial-trace.otlp.json",
        "kind": "synthetic_positive",
        "expected_gate": "pass",
        "purpose": "Verify the default partial-export parent policy.",
    },
    {
        "path": "examples/risky.otlp.json",
        "kind": "synthetic_negative",
        "expected_gate": "fail",
        "purpose": "Exercise structural, semantic, privacy, and secret findings.",
    },
    {
        "path": "examples/structured-content.otlp.json",
        "kind": "synthetic_positive",
        "expected_gate": "pass",
        "purpose": "Verify valid opt-in structured content with privacy review.",
    },
    {
        "path": "examples/valid.otlp.json",
        "kind": "synthetic_positive",
        "expected_gate": "pass",
        "purpose": "Provide the minimal conforming reference trace.",
    },
)

SIGNALS = (
    {"attribute": "gen_ai.operation.name", "requirement_level": "required"},
    {"attribute": "gen_ai.provider.name", "requirement_level": "required"},
    {
        "attribute": "gen_ai.request.model",
        "requirement_level": "conditionally_required_if_available",
    },
    {"attribute": "gen_ai.response.id", "requirement_level": "recommended"},
    {"attribute": "gen_ai.response.model", "requirement_level": "recommended"},
    {"attribute": "gen_ai.response.finish_reasons", "requirement_level": "recommended"},
    {"attribute": "gen_ai.usage.input_tokens", "requirement_level": "recommended"},
    {"attribute": "gen_ai.usage.output_tokens", "requirement_level": "recommended"},
    {"attribute": "server.address", "requirement_level": "recommended"},
    {
        "attribute": "server.port",
        "requirement_level": "conditionally_required_if_server_address",
    },
    {"attribute": "gen_ai.input.messages", "requirement_level": "opt_in"},
    {"attribute": "gen_ai.output.messages", "requirement_level": "opt_in"},
)


def _render(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rule_origin(rule_id: str) -> str:
    if rule_id.startswith("GTC0"):
        return "otel_structure"
    if rule_id.startswith("GTC1"):
        return "otel_genai_semantics"
    return "tracecheck_local_policy"


def _finding_disposition(kind: str, finding: Finding) -> str:
    if kind == "synthetic_negative":
        return "intentional_negative_case"
    if finding.rule_id.startswith("GTC2"):
        return "local_policy"
    if finding.rule_id == "GTC106":
        return "deprecated_shape"
    if finding.severity is Severity.ERROR:
        return "candidate_required_violation"
    return "advisory"


def _fixture_row(catalog_entry: Mapping[str, str], result: BatchFileResult) -> dict[str, Any]:
    if result.summary is None:
        raise RuntimeError(f"fixture did not load: {catalog_entry['path']}: {result.error}")

    expected_pass = catalog_entry["expected_gate"] == "pass"
    dispositions = Counter(
        _finding_disposition(catalog_entry["kind"], finding) for finding in result.findings
    )
    finding_rows = [
        {
            "rule_id": finding.rule_id,
            "severity": finding.severity.value,
            "origin": _rule_origin(finding.rule_id),
            "disposition": _finding_disposition(catalog_entry["kind"], finding),
        }
        for finding in result.findings
    ]
    return {
        **catalog_entry,
        "sha256": _sha256(ROOT / catalog_entry["path"]),
        "actual_gate": "pass" if result.passed else "fail",
        "expectation_match": result.passed is expected_pass,
        "summary": result.summary.model_dump(mode="json"),
        "rule_ids": sorted({finding.rule_id for finding in result.findings}),
        "finding_dispositions": dict(sorted(dispositions.items())),
        "findings": finding_rows,
    }


def _signal_status(signal: Mapping[str, str], present_attributes: set[str]) -> str:
    attribute = signal["attribute"]
    requirement_level = signal["requirement_level"]
    if attribute in present_attributes:
        return "present"
    if requirement_level == "required":
        return "missing_required"
    if requirement_level == "conditionally_required_if_server_address":
        return (
            "missing_conditionally_required"
            if "server.address" in present_attributes
            else "not_applicable"
        )
    if requirement_level == "recommended":
        return "recommended_not_observed"
    if requirement_level == "opt_in":
        return "opt_in_not_observed"
    return "availability_unknown"


def _framework_rows(
    fixture_rows: Sequence[Mapping[str, Any]], framework_manifest: Mapping[str, Any]
) -> list[dict[str, Any]]:
    manifest_by_path = {item["path"]: item for item in framework_manifest["fixtures"]}
    package_versions = framework_manifest["packages"]
    rows = []
    for fixture in fixture_rows:
        if fixture["kind"] != "framework_generated":
            continue
        path = ROOT / fixture["path"]
        spans = load_otlp_json(path)
        present_attributes = {key for span in spans for key in span.attributes}
        signal_rows = [
            {
                **signal,
                "status": _signal_status(signal, present_attributes),
            }
            for signal in SIGNALS
        ]
        required_missing = [
            signal["attribute"]
            for signal in signal_rows
            if signal["status"] in {"missing_required", "missing_conditionally_required"}
        ]
        error_candidates = [
            finding["rule_id"]
            for finding in fixture["findings"]
            if finding["disposition"] == "candidate_required_violation"
        ]
        manifest_entry = manifest_by_path[fixture["path"]]
        rows.append(
            {
                "source": manifest_entry["source"],
                "fixture": fixture["path"],
                "instrumentation_package": manifest_entry["instrumentation_package"],
                "instrumentation_version": package_versions[
                    manifest_entry["instrumentation_package"]
                ],
                "signals": signal_rows,
                "required_attributes_missing": required_missing,
                "recommended_attributes_not_observed": [
                    signal["attribute"]
                    for signal in signal_rows
                    if signal["status"] == "recommended_not_observed"
                ],
                "deprecated_shape_findings": [
                    finding["rule_id"]
                    for finding in fixture["findings"]
                    if finding["disposition"] == "deprecated_shape"
                ],
                "local_policy_findings": [
                    finding["rule_id"]
                    for finding in fixture["findings"]
                    if finding["disposition"] == "local_policy"
                ],
                "exporter_defect_candidates": sorted(set(required_missing + error_candidates)),
                "assessment": (
                    "candidate_required_violation"
                    if required_missing or error_candidates
                    else "no_required_violation_observed"
                ),
            }
        )
    return rows


def build_matrix() -> dict[str, Any]:
    catalog_paths = [ROOT / entry["path"] for entry in FIXTURES]
    discovered_paths = sorted(ROOT.glob("examples/**/*.otlp.json"))
    if catalog_paths != discovered_paths:
        missing = sorted(set(discovered_paths) - set(catalog_paths))
        stale = sorted(set(catalog_paths) - set(discovered_paths))
        raise RuntimeError(f"fixture catalog mismatch; missing={missing}, stale={stale}")

    previous_directory = Path.cwd()
    try:
        os.chdir(ROOT)
        batch = analyze_batch(catalog_paths, policy=Policy(), generated_at=GENERATED_AT)
    finally:
        os.chdir(previous_directory)

    results_by_source = {result.source: result for result in batch.files}
    fixture_rows = [_fixture_row(entry, results_by_source[entry["path"]]) for entry in FIXTURES]
    framework_manifest = json.loads(FRAMEWORK_MANIFEST_PATH.read_text(encoding="utf-8"))
    framework_rows = _framework_rows(fixture_rows, framework_manifest)
    exporter_candidates = [
        {"source": row["source"], "items": row["exporter_defect_candidates"]}
        for row in framework_rows
        if row["exporter_defect_candidates"]
    ]

    return {
        "schema_version": "1.0",
        "snapshot_date": SNAPSHOT_DATE,
        "standards_baseline": {
            "name": "OpenTelemetry GenAI semantic conventions",
            "source_revision": SEMCONV_REVISION,
            "source_url": SEMCONV_URL,
            "span_stability": "development",
            "scope": "gen_ai.inference.client attribute requirement levels",
        },
        "analysis_policy": {
            "fail_on": batch.fail_on.value,
            "content_policy": batch.content_policy.value,
            "detect_secret_values": batch.detect_secret_values,
            "trace_completeness": batch.trace_completeness.value,
            "disabled_rules": batch.disabled_rules,
            "severity_overrides": batch.severity_overrides,
        },
        "classification_contract": {
            "candidate_required_violation": (
                "A framework fixture violated a required/structural invariant; reproduce upstream "
                "before calling it an exporter defect."
            ),
            "deprecated_shape": (
                "A deprecated semantic shape was observed; this is migration evidence, not a "
                "required-field failure."
            ),
            "recommended_not_observed": (
                "A recommended attribute was absent; absence is not a defect without evidence that "
                "the source exposed the value."
            ),
            "missing_conditionally_required": (
                "A conditionally required attribute was absent while its stated condition was "
                "observed; record it as an exporter defect candidate pending upstream reproduction."
            ),
            "opt_in_not_observed": (
                "An opt-in content signal was absent; this may be a privacy configuration choice."
            ),
            "local_policy": (
                "A TraceCheck privacy/policy finding, not an exporter conformance claim."
            ),
            "intentional_negative_case": (
                "A synthetic fixture deliberately triggered the rule and is expected to fail."
            ),
        },
        "summary": {
            **batch.summary.model_dump(mode="json"),
            "expected_gate_matches": sum(row["expectation_match"] for row in fixture_rows),
            "framework_fixtures": len(framework_rows),
            "frameworks_with_required_violations": sum(
                row["assessment"] == "candidate_required_violation" for row in framework_rows
            ),
            "exporter_defect_candidates": len(exporter_candidates),
        },
        "exporter_defect_candidates": exporter_candidates,
        "fixtures": fixture_rows,
        "frameworks": framework_rows,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed matrix matches regeneration without writing it",
    )
    args = parser.parse_args(argv)

    rendered = _render(build_matrix())
    stale = not OUTPUT_PATH.exists() or OUTPUT_PATH.read_text(encoding="utf-8") != rendered
    if args.check:
        if stale:
            print(f"stale compatibility matrix: {OUTPUT_PATH.relative_to(ROOT)}", file=sys.stderr)
        return 1 if stale else 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
