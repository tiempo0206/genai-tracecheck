"""Coordinate rules and produce a stable, machine-readable report."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from genai_tracecheck.graph_rules import evaluate_trace_graph
from genai_tracecheck.models import (
    AnalysisReport,
    FailureThreshold,
    Finding,
    Policy,
    ReportSummary,
    Severity,
    SpanRecord,
)
from genai_tracecheck.rules import evaluate_span, is_genai_span

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


def analyze_spans(
    spans: list[SpanRecord],
    *,
    source: str,
    policy: Policy | None = None,
    generated_at: datetime | None = None,
) -> AnalysisReport:
    active_policy = policy or Policy()
    span_findings = [finding for span in spans for finding in evaluate_span(span, active_policy)]
    findings = sorted(
        [*span_findings, *evaluate_trace_graph(spans, active_policy)],
        key=_sort_key,
    )
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
        trace_completeness=active_policy.trace_completeness,
        summary=ReportSummary(
            spans=len(spans),
            genai_spans=sum(is_genai_span(span) for span in spans),
            errors=counts[Severity.ERROR],
            warnings=counts[Severity.WARNING],
        ),
        findings=findings,
    )
