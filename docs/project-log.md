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

## 2026-09-21 — Day 3: trace graph integrity

### Objective

Move beyond independent span linting and validate relationships across every span in a trace without
misclassifying normal partial exports.

### Completed

- Added a per-trace index keyed by `trace_id` and `span_id`.
- Added `GTC003` for duplicate span IDs inside one trace.
- Added non-recursive cycle detection and canonical cycle paths through `GTC004`.
- Added `GTC005` warnings when a child starts before or ends after its resolved parent.
- Added `GTC006` for missing parents when the export is explicitly declared complete.
- Added `parentSpanId` format validation to `GTC001`.
- Added the `--trace-completeness partial|complete` CLI policy and included it in JSON reports.
- Added graph-problem and partial-export OTLP fixtures.
- Expanded the suite from 20 to 30 tests, including self-cycles, cross-trace ID reuse, duplicate
  parents, invalid parent IDs, and failure-threshold integration.

### Engineering decisions

1. **Group by trace first.** Span IDs only need to be unique inside a trace, so identical IDs in two
   trace IDs are not duplicates.
2. **Partial is the safe default.** A collector batch or query window can omit a valid parent; absence
   becomes an error only when the caller promises a complete export.
3. **Do not recurse through untrusted graphs.** The iterative cycle detector avoids Python recursion
   limits on deep traces.
4. **Do not resolve ambiguous parents.** If a parent ID is duplicated, `GTC003` is sufficient; child
   checks do not pretend one duplicate is authoritative.
5. **Containment is a warning.** Asynchronous child work may outlive a parent even when the graph is
   useful, so timing evidence should prompt review without failing the default gate.

### Verification result

- Ruff lint and format checks: passed.
- Pytest: 30 passed.
- Graph fixture in partial mode: two errors and one warning.
- The same fixture in complete mode: one additional missing-parent error.
- Partial-only fixture: passes by default and fails with `--trace-completeness complete`.

### Next task

Implement Day 4 latency and token consistency: trace-level latency summaries, token aggregation, and
boundary tests for nested and incomplete traces.

## 2026-09-22 — Day 4: latency and token consistency

### Objective

Turn valid spans into useful per-trace measurements and detect impossible relationships between
streaming latency, token totals, and their detailed breakdowns.

### Upstream research

- Confirmed `gen_ai.response.time_to_first_chunk` is measured in seconds from request issuance to
  the first streamed chunk.
- Confirmed input/output totals include modality-specific details rather than being separate from
  them.
- Confirmed cache-read, cache-write, and reasoning counts are subsets of larger totals.
- Confirmed current naming uses `gen_ai.usage.cache_write.input_tokens` after the upstream rename
  from `cache_creation`.
- Confirmed `execute_tool` spans should not report token usage.

### Completed

- Added a strict `TraceMetrics` report contract and deterministic per-trace metric generation.
- Added trace wall-clock duration and summed model/tool-call durations in milliseconds.
- Added observed input, output, and combined token totals plus the number of tokenized spans.
- Added `GTC107` for invalid or impossible time-to-first-chunk values.
- Added `GTC108` for token subsets that exceed their enclosing aggregate.
- Added `GTC109` when `execute_tool` spans report token usage.
- Limited provider/model completeness warnings to model operations or spans with a missing operation,
  avoiding false warnings on valid tool spans.
- Added valid and inconsistent latency/token OTLP fixtures and a metrics contract document.
- Expanded the suite from 30 to 51 tests.

### Engineering decisions

1. **Observed, not billed.** Trace totals are direct sums of valid exported attributes. The report
   does not claim to deduplicate nested instrumentation or reproduce an invoice.
2. **Wall time and call time remain separate.** Parallel calls can make summed model duration larger
   than trace wall time; both values are useful when named precisely.
3. **Subset checks, not equality checks.** Providers may expose only some modalities or breakdowns,
   so `component sum < total` is valid while `component sum > total` is impossible.
4. **Invalid values do not enter arithmetic.** `GTC104` reports them and metrics omit them rather than
   guessing a correction.
5. **No Hypothesis dependency yet.** The current numeric state space is small and explicit
   parameterized tests cover negative, zero, exact-boundary, out-of-range, Boolean, infinite, and
   NaN cases. Property-based testing will be reconsidered when configuration creates combinatorial
   rule interactions.

### Verification result

- Ruff lint and format checks: passed.
- Pytest: 51 passed.
- Valid latency/token fixture: zero findings; 5,000 ms trace time, 2,000 ms model-call time, 500 ms
  tool-call time, and 130 observed tokens.
- Inconsistent fixture: three errors (`GTC107`, two `GTC108`) and one `GTC109` warning.
- Existing risky fixture remains stable at five errors and three warnings.

### Next task

