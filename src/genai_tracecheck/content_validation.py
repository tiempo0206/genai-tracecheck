"""Validate content-bearing GenAI attributes without retaining their values."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

INPUT_MESSAGES = "gen_ai.input.messages"
OUTPUT_MESSAGES = "gen_ai.output.messages"
SYSTEM_INSTRUCTIONS = "gen_ai.system_instructions"
SCHEMA_ATTRIBUTES = (INPUT_MESSAGES, OUTPUT_MESSAGES, SYSTEM_INSTRUCTIONS)


@dataclass(frozen=True, slots=True)
class ContentIssue:
    """A value-free schema problem at a JSON path."""

    path: str
    constraint: str


@dataclass(frozen=True, slots=True)
class ContentValidation:
    issues: tuple[ContentIssue, ...]
    deprecated_paths: tuple[str, ...]


def _issue(path: str, constraint: str) -> ContentIssue:
    return ContentIssue(path=path, constraint=constraint)


def _decode_json_string(value: Any) -> tuple[Any | None, list[ContentIssue]]:
    if not isinstance(value, str):
        return value, []
    try:
        return json.loads(value), []
    except json.JSONDecodeError:
        return None, [_issue("$", "must contain valid JSON when encoded as a string")]


def _required_string(value: dict[str, Any], key: str, path: str) -> list[ContentIssue]:
    property_path = f"{path}.{key}"
    if key not in value:
        return [_issue(property_path, "is required")]
    if not isinstance(value[key], str):
        return [_issue(property_path, "must be a string")]
    return []


def _optional_nullable_string(value: dict[str, Any], key: str, path: str) -> list[ContentIssue]:
    if key not in value or value[key] is None:
        return []
    if not isinstance(value[key], str):
        return [_issue(f"{path}.{key}", "must be a string or null")]
    return []


def _required_object(value: dict[str, Any], key: str, path: str) -> list[ContentIssue]:
    property_path = f"{path}.{key}"
    if key not in value:
        return [_issue(property_path, "is required")]
    if not isinstance(value[key], dict):
        return [_issue(property_path, "must be an object")]
    return []


def _required_property(value: dict[str, Any], key: str, path: str) -> list[ContentIssue]:
    if key not in value:
        return [_issue(f"{path}.{key}", "is required")]
    return []


def _validate_server_payload(value: dict[str, Any], key: str, path: str) -> list[ContentIssue]:
    issues = _required_object(value, key, path)
    if issues:
        return issues
    return _required_string(value[key], "type", f"{path}.{key}")


def _validate_part(part: Any, path: str) -> list[ContentIssue]:
    if not isinstance(part, dict):
        return [_issue(path, "must be an object")]

    issues = _required_string(part, "type", path)
    if issues:
        return issues

    part_type = part["type"]
    if part_type in {"text", "reasoning"}:
        issues.extend(_required_string(part, "content", path))
    elif part_type == "tool_call":
        issues.extend(_required_string(part, "name", path))
        issues.extend(_optional_nullable_string(part, "id", path))
    elif part_type == "tool_call_response":
        issues.extend(_required_property(part, "response", path))
        issues.extend(_optional_nullable_string(part, "id", path))
    elif part_type == "server_tool_call":
        issues.extend(_required_string(part, "name", path))
        issues.extend(_optional_nullable_string(part, "id", path))
        issues.extend(_validate_server_payload(part, "server_tool_call", path))
    elif part_type == "server_tool_call_response":
        issues.extend(_optional_nullable_string(part, "id", path))
        issues.extend(_validate_server_payload(part, "server_tool_call_response", path))
    elif part_type == "blob":
        issues.extend(_required_string(part, "modality", path))
        issues.extend(_required_string(part, "content", path))
        issues.extend(_optional_nullable_string(part, "mime_type", path))
    elif part_type == "file":
        issues.extend(_required_string(part, "modality", path))
        issues.extend(_required_string(part, "file_id", path))
        issues.extend(_optional_nullable_string(part, "mime_type", path))
    elif part_type == "uri":
        issues.extend(_required_string(part, "modality", path))
        issues.extend(_required_string(part, "uri", path))
        issues.extend(_optional_nullable_string(part, "mime_type", path))
    elif part_type == "compaction":
        issues.extend(_optional_nullable_string(part, "id", path))
        issues.extend(_optional_nullable_string(part, "content", path))

    # Unknown part types are valid extension points in the upstream GenericPart schema.
    return issues


def _validate_parts(parts: Any, path: str) -> list[ContentIssue]:
    if not isinstance(parts, list):
        return [_issue(path, "must be an array")]
    return [
        issue
        for index, part in enumerate(parts)
        for issue in _validate_part(part, f"{path}[{index}]")
    ]


def _validate_instruction_part(part: Any, path: str) -> list[ContentIssue]:
    if not isinstance(part, dict):
        return [_issue(path, "must be an object")]
    issues = _required_string(part, "type", path)
    if not issues and part["type"] == "text":
        issues.extend(_required_string(part, "content", path))
    return issues


def _validate_message(
    message: Any, path: str, *, output: bool
) -> tuple[list[ContentIssue], list[str]]:
    if not isinstance(message, dict):
        return [_issue(path, "must be an object")], []

    issues = _required_string(message, "role", path)
    issues.extend(_optional_nullable_string(message, "name", path))
    if "parts" not in message:
        issues.append(_issue(f"{path}.parts", "is required"))
    else:
        issues.extend(_validate_parts(message["parts"], f"{path}.parts"))

    deprecated_paths: list[str] = []
    if output and "finish_reason" in message:
        finish_reason_path = f"{path}.finish_reason"
        issues.extend(_optional_nullable_string(message, "finish_reason", path))
        deprecated_paths.append(finish_reason_path)
    return issues, deprecated_paths


def validate_content_attribute(attribute: str, value: Any) -> ContentValidation:
    """Validate one official GenAI content attribute and return only safe metadata."""

    decoded, issues = _decode_json_string(value)
    if issues:
        return ContentValidation(tuple(issues), ())
    if not isinstance(decoded, list):
        return ContentValidation((_issue("$", "must be an array"),), ())

    if attribute == SYSTEM_INSTRUCTIONS:
        instruction_issues = [
            issue
            for index, part in enumerate(decoded)
            for issue in _validate_instruction_part(part, f"$[{index}]")
        ]
        return ContentValidation(tuple(instruction_issues), ())

    if attribute not in {INPUT_MESSAGES, OUTPUT_MESSAGES}:
        raise ValueError(f"unsupported content attribute: {attribute}")

    message_issues: list[ContentIssue] = []
    deprecated_paths: list[str] = []
    for index, message in enumerate(decoded):
        current_issues, current_deprecated = _validate_message(
            message,
            f"$[{index}]",
            output=attribute == OUTPUT_MESSAGES,
        )
        message_issues.extend(current_issues)
        deprecated_paths.extend(current_deprecated)
    return ContentValidation(tuple(message_issues), tuple(deprecated_paths))
