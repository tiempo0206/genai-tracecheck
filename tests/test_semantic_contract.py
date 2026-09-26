import pytest

from genai_tracecheck.models import SpanRecord
from genai_tracecheck.rule_catalog import SUPPORTED_RULE_IDS
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
        end_time_unix_nano=2_000_000_000,
        attributes=base_attributes,
    )


def _rule_ids(span: SpanRecord) -> set[str]:
    return {finding.rule_id for finding in semantic_findings(span)}


def test_release_rule_catalog_contains_twenty_independently_addressable_rules() -> None:
    assert len(SUPPORTED_RULE_IDS) == 20
    assert {"GTC110", "GTC111", "GTC112"} <= SUPPORTED_RULE_IDS


@pytest.mark.parametrize("tool_name", [None, "", "   "])
def test_execute_tool_requires_a_non_empty_tool_name(tool_name: object) -> None:
    span = _span(
        **{
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": tool_name,
        }
    )

    assert "GTC110" in _rule_ids(span)


def test_execute_tool_accepts_a_non_empty_tool_name() -> None:
    span = _span(
        **{
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": "get_weather",
        }
    )

    assert "GTC110" not in _rule_ids(span)


@pytest.mark.parametrize(
    "finish_reasons",
    [None, "stop", [1], ["stop", 1], ["stop", ""]],
)
def test_response_finish_reasons_reject_non_string_array_shapes(
    finish_reasons: object,
) -> None:
    span = _span(**{"gen_ai.response.finish_reasons": finish_reasons})

    assert "GTC111" in _rule_ids(span)


@pytest.mark.parametrize("finish_reasons", [[], ["stop"], ["stop", "length", "error"]])
def test_response_finish_reasons_accept_string_arrays(finish_reasons: list[str]) -> None:
    span = _span(**{"gen_ai.response.finish_reasons": finish_reasons})

    assert "GTC111" not in _rule_ids(span)


@pytest.mark.parametrize("port", [True, "443", 443.0, 0, -1, 65_536])
def test_server_port_rejects_non_integer_or_out_of_range_values(port: object) -> None:
    span = _span(**{"server.port": port})

    assert "GTC112" in _rule_ids(span)


@pytest.mark.parametrize("port", [1, 443, 65_535])
def test_server_port_accepts_valid_integer_values(port: int) -> None:
    span = _span(**{"server.port": port})

    assert "GTC112" not in _rule_ids(span)
