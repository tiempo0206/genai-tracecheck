# GenAI TraceCheck

[![CI](https://github.com/tiempo0206/genai-tracecheck/actions/workflows/ci.yml/badge.svg)](https://github.com/tiempo0206/genai-tracecheck/actions/workflows/ci.yml)

GenAI TraceCheck is an offline, deterministic linter for OpenTelemetry GenAI traces. It reads
canonical OTLP/HTTP JSON and reports malformed spans, incomplete GenAI semantic attributes, and
captured content that deserves a privacy review.

The project is intentionally framework-neutral: a trace may originate from an OpenAI client,
LangChain, LlamaIndex, or another instrumented application. No trace data leaves your machine.

> [!IMPORTANT]
> This is an independent quality tool, not an official OpenTelemetry conformance certificate.
> `GTC1xx` rules follow published GenAI semantic-convention attributes; `GTC2xx` rules are explicit
> local policy and heuristic checks.

## Why this exists

GenAI telemetry can be syntactically valid while still being hard to analyze or unsafe to retain.
For example, a span can omit its operation name, report negative token counts, or contain a live API
key inside a captured prompt. TraceCheck makes these problems visible before trace artifacts enter a
benchmark, incident report, or shared observability backend.

## Quick start

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"

genai-tracecheck check examples/valid.otlp.json
genai-tracecheck check examples/risky.otlp.json --output reports/risky.json

# Recursively analyze a directory and a quoted glob as one deterministic batch.
genai-tracecheck batch traces/current 'traces/archive/**/*.json' \
  --output reports/batch.json

# Emit content-safe SARIF for code scanning integrations.
genai-tracecheck check examples/risky.otlp.json \
  --format sarif --output reports/risky.sarif
```

The command returns exit code `0` when the configured quality gate passes, `1` when findings reach
the failure threshold, and `2` for invalid input or CLI errors. This makes it directly usable in CI.

Two frozen fixtures are generated through real OpenAI and LangChain instrumentation with local
mock/fake backends. Analyze them together with:

```bash
genai-tracecheck batch 'examples/framework/*.otlp.json'
```

The generator, exact dependency versions, sanitization steps, and observed semantic differences are
documented in [`docs/framework-fixtures.md`](docs/framework-fixtures.md).

All ten committed fixtures are also summarized in a versioned, machine-readable compatibility
matrix. It separates required violations from recommended or opt-in absences, deprecations, local
privacy policy, and intentional negative tests. See
[`docs/compatibility-matrix.md`](docs/compatibility-matrix.md).

SARIF 2.1.0 output provides stable fingerprints and repository-relative locations without copying
captured trace content or identifiers. See [`docs/sarif.md`](docs/sarif.md).

The reproducible performance harness generates fixed-seed 1K, 10K, and 100K fixtures, measures load,
analysis, and end-to-end throughput plus peak Python allocations, and retains a 100K cumulative
profile. The committed arm64 run processed 100K spans end to end in a 1.678-second median (59.6K
spans/s); treat that as one-machine evidence, not a universal guarantee. See
[`docs/performance.md`](docs/performance.md).

Useful policy controls:

```bash
# Treat warnings as failures.
genai-tracecheck check trace.json --fail-on warning

# Reject any captured prompt, response, instruction, tool, or retrieval content.
genai-tracecheck check trace.json --content-policy forbid

# Inspect a trusted synthetic fixture without secret-pattern heuristics.
genai-tracecheck check trace.json --content-policy allow --no-secret-detection

# Require every non-root span to have its parent in this export.
genai-tracecheck check trace.json --trace-completeness complete

# Reuse a reviewed policy across local runs and CI.
genai-tracecheck check trace.json --config examples/policy.toml
```

TOML configuration can set the same policy controls, disable individual rules, and override rule
severity. Precedence is deterministic: built-in defaults, then the configuration file, then policy
flags explicitly supplied on the command line. Configuration is never discovered implicitly. See
[`docs/configuration.md`](docs/configuration.md) for the version `1.0` contract.

## Rule set

| Rule | Type | Default severity | What it checks |
| --- | --- | --- | --- |
| `GTC001` | OTLP structure | error | Trace and span identifiers are valid, non-zero hex IDs |
| `GTC002` | OTLP structure | error | Timestamps exist and the span does not end before it starts |
| `GTC003` | Trace graph | error | A span ID is unique within its trace |
| `GTC004` | Trace graph | error | Parent relationships do not contain a cycle |
| `GTC005` | Trace graph | warning | A child lifetime is contained by its parent lifetime |
| `GTC006` | Trace graph policy | error | Complete exports contain every referenced parent span |
| `GTC101` | GenAI semantics | error | `gen_ai.operation.name` is present |
| `GTC102` | GenAI semantics | warning | `gen_ai.provider.name` is present when available |
| `GTC103` | GenAI semantics | warning | A request or response model is recorded when available |
| `GTC104` | GenAI semantics | error | Token usage values are non-negative integers |
| `GTC105` | GenAI content schema | error | Messages, instructions, and known part types have valid structure |
| `GTC106` | GenAI content schema | warning | Output messages do not use deprecated `finish_reason` |
| `GTC107` | GenAI latency | error | Time to first chunk is finite, non-negative, and inside span duration |
| `GTC108` | GenAI token usage | error | Token breakdown subsets do not exceed their aggregate totals |
| `GTC109` | GenAI token usage | warning | `execute_tool` spans do not report token usage |
| `GTC201` | Local privacy policy | warning/error | Captured GenAI content is surfaced for review or forbidden |
| `GTC202` | Local privacy heuristic | error | Secret-shaped values do not appear in captured content |

Secret findings never copy the matched value into the report. Pattern detection is defense in depth,
not proof that data is safe; false positives and false negatives are possible.

## Input and output

Input is an OTLP JSON `ExportTraceServiceRequest` containing `resourceSpans`, `scopeSpans`, and
`spans`. Attribute `AnyValue` objects are decoded recursively, including arrays and key-value lists.

Output is a versioned JSON document with a summary and stable, sortable findings:

```json
{
  "report_type": "single",
  "schema_version": "1.0",
  "passed": false,
  "fail_on": "error",
  "content_policy": "review",
  "detect_secret_values": true,
  "trace_completeness": "partial",
  "disabled_rules": [],
  "severity_overrides": {},
  "summary": {
    "spans": 1,
    "genai_spans": 1,
    "errors": 5,
    "warnings": 3
  },
  "traces": [
    {
      "trace_id": "11111111111111111111111111111111",
      "spans": 1,
      "genai_spans": 1,
      "start_time_unix_nano": null,
      "end_time_unix_nano": null,
      "trace_duration_ms": null,
      "model_calls": 0,
      "model_call_duration_ms": 0.0,
      "tool_calls": 0,
      "tool_call_duration_ms": 0.0,
      "tokenized_spans": 0,
      "observed_input_tokens": 0,
      "observed_output_tokens": 0,
      "observed_total_tokens": 0
    }
  ],
  "findings": []
}
```

The `batch` command accepts one or more files, directories, and quoted glob patterns. Directories
are searched recursively for `.json` files; hidden entries and symlinked directories are skipped.
Resolved files are canonicalized, deduplicated, and sorted, so the same inputs produce the same
file order on repeated CI runs. A batch document uses `"report_type": "batch"` and contains both an
aggregate `summary` and a `files` array with independent summaries, traces, findings, and controlled
load errors. Quote glob patterns so TraceCheck—not the shell—expands them consistently. See
[`docs/batch-analysis.md`](docs/batch-analysis.md) for the exact contract.

## Architecture

```text
OTLP JSON -> strict loader -> normalized spans -> rules + trace graph -> metrics -> report
                                      |                  |              |
                               OTel semantics       privacy policy   latency/tokens
```

The parser, data contracts, content-schema validator, rules, and command-line boundary are separate
modules. This keeps future framework adapters outside the rule engine and makes every finding
independently testable. See
[`docs/architecture.md`](docs/architecture.md) for design details.

Schema failures report paths such as `$[1].parts[0].name`, never the captured value. Known official
part types—including text, reasoning, tool calls, tool responses, blobs, files, URIs, and server-side
tools—receive type-specific checks. Unknown part types remain valid extension points.

Trace graph checks are scoped by `trace_id`. Missing parents are ignored in the default `partial`
mode because collectors commonly export only part of a trace. Use `--trace-completeness complete`
when the input is expected to contain the full graph.

Each report also includes per-trace wall-clock duration, summed model/tool-call durations, and
observed input/output token totals. See [`docs/metrics.md`](docs/metrics.md) for exact definitions and
the important overlap and double-counting limitations.

## Standards baseline

The first release follows the current OpenTelemetry GenAI attribute registry and span guidance,
including the newer structured `gen_ai.input.messages`, `gen_ai.output.messages`, and
`gen_ai.system_instructions` model. The implementation is based on these upstream sources:

- [OpenTelemetry GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai)
- [GenAI span conventions](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md)
- [GenAI attribute registry](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/registry/attributes/gen-ai.md)

Semantic conventions evolve. Each rule should cite its upstream basis in tests or documentation,
and project releases will record the standards snapshot they target.

## Project status

Version `0.2.0` is a tested vertical slice: canonical OTLP JSON in, deterministic single-file or
batch reports out, with reusable policy configuration and auditable CI behavior. Framework-generated
fixtures now cover OpenAI and LangChain instrumentation, and the benchmark characterizes the pipeline
through 100K spans with one profile-backed optimization. The two-week plan continues with contributor
experience and an upstream-ready research note. See
[`docs/roadmap.md`](docs/roadmap.md) and [`docs/project-log.md`](docs/project-log.md).

## Development

```bash
ruff format .
ruff check .
pytest
```

Contributions should include a minimal OTLP fixture and tests for every new rule. See
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

MIT
