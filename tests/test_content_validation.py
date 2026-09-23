import pytest

from genai_tracecheck.content_validation import (
    INPUT_MESSAGES,
    OUTPUT_MESSAGES,
    SYSTEM_INSTRUCTIONS,
    validate_content_attribute,
)


def test_accepts_multi_part_messages_and_extension_parts() -> None:
    value = [
        {
            "role": "user",
            "parts": [
                {"type": "text", "content": "Weather in Paris?"},
                {
                    "type": "uri",
                    "modality": "image",
                    "uri": "https://example.test/map.png",
                    "mime_type": "image/png",
                },
                {"type": "vendor_extension", "custom": True},
            ],
        },
        {
            "role": "assistant",
            "parts": [
                {
                    "type": "tool_call",
                    "id": "call-1",
                    "name": "get_weather",
                    "arguments": {"city": "Paris"},
                }
            ],
        },
        {
            "role": "tool",
            "parts": [
                {
                    "type": "tool_call_response",
                    "id": "call-1",
                    "response": {"temperature": 18},
                }
            ],
        },
    ]

    result = validate_content_attribute(INPUT_MESSAGES, value)

    assert result.issues == ()
    assert result.deprecated_paths == ()


def test_accepts_json_encoded_system_instructions() -> None:
    value = '[{"type":"text","content":"Be concise."},{"type":"custom"}]'

    result = validate_content_attribute(SYSTEM_INSTRUCTIONS, value)

    assert result.issues == ()


def test_reports_exact_paths_without_echoing_values() -> None:
    secret_content = "do-not-copy-this-private-value"
    value = [
        {"role": "user", "parts": [{"type": "text"}], "name": 42},
        {"role": 7, "parts": "not-an-array", "private": secret_content},
        {"role": "assistant", "parts": [{"type": "tool_call"}]},
    ]

    result = validate_content_attribute(INPUT_MESSAGES, value)

    actual = {(issue.path, issue.constraint) for issue in result.issues}
    assert actual == {
        ("$[0].parts[0].content", "is required"),
        ("$[0].name", "must be a string or null"),
        ("$[1].role", "must be a string"),
        ("$[1].parts", "must be an array"),
        ("$[2].parts[0].name", "is required"),
    }
    assert secret_content not in repr(result)


def test_flags_deprecated_output_finish_reason() -> None:
    value = '[{"role":"assistant","parts":[],"finish_reason":"stop"}]'

    result = validate_content_attribute(OUTPUT_MESSAGES, value)

    assert result.issues == ()
    assert result.deprecated_paths == ("$[0].finish_reason",)


@pytest.mark.parametrize("value", ["not JSON", "{", "private-prompt-text"])
def test_invalid_json_errors_do_not_include_input(value: str) -> None:
    result = validate_content_attribute(INPUT_MESSAGES, value)

    assert result.issues[0].path == "$"
    assert value not in repr(result)


def test_rejects_wrong_root_type() -> None:
    result = validate_content_attribute(INPUT_MESSAGES, '{"role":"user"}')

    assert result.issues[0].path == "$"
    assert result.issues[0].constraint == "must be an array"


def test_rejects_unsupported_attribute_name() -> None:
    with pytest.raises(ValueError, match="unsupported content attribute"):
        validate_content_attribute("gen_ai.unknown", [])


@pytest.mark.parametrize(
    ("part", "expected_paths"),
    [
        (7, {"$[0].parts[0]"}),
        ({}, {"$[0].parts[0].type"}),
        (
            {"type": "server_tool_call", "id": 7, "name": 9},
            {
                "$[0].parts[0].id",
                "$[0].parts[0].name",
                "$[0].parts[0].server_tool_call",
            },
        ),
        (
            {
                "type": "server_tool_call_response",
                "server_tool_call_response": {},
            },
            {"$[0].parts[0].server_tool_call_response.type"},
        ),
        (
            {"type": "blob", "modality": 1, "content": 2, "mime_type": 3},
            {
                "$[0].parts[0].modality",
                "$[0].parts[0].content",
                "$[0].parts[0].mime_type",
            },
        ),
        (
            {"type": "file", "modality": 1, "file_id": 2, "mime_type": 3},
            {
                "$[0].parts[0].modality",
                "$[0].parts[0].file_id",
                "$[0].parts[0].mime_type",
            },
        ),
        (
            {"type": "compaction", "id": 1, "content": 2},
            {"$[0].parts[0].id", "$[0].parts[0].content"},
        ),
    ],
)
def test_known_part_mutations_are_rejected(part: object, expected_paths: set[str]) -> None:
    value = [{"role": "user", "parts": [part]}]

    result = validate_content_attribute(INPUT_MESSAGES, value)

    assert {issue.path for issue in result.issues} == expected_paths


def test_rejects_non_object_messages_and_instruction_parts() -> None:
    messages = validate_content_attribute(OUTPUT_MESSAGES, [7])
    instructions = validate_content_attribute(SYSTEM_INSTRUCTIONS, [7, {"type": "text"}])

    assert {issue.path for issue in messages.issues} == {"$[0]"}
    assert {issue.path for issue in instructions.issues} == {"$[0]", "$[1].content"}


def test_rejects_wrong_finish_reason_type_without_copying_value() -> None:
    result = validate_content_attribute(
        OUTPUT_MESSAGES,
        [{"role": "assistant", "parts": [], "finish_reason": 7}],
    )

    assert {(issue.path, issue.constraint) for issue in result.issues} == {
        ("$[0].finish_reason", "must be a string or null")
    }
    assert result.deprecated_paths == ("$[0].finish_reason",)
