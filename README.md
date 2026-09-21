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
```

The command returns exit code `0` when the configured quality gate passes, `1` when findings reach
the failure threshold, and `2` for invalid input or CLI errors. This makes it directly usable in CI.

Useful policy controls:

```bash
# Treat warnings as failures.
genai-tracecheck check trace.json --fail-on warning

# Reject any captured prompt, response, instruction, tool, or retrieval content.
genai-tracecheck check trace.json --content-policy forbid

# Inspect a trusted synthetic fixture without secret-pattern heuristics.
genai-tracecheck check trace.json --content-policy allow --no-secret-detection
```

## Initial rule set

| Rule | Type | Default severity | What it checks |
| --- | --- | --- | --- |
| `GTC001` | OTLP structure | error | Trace and span identifiers are valid, non-zero hex IDs |
| `GTC002` | OTLP structure | error | Timestamps exist and the span does not end before it starts |
| `GTC101` | GenAI semantics | error | `gen_ai.operation.name` is present |
| `GTC102` | GenAI semantics | warning | `gen_ai.provider.name` is present when available |
| `GTC103` | GenAI semantics | warning | A request or response model is recorded when available |
| `GTC104` | GenAI semantics | error | Token usage values are non-negative integers |
| `GTC105` | GenAI content schema | error | Messages, instructions, and known part types have valid structure |
| `GTC106` | GenAI content schema | warning | Output messages do not use deprecated `finish_reason` |
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
  "schema_version": "1.0",
  "passed": false,
  "fail_on": "error",
  "summary": {
    "spans": 1,
    "genai_spans": 1,
    "errors": 5,
    "warnings": 3
  },
  "findings": []
}
```

## Architecture

```text
OTLP JSON -> strict loader -> normalized spans -> rule families -> versioned report -> CI exit code
                                      |               |
                               OTel semantics    local privacy policy
```

The parser, data contracts, content-schema validator, rules, and command-line boundary are separate
modules. This keeps future framework adapters outside the rule engine and makes every finding
independently testable. See
[`docs/architecture.md`](docs/architecture.md) for design details.

Schema failures report paths such as `$[1].parts[0].name`, never the captured value. Known official
part types—including text, reasoning, tool calls, tool responses, blobs, files, URIs, and server-side
tools—receive type-specific checks. Unknown part types remain valid extension points.

## Standards baseline

The first release follows the current OpenTelemetry GenAI attribute registry and span guidance,
including the newer structured `gen_ai.input.messages`, `gen_ai.output.messages`, and
`gen_ai.system_instructions` model. The implementation is based on these upstream sources:

- [OpenTelemetry GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai)
- [GenAI span conventions](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md)
- [GenAI attribute registry](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/gen-ai.md)

Semantic conventions evolve. Each rule should cite its upstream basis in tests or documentation,
and project releases will record the standards snapshot they target.

## Project status

Version `0.1.0` is a tested vertical slice: canonical OTLP JSON in, machine-readable findings out,
with configurable CI behavior. The two-week plan adds multi-file analysis, trace-graph checks,
framework-generated fixtures, SARIF output, benchmarks, and an upstream-ready research note. See
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
