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

## 2026-09-23 — Day 7: release-candidate review

### Objective

Audit the first-week feature set as a release candidate, use coverage and mutation-oriented
reasoning to expose weak tests, improve command-line safety, and release only against measured gates.

### Baseline finding

The original 73-test suite passed but combined statement/branch coverage was 90%. Most missed paths
were malformed OTLP nesting, less-common official content parts, and CLI write failures. Passing
tests alone therefore did not provide enough release evidence.

### Completed

- Added Coverage.py branch measurement with a 95% CI minimum.
- Added mutation-oriented cases for known content parts, nested OTLP boundaries, configuration
  contradictions, batch all-files semantics, atomic cleanup, and CLI policy precedence.
- Expanded the suite from 73 to 105 tests and raised measured coverage from 90% to 98%.
- Fixed single-file `--force` output aliasing so an input cannot be overwritten by its own report.
- Improved batch status text to show file-load failures separately from rule errors and warnings.
- Added exit-code guidance and deterministic-glob guidance to CLI help.
- Added distribution builds and clean wheel-install smoke tests to both supported Python CI jobs.
- Bumped the package and runtime version to `0.2.0`.
- Added a release-candidate review, changelog, and explicit verification table.

### Engineering decisions

1. **Measure branches, not only lines.** Boolean decisions define quality-gate behavior; line-only
   coverage would overstate confidence in them.
2. **Use a meaningful floor.** The 95% aggregate gate leaves room for defensive OS race paths while
   preventing a substantial untested feature from entering unnoticed.
3. **Document mutation hypotheses honestly.** The tests target plausible logic mutations, but the
   project does not claim a mutation score without running a dedicated tool.
4. **Protect source data in every mode.** `--force` authorizes replacement of a report, never an
   input trace that happens to share the output path.
5. **Tag the merged commit.** The release tag is created only after the review PR passes both Python
   CI jobs and is merged to `main`.

### Verification result

- Ruff lint and format checks: passed.
- Pytest: 105 passed.
- Combined statement/branch coverage: 98% (minimum: 95%).
- Positive, quality-failing, load-failing, and invalid-configuration CLI paths: passed.
- Source distribution and wheel build: passed.
- Clean wheel installation and `genai-tracecheck --version`: passed.

### Next task

Begin Day 8 with framework-generated fixtures from two instrumentation libraries, sanitize them,
and document semantic differences without treating optional attributes as defects.

## 2026-09-23 — Day 8: framework-generated fixtures

### Objective

Replace hand-authored-only evidence with reproducible OTLP traces emitted by two real GenAI
instrumentation packages, while keeping the experiment offline, sanitized, and fair to each source.

### Upstream research

- Selected the OpenTelemetry Python GenAI OpenAI and LangChain instrumentations from the same
  upstream project and pinned both at `1.1b0`.
- Followed the upstream OpenAI test strategy of using an `httpx.MockTransport` so the official SDK
  request path executes without contacting a provider.
- Followed the upstream LangChain tests in using `FakeMessagesListChatModel` for an in-process model
  response.
- Confirmed that message-content capture is opt-in and enabled it only for invented fixture text.

### Completed

- Added a standalone generator environment with exact direct dependency pins.
- Generated one OpenAI SDK trace and one LangChain fake-model trace through real instrumentation.
- Exported the finished SDK spans as canonical OTLP/HTTP JSON.
- Replaced runtime IDs, timestamps, and resource metadata with deterministic synthetic values while
  preserving instrumentation-produced GenAI attributes.
- Added a versioned manifest with scenario provenance, installed versions, normalization steps, and
  SHA-256 fixture digests.
- Added regression tests for digest integrity, dependency pins, default-gate results, semantic
  differences, deterministic timestamps, and credential absence.
- Documented reproduction, sanitization, trust boundaries, and a neutral comparison of emitted
  attributes.
- Added a CI batch exercise covering both framework-generated fixtures.

### Engineering decisions

1. **Generate offline, not approximately.** The real SDK/instrumentation call paths run against a
   mock transport or fake model; no hand-authored JSON is presented as framework output.
2. **Keep framework dependencies isolated.** TraceCheck remains a small framework-neutral runtime;
   the pinned generator environment is installed only when deliberately regenerating fixtures.
