#!/usr/bin/env python3
"""Run a short, deterministic portfolio demonstration without network access."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).parents[1]


class DemoFailure(RuntimeError):
    """Raised when the installed CLI violates the demonstration contract."""


def _run_cli(arguments: Sequence[str], expected_exit: int) -> dict[str, object]:
    environment = os.environ.copy()
    source_path = str(ROOT / "src")
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        f"{source_path}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else source_path
    )
    completed = subprocess.run(
        [sys.executable, "-m", "genai_tracecheck", *arguments],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != expected_exit:
        raise DemoFailure(
            f"CLI returned {completed.returncode}, expected {expected_exit}: {completed.stderr}"
        )
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise DemoFailure("CLI did not return a JSON document") from exc
    if not isinstance(document, dict):
        raise DemoFailure("CLI returned a non-object JSON document")
    return document


def demo_lines() -> list[str]:
    """Exercise pass, quality-gate failure, and content-safe SARIF paths."""

    from genai_tracecheck import __version__

    valid = _run_cli(["check", "examples/valid.otlp.json"], expected_exit=0)
    risky = _run_cli(["check", "examples/risky.otlp.json"], expected_exit=1)
    sarif = _run_cli(
        ["check", "examples/risky.otlp.json", "--format", "sarif"],
        expected_exit=1,
    )

    valid_findings = valid["findings"]
    risky_findings = risky["findings"]
    if not isinstance(valid_findings, list) or not isinstance(risky_findings, list):
        raise DemoFailure("JSON report findings must be arrays")
    rule_ids = sorted({finding["rule_id"] for finding in risky_findings})

    runs = sarif.get("runs")
    if not isinstance(runs, list) or len(runs) != 1:
        raise DemoFailure("SARIF report must contain exactly one run")
    results = runs[0]["results"]
    fingerprint_count = sum(
        "primaryLocationLineHash" in result.get("partialFingerprints", {}) for result in results
    )
    rendered_sarif = json.dumps(sarif, ensure_ascii=False)
    secret_status = "yes" if "sk-exampleSecretValue" in rendered_sarif else "no"

    return [
        f"GenAI TraceCheck {__version__} portfolio demo",
        (
            "[1/3] valid fixture: PASS "
            f"spans={valid['summary']['spans']} findings={len(valid_findings)}"
        ),
        (
            "[2/3] risky fixture: EXPECTED FAIL "
            f"errors={risky['summary']['errors']} warnings={risky['summary']['warnings']} "
            f"rules={','.join(rule_ids)}"
        ),
        (
            "[3/3] SARIF: EXPECTED FAIL "
            f"results={len(results)} fingerprints={fingerprint_count} "
            f"captured_secret_embedded={secret_status}"
        ),
    ]


def main() -> int:
    try:
        lines = demo_lines()
    except (DemoFailure, KeyError, OSError, TypeError, ValueError) as exc:
        print(f"DEMO FAIL: {exc}", file=sys.stderr)
        return 1
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
