"""Cross-span integrity checks for parent/child trace graphs."""

from __future__ import annotations

import re
from collections import defaultdict

from genai_tracecheck.models import (
    Finding,
    Policy,
    Severity,
    SpanRecord,
    TraceCompleteness,
)

SPAN_ID = re.compile(r"[0-9a-f]{16}")


def _finding(
    span: SpanRecord,
    rule_id: str,
    severity: Severity,
    message: str,
    **details: object,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        message=message,
        trace_id=span.trace_id,
        span_id=span.span_id,
        details=details,
    )


def _valid_span_id(value: str | None) -> bool:
    return bool(value and SPAN_ID.fullmatch(value) and value != "0" * 16)


def _canonical_cycle(cycle: list[str]) -> list[str]:
    first_index = min(range(len(cycle)), key=cycle.__getitem__)
    return cycle[first_index:] + cycle[:first_index]


def _find_cycles(parent_by_child: dict[str, str]) -> list[list[str]]:
    """Find cycles in a functional graph without recursion depth limits."""

    completed: set[str] = set()
    cycles: list[list[str]] = []
    for start in sorted(parent_by_child):
        if start in completed:
            continue

        path: list[str] = []
        positions: dict[str, int] = {}
        current: str | None = start
        while current is not None and current not in completed:
            if current in positions:
                cycles.append(_canonical_cycle(path[positions[current] :]))
                break
            positions[current] = len(path)
            path.append(current)
            current = parent_by_child.get(current)
        completed.update(path)
    return sorted(cycles)


def _timing_findings(child: SpanRecord, parent: SpanRecord) -> list[Finding]:
    child_start = child.start_time_unix_nano
    child_end = child.end_time_unix_nano
    parent_start = parent.start_time_unix_nano
    parent_end = parent.end_time_unix_nano
    if None in {child_start, child_end, parent_start, parent_end}:
        return []
    assert child_start is not None
    assert child_end is not None
    assert parent_start is not None
    assert parent_end is not None
    if child_end < child_start or parent_end < parent_start:
        return []

    violations: list[str] = []
    if child_start < parent_start:
        violations.append("starts_before_parent")
    if child_end > parent_end:
        violations.append("ends_after_parent")
    if not violations:
        return []

    return [
        _finding(
            child,
            "GTC005",
            Severity.WARNING,
            "child span lifetime is not contained by its parent span",
            parent_span_id=parent.span_id,
            violations=violations,
        )
    ]


def _trace_findings(spans: list[SpanRecord], policy: Policy) -> list[Finding]:
    findings: list[Finding] = []
    spans_by_id: dict[str, list[SpanRecord]] = defaultdict(list)
    for span in spans:
        spans_by_id[span.span_id].append(span)

    for span_id in sorted(spans_by_id):
        occurrences = spans_by_id[span_id]
        if len(occurrences) > 1:
            findings.append(
                _finding(
                    occurrences[0],
                    "GTC003",
                    Severity.ERROR,
                    "spanId is duplicated within the same trace",
                    occurrence_count=len(occurrences),
                )
            )

    unique_spans = {
        span_id: occurrences[0]
        for span_id, occurrences in spans_by_id.items()
        if len(occurrences) == 1
    }
    parent_by_child: dict[str, str] = {}
    for child_id in sorted(unique_spans):
        child = unique_spans[child_id]
        parent_id = child.parent_span_id
        if parent_id is None or not _valid_span_id(parent_id):
            continue

        parent = unique_spans.get(parent_id)
        if parent is None:
            parent_is_absent = parent_id not in spans_by_id
            if parent_is_absent and policy.trace_completeness is TraceCompleteness.COMPLETE:
                findings.append(
                    _finding(
                        child,
                        "GTC006",
                        Severity.ERROR,
                        "parent span is absent from a complete trace export",
                        parent_span_id=parent_id,
                    )
                )
            continue

        parent_by_child[child_id] = parent_id
        findings.extend(_timing_findings(child, parent))

    for cycle in _find_cycles(parent_by_child):
        anchor = unique_spans[cycle[0]]
        findings.append(
            _finding(
                anchor,
                "GTC004",
                Severity.ERROR,
                "parentSpanId relationships contain a cycle",
                cycle_span_ids=[*cycle, cycle[0]],
            )
        )
    return findings


def evaluate_trace_graph(spans: list[SpanRecord], policy: Policy) -> list[Finding]:
    """Evaluate graph rules independently for every trace ID."""

    traces: dict[str, list[SpanRecord]] = defaultdict(list)
    for span in spans:
        traces[span.trace_id].append(span)

    findings: list[Finding] = []
    for trace_id in sorted(traces):
        findings.extend(_trace_findings(traces[trace_id], policy))
    return findings
