"""GenAI TraceCheck public package API."""

from genai_tracecheck.analysis import analyze_spans
from genai_tracecheck.batch import InputResolutionError, analyze_batch, resolve_input_paths
from genai_tracecheck.loader import TraceLoadError, load_otlp_json
from genai_tracecheck.models import (
    AnalysisReport,
    BatchReport,
    Policy,
    SpanRecord,
    TraceCompleteness,
    TraceMetrics,
)

__all__ = [
    "AnalysisReport",
    "BatchReport",
    "InputResolutionError",
    "Policy",
    "SpanRecord",
    "TraceCompleteness",
    "TraceMetrics",
    "TraceLoadError",
    "analyze_batch",
    "analyze_spans",
    "load_otlp_json",
    "resolve_input_paths",
]

__version__ = "0.1.0"
