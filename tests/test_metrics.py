from pathlib import Path

from genai_tracecheck.loader import load_otlp_json
from genai_tracecheck.metrics import summarize_traces
from genai_tracecheck.models import SpanRecord

ROOT = Path(__file__).parents[1]


def _span(
    trace_id: str,
    span_id: str,
    *,
    start: int | None,
    end: int | None,
    operation: str | None = None,
    input_tokens: object | None = None,
    output_tokens: object | None = None,
) -> SpanRecord:
    attributes: dict[str, object] = {}
    if operation is not None:
        attributes["gen_ai.operation.name"] = operation
    if input_tokens is not None:
        attributes["gen_ai.usage.input_tokens"] = input_tokens
    if output_tokens is not None:
        attributes["gen_ai.usage.output_tokens"] = output_tokens
    return SpanRecord(
        trace_id=trace_id,
        span_id=span_id,
        name=span_id,
        start_time_unix_nano=start,
        end_time_unix_nano=end,
        attributes=attributes,
    )


def test_valid_fixture_has_expected_trace_metrics() -> None:
    spans = load_otlp_json(ROOT / "examples" / "valid.otlp.json")

    metrics = summarize_traces(spans)

    assert len(metrics) == 1
    trace = metrics[0]
    assert trace.trace_duration_ms == 1200.0
    assert trace.model_calls == 1
    assert trace.model_call_duration_ms == 1200.0
    assert trace.tool_calls == 0
    assert trace.observed_input_tokens == 42
    assert trace.observed_output_tokens == 18
    assert trace.observed_total_tokens == 60


def test_parallel_call_durations_are_summed_and_wall_time_is_not() -> None:
    trace_id = "a" * 32
    spans = [
        _span(trace_id, "1" * 16, start=0, end=10_000_000_000),
        _span(
            trace_id,
            "2" * 16,
            start=1_000_000_000,
            end=3_000_000_000,
            operation="chat",
            input_tokens=10,
            output_tokens=5,
        ),
        _span(
            trace_id,
            "3" * 16,
            start=2_000_000_000,
            end=6_000_000_000,
            operation="generate_content",
            input_tokens=20,
            output_tokens=10,
        ),
        _span(
            trace_id,
            "4" * 16,
            start=3_000_000_000,
            end=4_000_000_000,
            operation="execute_tool",
        ),
    ]

    trace = summarize_traces(spans)[0]

    assert trace.spans == 4
    assert trace.genai_spans == 3
    assert trace.trace_duration_ms == 10_000.0
    assert trace.model_calls == 2
    assert trace.model_call_duration_ms == 6_000.0
    assert trace.tool_calls == 1
    assert trace.tool_call_duration_ms == 1_000.0
    assert trace.tokenized_spans == 2
    assert trace.observed_total_tokens == 45


def test_invalid_intervals_and_token_counts_are_excluded_from_metrics() -> None:
    span = _span(
        "b" * 32,
        "5" * 16,
        start=200,
        end=100,
        operation="chat",
        input_tokens=True,
        output_tokens=-1,
    )

    trace = summarize_traces([span])[0]

    assert trace.start_time_unix_nano is None
    assert trace.end_time_unix_nano is None
    assert trace.trace_duration_ms is None
    assert trace.model_calls == 1
    assert trace.model_call_duration_ms == 0.0
    assert trace.tokenized_spans == 0
    assert trace.observed_total_tokens == 0


def test_trace_metrics_are_sorted_by_trace_id() -> None:
    spans = [
        _span("f" * 32, "6" * 16, start=0, end=1),
        _span("0" * 31 + "1", "7" * 16, start=0, end=1),
    ]

    metrics = summarize_traces(spans)

    assert [item.trace_id for item in metrics] == ["0" * 31 + "1", "f" * 32]
