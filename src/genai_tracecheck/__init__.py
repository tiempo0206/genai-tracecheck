"""GenAI TraceCheck public package API."""

from genai_tracecheck.analysis import analyze_spans
from genai_tracecheck.batch import InputResolutionError, analyze_batch, resolve_input_paths
from genai_tracecheck.config import ConfigurationError, load_policy_config
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
    "ConfigurationError",
    "InputResolutionError",
    "Policy",
    "SpanRecord",
    "TraceCompleteness",
    "TraceMetrics",
    "TraceLoadError",
    "analyze_batch",
    "analyze_spans",
    "load_otlp_json",
    "load_policy_config",
    "resolve_input_paths",
]

__version__ = "0.2.0"
