#!/usr/bin/env python3
"""Install distributions in isolated environments and exercise the public product surface."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import venv
from collections.abc import Sequence
from pathlib import Path

REQUIRED_PUBLIC_NAMES = (
    "AnalysisReport",
    "BatchReport",
    "ContentPolicy",
    "FailureThreshold",
    "Finding",
    "Policy",
    "Severity",
    "SpanRecord",
    "TraceCompleteness",
    "TraceMetrics",
    "analyze_batch",
    "analyze_spans",
    "load_otlp_json",
    "load_policy_config",
    "report_to_sarif",
    "resolve_input_paths",
)

VALID_FIXTURE = {
    "resourceSpans": [
        {
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "clean-install-smoke"}}
                ]
            },
            "scopeSpans": [
                {
                    "scope": {"name": "smoke.genai"},
                    "spans": [
                        {
                            "traceId": "11111111111111111111111111111111",
                            "spanId": "2222222222222222",
                            "name": "chat smoke-model",
                            "startTimeUnixNano": "1000000000",
                            "endTimeUnixNano": "1001000000",
                            "attributes": [
                                {
                                    "key": "gen_ai.operation.name",
                                    "value": {"stringValue": "chat"},
                                },
                                {
                                    "key": "gen_ai.provider.name",
                                    "value": {"stringValue": "synthetic"},
                                },
                                {
                                    "key": "gen_ai.request.model",
                                    "value": {"stringValue": "smoke-model"},
                                },
                            ],
                        }
                    ],
                }
            ],
        }
    ]
}


class SmokeFailure(RuntimeError):
    """Raised when an installed distribution does not behave as expected."""


def _run(command: Sequence[str], *, cwd: Path) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        rendered = " ".join(command)
        raise SmokeFailure(
            f"command failed with exit {completed.returncode}: {rendered}\n{completed.stdout}"
        )
    return completed.stdout


def _environment_executable(environment: Path, name: str) -> Path:
    scripts = environment / ("Scripts" if os.name == "nt" else "bin")
    suffix = ".exe" if os.name == "nt" else ""
    return scripts / f"{name}{suffix}"


def smoke_distribution(artifact: Path) -> None:
    """Install one wheel or sdist and verify imports, metadata, typing, and CLI behavior."""

    artifact = artifact.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="tracecheck-clean-install-") as temporary:
        root = Path(temporary)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(environment)
        python = _environment_executable(environment, "python")
        cli = _environment_executable(environment, "genai-tracecheck")

        _run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-cache-dir",
                str(artifact),
            ],
            cwd=root,
        )
        _run([str(python), "-m", "pip", "check"], cwd=root)

        names = repr(REQUIRED_PUBLIC_NAMES)
        probe = (
            "import pathlib, sys; "
            "import genai_tracecheck as package; "
            f"required={names}; "
            "assert all(hasattr(package, name) for name in required); "
            "module=pathlib.Path(package.__file__).resolve(); "
            "assert module.is_relative_to(pathlib.Path(sys.prefix).resolve()); "
            "assert module.with_name('py.typed').is_file(); "
            "print(package.__version__)"
        )
        _run([str(python), "-I", "-c", probe], cwd=root)
        _run([str(cli), "--version"], cwd=root)

        fixture = root / "valid.otlp.json"
        report = root / "report.json"
        fixture.write_text(json.dumps(VALID_FIXTURE), encoding="utf-8")
        _run([str(cli), "check", str(fixture), "--output", str(report)], cwd=root)
        payload = json.loads(report.read_text(encoding="utf-8"))
        if payload["passed"] is not True or payload["summary"]["spans"] != 1:
            raise SmokeFailure(f"installed CLI produced an unexpected report for {artifact.name}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Smoke-test wheels and source distributions in fresh virtual environments."
    )
    parser.add_argument("artifacts", nargs="+", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for artifact in sorted(args.artifacts, key=lambda item: item.name):
        try:
            smoke_distribution(artifact)
        except (OSError, SmokeFailure, subprocess.SubprocessError, ValueError) as exc:
            print(f"FAIL {artifact}: {exc}", file=sys.stderr)
            return 1
        print(f"PASS {artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
