# Two-week implementation roadmap

The goal is a portfolio-ready project with a narrow, credible core and clear experimental evidence.
Each day ends with tests, a short log entry, and one reviewable commit.

## Week 1 — trustworthy core

### Day 1 — runnable vertical slice (completed)

- Create the repository and Python package.
- Parse canonical OTLP JSON and normalize span attributes.
- Add structural, GenAI semantic, and privacy rule families.
- Add a CLI, safe report writing, fixtures, tests, and CI.
- Document the architecture, standards boundary, and limitations.

**Definition of done:** a valid fixture exits `0`, a risky fixture exits `1`, and the test suite passes.

### Day 2 — schema-aware GenAI content

- Validate structured input/output messages and system instructions.
- Report precise JSON paths without echoing sensitive values.
- Add malformed and multi-part message fixtures.

### Day 3 — trace graph integrity

- Build per-trace parent/child indexes.
- Detect cycles, duplicate IDs, impossible containment, and optionally missing parents.
- Distinguish complete from partial exports through policy.

### Day 4 — latency and token consistency

- Compute model-call and tool-call latency summaries.
- Verify non-negative durations and trace-level token aggregation.
- Add property-based boundary tests if the dependency cost is justified.

### Day 5 — multi-file and batch analysis

- Accept directories and globs safely.
- Keep deterministic ordering across files.
- Add aggregate and per-file summaries.

### Day 6 — configuration contract

- Add a versioned TOML policy file.
- Support rule enable/disable and severity overrides.
- Validate unknown keys strictly and document precedence.

### Day 7 — release candidate review

- Run mutation-oriented edge cases and coverage analysis.
- Improve error messages and CLI help.
- Tag `v0.2.0` if all acceptance tests pass.

## Week 2 — evidence and open-source value

### Day 8 — framework-generated fixtures

- Generate comparable traces from two instrumentation libraries.
- Sanitize and freeze minimal reproducible fixtures.
- Document semantic differences without ranking projects unfairly.

### Day 9 — compatibility matrix

- Run every fixture through the same rules.
- Produce a machine-readable compatibility matrix.
- Separate exporter defects from optional/experimental attributes.

### Day 10 — SARIF output

- Map findings to SARIF without leaking trace content.
- Upload SARIF in a demonstration workflow.
- Test locations, severities, and stable fingerprints.

### Day 11 — performance benchmark

- Benchmark 1K, 10K, and 100K synthetic spans.
- Record peak memory, throughput, and fixture generator seed.
- Optimize only bottlenecks supported by a profile.

### Day 12 — contributor experience

- Add issue templates and a rule-author checklist.
- Expand public APIs and docstrings where useful.
- Test installation in a clean environment.

### Day 13 — upstream contribution preparation

- Search upstream issues and contribution guidelines again.
- Draft a small evidence-backed issue or documentation patch.
- Ask maintainers before proposing a broad semantic change.

Opening an upstream issue or pull request requires owner review; it is not an automated project step.

### Day 14 — portfolio release

- Publish an architecture diagram, benchmark table, and short demo.
- Tag `v1.0.0` only if the documented acceptance criteria are met.
- Write resume bullets that state measured results, not inflated adoption claims.

## Final acceptance criteria

- At least 20 independently tested rules across structure, semantics, and privacy.
- Two real instrumentation sources plus synthetic edge cases.
- Stable JSON and SARIF report contracts.
- Reproducible benchmark and compatibility-matrix generation.
- CI on supported Python versions and a clean install test.
- Documentation that distinguishes official conventions from project policy.
