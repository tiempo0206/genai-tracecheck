# Configuration contract

TraceCheck accepts an explicit, versioned TOML policy file on both `check` and `batch`:

```bash
genai-tracecheck check trace.json --config tracecheck.toml
genai-tracecheck batch traces/ --config tracecheck.toml
```

There is no automatic configuration discovery. This keeps a run independent of the caller's
working directory and prevents an unrelated parent-directory file from changing CI behavior.

## Version 1.0

Every file must declare its contract version as a string:

```toml
schema_version = "1.0"

[policy]
fail_on = "error"
content_policy = "review"
detect_secret_values = true
trace_completeness = "partial"

[rules.GTC102]
enabled = false

[rules.GTC005]
severity = "error"
```

The `[policy]` table is optional. Omitted values retain their built-in defaults:

| Key | Accepted values | Built-in default |
| --- | --- | --- |
| `fail_on` | `warning`, `error`, `never` | `error` |
| `content_policy` | `allow`, `review`, `forbid` | `review` |
| `detect_secret_values` | TOML Boolean | `true` |
| `trace_completeness` | `partial`, `complete` | `partial` |

Each `[rules.GTCxxx]` table must set `enabled`, `severity`, or both. `severity` accepts `warning` or
`error`. A disabled rule cannot also have a severity override because the combination has no clear
effect. Unknown rule IDs, keys, sections, values, and schema versions are rejected rather than
ignored. The supported IDs are the rules listed in the README.

Disabling a rule removes its findings before summary counts and quality-gate evaluation. A severity
override changes the finding, summary counts, sorting, and exit status consistently. Active rule
settings are included in single and batch JSON reports as `disabled_rules` and
`severity_overrides`.

## Precedence

Effective policy is assembled in this order, with later sources winning:

1. built-in defaults;
2. values in the explicit TOML file;
3. policy flags explicitly provided on the command line.

For example, this uses `warning` from the file:

```bash
genai-tracecheck check trace.json --config tracecheck.toml
```

This changes only the failure threshold to `error` while preserving all other file settings:

```bash
genai-tracecheck check trace.json --config tracecheck.toml --fail-on error
```

Secret detection has symmetric command-line flags, so either file value can be overridden:

```bash
genai-tracecheck check trace.json --config tracecheck.toml --secret-detection
genai-tracecheck check trace.json --config tracecheck.toml --no-secret-detection
```

Rule enablement and severity are deliberately configured only in TOML so a reviewed rule policy is
not hidden inside a long CI command.

## Safety notes

Disabling structural, schema, or privacy rules weakens the quality gate. In particular, disabling
`GTC202` suppresses reports of secret-shaped captured content. Keep exceptions narrow, document why
they exist, and commit the policy file so changes receive code review.
