# Contributing

Thank you for helping improve GenAI TraceCheck. Keep changes small, evidence-backed, deterministic,
and safe to review with public synthetic data.

## Start with the right issue

Use the structured bug-report form for reproducible incorrect behavior and the rule-proposal form
for a new invariant. Search existing issues first. Trace exports can contain prompts, credentials,
tool arguments, retrieved documents, and personal data; never attach a production trace. Reduce a
problem to invented data and rotate any credential that has already entered telemetry.

Broad semantic changes need maintainer agreement before implementation. A link to an open proposal
does not make an attribute an accepted OpenTelemetry requirement.

## Local setup

Python 3.11 or newer is required:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
coverage run -m pytest
coverage report
```

The project enforces combined statement/branch coverage at 95%. Use a short branch and one reviewable
commit for one coherent change. Avoid unrelated formatting or dependency churn.

## Adding or changing a rule

Read [`docs/rule-authoring.md`](docs/rule-authoring.md) before coding. The guide covers rule families,
pinned evidence, applicability, safe diagnostics, test dimensions, configuration behavior, SARIF,
and every public contract that must stay synchronized.

At minimum:

1. classify the claim as structure (`GTC0xx`), accepted GenAI semantics (`GTC1xx`), or explicit
   TraceCheck policy/privacy (`GTC2xx`);
2. cite an exact accepted revision when claiming standards behavior;
3. define severity, applicability, boundaries, and false-positive risks;
4. add the smallest invented positive, negative, and boundary cases;
5. prove findings and SARIF never echo sensitive values;
6. update `rule_catalog.py`, the README rule table, compatibility evidence, and the project log.

Recommended, opt-in, experimental, provider-dependent, and unavailable attributes must not be
presented as universal exporter defects.

## Public API changes

The intentional Python surface is listed in `genai_tracecheck.__all__` and documented in
[`docs/api.md`](docs/api.md). New public behavior needs type annotations, a useful docstring, a
top-level import when appropriate, and an integration test. Do not expose an internal helper merely
to make a test convenient.

## Before opening a pull request

Run the same durable checks used by CI:

```bash
ruff check .
ruff format --check .
coverage run -m pytest
coverage report
python tools/compatibility-matrix/generate.py --check
python -m build
python tools/clean-install-smoke.py dist/*.whl dist/*.tar.gz
```

The final command installs both the wheel and source distribution into separate temporary virtual
environments, imports the typed public API outside the checkout, runs `pip check`, and analyzes a
sanitized fixture through the installed CLI.

In the pull request, explain the user-visible behavior, evidence, privacy impact, verification, and
known limits. Complete the rule-specific checklist only when the change affects a rule.
