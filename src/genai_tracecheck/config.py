"""Load and validate the versioned TOML policy contract."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from genai_tracecheck.models import (
    ContentPolicy,
    FailureThreshold,
    Policy,
    Severity,
    TraceCompleteness,
)
from genai_tracecheck.rule_catalog import SUPPORTED_RULE_IDS


class ConfigurationError(ValueError):
    """Raised when a policy configuration cannot be safely loaded."""


class _PolicySection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    fail_on: Literal["warning", "error", "never"] | None = None
    content_policy: Literal["allow", "review", "forbid"] | None = None
    detect_secret_values: bool | None = None
    trace_completeness: Literal["partial", "complete"] | None = None


class _RuleOverride(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    enabled: bool | None = None
    severity: Literal["warning", "error"] | None = None

    @model_validator(mode="after")
    def _check_meaningful_override(self) -> _RuleOverride:
        if self.enabled is None and self.severity is None:
            raise ValueError("rule override must set enabled or severity")
        if self.enabled is False and self.severity is not None:
            raise ValueError("a disabled rule cannot also override severity")
        return self


class _ConfigurationFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"]
    policy: _PolicySection = Field(default_factory=_PolicySection)
    rules: dict[str, _RuleOverride] = Field(default_factory=dict)


def _validation_details(error: ValidationError) -> str:
    details: list[str] = []
    for item in error.errors(include_url=False, include_input=False):
        location = ".".join(str(part) for part in item["loc"]) or "configuration"
        details.append(f"{location}: {item['msg']}")
    return "; ".join(details)


def load_policy_config(path: str | Path) -> Policy:
    """Load a strict version ``1.0`` TOML configuration into an effective policy.

    Unknown fields, rule IDs, and contradictory overrides are rejected rather than ignored. This
    function performs no implicit configuration discovery.

    Raises:
        ConfigurationError: If the file is unreadable, invalid TOML, or violates the contract.
    """

    config_path = Path(path).expanduser()
    try:
        with config_path.open("rb") as handle:
            payload = tomllib.load(handle)
    except OSError as exc:
        raise ConfigurationError(f"cannot read configuration {config_path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigurationError(f"invalid TOML in {config_path}: {exc}") from exc

    try:
        configuration = _ConfigurationFile.model_validate(payload)
    except ValidationError as exc:
        details = _validation_details(exc)
        raise ConfigurationError(f"invalid configuration {config_path}: {details}") from exc

    unknown_rules = sorted(set(configuration.rules) - SUPPORTED_RULE_IDS)
    if unknown_rules:
        joined = ", ".join(unknown_rules)
        raise ConfigurationError(f"unsupported rule ID(s) in {config_path}: {joined}")

    defaults = Policy()
    configured = configuration.policy
    disabled_rules = frozenset(
        rule_id for rule_id, override in configuration.rules.items() if override.enabled is False
    )
    severity_overrides = {
        rule_id: Severity(override.severity)
        for rule_id, override in sorted(configuration.rules.items())
        if override.severity is not None
    }
    return Policy(
        fail_on=(
            FailureThreshold(configured.fail_on)
            if configured.fail_on is not None
            else defaults.fail_on
        ),
        content_policy=(
            ContentPolicy(configured.content_policy)
            if configured.content_policy is not None
            else defaults.content_policy
        ),
        detect_secret_values=(
            configured.detect_secret_values
            if configured.detect_secret_values is not None
            else defaults.detect_secret_values
        ),
        trace_completeness=(
            TraceCompleteness(configured.trace_completeness)
            if configured.trace_completeness is not None
            else defaults.trace_completeness
        ),
        disabled_rules=disabled_rules,
        severity_overrides=severity_overrides,
    )
