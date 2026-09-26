"""GenAI TraceCheck public package API."""

from genai_tracecheck._version import __version__
from genai_tracecheck.analysis import analyze_spans
from genai_tracecheck.batch import InputResolutionError, analyze_batch, resolve_input_paths
from genai_tracecheck.config import ConfigurationError, load_policy_config
from genai_tracecheck.loader import TraceLoadError, load_otlp_json
from genai_tracecheck.models import (
    AnalysisReport,
    BatchReport,
    ContentPolicy,
    FailureThreshold,
    Finding,
    Policy,
    Severity,
    SpanRecord,
    TraceCompleteness,
    TraceMetrics,
)
from genai_tracecheck.sarif import report_to_sarif

__all__ = [
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
    "TraceMetrics",
    "TraceLoadError",
    "analyze_batch",
    "analyze_spans",
    "load_otlp_json",
    "load_policy_config",
    "resolve_input_paths",
    "report_to_sarif",
    "__version__",
]
