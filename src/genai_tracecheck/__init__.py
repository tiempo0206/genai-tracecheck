"""GenAI TraceCheck public package API."""

from genai_tracecheck.analysis import analyze_spans
from genai_tracecheck.loader import TraceLoadError, load_otlp_json
from genai_tracecheck.models import (
    AnalysisReport,
    Policy,
    SpanRecord,
    TraceCompleteness,
    TraceMetrics,
)

__all__ = [
    "AnalysisReport",
    "Policy",
    "SpanRecord",
    "TraceCompleteness",
    "TraceMetrics",
    "TraceLoadError",
    "analyze_spans",
    "load_otlp_json",
]

__version__ = "0.1.0"
