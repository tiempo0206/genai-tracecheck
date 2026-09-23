import json
from pathlib import Path

import pytest

from genai_tracecheck.loader import TraceLoadError, load_otlp_json

ROOT = Path(__file__).parents[1]


def _write_payload(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "trace.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_loads_canonical_otlp_json_and_decodes_any_values() -> None:
    spans = load_otlp_json(ROOT / "examples" / "valid.otlp.json")

    assert len(spans) == 1
    span = spans[0]
    assert span.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert span.attributes["gen_ai.usage.input_tokens"] == 42
    assert span.attributes["gen_ai.response.finish_reasons"] == ["stop"]
    assert span.resource_attributes["service.name"] == "travel-assistant"
    assert span.scope_name == "example.instrumentation.genai"


def test_rejects_non_otlp_json(tmp_path: Path) -> None:
    input_path = tmp_path / "invalid.json"
    input_path.write_text('{"spans": []}', encoding="utf-8")

    with pytest.raises(TraceLoadError, match="resourceSpans"):
        load_otlp_json(input_path)


def test_decodes_nested_and_passthrough_any_values(tmp_path: Path) -> None:
    payload = {
        "resourceSpans": [
            {
                "resource": {"attributes": {"service.name": "dictionary-form"}},
                "scopeSpans": [
                    {
                        "scope": "invalid-but-optional",
                        "spans": [
                            {
                                "traceId": "a" * 32,
                                "spanId": "b" * 16,
                                "name": "nested-values",
                                "startTimeUnixNano": "",
                                "attributes": [
                                    {"key": "raw", "value": 7},
                                    {"key": "unknown", "value": {"futureValue": "kept"}},
                                    {
                                        "key": "map",
                                        "value": {
                                            "kvlistValue": {
                                                "values": [
                                                    {
                                                        "key": "nested",
                                                        "value": {"intValue": "4"},
                                                    }
                                                ]
                                            }
                                        },
                                    },
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }

    span = load_otlp_json(_write_payload(tmp_path, payload))[0]

    assert span.start_time_unix_nano is None
    assert span.scope_name is None
    assert span.attributes == {
        "raw": 7,
        "unknown": {"futureValue": "kept"},
        "map": {"nested": 4},
    }
    assert span.resource_attributes == {"service.name": "dictionary-form"}


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ({"intValue": "not-an-integer"}, "invalid OTLP intValue"),
        ({"arrayValue": {"values": "not-a-list"}}, "arrayValue.values"),
        ({"kvlistValue": "not-an-object"}, "kvlistValue must be an object"),
    ],
)
def test_rejects_malformed_any_values(tmp_path: Path, value: object, message: str) -> None:
    payload = {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "a" * 32,
                                "spanId": "b" * 16,
                                "name": "bad-value",
                                "attributes": [{"key": "test", "value": value}],
                            }
                        ]
                    }
                ]
            }
        ]
    }

    with pytest.raises(TraceLoadError, match=message):
        load_otlp_json(_write_payload(tmp_path, payload))


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"resourceSpans": [7]}, r"resourceSpans\[0\] must be an object"),
        ({"resourceSpans": [{"resource": []}]}, r"resourceSpans\[0\].resource"),
        ({"resourceSpans": [{"scopeSpans": {}}]}, "scopeSpans must be a list"),
        ({"resourceSpans": [{"scopeSpans": [7]}]}, r"scopeSpans\[0\] must be an object"),
        (
            {"resourceSpans": [{"scopeSpans": [{"spans": {}}]}]},
            "scopeSpans.spans must be a list",
        ),
        ({"resourceSpans": [{"scopeSpans": [{"spans": [7]}]}]}, "span at index 0"),
        (
            {"resourceSpans": [{"resource": {"attributes": "wrong"}, "scopeSpans": []}]},
            "attributes must be an OTLP key/value list",
        ),
        (
            {"resourceSpans": [{"resource": {"attributes": [{"value": {}}]}, "scopeSpans": []}]},
            "missing a string key",
        ),
    ],
)
def test_rejects_malformed_otlp_nesting(tmp_path: Path, payload: object, message: str) -> None:
    with pytest.raises(TraceLoadError, match=message):
        load_otlp_json(_write_payload(tmp_path, payload))


def test_rejects_missing_files_and_invalid_timestamps(tmp_path: Path) -> None:
    with pytest.raises(TraceLoadError, match="cannot read"):
        load_otlp_json(tmp_path / "missing.json")

    payload = {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "a" * 32,
                                "spanId": "b" * 16,
                                "name": "bad-time",
                                "startTimeUnixNano": "tomorrow",
                            }
                        ]
                    }
                ]
            }
        ]
    }
    with pytest.raises(TraceLoadError, match="startTimeUnixNano"):
        load_otlp_json(_write_payload(tmp_path, payload))
