"""Deterministic input discovery and multi-file trace analysis."""

from __future__ import annotations

import glob
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from genai_tracecheck.analysis import analyze_spans
from genai_tracecheck.loader import TraceLoadError, load_otlp_json
from genai_tracecheck.models import (
    BatchFileResult,
    BatchFileStatus,
    BatchReport,
    BatchSummary,
    Policy,
)


class InputResolutionError(ValueError):
    """Raised when a batch input cannot be resolved to a regular file."""


def _json_files_in_directory(directory: Path) -> list[Path]:
    discovered: list[Path] = []
    for root, directories, filenames in os.walk(directory, followlinks=False):
        directories[:] = sorted(name for name in directories if not name.startswith("."))
        for filename in sorted(filenames):
            if filename.startswith(".") or Path(filename).suffix.lower() != ".json":
                continue
            candidate = Path(root, filename)
            if candidate.is_file():
                discovered.append(candidate)
    return discovered


def _files_for_input(raw_input: str | Path) -> list[Path]:
    raw = os.path.expanduser(os.fspath(raw_input))
    if glob.has_magic(raw):
        matches = [Path(match) for match in glob.glob(raw, recursive=True, include_hidden=False)]
        candidates: list[Path] = []
        for match in sorted(matches, key=lambda path: path.as_posix()):
            if match.is_dir():
                candidates.extend(_json_files_in_directory(match))
            elif match.is_file():
                candidates.append(match)
        return candidates

    path = Path(raw)
    if path.is_dir():
        return _json_files_in_directory(path)
    if path.is_file():
        return [path]
    return []


def resolve_input_paths(inputs: Sequence[str | Path]) -> list[Path]:
    """Expand files, directories, and glob patterns into sorted unique files.

    Directory traversal is recursive, ignores hidden entries, and never follows
    symlinked directories. Glob expansion is performed by Python rather than a shell.
    """

    if not inputs:
        raise InputResolutionError("at least one batch input is required")

    resolved: dict[Path, None] = {}
    for raw_input in inputs:
        candidates = _files_for_input(raw_input)
        if not candidates:
            raise InputResolutionError(f"input matched no files: {raw_input}")
        for candidate in candidates:
            try:
                canonical = candidate.resolve(strict=True)
            except OSError as exc:
                raise InputResolutionError(f"cannot resolve input {candidate}: {exc}") from exc
            if not canonical.is_file():
                raise InputResolutionError(f"input is not a regular file: {candidate}")
            resolved[canonical] = None

    return sorted(resolved, key=lambda path: path.as_posix())


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def analyze_batch(
    paths: Sequence[Path],
    *,
    policy: Policy | None = None,
    generated_at: datetime | None = None,
) -> BatchReport:
    """Analyze resolved files independently and aggregate their stable results."""

    if not paths:
        raise InputResolutionError("at least one resolved file is required")

    active_policy = policy or Policy()
    timestamp = generated_at or datetime.now(UTC)
    results: list[BatchFileResult] = []

    for path in sorted(paths, key=lambda item: item.as_posix()):
        source = _display_path(path)
        try:
            spans = load_otlp_json(path)
        except TraceLoadError as exc:
            results.append(
                BatchFileResult(
                    source=source,
                    status=BatchFileStatus.LOAD_ERROR,
                    passed=False,
                    error=str(exc),
                    summary=None,
                    traces=[],
                    findings=[],
                )
            )
            continue

        report = analyze_spans(
            spans,
            source=source,
            policy=active_policy,
            generated_at=timestamp,
        )
        results.append(
            BatchFileResult(
                source=source,
                status=BatchFileStatus.ANALYZED,
                passed=report.passed,
                error=None,
                summary=report.summary,
                traces=report.traces,
                findings=report.findings,
            )
        )

    analyzed = [result for result in results if result.status is BatchFileStatus.ANALYZED]
    load_errors = len(results) - len(analyzed)
    passed_files = sum(result.passed for result in results)
    return BatchReport(
        generated_at=timestamp.isoformat().replace("+00:00", "Z"),
        passed=passed_files == len(results),
        fail_on=active_policy.fail_on,
        trace_completeness=active_policy.trace_completeness,
        summary=BatchSummary(
            files=len(results),
            analyzed_files=len(analyzed),
            load_errors=load_errors,
            passed_files=passed_files,
            failed_files=len(results) - passed_files,
            spans=sum(result.summary.spans for result in analyzed if result.summary),
            genai_spans=sum(result.summary.genai_spans for result in analyzed if result.summary),
            traces=sum(len(result.traces) for result in analyzed),
            errors=sum(result.summary.errors for result in analyzed if result.summary),
            warnings=sum(result.summary.warnings for result in analyzed if result.summary),
        ),
        files=results,
    )
