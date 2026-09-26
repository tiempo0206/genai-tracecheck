from __future__ import annotations

from pathlib import Path

from benchmarks.run import DEFAULT_SEED, run_benchmarks, write_fixture
from genai_tracecheck.analysis import analyze_spans
from genai_tracecheck.loader import load_otlp_json


def test_fixture_generation_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    first_metadata = write_fixture(first, 101, DEFAULT_SEED)
    second_metadata = write_fixture(second, 101, DEFAULT_SEED)

    assert first.read_bytes() == second.read_bytes()
    assert first_metadata == second_metadata


def test_fixture_is_valid_and_uses_complete_bounded_traces(tmp_path: Path) -> None:
    fixture = tmp_path / "synthetic.json"
    write_fixture(fixture, 101, DEFAULT_SEED)

    spans = load_otlp_json(fixture)
    report = analyze_spans(spans, source=str(fixture))

    assert len(spans) == 101
    assert report.passed is True
    assert report.findings == []
    assert report.summary.spans == 101
    assert report.summary.genai_spans == 101
    assert sorted(trace.spans for trace in report.traces) == [1, 100]


def test_small_benchmark_emits_machine_readable_contract(tmp_path: Path) -> None:
    results = run_benchmarks(
        sizes=(10,),
        repeats=1,
        warmups=0,
        seed=DEFAULT_SEED,
        fixture_directory=tmp_path / "fixtures",
        profile_output=None,
    )

    assert results["schema_version"] == "1.0"
    assert results["methodology"]["fixture_seed"] == DEFAULT_SEED
    assert results["profile"] is None
    case = results["cases"][0]
    assert case["spans"] == 10
    assert case["traces"] == 1
    assert case["fixture"]["seed"] == DEFAULT_SEED
    for phase in ("load", "analyze", "end_to_end"):
        measurement = case["phases"][phase]
        assert measurement["median_seconds"] > 0
        assert measurement["throughput_spans_per_second"] > 0
        assert measurement["peak_python_memory_bytes"] > 0
