import json
import runpy
import sys
from pathlib import Path

import pytest

import genai_tracecheck.cli as cli
from genai_tracecheck.cli import main

ROOT = Path(__file__).parents[1]


def test_cli_prints_json_and_returns_zero_for_valid_trace(capsys) -> None:
    exit_code = main(["check", str(ROOT / "examples" / "valid.otlp.json")])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["report_type"] == "single"
    assert output["passed"] is True


def test_cli_returns_one_for_policy_failure(capsys) -> None:
    exit_code = main(["check", str(ROOT / "examples" / "risky.otlp.json")])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["passed"] is False


def test_cli_writes_report_atomically_and_requires_force(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "report.json"
    args = [
        "check",
        str(ROOT / "examples" / "valid.otlp.json"),
        "--output",
        str(output_path),
    ]

    assert main(args) == 0
    assert json.loads(output_path.read_text(encoding="utf-8"))["passed"] is True
    assert main(args) == 2
    assert "use --force" in capsys.readouterr().err


def test_cli_accepts_schema_valid_structured_content(capsys) -> None:
    exit_code = main(["check", str(ROOT / "examples" / "structured-content.otlp.json")])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["summary"]["errors"] == 0


def test_cli_trace_completeness_controls_missing_parent(capsys) -> None:
    fixture = str(ROOT / "examples" / "partial-trace.otlp.json")

    partial_exit = main(["check", fixture])
    partial_output = json.loads(capsys.readouterr().out)
    complete_exit = main(["check", fixture, "--trace-completeness", "complete"])
    complete_output = json.loads(capsys.readouterr().out)

    assert partial_exit == 0
    assert partial_output["findings"] == []
    assert partial_output["trace_completeness"] == "partial"
    assert complete_exit == 1
    assert complete_output["trace_completeness"] == "complete"
    assert {finding["rule_id"] for finding in complete_output["findings"]} == {"GTC006"}


def test_cli_content_policy_override_is_reported(capsys) -> None:
    fixture = str(ROOT / "examples" / "structured-content.otlp.json")

    exit_code = main(["check", fixture, "--content-policy", "allow"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["content_policy"] == "allow"
    assert output["findings"] == []


def test_cli_rejects_single_input_output_alias_even_with_force(tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "trace.json"
    input_path.write_text(
        (ROOT / "examples" / "valid.otlp.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    original = input_path.read_text(encoding="utf-8")

    exit_code = main(["check", str(input_path), "--output", str(input_path), "--force"])

    assert exit_code == 2
    assert "output path is also an input" in capsys.readouterr().err
    assert input_path.read_text(encoding="utf-8") == original


def test_atomic_write_removes_temporary_file_after_replace_failure(
    tmp_path: Path, monkeypatch
) -> None:
    def fail_replace(source: str, destination: Path) -> None:
        raise OSError(f"cannot replace {destination.name} from {Path(source).name}")

    monkeypatch.setattr(cli.os, "replace", fail_replace)

    with pytest.raises(OSError, match="cannot replace"):
        cli._atomic_write(tmp_path / "report.json", "{}\n", force=False)

    assert list(tmp_path.iterdir()) == []


def test_help_explains_exit_status(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["batch", "--help"])

    help_text = capsys.readouterr().out
    assert exc_info.value.code == 0
    assert "exit status:" in help_text
    assert "quote glob patterns" in help_text


def test_module_entry_point_reports_version(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["genai-tracecheck", "--version"])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("genai_tracecheck.__main__", run_name="__main__")

    assert exc_info.value.code == 0
    assert "genai-tracecheck 1.0.0" in capsys.readouterr().out