3. **Freeze provenance and bytes together.** The manifest records exact versions and file digests so
   a dependency update cannot silently change the evidence.
4. **Normalize nondeterminism, preserve semantics.** Runtime IDs, times, and incidental resource
   fields are replaced, but span names and `gen_ai.*` values are retained for comparison.
5. **Absence is evidence, not a verdict.** Token totals and response metadata can depend on what a
   model backend exposes; the documentation reports their presence without ranking projects.

### Verification result

- Fixture regeneration check: byte-for-byte reproducible.
- Ruff lint and format checks: passed.
- Pytest: 110 passed.
- Combined statement/branch coverage remained above the enforced 95% minimum.
- Both individual fixtures passed with zero errors and two expected warnings (`GTC106`, `GTC201`).
- The two-file batch passed with 2 spans, 2 GenAI spans, 0 errors, and 4 warnings.
- Credential-marker and SHA-256 integrity checks: passed.

### Next task

Implement Day 9's machine-readable compatibility matrix across synthetic and framework-generated
fixtures, separating required failures from optional, experimental, or unavailable attributes.

## 2026-09-25 — Day 9: compatibility matrix

### Objective

Run every committed OTLP fixture through one policy and produce durable evidence that separates
actual required violations from missing-but-optional telemetry, evolving conventions, local policy,
and deliberate negative tests.

### Upstream research

- Pinned the matrix to OpenTelemetry GenAI semantic-convention revision `e57c543` rather than a
  moving documentation URL.
- Confirmed that inference spans remain at `development` stability in that revision.
- Confirmed `gen_ai.operation.name` and `gen_ai.provider.name` are required for inference clients.
- Recorded request model as conditionally required when available; response metadata, usage totals,
  finish reasons, and server address as recommended; and captured messages as opt-in.
- Reviewed the upstream Python GenAI project's conformance guidance so this project does not present
  its smaller fixture matrix as a replacement for Weaver live-check.

### Completed

- Added a deterministic generator that discovers and analyzes all ten OTLP fixtures with the same
  default TraceCheck policy.
- Added explicit fixture purposes, positive/negative/framework categories, and expected quality-gate
  outcomes.
- Added SHA-256 digests for every fixture and fail-fast catalog coverage for additions or removals.
- Added a version `1.0` machine-readable matrix with aggregate results, per-fixture rule evidence,
  framework package versions, and attribute-presence status.
- Added a classification contract for candidate required violations, deprecations, recommended and
  opt-in absence, local policy, and intentional negative cases.
- Excluded captured content, matched secrets, trace IDs, and span IDs from the matrix.
- Added documentation, README/architecture/roadmap updates, tests, and a CI regeneration check.

### Engineering decisions

1. **One policy for every fixture.** Separate per-source settings would make comparisons convenient
   but not comparable.
2. **Declare test intent.** Failures in a negative regression fixture are success evidence for the
   analyzer, not exporter defects.
3. **Treat recommended absence conservatively.** A missing value is not a defect without proof that
   the provider or framework exposed it to the instrumentation.
4. **Use a candidate threshold for exporter claims.** Only required/structural failures in a real
   framework fixture enter `exporter_defect_candidates`, and still require upstream reproduction.
5. **Snapshot evolving standards.** The matrix stores an exact upstream revision and `development`
   stability instead of implying a timeless compatibility result.
6. **Keep evidence content-free.** Presence and rule metadata answer the compatibility question
   without creating another copy of captured prompts or responses.

### Verification result

- Matrix regeneration check: byte-for-byte reproducible.
- Fixture coverage and SHA-256 integrity: 10 of 10 verified.
- Expected quality gates: 10 of 10 matched.
- Aggregate analysis: 20 spans, 10 traces, 16 deliberate errors, and 12 warnings.
- Framework-generated fixtures: both passed the TraceCheck gate; one conditional `server.port`
  absence was isolated as an exporter defect candidate pending upstream reproduction.
- Ruff lint and format checks: passed.
- Pytest: 115 passed.
- Combined statement/branch coverage remained above the enforced 95% minimum.

### Next task

Implement Day 10 SARIF output with content-free locations, stable fingerprints, severity mapping,
tests, and a demonstration GitHub code-scanning workflow.

