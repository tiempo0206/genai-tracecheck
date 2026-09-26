"""Stable rule metadata shared by configuration and report formats."""

RULE_METADATA = {
    "GTC001": ("Valid OTLP identifiers", "error"),
    "GTC002": ("Valid span timestamps", "error"),
    "GTC003": ("Unique span IDs within a trace", "error"),
    "GTC004": ("Acyclic parent relationships", "error"),
    "GTC005": ("Child lifetime contained by parent", "warning"),
    "GTC006": ("Complete exports contain referenced parents", "error"),
    "GTC101": ("GenAI operation name present", "error"),
    "GTC102": ("GenAI provider present when available", "warning"),
    "GTC103": ("GenAI request or response model present when available", "warning"),
    "GTC104": ("Non-negative integer token usage", "error"),
    "GTC105": ("Valid structured GenAI content", "error"),
    "GTC106": ("No deprecated output-message finish reason", "warning"),
    "GTC107": ("Valid time to first chunk", "error"),
    "GTC108": ("Token breakdown does not exceed aggregate", "error"),
    "GTC109": ("Tool spans do not report token usage", "warning"),
    "GTC110": ("Tool spans include a tool name", "error"),
    "GTC111": ("Valid response finish reasons", "error"),
    "GTC112": ("Valid GenAI server port", "error"),
    "GTC201": ("Captured GenAI content follows local privacy policy", "warning"),
    "GTC202": ("No secret-shaped values in captured GenAI content", "error"),
}

SUPPORTED_RULE_IDS = frozenset(RULE_METADATA)
