"""Command-line interface for CI and local trace checks."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from genai_tracecheck import __version__
from genai_tracecheck.analysis import analyze_spans
from genai_tracecheck.loader import TraceLoadError, load_otlp_json
from genai_tracecheck.models import (
    ContentPolicy,
    FailureThreshold,
    Policy,
    TraceCompleteness,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="genai-tracecheck",
        description="Check OpenTelemetry GenAI traces for quality and privacy risks.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="analyze an OTLP JSON trace export")
    check.add_argument("input", type=Path, help="path to an OTLP JSON file")
    check.add_argument("--output", "-o", type=Path, help="write the JSON report to this file")
    check.add_argument("--force", action="store_true", help="replace an existing report")
    check.add_argument(
        "--fail-on",
        choices=[item.value for item in FailureThreshold],
        default=FailureThreshold.ERROR.value,
        help="minimum severity that makes the command fail (default: error)",
    )
    check.add_argument(
        "--content-policy",
        choices=[item.value for item in ContentPolicy],
        default=ContentPolicy.REVIEW.value,
        help="allow, review, or forbid captured prompt/output content (default: review)",
    )
    check.add_argument(
        "--no-secret-detection",
        action="store_true",
        help="disable heuristic secret-pattern detection",
    )
    check.add_argument(
        "--trace-completeness",
        choices=[item.value for item in TraceCompleteness],
        default=TraceCompleteness.PARTIAL.value,
        help="treat input as a partial or complete trace export (default: partial)",
    )
    return parser


def _atomic_write(path: Path, content: str, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"report already exists: {path} (use --force to replace it)")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command != "check":
        return 2

    try:
        spans = load_otlp_json(args.input)
        policy = Policy(
            fail_on=FailureThreshold(args.fail_on),
            content_policy=ContentPolicy(args.content_policy),
            detect_secret_values=not args.no_secret_detection,
            trace_completeness=TraceCompleteness(args.trace_completeness),
        )
        report = analyze_spans(spans, source=str(args.input), policy=policy)
        document = json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"
        if args.output:
            _atomic_write(args.output, document, force=args.force)
            print(
                f"{'PASS' if report.passed else 'FAIL'}: {report.summary.errors} error(s), "
                f"{report.summary.warnings} warning(s); report: {args.output}",
                file=sys.stderr,
            )
        else:
            print(document, end="")
    except (TraceLoadError, FileExistsError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