## 2026-09-26 — Day 10: content-safe SARIF output

### Objective

Expose TraceCheck findings to standard code-scanning infrastructure without changing quality-gate
behavior or turning the SARIF artifact into another copy of sensitive telemetry.

### Standards and platform research

- Confirmed GitHub Code Scanning supports the SARIF `2.1.0` subset.
- Confirmed each displayed result needs a location and that repository-relative paths give the most
  reliable annotations.
- Confirmed GitHub uses `partialFingerprints.primaryLocationLineHash` to match alerts across runs.
- Confirmed third-party upload workflows require `security-events: write`.
- Used the OASIS SARIF 2.1.0 specification for top-level, rule, result, artifact-location, region,
  and partial-fingerprint structure.

### Completed

- Added `--format json|sarif` to both `check` and `batch`, preserving JSON as the default.
- Added a SARIF 2.1.0 converter with all 17 rules, deterministic indexes, descriptions, help links,
  and default severity metadata.
- Mapped effective post-configuration severities to SARIF `error` and `warning` levels.
- Added repository-relative artifact paths and span-scoped line/column locations with a safe line-1
  fallback.
- Added deterministic SHA-256 fingerprints under GitHub's primary key and a versioned TraceCheck
  key.
- Restricted fingerprint inputs to identifiers that are hashed plus an explicit allowlist of safe
  structural detail.
- Excluded raw trace/span IDs, captured content, secret matches, and unreviewed finding details from
  output.
- Added batch source preservation and run metadata for report type, gate status, and load errors.
- Added a least-privilege GitHub Code Scanning demonstration workflow using `upload-sarif@v4`.
- Added CLI/CI exercises, a SARIF contract document, architecture/README/roadmap updates, and nine
  focused regression tests.

### Engineering decisions

1. **Serialization does not alter evaluation.** JSON and SARIF share one analyzed report and return
   the same exit status.
2. **Point to the span, not captured content.** A span-level source location is useful in fixture
   review and avoids parsing sensitive nested values into annotations.
3. **Hash identity, emit no identity.** Trace and span IDs help distinguish telemetry events but
   appear only inside the fingerprint preimage.
4. **Allowlist fingerprint detail.** New rule details cannot silently leak into SARIF; only reviewed
   structural keys participate.
5. **Honor effective severity.** Configuration overrides must affect JSON counts, SARIF levels, and
   the quality gate consistently.
6. **Do not invent load-error rules.** Batch load failures remain run metadata and exit-code evidence.
7. **Keep the upload explicitly demonstrative.** Alerts target the deliberately risky fixture and
   are not presented as application vulnerabilities.

### Verification result

- Ruff lint and format checks: passed.
- Pytest: 124 passed.
- Combined statement/branch coverage remained above the enforced 95% minimum.
- Risky fixture: 8 SARIF results with valid rule indexes, levels, locations, and fingerprints.
- Generated output validated against the official OASIS SARIF 2.1.0 JSON Schema.
- Repeated conversion: byte-identical fingerprints.
- Known secret, captured message, raw trace ID, and raw span ID leakage checks: passed.
- Single, batch, stdout, file output, and severity-override paths: passed.
- Distribution build and installed CLI smoke test: passed.

### Next task

Implement Day 11's reproducible 1K/10K/100K span benchmark, recording seed, throughput, peak memory,
and profiler-backed optimization decisions.

## 2026-09-26 — Day 11: reproducible performance benchmark

### Objective

Characterize TraceCheck at 1K, 10K, and 100K spans with reproducible input, phase-specific timing
and memory evidence, then change production code only when a deterministic profile identifies a
specific avoidable cost.

### Method research

- Selected `time.perf_counter_ns` for high-resolution elapsed-time samples without floating-point
  clock conversion loss.
- Selected `tracemalloc.get_traced_memory` for phase-local current and peak Python allocations,
  explicitly distinguishing this value from operating-system RSS.
- Selected the standard-library deterministic `cProfile` implementation and `pstats` cumulative
  ordering for hotspot attribution.
- Kept timing and memory passes separate because allocation tracing changes runtime cost.

### Completed

