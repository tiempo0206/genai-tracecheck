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
from genai_tracecheck.batch import InputResolutionError, analyze_batch, resolve_input_paths
from genai_tracecheck.config import ConfigurationError, load_policy_config
from genai_tracecheck.loader import TraceLoadError, load_otlp_json
from genai_tracecheck.models import (
    ContentPolicy,
    FailureThreshold,
    Policy,
    TraceCompleteness,
)


def _add_common_check_options(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--config",
        type=Path,
        help="load a versioned TOML policy file (CLI policy flags take precedence)",
    )
    command.add_argument("--output", "-o", type=Path, help="write the JSON report to this file")
    command.add_argument("--force", action="store_true", help="replace an existing report")
    command.add_argument(
        "--fail-on",
        choices=[item.value for item in FailureThreshold],
        default=None,
        help="minimum severity that makes the command fail (built-in: error)",
    )
    command.add_argument(
        "--content-policy",
        choices=[item.value for item in ContentPolicy],
        default=None,
        help="allow, review, or forbid captured prompt/output content (built-in: review)",
    )
    command.add_argument(
        "--secret-detection",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="enable or disable heuristic secret-pattern detection (built-in: enabled)",
    )
    command.add_argument(
        "--trace-completeness",
        choices=[item.value for item in TraceCompleteness],
        default=None,
        help="treat input as a partial or complete trace export (built-in: partial)",
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
    _add_common_check_options(check)

    batch = subparsers.add_parser(
        "batch", help="analyze files, directories, or glob patterns as one batch"
    )
    batch.add_argument(
        "inputs",
        nargs="+",
        help="one or more OTLP JSON files, directories, or quoted glob patterns",
    )
    _add_common_check_options(batch)
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


def _policy_from_args(args: argparse.Namespace) -> Policy:
    policy = load_policy_config(args.config) if args.config is not None else Policy()
    updates: dict[str, object] = {}
    if args.fail_on is not None:
        updates["fail_on"] = FailureThreshold(args.fail_on)
    if args.content_policy is not None:
        updates["content_policy"] = ContentPolicy(args.content_policy)
    if args.secret_detection is not None:
        updates["detect_secret_values"] = args.secret_detection
    if args.trace_completeness is not None:
        updates["trace_completeness"] = TraceCompleteness(args.trace_completeness)
    return policy.model_copy(update=updates)


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        policy = _policy_from_args(args)
        if args.command == "check":
            spans = load_otlp_json(args.input)
            report = analyze_spans(spans, source=str(args.input), policy=policy)
        else:
            paths = resolve_input_paths(args.inputs)
            if args.output is not None:
                output_path = args.output.expanduser().resolve()
                if output_path in paths:
                    raise InputResolutionError("output path is also an input")
            report = analyze_batch(paths, policy=policy)

        document = json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"
        if args.output:
            _atomic_write(args.output, document, force=args.force)
            file_count = f"{report.summary.files} file(s); " if args.command == "batch" else ""
            print(
                f"{'PASS' if report.passed else 'FAIL'}: {file_count}"
                f"{report.summary.errors} error(s), "
                f"{report.summary.warnings} warning(s); report: {args.output}",
                file=sys.stderr,
            )
        else:
            print(document, end="")
    except (
        ConfigurationError,
        InputResolutionError,
        TraceLoadError,
        FileExistsError,
        OSError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
