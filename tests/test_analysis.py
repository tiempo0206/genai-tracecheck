from datetime import UTC, datetime
from pathlib import Path

from genai_tracecheck.analysis import analyze_spans
from genai_tracecheck.loader import load_otlp_json
from genai_tracecheck.models import ContentPolicy, FailureThreshold, Policy

ROOT = Path(__file__).parents[1]
NOW = datetime(2026, 9, 19, tzinfo=UTC)


def test_valid_trace_passes_default_error_threshold() -> None:
    spans = load_otlp_json(ROOT / "examples" / "valid.otlp.json")

    report = analyze_spans(spans, source="valid.otlp.json", generated_at=NOW)

    assert report.passed is True
    assert report.summary.spans == 1
    assert report.summary.genai_spans == 1
    assert report.summary.errors == 0
    assert report.findings == []
    assert report.generated_at == "2026-09-19T00:00:00Z"


def test_risky_trace_reports_structure_semantics_and_privacy() -> None:
    spans = load_otlp_json(ROOT / "examples" / "risky.otlp.json")

    report = analyze_spans(spans, source="risky.otlp.json", generated_at=NOW)

    rule_ids = {finding.rule_id for finding in report.findings}
    assert report.passed is False
    assert {"GTC002", "GTC101", "GTC102", "GTC103", "GTC104", "GTC201", "GTC202"} <= rule_ids
    assert report.summary.errors == 4
    assert report.summary.warnings == 3
    secret_finding = next(item for item in report.findings if item.rule_id == "GTC202")
    assert "sk-exampleSecretValue" not in secret_finding.model_dump_json()


def test_warning_threshold_and_content_policy_are_configurable() -> None:
    spans = load_otlp_json(ROOT / "examples" / "risky.otlp.json")
    policy = Policy(
        fail_on=FailureThreshold.NEVER,
        content_policy=ContentPolicy.ALLOW,
        detect_secret_values=False,
    )

    report = analyze_spans(spans, source="risky.otlp.json", policy=policy, generated_at=NOW)

    assert report.passed is True
    assert "GTC201" not in {finding.rule_id for finding in report.findings}
    assert "GTC202" not in {finding.rule_id for finding in report.findings}
