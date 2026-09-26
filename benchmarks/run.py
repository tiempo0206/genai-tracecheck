"""Generate deterministic OTLP fixtures and benchmark the TraceCheck pipeline."""

from __future__ import annotations

import argparse
import cProfile
import gc
import hashlib
import io
import json
import os
import platform
import pstats
import random
import statistics
import tempfile
import time
import tracemalloc
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from genai_tracecheck.analysis import analyze_spans
from genai_tracecheck.loader import load_otlp_json
from genai_tracecheck.models import AnalysisReport, SpanRecord

DEFAULT_SIZES = (1_000, 10_000, 100_000)
DEFAULT_SEED = 20_260_926
SPANS_PER_TRACE = 100
PROFILE_ROWS = 25
BENCHMARK_SCHEMA_VERSION = "1.0"
FIXTURE_GENERATOR_VERSION = "1.0"
FIXED_GENERATED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def _nonzero_hex(rng: random.Random, bits: int, width: int) -> str:
    value = 0
    while value == 0:
        value = rng.getrandbits(bits)
    return f"{value:0{width}x}"


def _attribute(key: str, value: str | int) -> dict[str, object]:
    encoded: dict[str, object]
    if isinstance(value, int):
        encoded = {"intValue": str(value)}
    else:
        encoded = {"stringValue": value}
    return {"key": key, "value": encoded}


def synthetic_spans(span_count: int, seed: int = DEFAULT_SEED) -> Iterator[dict[str, object]]:
    """Yield a deterministic, valid mix of complete 100-span GenAI traces."""

    if span_count <= 0:
        raise ValueError("span_count must be greater than zero")

    rng = random.Random(seed)
    emitted = 0
    trace_index = 0
    epoch_nanos = 1_700_000_000_000_000_000
    while emitted < span_count:
        trace_size = min(SPANS_PER_TRACE, span_count - emitted)
        trace_id = _nonzero_hex(rng, 128, 32)
        root_span_id = _nonzero_hex(rng, 64, 16)
        trace_start = epoch_nanos + trace_index * 1_000_000_000
        trace_end = trace_start + (trace_size + 1) * 1_000_000

        for offset in range(trace_size):
            is_root = offset == 0
            span_id = root_span_id if is_root else _nonzero_hex(rng, 64, 16)
            start = trace_start if is_root else trace_start + offset * 1_000_000
            end = trace_end if is_root else start + 500_000
            input_tokens = 16 + rng.randrange(128)
            output_tokens = 8 + rng.randrange(64)
            span: dict[str, object] = {
                "traceId": trace_id,
                "spanId": span_id,
                "name": "chat synthetic-benchmark-model",
                "kind": 3,
                "startTimeUnixNano": str(start),
                "endTimeUnixNano": str(end),
                "attributes": [
                    _attribute("gen_ai.operation.name", "chat"),
                    _attribute("gen_ai.provider.name", "synthetic"),
                    _attribute("gen_ai.request.model", "synthetic-benchmark-model"),
                    _attribute("gen_ai.usage.input_tokens", input_tokens),
                    _attribute("gen_ai.usage.output_tokens", output_tokens),
                ],
                "status": {"code": 1},
            }
            if not is_root:
                span["parentSpanId"] = root_span_id
            yield span
            emitted += 1
        trace_index += 1


def write_fixture(path: Path, span_count: int, seed: int = DEFAULT_SEED) -> dict[str, object]:
    """Stream one deterministic OTLP/HTTP JSON fixture to disk."""

    path.parent.mkdir(parents=True, exist_ok=True)
    encoder = json.JSONEncoder(ensure_ascii=True, separators=(",", ":"))
    prefix = {
        "resource": {"attributes": [_attribute("service.name", "tracecheck-benchmark")]},
        "scope": {"name": "benchmark.genai", "version": FIXTURE_GENERATOR_VERSION},
    }
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write('{"resourceSpans":[{"resource":')
        stream.write(encoder.encode(prefix["resource"]))
        stream.write(',"scopeSpans":[{"scope":')
        stream.write(encoder.encode(prefix["scope"]))
        stream.write(',"spans":[')
        for index, span in enumerate(synthetic_spans(span_count, seed)):
            if index:
                stream.write(",")
            for chunk in encoder.iterencode(span):
                stream.write(chunk)
        stream.write("]}]}]}\n")

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "generator_version": FIXTURE_GENERATOR_VERSION,
        "seed": seed,
        "sha256": digest.hexdigest(),
        "size_bytes": path.stat().st_size,
    }


def _load(path: Path) -> list[SpanRecord]:
    return load_otlp_json(path)


def _analyze(spans: list[SpanRecord], source: str) -> AnalysisReport:
    return analyze_spans(spans, source=source, generated_at=FIXED_GENERATED_AT)


def _end_to_end(path: Path) -> AnalysisReport:
    return _analyze(_load(path), str(path))


