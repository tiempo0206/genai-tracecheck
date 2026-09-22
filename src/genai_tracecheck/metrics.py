"""Compute deterministic per-trace latency and token summaries."""

from __future__ import annotations

from collections import defaultdict

from genai_tracecheck.classification import MODEL_OPERATIONS, TOOL_OPERATION, is_genai_span
from genai_tracecheck.models import SpanRecord, TraceMetrics

INPUT_TOKENS = "gen_ai.usage.input_tokens"
OUTPUT_TOKENS = "gen_ai.usage.output_tokens"


def _duration_nanos(span: SpanRecord) -> int | None:
    start = span.start_time_unix_nano
    end = span.end_time_unix_nano
    if start is None or end is None or end < start:
        return None
    return end - start


def _valid_token_count(span: SpanRecord, attribute: str) -> int | None:
    value = span.attributes.get(attribute)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _milliseconds(nanoseconds: int) -> float:
    return round(nanoseconds / 1_000_000, 6)


def _summarize_trace(trace_id: str, spans: list[SpanRecord]) -> TraceMetrics:
    valid_intervals = [
        (span.start_time_unix_nano, span.end_time_unix_nano)
        for span in spans
        if _duration_nanos(span) is not None
    ]
    start = min((item[0] for item in valid_intervals), default=None)
    end = max((item[1] for item in valid_intervals), default=None)
    trace_duration_ms = None
    if start is not None and end is not None:
        trace_duration_ms = _milliseconds(end - start)

    model_spans = [
        span for span in spans if span.attributes.get("gen_ai.operation.name") in MODEL_OPERATIONS
    ]
    tool_spans = [
        span for span in spans if span.attributes.get("gen_ai.operation.name") == TOOL_OPERATION
    ]
    model_duration = sum(
        duration for span in model_spans if (duration := _duration_nanos(span)) is not None
    )
    tool_duration = sum(
        duration for span in tool_spans if (duration := _duration_nanos(span)) is not None
    )

    input_counts = [
        count for span in spans if (count := _valid_token_count(span, INPUT_TOKENS)) is not None
    ]
    output_counts = [
        count for span in spans if (count := _valid_token_count(span, OUTPUT_TOKENS)) is not None
    ]
    tokenized_spans = sum(
        1
        for span in spans
        if _valid_token_count(span, INPUT_TOKENS) is not None
        or _valid_token_count(span, OUTPUT_TOKENS) is not None
    )
    input_total = sum(input_counts)
    output_total = sum(output_counts)
    return TraceMetrics(
        trace_id=trace_id,
        spans=len(spans),
        genai_spans=sum(is_genai_span(span) for span in spans),
        start_time_unix_nano=start,
        end_time_unix_nano=end,
        trace_duration_ms=trace_duration_ms,
        model_calls=len(model_spans),
        model_call_duration_ms=_milliseconds(model_duration),
        tool_calls=len(tool_spans),
        tool_call_duration_ms=_milliseconds(tool_duration),
        tokenized_spans=tokenized_spans,
        observed_input_tokens=input_total,
        observed_output_tokens=output_total,
        observed_total_tokens=input_total + output_total,
    )


def summarize_traces(spans: list[SpanRecord]) -> list[TraceMetrics]:
    """Return trace summaries in stable trace-ID order."""

    traces: dict[str, list[SpanRecord]] = defaultdict(list)
    for span in spans:
        traces[span.trace_id].append(span)
    return [_summarize_trace(trace_id, traces[trace_id]) for trace_id in sorted(traces)]
