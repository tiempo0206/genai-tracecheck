# Contributing

Thank you for helping improve GenAI TraceCheck. Keep changes small, evidence-backed, and safe to test
with public synthetic data.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest
```

## Adding a rule

1. Choose the correct family: `GTC0xx` structure, `GTC1xx` OpenTelemetry GenAI semantics, or
   `GTC2xx` TraceCheck policy/privacy.
2. Link the exact upstream requirement when claiming semantic-convention behavior.
3. Add the smallest synthetic OTLP fixture that proves the issue.
4. Test positive, negative, and boundary cases without including real prompts or credentials.
5. Ensure findings never echo sensitive values.
6. Add the rule ID to `rule_catalog.py` so configuration can validate it.
7. Update the rule table and project log.

Attributes that only appear in an open proposal must not be enforced as accepted convention. Label
experimental behavior and document false-positive risks.
