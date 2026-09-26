"""Content-safe SARIF 2.1.0 conversion for TraceCheck reports."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from genai_tracecheck._version import __version__
from genai_tracecheck.models import (
    AnalysisReport,
    BatchFileStatus,
    BatchReport,
    Finding,
    Severity,
)
from genai_tracecheck.rule_catalog import RULE_METADATA

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
SARIF_VERSION = "2.1.0"
HELP_URI = "https://github.com/tiempo0206/genai-tracecheck#rule-set"
SAFE_FINGERPRINT_DETAIL_KEYS = frozenset(
    {
        "component_attributes",
        "constraint",
        "json_path",
        "policy",
        "redacted",
        "violations",
    }
)


def _source_uri(source: str, working_directory: Path) -> str:
    path = Path(source).expanduser()
    try:
        return path.resolve().relative_to(working_directory.resolve()).as_posix()
    except (OSError, ValueError):
        if path.is_absolute():
            return f"external/{path.name}"
        return path.as_posix()


def _span_region(source: str, span_id: str, working_directory: Path) -> dict[str, int]:
    path = Path(source).expanduser()
    if not path.is_absolute():
        path = working_directory / path
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {"startLine": 1}

    pattern = re.compile(rf'"spanId"\s*:\s*"{re.escape(span_id)}"')
    match = pattern.search(text)
    if match is None:
        return {"startLine": 1}
    key_offset = text.find('"spanId"', match.start(), match.end())
    line_start = text.rfind("\n", 0, key_offset) + 1
    return {
        "startLine": text.count("\n", 0, key_offset) + 1,
        "startColumn": key_offset - line_start + 1,
        "endColumn": key_offset - line_start + len('"spanId"') + 1,
    }


def _fingerprint(finding: Finding, source_uri: str) -> str:
    safe_details = {
        key: finding.details[key]
        for key in sorted(finding.details)
        if key in SAFE_FINGERPRINT_DETAIL_KEYS
    }
    identity = {
        "rule_id": finding.rule_id,
        "source": source_uri,
        "trace_id": finding.trace_id,
        "span_id": finding.span_id,
        "attribute": finding.attribute,
        "message": finding.message,
        "safe_details": safe_details,
    }
    canonical = json.dumps(identity, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _result(
    finding: Finding,
    *,
    source: str,
    working_directory: Path,
    rule_indexes: Mapping[str, int],
) -> dict[str, Any]:
    source_uri = _source_uri(source, working_directory)
    fingerprint = _fingerprint(finding, source_uri)
    properties: dict[str, Any] = {"tracecheck.severity": finding.severity.value}
    if finding.attribute is not None:
        properties["tracecheck.attribute"] = finding.attribute
    return {
        "ruleId": finding.rule_id,
        "ruleIndex": rule_indexes[finding.rule_id],
        "level": "error" if finding.severity is Severity.ERROR else "warning",
        "message": {"text": finding.message},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": source_uri},
                    "region": _span_region(source, finding.span_id, working_directory),
                }
            }
        ],
        "partialFingerprints": {
            "primaryLocationLineHash": fingerprint,
            "genaiTracecheck/v1": fingerprint,
        },
        "properties": properties,
    }


def _finding_sources(
    report: AnalysisReport | BatchReport,
) -> Iterable[tuple[str, Finding]]:
    if isinstance(report, AnalysisReport):
        yield from ((report.source, finding) for finding in report.findings)
        return
    for file_result in report.files:
        if file_result.status is BatchFileStatus.ANALYZED:
            yield from ((file_result.source, finding) for finding in file_result.findings)


def _rules() -> list[dict[str, Any]]:
    return [
        {
            "id": rule_id,
            "name": rule_id,
            "shortDescription": {"text": description},
            "fullDescription": {"text": description},
            "helpUri": HELP_URI,
            "defaultConfiguration": {"level": default_level},
            "properties": {
                "tags": [
                    "opentelemetry",
                    "genai",
                    "privacy" if rule_id.startswith("GTC2") else "quality",
                ]
            },
        }
        for rule_id, (description, default_level) in sorted(RULE_METADATA.items())
    ]


def report_to_sarif(
    report: AnalysisReport | BatchReport,
    *,
    working_directory: Path | None = None,
) -> dict[str, Any]:
    """Convert a report without copying captured values or trace identifiers."""

    active_directory = working_directory or Path.cwd()
    rules = _rules()
    rule_indexes = {rule["id"]: index for index, rule in enumerate(rules)}
    results = [
        _result(
            finding,
            source=source,
            working_directory=active_directory,
            rule_indexes=rule_indexes,
        )
        for source, finding in _finding_sources(report)
    ]
    load_errors = report.summary.load_errors if isinstance(report, BatchReport) else 0
    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "GenAI TraceCheck",
                        "semanticVersion": __version__,
                        "informationUri": "https://github.com/tiempo0206/genai-tracecheck",
                        "rules": rules,
                    }
                },
                "automationDetails": {"id": "genai-tracecheck/"},
                "results": results,
                "properties": {
                    "tracecheck.reportType": report.report_type,
                    "tracecheck.qualityGatePassed": report.passed,
                    "tracecheck.loadErrors": load_errors,
                },
            }
        ],
    }
