"""Deterministic structural, semantic-convention, and privacy-policy rules."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable

from genai_tracecheck.classification import MODEL_OPERATIONS, TOOL_OPERATION, is_genai_span
from genai_tracecheck.content_validation import SCHEMA_ATTRIBUTES, validate_content_attribute
from genai_tracecheck.models import ContentPolicy, Finding, Policy, Severity, SpanRecord

TRACE_ID = re.compile(r"[0-9a-f]{32}")
SPAN_ID = re.compile(r"[0-9a-f]{16}")

CONTENT_ATTRIBUTES = {
    "gen_ai.input.messages",
    "gen_ai.output.messages",
    "gen_ai.system_instructions",
    "gen_ai.tool.call.arguments",
    "gen_ai.tool.call.result",
    "gen_ai.tool.definitions",
    "gen_ai.retrieval.documents",
    "gen_ai.retrieval.query.text",
}

SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(
        r"(?i)(?:api[_-]?key|authorization|password|secret|token)\s*[:=]\s*['\"]?"
        r"[A-Za-z0-9_./+\-]{8,}"
    ),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)

TIME_TO_FIRST_CHUNK = "gen_ai.response.time_to_first_chunk"

TOKEN_SUBSET_GROUPS = (
    (
        "gen_ai.usage.input_tokens",
        (
            "gen_ai.usage.text.input_tokens",
            "gen_ai.usage.image.input_tokens",
            "gen_ai.usage.audio.input_tokens",
        ),
    ),
    (
        "gen_ai.usage.output_tokens",
        (
            "gen_ai.usage.text.output_tokens",
            "gen_ai.usage.image.output_tokens",
            "gen_ai.usage.audio.output_tokens",
        ),
    ),
    (
        "gen_ai.usage.input_tokens",
        ("gen_ai.usage.cache_read.input_tokens",),
    ),
    (
        "gen_ai.usage.input_tokens",
        ("gen_ai.usage.cache_write.input_tokens",),
    ),
    (
        "gen_ai.usage.output_tokens",
        ("gen_ai.usage.reasoning.output_tokens",),
    ),
    (
        "gen_ai.usage.cache_read.input_tokens",
        (
            "gen_ai.usage.text.cache_read.input_tokens",
            "gen_ai.usage.image.cache_read.input_tokens",
            "gen_ai.usage.audio.cache_read.input_tokens",
        ),
    ),
    (
        "gen_ai.usage.text.input_tokens",
        ("gen_ai.usage.text.cache_read.input_tokens",),
    ),
    (
        "gen_ai.usage.image.input_tokens",
        ("gen_ai.usage.image.cache_read.input_tokens",),
    ),
    (
        "gen_ai.usage.audio.input_tokens",
        ("gen_ai.usage.audio.cache_read.input_tokens",),
    ),
)


def _finding(
    span: SpanRecord,
    rule_id: str,
    severity: Severity,
    message: str,
    attribute: str | None = None,
    **details: object,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        message=message,
        trace_id=span.trace_id,
        span_id=span.span_id,
        attribute=attribute,
        details=details,
    )


def structural_findings(span: SpanRecord) -> Iterable[Finding]:
    if TRACE_ID.fullmatch(span.trace_id) is None or span.trace_id == "0" * 32:
        yield _finding(span, "GTC001", Severity.ERROR, "traceId must be 32 non-zero hex digits")
    if SPAN_ID.fullmatch(span.span_id) is None or span.span_id == "0" * 16:
        yield _finding(span, "GTC001", Severity.ERROR, "spanId must be 16 non-zero hex digits")
    if span.parent_span_id is not None and (
        SPAN_ID.fullmatch(span.parent_span_id) is None or span.parent_span_id == "0" * 16
    ):
        yield _finding(
            span,
            "GTC001",
            Severity.ERROR,
            "parentSpanId must be 16 non-zero hex digits when present",
        )

    if span.start_time_unix_nano is None or span.end_time_unix_nano is None:
        yield _finding(span, "GTC002", Severity.ERROR, "span must include start and end timestamps")
    elif span.end_time_unix_nano < span.start_time_unix_nano:
        yield _finding(span, "GTC002", Severity.ERROR, "span end timestamp precedes its start")


def _valid_token(attributes: dict[str, object], key: str) -> int | None:
    value = attributes.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _latency_findings(span: SpanRecord) -> Iterable[Finding]:
    if TIME_TO_FIRST_CHUNK not in span.attributes:
        return

    value = span.attributes[TIME_TO_FIRST_CHUNK]
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or (isinstance(value, float) and not math.isfinite(value))
        or value < 0
    ):
        yield _finding(
            span,
            "GTC107",
            Severity.ERROR,
            "time to first chunk must be a finite, non-negative number of seconds",
            TIME_TO_FIRST_CHUNK,
        )
        return

    start = span.start_time_unix_nano
    end = span.end_time_unix_nano
    if start is None or end is None or end < start:
        return
    duration_seconds = (end - start) / 1_000_000_000
    if value > duration_seconds:
        yield _finding(
            span,
            "GTC107",
            Severity.ERROR,
            "time to first chunk exceeds the span duration",
            TIME_TO_FIRST_CHUNK,
            observed_seconds=value,
            span_duration_seconds=duration_seconds,
        )


def _token_consistency_findings(span: SpanRecord) -> Iterable[Finding]:
    for aggregate_key, component_keys in TOKEN_SUBSET_GROUPS:
        aggregate = _valid_token(span.attributes, aggregate_key)
        if aggregate is None:
            continue
        components = {
            key: value
            for key in component_keys
            if (value := _valid_token(span.attributes, key)) is not None
        }
        component_sum = sum(components.values())
        if components and component_sum > aggregate:
            yield _finding(
                span,
                "GTC108",
                Severity.ERROR,
                "token usage breakdown exceeds its enclosing aggregate",
                aggregate_key,
                aggregate_value=aggregate,
                component_attributes=sorted(components),
                component_sum=component_sum,
            )

    operation = span.attributes.get("gen_ai.operation.name")
    usage_attributes = sorted(
        key
        for key in span.attributes
        if key.startswith("gen_ai.usage.") and key.endswith("_tokens")
    )
    if operation == TOOL_OPERATION and usage_attributes:
        yield _finding(
            span,
            "GTC109",
            Severity.WARNING,
            "execute_tool spans should not report token usage",
            usage_attributes=usage_attributes,
        )


def semantic_findings(span: SpanRecord) -> Iterable[Finding]:
    operation = span.attributes.get("gen_ai.operation.name")
    operation_is_missing = not isinstance(operation, str) or not operation.strip()
    if operation_is_missing:
        yield _finding(
            span,
            "GTC101",
            Severity.ERROR,
            "GenAI span is missing gen_ai.operation.name",
            "gen_ai.operation.name",
        )

    if operation_is_missing or operation in MODEL_OPERATIONS:
        provider = span.attributes.get("gen_ai.provider.name")
        if not isinstance(provider, str) or not provider.strip():
            yield _finding(
                span,
                "GTC102",
                Severity.WARNING,
                "GenAI provider is unknown; add gen_ai.provider.name when available",
                "gen_ai.provider.name",
            )

        request_model = span.attributes.get("gen_ai.request.model")
        response_model = span.attributes.get("gen_ai.response.model")
        has_model = any(
            isinstance(value, str) and value.strip() for value in (request_model, response_model)
        )
        if not has_model:
            yield _finding(
                span,
                "GTC103",
                Severity.WARNING,
                "GenAI model is unknown; add request or response model when available",
            )

    for key, value in span.attributes.items():
        if key.startswith("gen_ai.usage.") and key.endswith("_tokens"):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                yield _finding(
                    span,
                    "GTC104",
                    Severity.ERROR,
                    "token usage must be a non-negative integer",
                    key,
                )

    yield from _latency_findings(span)
    yield from _token_consistency_findings(span)

    for key in SCHEMA_ATTRIBUTES:
        if key not in span.attributes:
            continue
        validation = validate_content_attribute(key, span.attributes[key])
        for issue in validation.issues:
            yield _finding(
                span,
                "GTC105",
                Severity.ERROR,
                "captured GenAI content does not match its message schema",
                key,
                json_path=issue.path,
                constraint=issue.constraint,
            )
        for path in validation.deprecated_paths:
            yield _finding(
                span,
                "GTC106",
                Severity.WARNING,
                "finish_reason in output messages is deprecated; use "
                "gen_ai.response.finish_reasons",
                key,
                json_path=path,
            )


def privacy_findings(span: SpanRecord, policy: Policy) -> Iterable[Finding]:
    captured = sorted(
        key
        for key in CONTENT_ATTRIBUTES
        if key in span.attributes and span.attributes[key] not in (None, "")
    )
    if not captured:
        return

    if policy.content_policy is not ContentPolicy.ALLOW:
        severity = (
            Severity.ERROR if policy.content_policy is ContentPolicy.FORBID else Severity.WARNING
        )
        yield _finding(
            span,
            "GTC201",
            severity,
            "captured GenAI content requires a privacy review",
            captured_attributes=captured,
            policy=policy.content_policy.value,
        )

    if not policy.detect_secret_values:
        return

    for key in captured:
        serialized = json.dumps(span.attributes[key], ensure_ascii=False, sort_keys=True)
        if any(pattern.search(serialized) for pattern in SECRET_PATTERNS):
            yield _finding(
                span,
                "GTC202",
                Severity.ERROR,
                "secret-shaped value detected in captured GenAI content",
                key,
                redacted=True,
            )


def evaluate_span(span: SpanRecord, policy: Policy) -> list[Finding]:
    findings = list(structural_findings(span))
    if is_genai_span(span):
        findings.extend(semantic_findings(span))
        findings.extend(privacy_findings(span, policy))
    return findings
