import json
from pathlib import Path

from genai_tracecheck.cli import main

ROOT = Path(__file__).parents[1]


def test_cli_prints_json_and_returns_zero_for_valid_trace(capsys) -> None:
    exit_code = main(["check", str(ROOT / "examples" / "valid.otlp.json")])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
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
