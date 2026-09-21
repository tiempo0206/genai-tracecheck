"""Strict data contracts shared by the loader, rules, and CLI."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    WARNING = "warning"
    ERROR = "error"


class FailureThreshold(StrEnum):
    WARNING = "warning"
    ERROR = "error"
    NEVER = "never"


class ContentPolicy(StrEnum):
    ALLOW = "allow"
    REVIEW = "review"
    FORBID = "forbid"


class TraceCompleteness(StrEnum):
    PARTIAL = "partial"
    COMPLETE = "complete"


class SpanRecord(BaseModel):
    """A small, exporter-independent view of an OTLP span."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    name: str
    start_time_unix_nano: int | None = None
    end_time_unix_nano: int | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    resource_attributes: dict[str, Any] = Field(default_factory=dict)
    scope_name: str | None = None


class Policy(BaseModel):
    """Local policy controls; these are not OpenTelemetry requirements."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    fail_on: FailureThreshold = FailureThreshold.ERROR
    content_policy: ContentPolicy = ContentPolicy.REVIEW
    detect_secret_values: bool = True
    trace_completeness: TraceCompleteness = TraceCompleteness.PARTIAL


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    rule_id: str
    severity: Severity
    message: str
    trace_id: str
    span_id: str
    attribute: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ReportSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    spans: int
    genai_spans: int
    errors: int
    warnings: int


class AnalysisReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: str = "1.0"
    generated_at: str
    source: str
    passed: bool
    fail_on: FailureThreshold
    trace_completeness: TraceCompleteness
    summary: ReportSummary
    findings: list[Finding]
