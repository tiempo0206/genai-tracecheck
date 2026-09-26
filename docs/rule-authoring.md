# Rule-authoring guide

A TraceCheck rule is a documented invariant, a content-safe diagnostic, and independently testable
evidence. It is not only a conditional in `rules.py`. Use this workflow for new rules and material
changes to existing ones.

## 1. Classify the claim

Choose exactly one family:

- `GTC0xx`: OTLP structure, identifier, timestamp, or trace-graph integrity;
- `GTC1xx`: OpenTelemetry GenAI semantic conventions;
- `GTC2xx`: explicit TraceCheck privacy policy or heuristic behavior.

For a `GTC1xx` rule, link an exact accepted specification revision and record whether the behavior
is required, conditionally required, recommended, opt-in, deprecated, or experimental. Do not turn
an open proposal into a required rule. Provider availability and partial trace exports must be part
of the applicability analysis.

## 2. Define the invariant before coding

Write down:

1. the span or trace population to which the rule applies;
2. the valid condition and precise invalid boundary;
3. warning or error severity and why that gate behavior is appropriate;
4. a diagnostic that remains useful without echoing attribute values;
5. expected false positives, false negatives, and compatibility limits.

TraceCheck defaults errors to gate failures. Optional metadata and plausible asynchronous behavior
usually require warnings or narrower applicability.

## 3. Implement in the correct layer

- Independent span checks belong in `rules.py`.
- Parent, cycle, duplicate, or containment checks belong in `graph_rules.py`.
- Structured captured-content shapes belong in `content_validation.py`.
- Derived measurements belong in `metrics.py`; a metric is not automatically a rule.
- Rule policy is applied centrally in `analysis.py`, after rule evaluation.

Add the ID and description to `rule_catalog.py`. Reuse classification helpers and normalized
`SpanRecord` fields instead of reparsing raw OTLP. Keep traversal deterministic and avoid network
access, runtime schema downloads, or provider calls.

## 4. Preserve the diagnostic safety contract

A finding may identify a rule, trace/span internally, attribute name, JSON path, constraint, count,
or reviewed structural relationship. It must not contain:

- prompts, responses, instructions, tool arguments/results, or retrieved documents;
- secret-shaped matches or the surrounding string;
- production trace samples or personal/proprietary data;
- new arbitrary `details` fields that automatically flow into SARIF fingerprints.

Use invented fixture content. If a secret pattern is tested, make it unmistakably synthetic and
assert that the value is absent from JSON, SARIF, logs, and exception text.

## 5. Test independently

Every rule needs focused tests for:

- a positive case that must not emit the rule;
- the smallest negative case that emits it;
- exact boundaries, missing/invalid types, and Boolean-versus-integer behavior where relevant;
- policy disablement and severity override through the shared analysis path;
- deterministic ordering when more than one finding is possible;
- non-disclosure whenever captured or secret-shaped data is involved.

Prefer a model-level unit test for numeric boundaries and a minimal OTLP fixture for loader-to-report
integration. A deliberately failing fixture must declare its expected gate in the compatibility
matrix catalog.

## 6. Update every public contract

- `rule_catalog.py` metadata and supported IDs;
- README rule table;
- tests and minimal synthetic fixture, if needed;
- compatibility-matrix fixture catalog and regenerated JSON, if the fixture set changes;
- SARIF expectations when safe metadata or location behavior changes;
- configuration examples when rule controls are relevant;
- project log with evidence, decisions, and verification results.

Run the complete checks, not only the new test:

```bash
ruff check .
ruff format --check .
coverage run -m pytest
coverage report
python tools/compatibility-matrix/generate.py --check
python -m build
python tools/clean-install-smoke.py dist/*.whl dist/*.tar.gz
```

## Review checklist

- [ ] The ID is unused and belongs to the correct family.
- [ ] The applicability and severity follow pinned evidence or are labeled local policy.
- [ ] Recommended, experimental, and unavailable attributes are not presented as universal defects.
- [ ] Partial exports and provider differences cannot create avoidable noise.
- [ ] Diagnostics and SARIF output reveal no captured values or identifiers.
- [ ] Positive, negative, boundary, configuration, ordering, and privacy behavior are tested.
- [ ] Rule catalog, README, fixtures, compatibility evidence, and project log agree.
- [ ] The full suite, coverage gate, distribution build, and clean-install smoke pass.
