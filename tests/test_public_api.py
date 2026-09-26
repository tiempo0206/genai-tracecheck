from __future__ import annotations

import inspect
from datetime import UTC, datetime
from pathlib import Path

import genai_tracecheck

ROOT = Path(__file__).parents[1]
EXPECTED_PUBLIC_NAMES = {
    "AnalysisReport",
    "BatchReport",
    "ConfigurationError",
    "ContentPolicy",
    "FailureThreshold",
    "Finding",
    "InputResolutionError",
    "Policy",
    "Severity",
    "SpanRecord",
    "TraceCompleteness",
    "TraceLoadError",
    "TraceMetrics",
    "__version__",
    "analyze_batch",
    "analyze_spans",
    "load_otlp_json",
    "load_policy_config",
    "report_to_sarif",
    "resolve_input_paths",
}


def test_public_api_is_explicit_and_importable() -> None:
    assert set(genai_tracecheck.__all__) == EXPECTED_PUBLIC_NAMES
    assert all(hasattr(genai_tracecheck, name) for name in EXPECTED_PUBLIC_NAMES)


def test_public_operations_have_useful_docstrings() -> None:
    operations = (
        genai_tracecheck.analyze_batch,
        genai_tracecheck.analyze_spans,
        genai_tracecheck.load_otlp_json,
        genai_tracecheck.load_policy_config,
        genai_tracecheck.report_to_sarif,
        genai_tracecheck.resolve_input_paths,
    )

    for operation in operations:
        documentation = inspect.getdoc(operation) or ""
        assert len(documentation.split()) >= 12, operation.__name__


def test_top_level_api_supports_programmatic_analysis() -> None:
    spans = genai_tracecheck.load_otlp_json(ROOT / "examples" / "valid.otlp.json")
    policy = genai_tracecheck.Policy(
        fail_on=genai_tracecheck.FailureThreshold.WARNING,
        content_policy=genai_tracecheck.ContentPolicy.FORBID,
    )

    report = genai_tracecheck.analyze_spans(
        spans,
        source="valid.otlp.json",
        policy=policy,
        generated_at=datetime(2026, 9, 26, tzinfo=UTC),
    )

    assert report.passed is True
    assert report.summary.spans == 1
    assert report.findings == []


def test_source_package_declares_inline_typing() -> None:
    package_directory = Path(genai_tracecheck.__file__).parent

    assert (package_directory / "py.typed").is_file()
