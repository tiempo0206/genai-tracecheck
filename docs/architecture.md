# Architecture

## Design goal

TraceCheck separates transport decoding from policy. The core rule engine only sees normalized
`SpanRecord` values, so adding an OTLP protobuf reader or a framework adapter does not require
rewriting quality rules.

## Data flow

1. `config.py` strictly validates an explicit, versioned TOML policy and resolves rule controls.
2. `batch.py` safely resolves file, directory, and glob inputs into a canonical sorted set.
3. `loader.py` parses a canonical OTLP/HTTP JSON request and recursively decodes OTLP `AnyValue`
   attributes.
4. `models.py` validates the normalized span and report contracts with strict Pydantic models.
5. `classification.py` identifies GenAI, known model-call, and tool-call spans consistently across
   rules and metrics.
6. `content_validation.py` parses structured values or JSON strings and validates known GenAI
   message parts. Its result contains paths and constraints, never captured values.
7. `rules.py` applies three independent rule families:
   - OTLP structural integrity (`GTC0xx`)
   - OpenTelemetry GenAI semantic completeness (`GTC1xx`)
   - TraceCheck privacy policy and heuristics (`GTC2xx`)
8. `graph_rules.py` groups spans by trace, resolves unique parents, and checks cross-span integrity
   without recursion.
9. `metrics.py` derives trace wall time, model/tool call time, and observed token totals.
10. `analysis.py` applies rule configuration, then sorts and counts findings before evaluating the
    selected CI threshold.
11. `batch.py` preserves independent file results and derives aggregate batch counts.
12. `sarif.py` maps safe finding metadata to SARIF 2.1.0 locations, rules, severity, and stable
    fingerprints without copying trace identity or captured values.
13. `cli.py` prints JSON/SARIF or writes it atomically, then returns a machine-friendly exit code.

The core package remains framework-neutral. A separate development-only pipeline under
`tools/framework-fixtures/` invokes real instrumentation against local mock/fake backends, exports
SDK spans to canonical OTLP JSON, normalizes nondeterministic identifiers and timestamps, and freezes
content-addressed fixtures. It never runs inside the analyzer.

`tools/compatibility-matrix/` then discovers every frozen OTLP fixture, analyzes the complete set
with one default policy, joins framework provenance, and writes a content-free compatibility
snapshot. Fixture purpose and expected gate are explicit, so a new fixture cannot silently disappear
from the evidence set.

`benchmarks/run.py` streams fixed-seed canonical OTLP fixtures into a temporary directory, validates
them through the public loader and analyzer, and measures load, analysis, and end-to-end phases
independently. Only compact result and cumulative-profile evidence is committed; 1K/10K/100K input
files are regenerated rather than stored.

## Trust boundaries

- Input trace files are untrusted. Invalid structure produces a controlled load error.
- The analyzer never performs network requests.
- Framework fixture generation uses only a local HTTP mock transport or an in-process fake model.
- A secret-shaped match is never copied into a finding.
- A schema finding contains only its attribute, JSON path, and violated constraint.
- Existing report files are not replaced unless `--force` is explicit.
- A batch output path cannot also be one of its source files, including through a symlink.
- Directory discovery ignores hidden entries and does not follow symlinked directories.
- Configuration is explicit, versioned, and rejects unknown fields or rule IDs.
- Policy rules are labeled separately from upstream semantic-convention checks.
- Compatibility output contains presence metadata and rule IDs, never captured content values.
- SARIF fingerprints hash trace identity and safe structural details; raw identifiers are omitted.
- Benchmark fixtures contain invented metadata only and are deleted with their temporary directory.

## Partial versus complete trace exports

An OTLP file is not necessarily a complete trace. Sampling, batching, and bounded query windows can
leave a child span without its parent. TraceCheck therefore defaults to `partial` mode and does not
report missing parents. In `complete` mode, every valid `parentSpanId` must resolve inside the same
trace or `GTC006` is emitted.

Duplicate IDs and cycles are errors in both modes. Parent/child time containment is a warning rather
than an error because asynchronous work can legitimately outlive the initiating parent.

## Extension points

- **Readers:** OTLP protobuf, JSON Lines, and collector endpoints.
- **Rules:** response-stream timing, provider-specific invariants, and richer graph policies.
- **Outputs:** HTML for portfolio demonstrations and additional CI annotations.
- **Adapters:** more reproducible fixtures emitted by GenAI instrumentation libraries.

## Deliberate first-release limits

- Only OTLP/HTTP JSON content is accepted; protobuf and JSON Lines are not yet supported.
- Partial exports are allowed, so an absent parent span is not yet an error.
- Observed token totals can double count duplicate or nested instrumentation and are not billing data.
- Secret detection is heuristic and only scans known content-bearing GenAI attributes.
- Experimental OpenTelemetry attributes may change; TraceCheck does not invent proposed attributes
  or treat unaccepted proposals as normative.
