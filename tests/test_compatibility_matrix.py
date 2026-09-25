import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
MATRIX_PATH = ROOT / "compatibility" / "compatibility-matrix.json"
GENERATOR_PATH = ROOT / "tools" / "compatibility-matrix" / "generate.py"


def _matrix() -> dict[str, object]:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def test_compatibility_matrix_is_reproducible() -> None:
    result = subprocess.run(
        [sys.executable, str(GENERATOR_PATH), "--check"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_compatibility_matrix_covers_every_fixture_with_verified_bytes() -> None:
    matrix = _matrix()
    fixture_rows = matrix["fixtures"]
    actual_paths = {row["path"] for row in fixture_rows}
    discovered_paths = {
        path.relative_to(ROOT).as_posix() for path in ROOT.glob("examples/**/*.otlp.json")
    }

    assert actual_paths == discovered_paths
    for row in fixture_rows:
        fixture_path = ROOT / row["path"]
        assert hashlib.sha256(fixture_path.read_bytes()).hexdigest() == row["sha256"]


def test_compatibility_matrix_records_expected_gate_results() -> None:
    matrix = _matrix()
    summary = matrix["summary"]

    assert matrix["schema_version"] == "1.0"
    assert matrix["standards_baseline"]["source_revision"] == (
        "e57c543b4889619eb2a05702471937db5119165d"
    )
    assert matrix["standards_baseline"]["span_stability"] == "development"
    assert matrix["analysis_policy"] == {
        "fail_on": "error",
        "content_policy": "review",
        "detect_secret_values": True,
        "trace_completeness": "partial",
        "disabled_rules": [],
        "severity_overrides": {},
    }
    assert summary == {
        "files": 10,
        "analyzed_files": 10,
        "load_errors": 0,
        "passed_files": 6,
        "failed_files": 4,
        "spans": 20,
        "genai_spans": 10,
        "traces": 10,
        "errors": 16,
        "warnings": 12,
        "expected_gate_matches": 10,
        "framework_fixtures": 2,
        "frameworks_with_required_violations": 1,
        "exporter_defect_candidates": 1,
    }
    assert all(row["expectation_match"] for row in matrix["fixtures"])


def test_framework_assessments_separate_absence_from_defects() -> None:
    matrix = _matrix()
    frameworks = {row["source"]: row for row in matrix["frameworks"]}

    assert matrix["exporter_defect_candidates"] == [{"source": "openai", "items": ["server.port"]}]
    assert set(frameworks) == {"openai", "langchain"}
    for row in frameworks.values():
        assert row["deprecated_shape_findings"] == ["GTC106"]
        assert row["local_policy_findings"] == ["GTC201"]

    assert frameworks["openai"]["assessment"] == "candidate_required_violation"
    assert frameworks["openai"]["required_attributes_missing"] == ["server.port"]
    assert frameworks["openai"]["exporter_defect_candidates"] == ["server.port"]
    assert frameworks["openai"]["recommended_attributes_not_observed"] == []
    assert frameworks["langchain"]["assessment"] == "no_required_violation_observed"
    assert frameworks["langchain"]["required_attributes_missing"] == []
    assert frameworks["langchain"]["exporter_defect_candidates"] == []
    assert set(frameworks["langchain"]["recommended_attributes_not_observed"]) == {
        "gen_ai.response.id",
        "gen_ai.response.model",
        "gen_ai.response.finish_reasons",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "server.address",
    }


def test_compatibility_matrix_contains_no_captured_content_or_secret_values() -> None:
    rendered = MATRIX_PATH.read_text(encoding="utf-8").lower()

    assert "what is two plus two" not in rendered
    assert "the answer is four" not in rendered
    assert "sk-examplesecretvalue" not in rendered
    assert "fixture-not-a-secret" not in rendered
