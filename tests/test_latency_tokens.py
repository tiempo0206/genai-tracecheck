import pytest

from genai_tracecheck.models import SpanRecord
from genai_tracecheck.rules import semantic_findings


def _span(**attributes: object) -> SpanRecord:
    base_attributes = {
        "gen_ai.operation.name": "chat",
        "gen_ai.provider.name": "example",
        "gen_ai.request.model": "example-model",
    }
    base_attributes.update(attributes)
    return SpanRecord(
        trace_id="a" * 32,
        span_id="1" * 16,
        name="chat example-model",
        start_time_unix_nano=1_000_000_000,
        end_time_unix_nano=3_000_000_000,
        attributes=base_attributes,
    )


@pytest.mark.parametrize("value", [-0.1, "0.5", float("inf"), float("nan"), True, 10**400])
def test_rejects_invalid_time_to_first_chunk(value: object) -> None:
    span = _span(**{"gen_ai.response.time_to_first_chunk": value})

    findings = list(semantic_findings(span))

    assert "GTC107" in {finding.rule_id for finding in findings}


@pytest.mark.parametrize("value", [0, 0.5, 2.0])
def test_accepts_time_to_first_chunk_within_span(value: float) -> None:
    span = _span(**{"gen_ai.response.time_to_first_chunk": value})

    findings = list(semantic_findings(span))

    assert "GTC107" not in {finding.rule_id for finding in findings}


def test_rejects_time_to_first_chunk_larger_than_span_duration() -> None:
    span = _span(**{"gen_ai.response.time_to_first_chunk": 2.1})

    finding = next(item for item in semantic_findings(span) if item.rule_id == "GTC107")

    assert finding.details == {"observed_seconds": 2.1, "span_duration_seconds": 2.0}


def test_modality_input_sum_cannot_exceed_input_total() -> None:
    span = _span(
        **{
            "gen_ai.usage.input_tokens": 100,
            "gen_ai.usage.text.input_tokens": 80,
            "gen_ai.usage.image.input_tokens": 30,
        }
    )

    finding = next(item for item in semantic_findings(span) if item.rule_id == "GTC108")

    assert finding.attribute == "gen_ai.usage.input_tokens"
    assert finding.details["component_sum"] == 110


def test_reasoning_tokens_cannot_exceed_output_total() -> None:
    span = _span(
        **{
            "gen_ai.usage.output_tokens": 50,
            "gen_ai.usage.reasoning.output_tokens": 51,
        }
    )

    finding = next(item for item in semantic_findings(span) if item.rule_id == "GTC108")

    assert finding.attribute == "gen_ai.usage.output_tokens"
    assert finding.details["component_sum"] == 51


def test_modality_cache_sum_cannot_exceed_cache_total() -> None:
    span = _span(
        **{
            "gen_ai.usage.input_tokens": 100,
            "gen_ai.usage.cache_read.input_tokens": 40,
            "gen_ai.usage.text.cache_read.input_tokens": 30,
            "gen_ai.usage.image.cache_read.input_tokens": 20,
        }
    )

    findings = [item for item in semantic_findings(span) if item.rule_id == "GTC108"]

    assert len(findings) == 1
    assert findings[0].attribute == "gen_ai.usage.cache_read.input_tokens"
    assert findings[0].details["component_sum"] == 50


def test_partial_token_breakdowns_do_not_need_to_equal_total() -> None:
    span = _span(
        **{
            "gen_ai.usage.input_tokens": 100,
            "gen_ai.usage.text.input_tokens": 60,
        }
    )

    findings = list(semantic_findings(span))

    assert "GTC108" not in {finding.rule_id for finding in findings}


def test_execute_tool_token_usage_is_a_warning_without_model_metadata_noise() -> None:
    span = SpanRecord(
        trace_id="a" * 32,
        span_id="1" * 16,
        name="execute_tool get_weather",
        start_time_unix_nano=1_000_000_000,
        end_time_unix_nano=3_000_000_000,
        attributes={
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": "get_weather",
            "gen_ai.usage.input_tokens": 10,
        },
    )

    findings = list(semantic_findings(span))
    rule_ids = {finding.rule_id for finding in findings}

    assert rule_ids == {"GTC109"}
    assert findings[0].severity.value == "warning"
