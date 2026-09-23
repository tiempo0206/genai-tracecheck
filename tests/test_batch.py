import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from genai_tracecheck.batch import InputResolutionError, analyze_batch, resolve_input_paths
from genai_tracecheck.cli import main

ROOT = Path(__file__).parents[1]
EXAMPLES = ROOT / "examples"


def test_resolve_inputs_is_recursive_deduplicated_and_deterministic(tmp_path: Path) -> None:
    top = tmp_path / "z.json"
    nested = tmp_path / "nested" / "a.json"
    hidden = tmp_path / ".private" / "hidden.json"
    ignored = tmp_path / "notes.txt"
    for path in (top, nested, hidden, ignored):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")

    paths = resolve_input_paths([top, tmp_path, str(tmp_path / "**" / "*.json"), ignored, top])

    assert paths == sorted([nested.resolve(), ignored.resolve(), top.resolve()])
    assert hidden.resolve() not in paths


def test_resolve_inputs_rejects_an_unmatched_argument(tmp_path: Path) -> None:
    with pytest.raises(InputResolutionError, match="matched no files"):
        resolve_input_paths([tmp_path / "missing"])


def test_resolve_inputs_rejects_an_empty_argument_list() -> None:
    with pytest.raises(InputResolutionError, match="at least one batch input"):
        resolve_input_paths([])


def test_glob_that_matches_a_directory_discovers_its_json_files(tmp_path: Path) -> None:
    nested = tmp_path / "matched-directory"
    nested.mkdir()
    trace = nested / "trace.json"
    trace.write_text("{}", encoding="utf-8")

    paths = resolve_input_paths([str(tmp_path / "matched-*")])

    assert paths == [trace.resolve()]


def test_analyze_batch_rejects_an_empty_file_sequence() -> None:
    with pytest.raises(InputResolutionError, match="at least one resolved file"):
        analyze_batch([])


def test_analyze_batch_aggregates_valid_and_failing_files() -> None:
    paths = resolve_input_paths([EXAMPLES / "risky.otlp.json", EXAMPLES / "valid.otlp.json"])

    report = analyze_batch(paths, generated_at=datetime(2026, 9, 23, tzinfo=UTC))

    assert report.generated_at == "2026-09-23T00:00:00Z"
    assert report.passed is False
    assert report.summary.files == 2
    assert report.summary.analyzed_files == 2
    assert report.summary.load_errors == 0
    assert report.summary.passed_files == 1
    assert report.summary.failed_files == 1
    assert report.summary.spans == 2
    assert report.summary.traces == 2
    assert [Path(result.source).name for result in report.files] == [
        "risky.otlp.json",
        "valid.otlp.json",
    ]
    assert sum(result.summary.errors for result in report.files if result.summary) == (
        report.summary.errors
    )
    assert sum(result.summary.warnings for result in report.files if result.summary) == (
        report.summary.warnings
    )


def test_analyze_batch_records_load_errors_without_aborting(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("not json", encoding="utf-8")
    paths = resolve_input_paths([EXAMPLES / "valid.otlp.json", broken])

    report = analyze_batch(paths)

    assert report.passed is False
    assert report.summary.files == 2
    assert report.summary.analyzed_files == 1
    assert report.summary.load_errors == 1
    assert report.summary.passed_files == 1
    assert report.summary.failed_files == 1
    failed = next(result for result in report.files if result.status == "load_error")
    assert failed.summary is None
    assert failed.traces == []
    assert failed.findings == []
    assert "invalid JSON" in (failed.error or "")


def test_batch_cli_accepts_a_directory_and_returns_quality_exit_code(
    tmp_path: Path, capsys
) -> None:
    shutil.copy(EXAMPLES / "valid.otlp.json", tmp_path / "b-valid.json")
    shutil.copy(EXAMPLES / "risky.otlp.json", tmp_path / "a-risky.json")

    exit_code = main(["batch", str(tmp_path)])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert output["report_type"] == "batch"
    assert output["summary"]["files"] == 2
    assert [Path(item["source"]).name for item in output["files"]] == [
        "a-risky.json",
        "b-valid.json",
    ]


def test_batch_cli_rejects_an_output_that_is_also_an_input(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "report.json"
    shutil.copy(EXAMPLES / "valid.otlp.json", output_path)
    original = output_path.read_text(encoding="utf-8")

    exit_code = main(["batch", str(tmp_path), "--output", str(output_path), "--force"])

    assert exit_code == 2
    assert "output path is also an input" in capsys.readouterr().err
    assert output_path.read_text(encoding="utf-8") == original


def test_batch_cli_expands_a_quoted_glob(tmp_path: Path, capsys) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    shutil.copy(EXAMPLES / "valid.otlp.json", nested / "valid.json")

    exit_code = main(["batch", str(tmp_path / "**" / "*.json")])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["summary"]["files"] == 1


def test_batch_cli_returns_one_for_a_load_error_and_keeps_valid_results(
    tmp_path: Path, capsys
) -> None:
    shutil.copy(EXAMPLES / "valid.otlp.json", tmp_path / "valid.json")
    (tmp_path / "broken.json").write_text("not json", encoding="utf-8")

    exit_code = main(["batch", str(tmp_path)])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert output["summary"]["analyzed_files"] == 1
    assert output["summary"]["load_errors"] == 1
    assert {item["status"] for item in output["files"]} == {"analyzed", "load_error"}


def test_batch_output_status_mentions_load_errors(tmp_path: Path, capsys) -> None:
    (tmp_path / "broken.json").write_text("not json", encoding="utf-8")
    output_path = tmp_path.parent / f"{tmp_path.name}-report.json"

    exit_code = main(["batch", str(tmp_path), "--output", str(output_path)])

    assert exit_code == 1
    assert "1 load error(s)" in capsys.readouterr().err
