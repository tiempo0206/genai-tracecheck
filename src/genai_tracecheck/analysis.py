"""Coordinate rules and produce a stable, machine-readable report."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from genai_tracecheck.classification import is_genai_span
from genai_tracecheck.graph_rules import evaluate_trace_graph
from genai_tracecheck.metrics import summarize_traces
from genai_tracecheck.models import (
    AnalysisReport,
    FailureThreshold,
    Finding,
    Policy,
    ReportSummary,
    Severity,
    SpanRecord,
)
from genai_tracecheck.rules import evaluate_span

SEVERITY_RANK = {Severity.WARNING: 1, Severity.ERROR: 2}
THRESHOLD_RANK = {FailureThreshold.WARNING: 1, FailureThreshold.ERROR: 2}


def _sort_key(finding: Finding) -> tuple[object, ...]:
    return (
        -SEVERITY_RANK[finding.severity],
        finding.rule_id,
        finding.trace_id,
        finding.span_id,
        finding.attribute or "",
    )


def _apply_rule_policy(findings: list[Finding], policy: Policy) -> list[Finding]:
    configured: list[Finding] = []
    for finding in findings:
        if finding.rule_id in policy.disabled_rules:
            continue
        severity = policy.severity_overrides.get(finding.rule_id)
        configured.append(
            finding if severity is None else finding.model_copy(update={"severity": severity})
        )
    return configured


def analyze_spans(
    spans: list[SpanRecord],
    *,
    source: str,
    policy: Policy | None = None,
    generated_at: datetime | None = None,
) -> AnalysisReport:
    """Evaluate normalized spans and return one deterministic analysis report.

    Args:
        spans: Records produced by :func:`load_otlp_json` or another trusted adapter.
        source: Display identity retained in JSON and SARIF output. The analyzer does not read it.
        policy: Effective rule and quality-gate settings. Defaults to :class:`Policy`.
        generated_at: Optional timestamp override for reproducible tests and generated artifacts.

    Returns:
        A strict report containing sorted findings, per-trace metrics, and the gate decision.

    The input list is not mutated. Captured values are inspected only by rule implementations and
    are never copied into findings unless an explicitly reviewed diagnostic contract allows it.
    """

    active_policy = policy or Policy()
    span_findings = [finding for span in spans for finding in evaluate_span(span, active_policy)]
    raw_findings = [*span_findings, *evaluate_trace_graph(spans, active_policy)]
    findings = sorted(_apply_rule_policy(raw_findings, active_policy), key=_sort_key)
    counts = Counter(finding.severity for finding in findings)

    if active_policy.fail_on is FailureThreshold.NEVER:
        passed = True
    else:
        threshold = THRESHOLD_RANK[active_policy.fail_on]
        passed = not any(SEVERITY_RANK[finding.severity] >= threshold for finding in findings)

    timestamp = generated_at or datetime.now(UTC)
    return AnalysisReport(
        generated_at=timestamp.isoformat().replace("+00:00", "Z"),
        source=source,
        passed=passed,
        fail_on=active_policy.fail_on,
        content_policy=active_policy.content_policy,
        detect_secret_values=active_policy.detect_secret_values,
        trace_completeness=active_policy.trace_completeness,
        disabled_rules=sorted(active_policy.disabled_rules),
        severity_overrides=dict(sorted(active_policy.severity_overrides.items())),
        summary=ReportSummary(
            spans=len(spans),
            genai_spans=sum(is_genai_span(span) for span in spans),
            errors=counts[Severity.ERROR],
            warnings=counts[Severity.WARNING],
        ),
        traces=summarize_traces(spans),
        findings=findings,
    )