- Added a versioned generator with seed `20260926` that streams canonical OTLP JSON without holding
  a second large fixture object graph in memory.
- Generated valid 100-span trace groups with deterministic IDs, contained child timing, model and
  provider identity, and valid token usage.
- Added preflight validation requiring exact span counts, a passing quality gate, and zero findings.
- Measured isolated loading, analysis, and end-to-end phases with one warm-up and three timed samples.
- Recorded medians, sample ranges, throughput, phase-local peak Python allocations, fixture sizes,
  SHA-256 digests, environment metadata, and methodology in a versioned JSON artifact.
- Retained cumulative profiles before and after the production optimization.
- Reused each validated token value across nine token-subset checks instead of validating the same
  attributes repeatedly.
- Added deterministic-generator, fixture-validity, and benchmark-contract tests.
- Added a 100-span benchmark smoke step to both Python 3.11 and 3.12 CI jobs.
- Documented reproduction commands, results, interpretation limits, and why no time threshold is
  enforced on shared CI runners.

### Engineering decisions

1. **Generate large evidence, do not commit it.** The 100K input is about 58.5 MiB and is reproduced
   from a seed; only its digest and compact results belong in Git.
2. **Separate phases.** Loading and analysis answer different architectural questions, while the
   end-to-end number represents the user-visible path.
3. **Separate timing from tracing.** Untraced medians describe speed; a separate `tracemalloc` run
   describes allocations without pretending the two measurements are one uncontaminated sample.
4. **Optimize from evidence.** The baseline profile showed 1.8 million token-validation calls for
   200,000 attributes. Per-span reuse was local, testable, and preserved rule semantics.
5. **Do not optimize away contracts.** Strict Pydantic construction and full-document JSON parsing
   remain visible costs; changing either needs broader input and API evidence.
6. **No benchmark theater in CI.** CI checks that the harness works but does not fail builds because
   a shared runner was temporarily slow.

### Verification result

- Fixed-seed regeneration: byte-identical files and stable SHA-256 digests.
- 100K fixture: 100,000 valid GenAI spans across 1,000 complete traces with zero findings.
- Optimized 100K analysis median: 0.495828 seconds, or 201,683 spans/second.
- Optimized 100K end-to-end median: 1.677553 seconds, or 59,611 spans/second.
- 100K end-to-end peak Python allocations: 483.60 MiB; loading is the dominant memory phase.
- Profile-backed change: analysis median improved 20.2% and end-to-end median improved 10.5%.
- Token-check cumulative profile time fell from 1.157 seconds to 0.298 seconds.
- Focused rule and benchmark tests, Ruff lint, and formatting checks passed before the full suite.

### Next task

Implement Day 12 contributor experience: issue templates, a rule-author checklist, clearer public
API/docstrings, and another clean-environment installation test.

## 2026-09-26 — Day 12: contributor experience

### Objective

Make the repository safe and understandable for an outside contributor: route reports into useful
structured evidence, define the complete rule-development contract, expose an intentional typed
Python API, and prove that both distribution formats work outside the source checkout.

### Platform and packaging research

- Followed GitHub's Issue Forms structure and template-chooser configuration, including unique field
  IDs, required validations, and `blank_issues_enabled: false`.
- Followed the Python Packaging User Guide recommendation to build both a wheel and source
  distribution and install artifacts into isolated virtual environments.
- Treated the installed package—not an editable source tree—as the authoritative clean-install
  target, and used Python isolated mode for the import probe.

### Completed

- Added separate Issue Forms for sanitized bug reports and evidence-backed rule proposals.
- Added privacy notices that prohibit real prompts, credentials, personal data, and proprietary
  trace content in reproductions.
- Added a pull-request template covering evidence, tests, privacy, documentation, distribution
  changes, and rule-specific synchronization.
- Rewrote the contributor guide around issue routing, coverage, evidence classification, public API
  changes, complete local checks, and pull-request expectations.
- Added a rule-authoring guide covering family selection, applicability, severity, safe diagnostics,
  implementation layers, independent tests, configuration, SARIF, and public contract updates.
- Expanded the top-level API with `ContentPolicy`, `FailureThreshold`, `Finding`, and `Severity`.
- Added useful docstrings to loader, discovery, configuration, single/batch analysis, and SARIF
  operations, plus programmatic single, batch, policy, and SARIF examples.
