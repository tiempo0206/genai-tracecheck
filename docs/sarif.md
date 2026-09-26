# SARIF output

TraceCheck can emit [SARIF 2.1.0](https://docs.oasis-open.org/sarif/sarif/v2.1.0/os/sarif-v2.1.0-os.html)
for local tooling and GitHub Code Scanning. JSON remains the default report contract; selecting SARIF
changes only the serialization, not rule evaluation, policy overrides, or exit codes.

## Generate a report

```bash
# A failing quality gate still writes SARIF and exits 1.
genai-tracecheck check examples/risky.otlp.json \
  --format sarif --output reports/risky.sarif

# Batch findings retain the source file for each result.
genai-tracecheck batch 'examples/**/*.otlp.json' \
  --format sarif --output reports/all-fixtures.sarif
```

The existing exit contract still applies: `0` means the quality gate passed, `1` means findings met
the failure threshold or a batch input could not be loaded, and `2` means command usage, input,
configuration, or report writing was invalid.

## Mapping contract

| TraceCheck field | SARIF field |
| --- | --- |
| Rule catalog | `runs[0].tool.driver.rules` |
| Effective error severity | `results[].level = error` |
| Effective warning severity | `results[].level = warning` |
| Safe finding message | `results[].message.text` |
| Input file | `artifactLocation.uri` |
| Span location | `region.startLine` and columns around the `spanId` key |
| Stable identity | `partialFingerprints.primaryLocationLineHash` |
| Report/gate/load status | run-level `properties` |

Rule indexes are deterministic and point into the sorted rule catalog. Severity comes from the
effective finding after configuration, so promoting `GTC201` to an error also produces SARIF level
`error`.

Locations use repository-relative POSIX paths when the input is inside the working tree. TraceCheck
locates the matching `spanId` key in the source JSON and emits only its line and columns. If the
source cannot be read or the key cannot be found, the result falls back to line 1. An absolute input
outside the working tree is reduced to `external/<filename>` to avoid leaking a local directory.

## Stable fingerprints

Each result contains both `primaryLocationLineHash`, the key GitHub uses for alert matching, and a
versioned `genaiTracecheck/v1` fingerprint. Both contain the same SHA-256 digest over:

- rule ID and safe static message;
- normalized source path;
- trace/span identity, hashed rather than emitted;
- affected attribute name; and
- an allowlist of structural detail such as JSON path, constraint, or violation category.

Repeated conversion of the same report is byte-stable. A different trace or span intentionally gets
a different identity, while formatting changes that preserve the logical location do not expose or
copy telemetry values.

## Privacy boundary

SARIF results intentionally exclude:

- raw trace and span IDs;
- captured prompts, responses, instructions, retrieval documents, and tool arguments/results;
- secret-shaped matches;
- raw finding-detail values that are not explicitly allowlisted.

Messages are static diagnostics already used by TraceCheck JSON reports. Result properties contain
only the effective severity and, when available, the attribute name. Tests assert that the known
secret fixture and identifiers do not appear in serialized SARIF.

## GitHub Code Scanning demonstration

The manual/push demonstration workflow at `.github/workflows/sarif-demo.yml`:

1. installs the released project shape;
2. analyzes the deliberately risky fixture and verifies exit code `1`;
3. uploads `reports/tracecheck.sarif` with `github/codeql-action/upload-sarif@v4`; and
4. uses the `genai-tracecheck-demo` category to keep the analysis identity stable.

The workflow grants only `contents: read` and `security-events: write`. GitHub documents that SARIF
uploads require the latter permission and supports the SARIF 2.1.0 subset used here. The deliberately
risky fixture creates demonstration alerts in its own fixture file; it does not imply repository
source-code vulnerabilities.

## Limits

- A SARIF result points to the span record, not the exact nested JSON attribute value, so no captured
  content needs to be parsed into a source-code location.
- Load errors affect the run metadata and process exit code but do not become invented lint rules.
- Fingerprints identify a finding in one exported telemetry event. New runtime trace/span IDs create
  a new alert identity by design.
- TraceCheck is a telemetry quality/privacy linter, not a general static application security tool.
