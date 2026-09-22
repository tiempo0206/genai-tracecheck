from genai_tracecheck.analysis import analyze_spans
from genai_tracecheck.graph_rules import evaluate_trace_graph
from genai_tracecheck.models import Policy, SpanRecord, TraceCompleteness
from genai_tracecheck.rules import structural_findings

TRACE_A = "a" * 32
TRACE_B = "b" * 32


def _span(
    span_id: str,
    *,
    trace_id: str = TRACE_A,
    parent_span_id: str | None = None,
    start: int = 100,
    end: int = 200,
) -> SpanRecord:
    return SpanRecord(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        name=f"span-{span_id}",
        start_time_unix_nano=start,
        end_time_unix_nano=end,
    )


def test_duplicate_span_ids_are_scoped_to_one_trace() -> None:
    duplicate_id = "1" * 16
    spans = [
        _span(duplicate_id),
        _span(duplicate_id),
        _span(duplicate_id, trace_id=TRACE_B),
    ]

    findings = evaluate_trace_graph(spans, Policy())

    duplicates = [finding for finding in findings if finding.rule_id == "GTC003"]
    assert len(duplicates) == 1
    assert duplicates[0].trace_id == TRACE_A
    assert duplicates[0].details["occurrence_count"] == 2


def test_parent_cycles_are_reported_once_in_canonical_order() -> None:
    first = "1" * 16
    second = "2" * 16
    third = "3" * 16
    spans = [
        _span(first, parent_span_id=second),
        _span(second, parent_span_id=third),
        _span(third, parent_span_id=first),
    ]

    findings = evaluate_trace_graph(spans, Policy())

    cycles = [finding for finding in findings if finding.rule_id == "GTC004"]
    assert len(cycles) == 1
    assert cycles[0].span_id == first
    assert cycles[0].details["cycle_span_ids"] == [first, second, third, first]


def test_self_parent_is_a_cycle() -> None:
    span_id = "4" * 16

    findings = evaluate_trace_graph([_span(span_id, parent_span_id=span_id)], Policy())

    cycle = next(finding for finding in findings if finding.rule_id == "GTC004")
    assert cycle.details["cycle_span_ids"] == [span_id, span_id]


def test_child_outside_parent_interval_is_a_warning() -> None:
    parent_id = "5" * 16
    child_id = "6" * 16
    spans = [
        _span(parent_id, start=100, end=200),
        _span(child_id, parent_span_id=parent_id, start=90, end=210),
    ]

    findings = evaluate_trace_graph(spans, Policy())

    timing = next(finding for finding in findings if finding.rule_id == "GTC005")
    assert timing.severity.value == "warning"
    assert timing.details == {
        "parent_span_id": parent_id,
        "violations": ["starts_before_parent", "ends_after_parent"],
    }


def test_missing_parent_depends_on_trace_completeness() -> None:
    child = _span("7" * 16, parent_span_id="8" * 16)

    partial_findings = evaluate_trace_graph([child], Policy())
    complete_findings = evaluate_trace_graph(
        [child],
        Policy(trace_completeness=TraceCompleteness.COMPLETE),
    )

    assert "GTC006" not in {finding.rule_id for finding in partial_findings}
    missing = next(finding for finding in complete_findings if finding.rule_id == "GTC006")
    assert missing.details["parent_span_id"] == "8" * 16


def test_duplicate_parent_is_not_misreported_as_absent() -> None:
    parent_id = "9" * 16
    spans = [
        _span(parent_id),
        _span(parent_id),
        _span("a" * 16, parent_span_id=parent_id),
    ]
    policy = Policy(trace_completeness=TraceCompleteness.COMPLETE)

    findings = evaluate_trace_graph(spans, policy)

    assert "GTC003" in {finding.rule_id for finding in findings}
    assert "GTC006" not in {finding.rule_id for finding in findings}


def test_graph_errors_participate_in_analysis_failure_threshold() -> None:
    child = _span("c" * 16, parent_span_id="d" * 16)
    policy = Policy(trace_completeness=TraceCompleteness.COMPLETE)

    report = analyze_spans([child], source="unit-test", policy=policy)

    assert report.passed is False
    assert report.summary.errors == 1
    assert report.findings[0].rule_id == "GTC006"
    assert report.trace_completeness is TraceCompleteness.COMPLETE


def test_invalid_parent_id_is_a_structural_error_not_a_missing_parent() -> None:
    child = _span("e" * 16, parent_span_id="invalid-parent")

    structural = list(structural_findings(child))
    graph = evaluate_trace_graph(
        [child],
        Policy(trace_completeness=TraceCompleteness.COMPLETE),
    )

    assert any(
        finding.rule_id == "GTC001" and "parentSpanId" in finding.message for finding in structural
    )
    assert "GTC006" not in {finding.rule_id for finding in graph}