- Declared inline typing with `py.typed` and configured package data so both artifacts retain it.
- Added a cross-platform clean-install tool that creates one fresh environment per artifact, runs
  `pip check`, imports the public API with `python -I`, verifies installation outside the checkout,
  checks `py.typed`, and exercises the installed CLI on an invented one-span fixture.
- Replaced the former wheel-version-only CI smoke with wheel and sdist end-to-end smoke tests on both
  supported Python versions.

### Engineering decisions

1. **Ask for evidence at issue creation.** Version, Python, installation method, commands, sanitized
   input, expected behavior, and actual behavior are easier to collect before triage begins.
2. **Give rule proposals their own path.** A rule needs normative status, pinned source, diagnostic,
   examples, and false-positive analysis that a generic feature template would not request.
3. **Keep accidental internals private.** `genai_tracecheck.__all__` is the explicit integration
   boundary; adding a top-level name requires types, documentation, and tests.
4. **Ship typing as product behavior.** Source annotations are useful to downstream users only when
   the wheel and sdist include the PEP 561 marker.
5. **Test artifacts away from the repository.** Isolated mode and a temporary working directory
   prevent the checkout from hiding a missing module or package-data error.
6. **Exercise behavior, not only importability.** A successful `--version` cannot prove the console
   entry point, Pydantic dependency, loader, analyzer, and report writer work together.

### Verification result

- All three Issue Form/config YAML files parsed as mappings.
- Ruff lint and formatting checks: passed.
- Pytest: 131 passed.
- Combined statement/branch coverage: 98% (minimum: 95%).
- Compatibility matrix regeneration check: passed.
- Wheel and source distribution rebuilt with `genai_tracecheck/py.typed` present.
- Fresh wheel installation: public API, `pip check`, isolated import, typing marker, and CLI passed.
- Fresh sdist installation: public API, `pip check`, isolated import, typing marker, and CLI passed.

### Next task

Prepare Day 13's upstream contribution research: re-check current upstream contribution guidance and
issues, reduce the compatibility observation to a small evidence-backed proposal, and draft it for
owner review without publishing externally.

## 2026-09-26 — Day 13: upstream contribution preparation

### Objective

Turn one compatibility-matrix observation into a narrow, reproducible upstream contribution
candidate while respecting the upstream project's contribution policy and avoiding an unsupported
claim that the behavior is already a confirmed defect.

### Upstream research

- Confirmed that the maintained GenAI packages moved from `opentelemetry-python-contrib` to
  `open-telemetry/opentelemetry-python-genai`.
- Pinned the inspected Python GenAI source to `14c76fee1a5270d194bfada07f711352a2d3aa4d`, where
  the OpenAI instrumentation reports version `1.2b0`.
- Reused the compatibility matrix's pinned semantic-convention revision
  `e57c543b4889619eb2a05702471937db5119165d`.
- Re-checked the new repository's contribution guidance, bug form, and two focused issue searches;
  no matching default-HTTPS-port issue was found on the research date.
- Recorded the upstream rule that AI-generated issue and pull-request comments must not be posted.

### Completed

- Added a versioned machine-readable evidence snapshot with repository revisions, the frozen fixture
  digest, observed attributes, source/test behavior, duplicate-search links, and publication status.
- Connected four independent evidence layers: the local `1.1b0` fixture, current `1.2b0` source,
  current upstream tests, and the pinned GenAI semantic-convention model.
- Documented that upstream deliberately converts port 443 to `None` while the current GenAI span
  model makes `server.port` conditional on `server.address` without stating a default-port exception.
- Classified the result as a specification/implementation clarification candidate, not a confirmed
  instrumentation defect.
- Prepared a concise bug-form draft, maintainer question, minimal post-confirmation patch plan, and
  owner checklist without publishing any external comment or issue.
- Added regression tests that bind the evidence to the real frozen fixture and protect the human
  review boundary.
- Updated the compatibility narrative, roadmap, and project status to point to the research artifact.

### Engineering decisions

1. **Ask before changing semantics.** The current evidence proves a mismatch candidate but does not
   decide whether instrumentation or a development-stage convention should change.