def _timing(operation: Callable[[], object], repeats: int) -> dict[str, float]:
    samples: list[float] = []
    for _ in range(repeats):
        gc.collect()
        started = time.perf_counter_ns()
        result = operation()
        elapsed = time.perf_counter_ns() - started
        del result
        samples.append(elapsed / 1_000_000_000)
    return {
        "median_seconds": round(statistics.median(samples), 9),
        "min_seconds": round(min(samples), 9),
        "max_seconds": round(max(samples), 9),
    }


def _peak_python_memory(operation: Callable[[], object]) -> int:
    gc.collect()
    tracemalloc.start()
    try:
        result = operation()
        _, peak = tracemalloc.get_traced_memory()
        del result
        return peak
    finally:
        tracemalloc.stop()


def _measure_phase(
    operation: Callable[[], object], *, span_count: int, repeats: int
) -> dict[str, float | int]:
    timing = _timing(operation, repeats)
    median_seconds = timing["median_seconds"]
    return {
        **timing,
        "throughput_spans_per_second": round(span_count / median_seconds, 2),
        "peak_python_memory_bytes": _peak_python_memory(operation),
    }


def _profile(operation: Callable[[], object], output: Path) -> None:
    profiler = cProfile.Profile()
    result = profiler.runcall(operation)
    del result
    report = io.StringIO()
    pstats.Stats(profiler, stream=report).strip_dirs().sort_stats(
        pstats.SortKey.CUMULATIVE
    ).print_stats(PROFILE_ROWS)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.getvalue(), encoding="utf-8")


def _environment() -> dict[str, object]:
    return {
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "logical_cpu_count": os.cpu_count(),
    }


def run_benchmarks(
    *,
    sizes: Sequence[int],
    repeats: int,
    warmups: int,
    seed: int,
    fixture_directory: Path,
    profile_output: Path | None,
) -> dict[str, object]:
    """Run all benchmark phases and return the machine-readable result document."""

    cases: list[dict[str, object]] = []
    profile_path: Path | None = None
    for span_count in sizes:
        fixture_path = fixture_directory / f"synthetic-{span_count}.otlp.json"
        fixture = write_fixture(fixture_path, span_count, seed)
        loaded = _load(fixture_path)
        report = _analyze(loaded, str(fixture_path))
        if len(loaded) != span_count or report.summary.spans != span_count or report.findings:
            raise RuntimeError("synthetic fixture failed its benchmark preflight validation")

        for _ in range(warmups):
            _load(fixture_path)
            _analyze(loaded, str(fixture_path))
            _end_to_end(fixture_path)

        load_operation = partial(_load, fixture_path)
        analyze_operation = partial(_analyze, loaded, str(fixture_path))
        end_to_end_operation = partial(_end_to_end, fixture_path)
        phases = {
            "load": _measure_phase(load_operation, span_count=span_count, repeats=repeats),
            "analyze": _measure_phase(
                analyze_operation,
                span_count=span_count,
                repeats=repeats,
            ),
            "end_to_end": _measure_phase(
                end_to_end_operation,
                span_count=span_count,
                repeats=repeats,
            ),
        }
        cases.append(
            {
                "spans": span_count,
                "traces": len(report.traces),
                "fixture": fixture,
                "phases": phases,
            }
        )

        if profile_output is not None and span_count == max(sizes):
            _profile(end_to_end_operation, profile_output)
            profile_path = profile_output

    return {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "environment": _environment(),
        "methodology": {
            "clock": "time.perf_counter_ns",
            "timing_statistic": "median",
            "repeats": repeats,
            "warmups_per_phase": warmups,
            "memory": "tracemalloc peak Python allocations from a separate run",
            "spans_per_trace": SPANS_PER_TRACE,
            "fixture_seed": seed,
        },
        "cases": cases,
        "profile": (
            {
                "spans": max(sizes),
                "sort": "cumulative",
                "rows": PROFILE_ROWS,
                "output": profile_path.name,
            }
            if profile_path is not None
            else None
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run reproducible load, analysis, and end-to-end TraceCheck benchmarks."
    )
    parser.add_argument("--sizes", nargs="+", type=_positive_int, default=list(DEFAULT_SIZES))
    parser.add_argument("--repeats", type=_positive_int, default=3)
    parser.add_argument("--warmups", type=int, choices=range(0, 11), default=1)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, default=Path("benchmarks/results.json"))
    parser.add_argument("--profile-output", type=Path, default=Path("benchmarks/profile-100k.txt"))
    parser.add_argument("--no-profile", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sizes = tuple(sorted(set(args.sizes)))
    profile_output = None if args.no_profile else args.profile_output
    with tempfile.TemporaryDirectory(prefix="tracecheck-benchmark-") as temporary:
        results = run_benchmarks(
            sizes=sizes,
            repeats=args.repeats,
            warmups=args.warmups,
            seed=args.seed,
            fixture_directory=Path(temporary),
            profile_output=profile_output,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote benchmark results to {args.output}")
    if profile_output is not None:
        print(f"Wrote cumulative profile to {profile_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
