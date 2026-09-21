# Project log

This journal records what changed, why it changed, how it was verified, and what was learned. Future
entries should preserve this structure so the repository shows an auditable engineering process.

## 2026-09-19 — Day 1: vertical slice

### Objective

Create a small but complete end-to-end product: ingest a real telemetry interchange format, apply
useful checks, emit a stable report, and enforce the result in CI.

### Completed

- Selected the name **GenAI TraceCheck** and verified that the GitHub repository name was available.
- Chose canonical OTLP/HTTP JSON as the initial input instead of inventing a custom trace format.
- Implemented recursive OTLP `AnyValue` decoding for scalars, arrays, and key-value lists.
- Added strict internal contracts for spans, policies, findings, summaries, and reports.
- Implemented seven initial checks across structure, semantic completeness, and privacy.
- Added configurable failure thresholds and captured-content policies.
- Ensured secret-shaped matches are reported without copying the matched value.
- Added atomic output writes and opt-in replacement through `--force`.
- Added valid and deliberately risky OTLP fixtures, unit tests, and a Python-version CI matrix.
- Documented project boundaries, architecture, rule provenance, and a 14-day roadmap.

### Engineering decisions

1. **Offline by default.** Trace data can contain prompts, tool arguments, and retrieved documents;
   the first version makes no network requests.
2. **Normalize before evaluating.** Rules operate on a small span model rather than raw OTLP nesting.
   This leaves room for protobuf and framework adapters.
3. **Separate standards from policy.** `GTC1xx` reflects published OpenTelemetry GenAI fields, while
   `GTC2xx` is clearly labeled as local policy or heuristic behavior.
4. **Fail only on errors by default.** Optional-but-useful metadata creates warnings, while broken
   IDs, time order, operation identity, usage counts, or likely secrets fail the command.
5. **Do not leak during detection.** Reports identify the affected attribute but redact matches.

### Learning notes

- OTLP JSON encodes attributes through nested `AnyValue` objects and represents 64-bit integers as
  decimal strings, so parsing must normalize values before validation.
- Current GenAI conventions favor structured span attributes such as `gen_ai.input.messages` over
  older per-message event patterns.
- Content-bearing telemetry fields are useful for evaluation but create a separate privacy decision;
  semantic validity does not imply safe retention.
- Partial trace exports are normal. Missing-parent checks need an explicit complete-trace mode rather
  than a universal error rule.

### Verification target

```bash
ruff check .
ruff format --check .
pytest
genai-tracecheck check examples/valid.otlp.json
genai-tracecheck check examples/risky.otlp.json
```

The valid fixture must pass, the risky fixture must fail, and no report may contain the sample secret.

### Next task

Implement Day 2 schema-aware validation for structured messages, with exact JSON-path findings and
tests for text, tool-call, and malformed message content.

## 2026-09-21 — Day 2: schema-aware captured content

### Objective

Validate the shape of the three content attributes defined by the current OpenTelemetry GenAI
conventions while keeping all diagnostics safe for logs and CI artifacts.

### Upstream research

- Confirmed that span attributes may carry structured values or JSON-encoded strings.
- Reviewed the current input-message, output-message, and system-instruction JSON schemas.
- Confirmed required fields for text, reasoning, tool-call, tool-response, blob, file, URI,
  compaction, and server-tool parts.
- Confirmed that `finish_reason` inside an output message is deprecated in favor of
  `gen_ai.response.finish_reasons`.
- Preserved the upstream `GenericPart` extension point instead of rejecting unknown part types.

### Completed

- Added a standalone, network-free content-schema validation module.
- Added `GTC105` errors for invalid JSON, wrong root types, malformed messages, and missing or
  mistyped fields in known parts.
- Added `GTC106` warnings for deprecated output-message `finish_reason` fields.
- Added JSON-path diagnostics such as `$[2].parts[0].name` without including captured values.
- Added valid multi-part input/tool/output content and deliberately malformed OTLP fixtures.
- Expanded tests from 8 to 20, including privacy non-disclosure assertions and extension-part cases.
- Extended CI to exercise both new fixtures through the installed command-line entry point.

### Engineering decisions

1. **No runtime schema download.** Validation works offline and cannot silently change when upstream
   changes.
2. **Known types are strict; unknown types are extensible.** This catches common instrumentation
   mistakes without blocking provider-specific parts.
3. **Paths, not values.** A diagnostic records only the attribute, location, and constraint so the
   report does not become a second copy of sensitive telemetry.
4. **JSON strings and structured values share one path.** Both representations are normalized before
   validation, matching the formats allowed on spans.

### Verification result

- Ruff lint and format checks: passed.
- Pytest: 20 passed.
- Valid structured fixture: exit `0`, zero schema errors, one expected privacy warning.
- Malformed fixture: exit `1`, six schema errors and precise paths.
- Report leakage check: no captured fixture text appeared in the malformed report.

### Next task

Implement Day 3 trace-graph integrity: duplicate span IDs, parent cycles, impossible timing
containment, and policy-aware missing-parent handling for complete versus partial exports.
