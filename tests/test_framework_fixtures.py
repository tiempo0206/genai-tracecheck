import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from genai_tracecheck.analysis import analyze_spans
from genai_tracecheck.loader import load_otlp_json

ROOT = Path(__file__).parents[1]
FIXTURE_DIRECTORY = ROOT / "examples" / "framework"
MANIFEST_PATH = ROOT / "tools" / "framework-fixtures" / "manifest.json"
REQUIREMENTS_PATH = ROOT / "tools" / "framework-fixtures" / "requirements.txt"
NOW = datetime(2026, 9, 23, tzinfo=UTC)


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _requirements() -> dict[str, str]:
    return dict(
        line.split("==", maxsplit=1)
        for line in REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )


def test_framework_fixture_manifest_is_complete_and_content_addressed() -> None:
    manifest = _manifest()

    assert manifest["schema_version"] == "1.0"
    assert manifest["fixture_date"] == "2026-09-23"
    assert manifest["network_access"] is False
    assert manifest["packages"] == _requirements()

    fixtures = manifest["fixtures"]
    assert isinstance(fixtures, list)
    assert {item["source"] for item in fixtures} == {"openai", "langchain"}
    for item in fixtures:
        path = ROOT / item["path"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]


@pytest.mark.parametrize("source", ["openai", "langchain"])
def test_framework_fixture_passes_default_quality_gate(source: str) -> None:
    path = FIXTURE_DIRECTORY / f"{source}-chat.otlp.json"
    spans = load_otlp_json(path)

    report = analyze_spans(spans, source=str(path), generated_at=NOW)

    assert report.passed is True
    assert report.summary.spans == 1
    assert report.summary.genai_spans == 1
    assert report.summary.errors == 0
    assert {finding.rule_id for finding in report.findings} == {"GTC106", "GTC201"}
    assert spans[0].start_time_unix_nano == 1_760_000_000_000_000_000
    assert spans[0].end_time_unix_nano == 1_760_000_000_010_000_000


def test_framework_fixtures_share_scenario_but_preserve_source_differences() -> None:
    openai = load_otlp_json(FIXTURE_DIRECTORY / "openai-chat.otlp.json")[0]
    langchain = load_otlp_json(FIXTURE_DIRECTORY / "langchain-chat.otlp.json")[0]

    common_attributes = {
        "gen_ai.operation.name",
        "gen_ai.input.messages",
        "gen_ai.output.messages",
        "gen_ai.provider.name",
        "gen_ai.request.model",
    }
    assert common_attributes <= openai.attributes.keys()
    assert common_attributes <= langchain.attributes.keys()
    assert openai.attributes["gen_ai.operation.name"] == "chat"
    assert langchain.attributes["gen_ai.operation.name"] == "chat"
    assert openai.scope_name == langchain.scope_name == "opentelemetry.util.genai.handler"

    openai_only = openai.attributes.keys() - langchain.attributes.keys()
    assert openai_only == {
        "gen_ai.response.finish_reasons",
        "gen_ai.response.id",
        "gen_ai.response.model",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "server.address",
    }


def test_framework_fixtures_do_not_contain_credentials() -> None:
    rendered = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(FIXTURE_DIRECTORY.glob("*.json"))
    ).lower()

    assert "fixture-not-a-secret" not in rendered
    assert "authorization" not in rendered
    assert "bearer " not in rendered
    assert "sk-" not in rendered
