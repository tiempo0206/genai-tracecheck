# Architecture

## Design goal

TraceCheck separates transport decoding from policy. The core rule engine only sees normalized
`SpanRecord` values, so adding an OTLP protobuf reader or a framework adapter does not require
rewriting quality rules.

## Data flow

1. `loader.py` parses a canonical OTLP/HTTP JSON request and recursively decodes OTLP `AnyValue`
   attributes.
2. `models.py` validates the normalized span and report contracts with strict Pydantic models.
3. `rules.py` applies three independent rule families:
   - OTLP structural integrity (`GTC0xx`)
   - OpenTelemetry GenAI semantic completeness (`GTC1xx`)
   - TraceCheck privacy policy and heuristics (`GTC2xx`)
4. `analysis.py` sorts findings, counts severities, and evaluates the selected CI threshold.
5. `cli.py` prints JSON or writes it atomically, then returns a machine-friendly exit code.

## Trust boundaries

- Input trace files are untrusted. Invalid structure produces a controlled load error.
- The analyzer never performs network requests.
- A secret-shaped match is never copied into a finding.
- Existing report files are not replaced unless `--force` is explicit.
- Policy rules are labeled separately from upstream semantic-convention checks.

## Extension points

- **Readers:** OTLP protobuf, JSON Lines, and collector endpoints.
- **Rules:** parent/child graph integrity, latency consistency, token aggregation, and schema-aware
  validation of structured messages.
- **Outputs:** SARIF for code scanning and HTML for portfolio demonstrations.
- **Adapters:** reproducible fixtures emitted by multiple GenAI instrumentation libraries.

## Deliberate first-release limits

- Only OTLP/HTTP JSON files are accepted.
- Partial exports are allowed, so an absent parent span is not yet an error.
- Secret detection is heuristic and only scans known content-bearing GenAI attributes.
- Experimental OpenTelemetry attributes may change; TraceCheck does not invent proposed attributes
  or treat unaccepted proposals as normative.
