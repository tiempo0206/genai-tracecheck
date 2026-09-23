# Changelog

All notable changes to GenAI TraceCheck are documented here.

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
