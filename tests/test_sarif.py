import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from genai_tracecheck.analysis import analyze_spans
from genai_tracecheck.batch import analyze_batch, resolve_input_paths
from genai_tracecheck.cli import main
from genai_tracecheck.loader import load_otlp_json
from genai_tracecheck.models import Policy, Severity
from genai_tracecheck.rule_catalog import SUPPORTED_RULE_IDS
from genai_tracecheck.sarif import report_to_sarif

ROOT = Path(__file__).parents[1]
EXAMPLES = ROOT / "examples"
NOW = datetime(2026, 9, 26, tzinfo=UTC)


def _risky_sarif() -> tuple[list, dict]:
    spans = load_otlp_json(EXAMPLES / "risky.otlp.json")
    report = analyze_spans(
        spans,
        source=str(EXAMPLES / "risky.otlp.json"),
        generated_at=NOW,
    )
    return spans, report_to_sarif(report, working_directory=ROOT)


def test_sarif_uses_supported_schema_rules_and_result_levels() -> None:
    _, document = _risky_sarif()
    run = document["runs"][0]
    results = run["results"]
    rules = run["tool"]["driver"]["rules"]

    assert document["$schema"] == "https://json.schemastore.org/sarif-2.1.0.json"
    assert document["version"] == "2.1.0"
    assert run["tool"]["driver"]["name"] == "GenAI TraceCheck"
    assert {rule["id"] for rule in rules} == SUPPORTED_RULE_IDS
    assert len(results) == 8
    assert {result["level"] for result in results} == {"error", "warning"}
    assert all(rules[result["ruleIndex"]]["id"] == result["ruleId"] for result in results)


def test_sarif_locations_are_repository_relative_and_span_scoped() -> None:
    spans, document = _risky_sarif()
    location = document["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
    region = location["region"]
    source_lines = (EXAMPLES / "risky.otlp.json").read_text(encoding="utf-8").splitlines()

    assert location["artifactLocation"]["uri"] == "examples/risky.otlp.json"
    assert region["startLine"] > 1
    assert '"spanId"' in source_lines[region["startLine"] - 1]
    assert spans[0].span_id in source_lines[region["startLine"] - 1]


def test_sarif_fingerprints_are_stable_and_distinguish_schema_paths() -> None:
    spans = load_otlp_json(EXAMPLES / "malformed-content.otlp.json")
    report = analyze_spans(
        spans,
        source="examples/malformed-content.otlp.json",
        generated_at=NOW,
    )

    first = report_to_sarif(report, working_directory=ROOT)
    second = report_to_sarif(report, working_directory=ROOT)
    fingerprints = [
        result["partialFingerprints"]["primaryLocationLineHash"]
        for result in first["runs"][0]["results"]
    ]

    assert first == second
    assert len(fingerprints) == len(set(fingerprints))
    assert all(len(fingerprint) == 64 for fingerprint in fingerprints)


def test_sarif_does_not_copy_trace_identity_or_captured_values() -> None:
    spans, document = _risky_sarif()
    rendered = json.dumps(document)

    assert spans[0].trace_id not in rendered
    assert spans[0].span_id not in rendered
    assert "api_key=" not in rendered
    assert "sk-exampleSecretValue" not in rendered
    assert "tracecheck.severity" in rendered
    assert "gen_ai.input.messages" in rendered


def test_sarif_uses_effective_severity_after_policy_override() -> None:
    spans = load_otlp_json(EXAMPLES / "structured-content.otlp.json")
    report = analyze_spans(
        spans,
        source="examples/structured-content.otlp.json",
        policy=Policy(severity_overrides={"GTC201": Severity.ERROR}),
        generated_at=NOW,
    )

    result = report_to_sarif(report, working_directory=ROOT)["runs"][0]["results"][0]

    assert result["ruleId"] == "GTC201"
    assert result["level"] == "error"


def test_batch_sarif_preserves_file_locations_and_gate_metadata() -> None:
    paths = resolve_input_paths([EXAMPLES / "risky.otlp.json", EXAMPLES / "valid.otlp.json"])
    report = analyze_batch(paths, generated_at=NOW)

    run = report_to_sarif(report, working_directory=ROOT)["runs"][0]

    assert run["properties"] == {
        "tracecheck.reportType": "batch",
        "tracecheck.qualityGatePassed": False,
        "tracecheck.loadErrors": 0,
    }
    assert {
        result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        for result in run["results"]
    } == {"examples/risky.otlp.json"}


def test_batch_sarif_counts_load_errors_without_creating_results(
    tmp_path: Path,
) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("not json", encoding="utf-8")
    paths = resolve_input_paths([EXAMPLES / "risky.otlp.json", broken])
    report = analyze_batch(paths, generated_at=NOW)

    run = report_to_sarif(report, working_directory=ROOT)["runs"][0]

    assert run["properties"]["tracecheck.loadErrors"] == 1
    assert len(run["results"]) == 8


def test_sarif_anonymizes_external_paths_and_falls_back_to_line_one(
    tmp_path: Path,
) -> None:
    spans = load_otlp_json(EXAMPLES / "risky.otlp.json")
    report = analyze_spans(spans, source="placeholder.json", generated_at=NOW)
    missing_source = tmp_path / "missing.json"
    missing_report = report.model_copy(update={"source": str(missing_source)})

    missing_location = report_to_sarif(missing_report, working_directory=ROOT)["runs"][0][
        "results"
    ][0]["locations"][0]["physicalLocation"]

    assert missing_location["artifactLocation"]["uri"] == "external/missing.json"
    assert missing_location["region"] == {"startLine": 1}

    unmatched_source = tmp_path / "unmatched.json"
    shutil.copy(EXAMPLES / "valid.otlp.json", unmatched_source)
    unmatched_report = report.model_copy(update={"source": str(unmatched_source)})
    unmatched_location = report_to_sarif(unmatched_report, working_directory=ROOT)["runs"][0][
        "results"
    ][0]["locations"][0]["physicalLocation"]

    assert unmatched_location["artifactLocation"]["uri"] == "external/unmatched.json"
    assert unmatched_location["region"] == {"startLine": 1}


def test_cli_prints_and_writes_sarif_without_changing_gate_exit_code(
    tmp_path: Path, capsys
) -> None:
    fixture = str(EXAMPLES / "risky.otlp.json")

    stdout_exit = main(["check", fixture, "--format", "sarif"])
    stdout_document = json.loads(capsys.readouterr().out)
    output_path = tmp_path / "report.sarif"
    file_exit = main(["check", fixture, "--format", "sarif", "--output", str(output_path)])
    file_document = json.loads(output_path.read_text(encoding="utf-8"))

    assert stdout_exit == file_exit == 1
    assert stdout_document["version"] == file_document["version"] == "2.1.0"
    assert len(stdout_document["runs"][0]["results"]) == 8
