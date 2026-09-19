"""Load canonical OTLP/HTTP JSON into small internal span records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from genai_tracecheck.models import SpanRecord


class TraceLoadError(ValueError):
    """Raised when an input is not a readable OTLP JSON trace export."""


def _decode_any_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value

    scalar_keys = ("stringValue", "boolValue", "doubleValue", "bytesValue")
    for key in scalar_keys:
        if key in value:
            return value[key]

    if "intValue" in value:
        try:
            return int(value["intValue"])
        except (TypeError, ValueError) as exc:
            raise TraceLoadError(f"invalid OTLP intValue: {value['intValue']!r}") from exc

    if "arrayValue" in value:
        array = value["arrayValue"]
        if not isinstance(array, dict) or not isinstance(array.get("values", []), list):
            raise TraceLoadError("arrayValue.values must be a list")
        return [_decode_any_value(item) for item in array.get("values", [])]

    if "kvlistValue" in value:
        kvlist = value["kvlistValue"]
        if not isinstance(kvlist, dict):
            raise TraceLoadError("kvlistValue must be an object")
        return _decode_attributes(kvlist.get("values", []))

    return value


def _decode_attributes(attributes: Any) -> dict[str, Any]:
    if attributes is None:
        return {}
    if isinstance(attributes, dict):
        return dict(attributes)
    if not isinstance(attributes, list):
        raise TraceLoadError("attributes must be an OTLP key/value list")

    decoded: dict[str, Any] = {}
    for index, item in enumerate(attributes):
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            raise TraceLoadError(f"attribute at index {index} is missing a string key")
        decoded[item["key"]] = _decode_any_value(item.get("value"))
    return decoded


def _optional_int(value: Any, field_name: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise TraceLoadError(f"{field_name} must be an integer or decimal string") from exc


def load_otlp_json(path: str | Path) -> list[SpanRecord]:
    """Load spans from an OTLP/HTTP JSON ExportTraceServiceRequest."""

    input_path = Path(path)
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TraceLoadError(f"cannot read {input_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        message = f"invalid JSON in {input_path}: {exc.msg} at line {exc.lineno}"
        raise TraceLoadError(message) from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("resourceSpans"), list):
        raise TraceLoadError("expected an OTLP JSON object with a resourceSpans list")

    records: list[SpanRecord] = []
    try:
        for resource_index, resource_span in enumerate(payload["resourceSpans"]):
            if not isinstance(resource_span, dict):
                raise TraceLoadError(f"resourceSpans[{resource_index}] must be an object")
            resource = resource_span.get("resource", {})
            if not isinstance(resource, dict):
                raise TraceLoadError(f"resourceSpans[{resource_index}].resource must be an object")
            resource_attributes = _decode_attributes(resource.get("attributes", []))
            scope_spans = resource_span.get("scopeSpans", [])
            if not isinstance(scope_spans, list):
                raise TraceLoadError(f"resourceSpans[{resource_index}].scopeSpans must be a list")

            for scope_index, scope_span in enumerate(scope_spans):
                if not isinstance(scope_span, dict):
                    location = f"resourceSpans[{resource_index}].scopeSpans[{scope_index}]"
                    raise TraceLoadError(f"{location} must be an object")
                scope = scope_span.get("scope", {})
                scope_name = scope.get("name") if isinstance(scope, dict) else None
                spans = scope_span.get("spans", [])
                if not isinstance(spans, list):
                    raise TraceLoadError("scopeSpans.spans must be a list")

                for span_index, span in enumerate(spans):
                    if not isinstance(span, dict):
                        raise TraceLoadError(f"span at index {span_index} must be an object")
                    records.append(
                        SpanRecord(
                            trace_id=str(span.get("traceId", "")).lower(),
                            span_id=str(span.get("spanId", "")).lower(),
                            parent_span_id=(
                                str(span["parentSpanId"]).lower()
                                if span.get("parentSpanId")
                                else None
                            ),
                            name=str(span.get("name", "")),
                            start_time_unix_nano=_optional_int(
                                span.get("startTimeUnixNano"), "startTimeUnixNano"
                            ),
                            end_time_unix_nano=_optional_int(
                                span.get("endTimeUnixNano"), "endTimeUnixNano"
                            ),
                            attributes=_decode_attributes(span.get("attributes", [])),
                            resource_attributes=resource_attributes,
                            scope_name=scope_name if isinstance(scope_name, str) else None,
                        )
                    )
    except ValidationError as exc:
        raise TraceLoadError(f"invalid span data: {exc}") from exc

    return records