Implement Day 5 batch analysis: safe directory/glob inputs, deterministic file ordering, per-file
summaries, and one aggregate report without overwriting individual source identities.

## 2026-09-23 — Day 5: deterministic batch analysis

### Objective

Scale the single-file analyzer to real trace collections while keeping discovery safe, output order
reproducible, and failures attributable to an individual source file.

### Completed

- Added a dedicated `batch` command for multiple files, recursively scanned directories, and quoted
  glob patterns.
- Canonicalized, deduplicated, and lexicographically sorted all resolved paths.
- Skipped hidden discovery entries and avoided following directory symlinks.
- Added strict batch report, aggregate summary, per-file result, and file-status models.
- Preserved summaries, trace measurements, and findings independently for every analyzed file.
- Recorded malformed or unreadable files as `load_error` results without aborting the batch.
- Added an explicit `report_type` discriminator to both single and batch JSON reports.
- Rejected batch output paths that also resolve to a source file, even when `--force` is present.
- Added a batch contract document, command examples, architecture notes, and CI exercises.
- Expanded the suite from 51 to 60 tests.

### Engineering decisions

1. **A separate command keeps compatibility visible.** `check` still accepts exactly one file and
   emits the existing single-report shape; `batch` has an intentionally distinct aggregate shape.
2. **Every requested input must match.** A missing path or empty glob returns exit `2` instead of
   silently producing an incomplete batch.
3. **Load failure is a batch result.** Once discovery succeeds, a malformed file returns exit `1`
   and appears beside successful analyses rather than turning the whole operation into a usage
   error.
4. **Canonical paths define identity.** The same file reached through a directory, glob, explicit
   path, or symlink is analyzed once.
5. **Discovery and analysis stay offline.** Patterns are expanded by Python without shell
   evaluation or network access.

### Verification result

- Ruff lint and format checks: passed.
- Pytest: 60 passed.
- A two-file valid batch passed with stable source ordering and an aggregate summary.
- A mixed valid/risky batch returned exit `1` while retaining both per-file results.
- An invalid JSON file became a controlled `load_error`; the valid companion still contributed its
  spans, traces, and summary.
- A report path discovered as an input was rejected without modifying the source.

### Next task

Implement Day 6's versioned TOML policy file with strict unknown-key validation, rule
enable/disable controls, severity overrides, and documented CLI precedence.

## 2026-09-23 — Day 6: versioned configuration contract

### Objective

Make policy reusable and reviewable across developer machines and CI while ensuring configuration
mistakes fail visibly instead of silently weakening the quality gate.

### Completed

- Added an explicit `--config` option to both single-file and batch commands.
- Added a version `1.0` TOML contract for failure threshold, captured-content policy, secret
  detection, and partial/complete trace handling.
- Added per-rule `enabled` controls and `warning`/`error` severity overrides.
- Added a supported-rule catalog and validation for both TOML and programmatic policies.
- Rejected unknown top-level keys, policy keys, rule keys, rule IDs, values, and schema versions.
- Rejected empty rule entries and contradictory disabled-plus-severity settings.
- Applied rule settings centrally before sorting, summary counts, and quality-gate evaluation so
  `check` and `batch` share identical behavior.
- Added symmetric `--secret-detection` and `--no-secret-detection` CLI overrides.
- Recorded all effective policy and rule settings in JSON reports for auditability.
- Added a reviewed example policy, configuration reference, architecture notes, and CI exercise.
- Expanded the suite from 60 to 73 tests.

### Engineering decisions

1. **No implicit discovery.** Callers must pass `--config`; results cannot change because a new file
   appears in a parent directory.
2. **Strict means no silent typos.** Unknown keys and rule IDs return exit `2`, preventing a
   misspelled exception from looking active.
3. **Precedence is field-wise.** Built-ins are overlaid by TOML and then by explicit CLI flags, so
   one CLI override does not erase unrelated file settings.
4. **Rule policy is centralized.** Disablement and severity changes happen after all rule families
   emit findings but before counts, ordering, and pass/fail evaluation.
5. **Reports contain effective settings, not config paths.** This makes decisions reproducible
   without embedding machine-specific filesystem details.

### Verification result

- Ruff lint and format checks: passed.
- Pytest: 73 passed.
- A disabled `GTC201` disappeared from findings and summary counts.
- Promoting `GTC201` to error changed the finding, counts, ordering, and default quality-gate result.
- Explicit `--fail-on` and `--secret-detection` flags overrode file values independently.
- Invalid TOML, unsupported versions, unknown keys/rules, and contradictory overrides produced
  controlled configuration errors.

### Next task

Perform Day 7 release-candidate review: exercise mutation-oriented edge cases, measure coverage,
improve CLI/error ergonomics, and decide whether the evidence supports a `v0.2.0` tag.
