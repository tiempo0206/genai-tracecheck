from pathlib import Path

import pytest

from genai_tracecheck.loader import TraceLoadError, load_otlp_json

ROOT = Path(__file__).parents[1]


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
