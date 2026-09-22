from datetime import UTC, datetime
from pathlib import Path

from genai_tracecheck.analysis import analyze_spans
from genai_tracecheck.loader import load_otlp_json
from genai_tracecheck.models import ContentPolicy, FailureThreshold, Policy, TraceCompleteness

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
    assert {
        "GTC002",
        "GTC101",
        "GTC102",
        "GTC103",
        "GTC104",
        "GTC105",
        "GTC201",
        "GTC202",
    } <= rule_ids
    assert report.summary.errors == 5
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


def test_structured_content_fixture_passes_with_privacy_warning() -> None:
    spans = load_otlp_json(ROOT / "examples" / "structured-content.otlp.json")

    report = analyze_spans(spans, source="structured-content.otlp.json", generated_at=NOW)

    assert report.passed is True
    assert report.summary.errors == 0
    assert {finding.rule_id for finding in report.findings} == {"GTC201"}


def test_malformed_content_reports_exact_paths() -> None:
    spans = load_otlp_json(ROOT / "examples" / "malformed-content.otlp.json")

    report = analyze_spans(spans, source="malformed-content.otlp.json", generated_at=NOW)

    schema_findings = [finding for finding in report.findings if finding.rule_id == "GTC105"]
    actual = {(finding.attribute, finding.details["json_path"]) for finding in schema_findings}
    assert actual == {
        ("gen_ai.system_instructions", "$"),
        ("gen_ai.input.messages", "$[0].parts[0].content"),
        ("gen_ai.input.messages", "$[1].role"),
        ("gen_ai.input.messages", "$[1].parts"),
        ("gen_ai.input.messages", "$[2].parts[0].name"),
        ("gen_ai.output.messages", "$[0].parts[0].response"),
    }
    assert any(finding.rule_id == "GTC106" for finding in report.findings)


def test_graph_fixture_changes_with_completeness_policy() -> None:
    spans = load_otlp_json(ROOT / "examples" / "graph-issues.otlp.json")

    partial_report = analyze_spans(spans, source="graph-issues.otlp.json", generated_at=NOW)
    complete_report = analyze_spans(
        spans,
        source="graph-issues.otlp.json",
        policy=Policy(trace_completeness=TraceCompleteness.COMPLETE),
        generated_at=NOW,
    )

    assert partial_report.summary.errors == 2
    assert partial_report.summary.warnings == 1
    assert {finding.rule_id for finding in partial_report.findings} == {
        "GTC003",
        "GTC004",
        "GTC005",
    }
    assert complete_report.summary.errors == 3
    assert "GTC006" in {finding.rule_id for finding in complete_report.findings}
