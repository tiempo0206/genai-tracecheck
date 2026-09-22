"""Strict data contracts shared by the loader, rules, and CLI."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from genai_tracecheck.rule_catalog import SUPPORTED_RULE_IDS


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
    disabled_rules: frozenset[str] = Field(default_factory=frozenset)
    severity_overrides: dict[str, Severity] = Field(default_factory=dict)

    @field_validator("disabled_rules")
    @classmethod
    def _validate_disabled_rules(cls, value: frozenset[str]) -> frozenset[str]:
        unknown = sorted(value - SUPPORTED_RULE_IDS)
        if unknown:
            raise ValueError(f"unsupported rule ID(s): {', '.join(unknown)}")
        return value

    @field_validator("severity_overrides")
    @classmethod
    def _validate_severity_rules(cls, value: dict[str, Severity]) -> dict[str, Severity]:
        unknown = sorted(set(value) - SUPPORTED_RULE_IDS)
        if unknown:
            raise ValueError(f"unsupported rule ID(s): {', '.join(unknown)}")
        return value

    @model_validator(mode="after")
    def _validate_rule_settings(self) -> Policy:
        conflicts = sorted(self.disabled_rules & set(self.severity_overrides))
        if conflicts:
            raise ValueError(f"disabled rule(s) cannot override severity: {', '.join(conflicts)}")
        return self


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


class TraceMetrics(BaseModel):
    """Deterministic measurements derived from one trace."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    trace_id: str
    spans: int
    genai_spans: int
    start_time_unix_nano: int | None
    end_time_unix_nano: int | None
    trace_duration_ms: float | None
    model_calls: int
    model_call_duration_ms: float
    tool_calls: int
    tool_call_duration_ms: float
    tokenized_spans: int
    observed_input_tokens: int
    observed_output_tokens: int
    observed_total_tokens: int


class AnalysisReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    report_type: Literal["single"] = "single"
    schema_version: str = "1.0"
    generated_at: str
    source: str
    passed: bool
    fail_on: FailureThreshold
    content_policy: ContentPolicy
    detect_secret_values: bool
    trace_completeness: TraceCompleteness
    disabled_rules: list[str]
    severity_overrides: dict[str, Severity]
    summary: ReportSummary
    traces: list[TraceMetrics]
    findings: list[Finding]


class BatchFileStatus(StrEnum):
    ANALYZED = "analyzed"
    LOAD_ERROR = "load_error"


class BatchSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    files: int
    analyzed_files: int
    load_errors: int
    passed_files: int
    failed_files: int
    spans: int
    genai_spans: int
    traces: int
    errors: int
    warnings: int


class BatchFileResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source: str
    status: BatchFileStatus
    passed: bool
    error: str | None
    summary: ReportSummary | None
    traces: list[TraceMetrics]
    findings: list[Finding]


class BatchReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    report_type: Literal["batch"] = "batch"
    schema_version: str = "1.0"
    generated_at: str
    passed: bool
    fail_on: FailureThreshold
    content_policy: ContentPolicy
    detect_secret_values: bool
    trace_completeness: TraceCompleteness
    disabled_rules: list[str]
    severity_overrides: dict[str, Severity]
    summary: BatchSummary
    files: list[BatchFileResult]
