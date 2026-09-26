import hashlib
import json
from pathlib import Path

from genai_tracecheck.loader import load_otlp_json

ROOT = Path(__file__).parents[1]
EVIDENCE_PATH = ROOT / "upstream" / "openai-default-port-evidence.json"
DRAFT_PATH = ROOT / "docs" / "upstream-contribution-draft.md"


def _evidence() -> dict[str, object]:
    return json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))


def test_upstream_evidence_is_pinned_and_not_marked_published() -> None:
    evidence = _evidence()

    assert evidence["schema_version"] == "1.0"
    assert evidence["researched_at"] == "2026-09-26"
    assert evidence["publication_status"] == "draft_only_owner_review_required"
    assert evidence["upstream"] == {
        "repository": "open-telemetry/opentelemetry-python-genai",
        "revision": "14c76fee1a5270d194bfada07f711352a2d3aa4d",
        "openai_instrumentation_version": "1.2b0",
    }
    assert evidence["semantic_conventions"]["revision"] == (
        "e57c543b4889619eb2a05702471937db5119165d"
    )
    assert all(
        search["result"] == "no_matching_issue_found" for search in evidence["issue_searches"]
    )


def test_upstream_evidence_matches_the_frozen_fixture() -> None:
    evidence = _evidence()
    fixture = evidence["local_fixture"]
    path = ROOT / fixture["path"]
    span = load_otlp_json(path)[0]

    assert hashlib.sha256(path.read_bytes()).hexdigest() == fixture["sha256"]
    assert fixture["implicit_port"] == 443
    assert fixture["observed_attributes"] == {
        "server.address": True,
        "server.port": False,
    }
    assert "server.address" in span.attributes
    assert "server.port" not in span.attributes


def test_upstream_draft_preserves_the_human_review_boundary() -> None:
    draft = DRAFT_PATH.read_text(encoding="utf-8")

    assert "It has **not** been posted upstream" in draft
    assert "rewrite the public message in their own words" in draft
    assert "prohibits AI-generated issue" in draft
    assert "14c76fee1a5270d194bfada07f711352a2d3aa4d" in draft
    assert "e57c543b4889619eb2a05702471937db5119165d" in draft
