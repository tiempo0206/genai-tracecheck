# Python API

The command-line interface is the primary CI boundary, but the package also exposes a small typed
API for adapters, notebooks, and local automation. Names listed in `genai_tracecheck.__all__` are the
intentional public surface; other modules and underscored names are implementation details.

Version `1.x` treats the explicit `genai_tracecheck.__all__` surface and report schema version `1.0`
as compatibility commitments. An incompatible public API or report change requires a new major
version; additive changes still require documentation and regression tests. The installed package
includes `py.typed` so type checkers can consume its inline annotations.

## Analyze one export

```python
from genai_tracecheck import (
    ContentPolicy,
    FailureThreshold,
    Policy,
    analyze_spans,
    load_otlp_json,
)

spans = load_otlp_json("trace.otlp.json")
policy = Policy(
    fail_on=FailureThreshold.WARNING,
    content_policy=ContentPolicy.FORBID,
)
report = analyze_spans(spans, source="trace.otlp.json", policy=policy)

if not report.passed:
    for finding in report.findings:
        print(finding.rule_id, finding.severity, finding.attribute)
```

`load_otlp_json` raises `TraceLoadError` for unsafe or malformed input. `analyze_spans` does not read
the `source` path; it retains that display identity in output and uses the supplied normalized spans.
The input list is not mutated.

## Analyze a deterministic batch

```python
from genai_tracecheck import analyze_batch, resolve_input_paths

paths = resolve_input_paths(["traces/current", "traces/archive/**/*.json"])
report = analyze_batch(paths)

print(report.summary.files, report.summary.load_errors, report.passed)
```

Quote globs at the shell boundary when using the CLI. In Python, pass the pattern directly as shown.
Every requested input must resolve; `InputResolutionError` signals an empty or unmatched request.
After discovery, an individual malformed file becomes a `load_error` result instead of aborting the
rest of the batch.

## Load a policy and create SARIF

```python
import json
from pathlib import Path

from genai_tracecheck import analyze_spans, load_otlp_json, load_policy_config, report_to_sarif

policy = load_policy_config("tracecheck.toml")
report = analyze_spans(
    load_otlp_json("trace.otlp.json"),
    source="trace.otlp.json",
    policy=policy,
)
sarif = report_to_sarif(report, working_directory=Path.cwd())
Path("tracecheck.sarif").write_text(json.dumps(sarif, indent=2) + "\n", encoding="utf-8")
```

Configuration is never discovered implicitly. `ConfigurationError` reports invalid TOML, unknown
keys, unknown rule IDs, and contradictory settings. SARIF conversion preserves the report's gate
decision and omits raw trace IDs, span IDs, and captured values.

## Public contracts

- Inputs: `SpanRecord`, `Policy`, `ContentPolicy`, `FailureThreshold`, and `TraceCompleteness`.
- Findings: `Finding` and `Severity`.
- Outputs: `AnalysisReport`, `BatchReport`, and `TraceMetrics`.
- Controlled errors: `TraceLoadError`, `InputResolutionError`, and `ConfigurationError`.
- Operations: `load_otlp_json`, `resolve_input_paths`, `load_policy_config`, `analyze_spans`,
  `analyze_batch`, and `report_to_sarif`.

Pydantic models are frozen and reject undeclared fields. Call `model_dump(mode="json")` when a plain
JSON-compatible object is needed. Findings are stable and sortable, but downstream code should key
on `rule_id`, `severity`, and documented fields rather than parsing human-readable messages.

## Safety boundary

Trace data is untrusted and can contain sensitive content. Do not log complete `SpanRecord`
attributes or build diagnostics from captured values. Public findings intentionally expose the
affected attribute and safe structural metadata without copying matched content.
