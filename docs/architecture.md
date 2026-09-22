# Architecture

## Design goal

TraceCheck separates transport decoding from policy. The core rule engine only sees normalized
`SpanRecord` values, so adding an OTLP protobuf reader or a framework adapter does not require
rewriting quality rules.

## Data flow

1. `loader.py` parses a canonical OTLP/HTTP JSON request and recursively decodes OTLP `AnyValue`
   attributes.
2. `models.py` validates the normalized span and report contracts with strict Pydantic models.
3. `classification.py` identifies GenAI, known model-call, and tool-call spans consistently across
   rules and metrics.
4. `content_validation.py` parses structured values or JSON strings and validates known GenAI
   message parts. Its result contains paths and constraints, never captured values.
5. `rules.py` applies three independent rule families:
   - OTLP structural integrity (`GTC0xx`)
   - OpenTelemetry GenAI semantic completeness (`GTC1xx`)
   - TraceCheck privacy policy and heuristics (`GTC2xx`)
6. `graph_rules.py` groups spans by trace, resolves unique parents, and checks cross-span integrity
   without recursion.
7. `metrics.py` derives trace wall time, model/tool call time, and observed token totals.
8. `analysis.py` combines, sorts, and counts findings before evaluating the selected CI threshold.
9. `cli.py` prints JSON or writes it atomically, then returns a machine-friendly exit code.

## Trust boundaries

- Input trace files are untrusted. Invalid structure produces a controlled load error.
- The analyzer never performs network requests.
- A secret-shaped match is never copied into a finding.
- A schema finding contains only its attribute, JSON path, and violated constraint.
- Existing report files are not replaced unless `--force` is explicit.
- Policy rules are labeled separately from upstream semantic-convention checks.

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
- **Outputs:** SARIF for code scanning and HTML for portfolio demonstrations.
- **Adapters:** reproducible fixtures emitted by multiple GenAI instrumentation libraries.

## Deliberate first-release limits

- Only OTLP/HTTP JSON files are accepted.
- Partial exports are allowed, so an absent parent span is not yet an error.
- Observed token totals can double count duplicate or nested instrumentation and are not billing data.
- Secret detection is heuristic and only scans known content-bearing GenAI attributes.
- Experimental OpenTelemetry attributes may change; TraceCheck does not invent proposed attributes
  or treat unaccepted proposals as normative.
