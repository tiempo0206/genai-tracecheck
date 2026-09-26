# Changelog

All notable changes to GenAI TraceCheck are documented here.

## 1.0.0 — 2026-09-26

### Added

- Twenty independently addressable rules across OTLP structure, GenAI semantics, and local privacy
  policy, including tool-name, finish-reason, and server-port contracts.
- Reproducible OpenAI and LangChain instrumentation fixtures generated without provider network
  access.
- A versioned compatibility matrix that separates normative violations, recommended or opt-in
  absence, deprecations, local policy, and deliberate negative tests.
- Content-safe SARIF 2.1.0 output with repository-relative locations and stable fingerprints.
- Fixed-seed 1K, 10K, and 100K benchmark generation, compact result evidence, and retained profiles.
- Structured contribution templates, a typed public API, rule-author guidance, and clean wheel/sdist
  installation tests.
- A pinned upstream contribution research note, portfolio page, architecture diagram, and executable
  local demonstration.

### Changed

- Reused validated token values across subset checks, improving the committed 100K analysis median
  by 20.2% and end-to-end median by 10.5% on the recorded machine.
- Expanded CI to run lint, coverage, compatibility regeneration, benchmark smoke, portfolio demo,
  CLI behavior, distribution builds, and clean installs on Python 3.11 and 3.12.
- Advanced the package classifier from alpha to beta while retaining explicit warnings that the
  upstream GenAI semantic conventions remain at development stability.

### Verification

- All 159 final tests pass with 98% combined statement/branch coverage, enforced at a 95% minimum.
- Both framework fixtures pass the default error gate; all ten committed fixture expectations match.
- JSON and SARIF contracts, fixed-seed benchmark generation, clean wheel/sdist installation, and
  content non-disclosure are covered by CI.

## 0.2.0 — 2026-09-23

### Added

- Schema-aware validation for structured GenAI messages and system instructions.
- Trace-graph rules for duplicate IDs, cycles, parent containment, and complete exports.
- Per-trace latency, model/tool duration, and observed-token measurements.
- Latency and token consistency rules `GTC107` through `GTC109`.
- Deterministic multi-file analysis for files, recursive directories, and glob patterns.
- Strict version `1.0` TOML configuration with rule enablement and severity overrides.
- Effective policy metadata in single and batch reports.
- Branch coverage enforcement and wheel smoke tests in CI.

### Changed

- CLI help now documents exit statuses and deterministic glob behavior.
- Batch status output distinguishes rule findings from file-load failures.
- Report writes reject any output path that resolves to an input, including in single-file mode.

### Verification

- 105 tests across Python 3.11 and 3.12.
- 98% combined statement and branch coverage, enforced at a 95% minimum.
- Source distribution and wheel build plus clean wheel installation in CI.