2. **Pin every moving source.** Commit revisions and the fixture digest make the claim inspectable
   after upstream main and issue results change.
3. **Test research artifacts.** A prose note alone could drift away from the fixture; tests now check
   both the digest and the actual attribute presence.
4. **Keep public authorship human.** The repository contains preparation and evidence only. The owner
   must reproduce, search again, rewrite in their own words, and choose the discussion channel.
5. **Target the migrated repository.** Preparing work against the former contrib location would make
   an otherwise correct proposal operationally obsolete.

### Verification result

- Ruff lint and formatting checks: passed.
- Pytest: 134 passed.
- Combined statement/branch coverage: 98% (minimum: 95%).
- Compatibility matrix regeneration check: passed.
- Wheel and source distribution build: passed.
- Evidence digest and fixture observation test: passed.
- External publication: none; status remains `draft_only_owner_review_required`.

### Next task

Complete Day 14's portfolio release: audit the final acceptance criteria, close any remaining rule
count gap, publish durable architecture/demo evidence, prepare measured resume bullets, and tag
`v1.0.0` only after the merged release commit and CI are green.

## 2026-09-26 — Day 14: portfolio release

### Objective

Close every documented acceptance gap, present the engineering evidence in a concise portfolio
artifact, and prepare a release that can be tagged only from a reviewed, green `main` commit.

### Acceptance audit and rule completion

- Audited each final criterion against executable tests, generators, artifacts, CI configuration,
  and current documentation rather than treating the roadmap as proof by itself.
- Found one real gap: the project had 17 rule IDs while the roadmap required at least 20.
- Added `GTC110` for the required non-empty tool name on `execute_tool` spans.
- Added `GTC111` for the published `string[]` finish-reasons attribute contract.
- Added `GTC112` for an integer GenAI server port in the usable 1–65535 range, while explicitly
  keeping the disputed default-port emission question outside the rule.
- Added independent invalid/valid boundary tests and an exact 20-rule release invariant.

### Completed

- Advanced package and runtime metadata to `1.0.0` and the beta development classifier.
- Added a portfolio page with a rendered Mermaid architecture diagram, measured benchmark summary,
  acceptance evidence, reproducibility commands, and three honest resume bullets.
- Added a deterministic three-stage demo covering a passing trace, expected gate failure, and
  content-safe SARIF with stable fingerprints.
- Added the demo to both supported CI jobs and regression-tested its exact output.
- Added release-contract tests binding the runtime/package version, changelog, README, rule count,
  diagram, benchmark numbers, optimization claim, and demo documentation.
- Updated the README rule catalog and release status, changelog, architecture cross-reference, and
  roadmap acceptance audit.

### Engineering decisions

1. **Close the rule gap with normative data contracts.** New checks use required attributes or
   published value types and deterministic boundaries, not subjective model-output quality.
2. **Do not turn the upstream question into a local fact.** `GTC112` validates a port only when it is
   present; it does not claim that implicit HTTPS 443 must be emitted.
3. **Make the demo executable evidence.** Its expected failures are asserted as product behavior,
   and any secret value appearing in SARIF makes the demo fail.
4. **Publish measured context, not a vanity number.** Benchmark environment, seed, samples, peak
   allocation definition, and one-machine limitations remain adjacent to the headline throughput.
5. **Separate release content from release authority.** Versioned code is reviewed through a PR;
   the annotated tag is created only at the merged commit after main CI is green.

### Verification result

- Rule catalog: exactly 20 independently addressable IDs.
- Ruff lint and formatting checks: passed.
- Pytest: 159 passed.
- Combined statement/branch coverage: 98% (minimum: 95%).
- All ten compatibility expectations and regeneration check: passed.
- Deterministic portfolio demo and SARIF non-disclosure assertion: passed.
- 100-span fixed-seed benchmark smoke: passed.
- Version `1.0.0` wheel and source distribution builds: passed.
- Fresh wheel and fresh sdist installation, dependency, typing, import, and CLI probes: passed.

### Release control

Merge the Day 14 review commit, wait for both Python 3.11 and 3.12 checks on `main`, then create the
annotated `v1.0.0` tag at that exact commit. Do not tag the feature branch or a merely local commit.
