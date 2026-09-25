"""Generate sanitized, deterministic OTLP fixtures from real instrumentations.

The scenarios use an HTTP mock transport and a LangChain fake model. They do
not contact a model provider or require credentials. Runtime IDs and timestamps
are normalized after instrumentation so committed artifacts are reproducible.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from importlib.metadata import version
from pathlib import Path
from typing import Any

FIXTURE_DATE = "2026-09-23"
ROOT = Path(__file__).parents[2]
OUTPUT_DIRECTORY = ROOT / "examples" / "framework"
MANIFEST_PATH = Path(__file__).with_name("manifest.json")
CAPTURE_ENV = "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"

PACKAGES = (
    "httpx",
    "langchain",
    "langchain-core",
    "openai",
    "opentelemetry-api",
    "opentelemetry-instrumentation",
    "opentelemetry-instrumentation-genai-langchain",
    "opentelemetry-instrumentation-genai-openai",
    "opentelemetry-sdk",
    "opentelemetry-semantic-conventions",
    "opentelemetry-util-genai",
)

SCENARIOS = (
    {
        "source": "openai",
        "path": "examples/framework/openai-chat.otlp.json",
        "instrumentation_package": "opentelemetry-instrumentation-genai-openai",
        "scenario": "OpenAI chat completion through an httpx MockTransport",
    },
    {
        "source": "langchain",
        "path": "examples/framework/langchain-chat.otlp.json",
        "instrumentation_package": "opentelemetry-instrumentation-genai-langchain",
        "scenario": "LangChain FakeMessagesListChatModel invocation",
    },
)


def _provider():
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "tracecheck-fixture"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _capture_openai_spans() -> Sequence[Any]:
    import httpx
    from openai import OpenAI
    from opentelemetry.instrumentation.genai.openai import OpenAIInstrumentor

    def response(request: httpx.Request) -> httpx.Response:
        payload = {
            "id": "chatcmpl-tracecheck-fixture",
            "object": "chat.completion",
            "created": 1_760_000_000,
            "model": "fixture-openai-model-2026-09-01",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "The answer is four."},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 9, "completion_tokens": 5, "total_tokens": 14},
        }
        return httpx.Response(200, json=payload, request=request)

    provider, exporter = _provider()
    instrumentor = OpenAIInstrumentor()
    instrumentor.instrument(tracer_provider=provider)
    try:
        with httpx.Client(transport=httpx.MockTransport(response)) as http_client:
            client = OpenAI(
                api_key="fixture-not-a-secret",
                base_url="https://openai.fixture.invalid/v1",
                http_client=http_client,
            )
            client.chat.completions.create(
                model="fixture-openai-model",
                messages=[{"role": "user", "content": "What is two plus two?"}],
            )
    finally:
        instrumentor.uninstrument()
        provider.shutdown()
    return exporter.get_finished_spans()


def _capture_langchain_spans() -> Sequence[Any]:
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage, HumanMessage
    from opentelemetry.instrumentation.genai.langchain import LangChainInstrumentor

    class FixtureChatModel(FakeMessagesListChatModel):
        model_name: str = "fixture-langchain-model"

        @property
        def _identifying_params(self) -> Mapping[str, Any]:
            return {"model_name": self.model_name}

    provider, exporter = _provider()
    instrumentor = LangChainInstrumentor()
    instrumentor.instrument(tracer_provider=provider)
    try:
        model = FixtureChatModel(
            responses=[AIMessage(content="The answer is four.", name="fixture-assistant")]
        )
        model.invoke([HumanMessage(content="What is two plus two?", name="fixture-user")])
    finally:
        instrumentor.uninstrument()
        provider.shutdown()
    return exporter.get_finished_spans()


def _any_value(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, bytes):
        return {"bytesValue": base64.b64encode(value).decode("ascii")}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, Mapping):
        return {
            "kvlistValue": {
                "values": [
                    {"key": str(key), "value": _any_value(item)}
                    for key, item in sorted(value.items())
                ]
            }
        }
    if isinstance(value, Sequence):
        return {"arrayValue": {"values": [_any_value(item) for item in value]}}
    raise TypeError(f"unsupported OpenTelemetry attribute type: {type(value).__name__}")


def _attributes(values: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [{"key": key, "value": _any_value(value)} for key, value in sorted(values.items())]


def _stable_hex(label: str, width: int) -> str:
    return hashlib.sha256(label.encode()).hexdigest()[:width]


def _otlp_document(source: str, spans: Sequence[Any]) -> dict[str, Any]:
    ordered = sorted(spans, key=lambda span: (span.name, span.start_time or 0))
    if not ordered:
        raise RuntimeError(f"{source} instrumentation emitted no spans")

    trace_ids = {
        trace_id: _stable_hex(f"{source}:trace:{index}", 32)
        for index, trace_id in enumerate(
            sorted({span.context.trace_id for span in ordered}), start=1
        )
    }
    span_ids = {
        span.context.span_id: _stable_hex(f"{source}:span:{index}", 16)
        for index, span in enumerate(ordered, start=1)
    }
    scopes: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    base_timestamp = 1_760_000_000_000_000_000

    for index, span in enumerate(ordered):
        scope = span.instrumentation_scope
        scope_key = (scope.name, scope.version or "")
        normalized: dict[str, Any] = {
            "traceId": trace_ids[span.context.trace_id],
            "spanId": span_ids[span.context.span_id],
            "name": span.name,
            "startTimeUnixNano": str(base_timestamp + index * 20_000_000),
            "endTimeUnixNano": str(base_timestamp + index * 20_000_000 + 10_000_000),
            "attributes": _attributes(span.attributes or {}),
        }
        if span.parent is not None and span.parent.span_id in span_ids:
            normalized["parentSpanId"] = span_ids[span.parent.span_id]
        scopes[scope_key].append(normalized)

    scope_spans = []
    for (name, scope_version), normalized_spans in sorted(scopes.items()):
        scope: dict[str, Any] = {"name": name}
        if scope_version:
            scope["version"] = scope_version
        scope_spans.append({"scope": scope, "spans": normalized_spans})

    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {
                            "key": "service.name",
                            "value": {"stringValue": "tracecheck-fixture"},
                        }
                    ]
                },
                "scopeSpans": scope_spans,
            }
        ]
    }


def _render(document: object) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def _generate() -> dict[Path, str]:
    previous_capture = os.environ.get(CAPTURE_ENV)
    os.environ[CAPTURE_ENV] = "span_only"
    try:
        documents = {
            "openai": _otlp_document("openai", _capture_openai_spans()),
            "langchain": _otlp_document("langchain", _capture_langchain_spans()),
        }
    finally:
        if previous_capture is None:
            os.environ.pop(CAPTURE_ENV, None)
        else:
            os.environ[CAPTURE_ENV] = previous_capture

    rendered = {
        ROOT / scenario["path"]: _render(documents[scenario["source"]]) for scenario in SCENARIOS
    }
    package_versions = {package: version(package) for package in PACKAGES}
    manifest_fixtures = []
    for scenario in SCENARIOS:
        fixture_path = ROOT / scenario["path"]
        manifest_fixtures.append(
            {
                **scenario,
                "sha256": hashlib.sha256(rendered[fixture_path].encode()).hexdigest(),
            }
        )
    manifest = {
        "schema_version": "1.0",
        "fixture_date": FIXTURE_DATE,
        "network_access": False,
        "content_capture": "synthetic span content only",
        "normalization": [
            "replace trace and span IDs deterministically",
            "replace runtime timestamps with fixed 10 ms intervals",
            "retain only the synthetic service.name resource attribute",
            "sort scopes, spans, and attributes deterministically",
        ],
        "packages": package_versions,
        "fixtures": manifest_fixtures,
    }
    rendered[MANIFEST_PATH] = _render(manifest)
    return rendered


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify committed fixtures match regeneration without writing files",
    )
    args = parser.parse_args(argv)

    generated = _generate()
    stale = [
        path
        for path, content in generated.items()
        if not path.exists() or path.read_text(encoding="utf-8") != content
    ]
    if args.check:
        for path in stale:
            print(f"stale framework fixture: {path.relative_to(ROOT)}", file=sys.stderr)
        return 1 if stale else 0

    for path, content in generated.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
