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

### Day 2 — schema-aware GenAI content (completed)

- Validate structured input/output messages and system instructions.
- Report precise JSON paths without echoing sensitive values.
- Add malformed and multi-part message fixtures.

**Definition of done:** known message parts are validated, extensions remain allowed, malformed
fixtures report exact paths, and neither tests nor generated reports expose captured values.

### Day 3 — trace graph integrity (completed)

- Build per-trace parent/child indexes.
- Detect cycles, duplicate IDs, impossible containment, and optionally missing parents.
- Distinguish complete from partial exports through policy.

**Definition of done:** graph checks are trace-scoped and deterministic, cycle detection is
non-recursive, partial exports avoid missing-parent noise, and complete exports enforce closure.

### Day 4 — latency and token consistency (completed)

- Compute model-call and tool-call latency summaries.
- Verify non-negative durations and trace-level token aggregation.
- Add property-based boundary tests if the dependency cost is justified.

**Definition of done:** reports contain deterministic trace/call latency and observed-token summaries,
subset relationships are checked conservatively, and numeric boundary behavior is covered by tests.

### Day 5 — multi-file and batch analysis (completed)

- Accept directories and globs safely.
- Keep deterministic ordering across files.
- Add aggregate and per-file summaries.

**Definition of done:** overlapping inputs are safely deduplicated and deterministically ordered,
one bad file does not discard other results, batch reports preserve per-file identity, and the CLI
distinguishes quality/load failures from invalid command usage.

### Day 6 — configuration contract (completed)

- Add a versioned TOML policy file.
- Support rule enable/disable and severity overrides.
- Validate unknown keys strictly and document precedence.

**Definition of done:** an explicit version `1.0` TOML file is strictly validated, rule controls
affect findings and the quality gate consistently, active settings appear in reports, and explicit
CLI policy flags override file values without discarding unrelated settings.

### Day 7 — release candidate review (completed)

- Run mutation-oriented edge cases and coverage analysis.
- Improve error messages and CLI help.
- Tag `v0.2.0` if all acceptance tests pass.

**Definition of done:** lint and 105 tests pass, combined statement/branch coverage reaches 98% and
is enforced at 95%, distributions build and install cleanly, CLI safety/ergonomics are reviewed,
and the passing `main` commit is tagged `v0.2.0`.

## Week 2 — evidence and open-source value

### Day 8 — framework-generated fixtures (completed)

- Generate comparable traces from two instrumentation libraries.
- Sanitize and freeze minimal reproducible fixtures.
- Document semantic differences without ranking projects unfairly.

**Definition of done:** two pinned official instrumentation packages generate comparable traces
without provider network access, normalized fixtures are content-addressed and reproducible, both
pass the default quality gate, and observed differences are documented as evidence rather than
project rankings.

### Day 9 — compatibility matrix (completed)

- Run every fixture through the same rules.
- Produce a machine-readable compatibility matrix.
- Separate exporter defects from optional/experimental attributes.

**Definition of done:** all ten fixtures are analyzed with one policy, every expected gate is
verified, a versioned JSON matrix records fixture digests and the pinned standards revision, and
framework observations distinguish required violations from recommended/opt-in absence,
deprecations, local policy, and deliberate negative tests.

### Day 10 — SARIF output (completed)

- Map findings to SARIF without leaking trace content.
- Upload SARIF in a demonstration workflow.
- Test locations, severities, and stable fingerprints.

**Definition of done:** single and batch reports emit SARIF 2.1.0 without changing gate semantics,
every result has a repository-relative location and deterministic fingerprint, tests prove severity
overrides and content non-disclosure, and a least-privilege workflow demonstrates GitHub upload.

### Day 11 — performance benchmark (completed)

- Benchmark 1K, 10K, and 100K synthetic spans.
- Record peak memory, throughput, and fixture generator seed.
- Optimize only bottlenecks supported by a profile.

**Definition of done:** a fixed-seed streaming generator produces valid 1K/10K/100K OTLP fixtures,
three isolated phases record median throughput and peak Python allocations, a 100K cumulative
profile is retained, and the only core optimization is supported by before/after measurements while
CI smoke-tests the benchmark contract on both supported Python versions.

### Day 12 — contributor experience (completed)

- Add issue templates and a rule-author checklist.
- Expand public APIs and docstrings where useful.
- Test installation in a clean environment.

**Definition of done:** structured bug and rule-proposal forms request sanitized, reproducible
evidence; the PR template and rule-author guide cover provenance, privacy, tests, and synchronized
contracts; the typed top-level API is documented and regression-tested; and CI installs both wheel
and sdist into fresh environments before exercising imports, dependency integrity, and the CLI.

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
