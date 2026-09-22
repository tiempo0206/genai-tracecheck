"""Shared classification helpers for GenAI span operations."""

from genai_tracecheck.models import SpanRecord

MODEL_OPERATIONS = frozenset({"chat", "embeddings", "generate_content", "text_completion"})
TOOL_OPERATION = "execute_tool"


def is_genai_span(span: SpanRecord) -> bool:
    if any(key.startswith("gen_ai.") for key in span.attributes):
        return True
    scope = (span.scope_name or "").lower()
    return "genai" in scope or "gen_ai" in scope
