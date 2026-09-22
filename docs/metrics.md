# Trace metrics contract

TraceCheck derives one `TraceMetrics` object per trace and writes the objects in stable `trace_id`
order. Metrics are diagnostic summaries of the supplied export, not billing records or server-side
service-level metrics.

## Latency fields

All report durations use milliseconds.

- `trace_duration_ms` is the difference between the earliest valid start and latest valid end in the
  trace. Spans with missing or reversed timestamps are excluded and separately reported by `GTC002`.
- `model_call_duration_ms` is the sum of valid durations for known model operations: `chat`,
  `generate_content`, `text_completion`, and `embeddings`.
- `tool_call_duration_ms` is the sum of valid `execute_tool` span durations.

Summed call duration may exceed trace wall-clock duration when calls overlap. This is expected and is
why the report does not label these fields as exclusive time.

`GTC107` validates `gen_ai.response.time_to_first_chunk`. It must be a finite, non-negative number of
seconds and cannot exceed its containing span duration.

## Token fields

- `observed_input_tokens` sums valid `gen_ai.usage.input_tokens` values in the supplied trace.
- `observed_output_tokens` sums valid `gen_ai.usage.output_tokens` values.
- `observed_total_tokens` is the sum of those two observed totals.
- `tokenized_spans` counts spans with at least one valid input or output total.

The word **observed** is intentional. Duplicate instrumentation or nested spans can describe the same
provider call more than once, and partial exports can omit calls. TraceCheck does not claim these
numbers equal a provider invoice.

## Consistency relationships

Current OpenTelemetry guidance defines detailed usage values as subsets of aggregate totals.
`GTC108` therefore checks only impossible `subset > aggregate` relationships:

- text + image + audio input must not exceed total input;
- text + image + audio output must not exceed total output;
- cache-read and cache-write input must not exceed total input;
- reasoning output must not exceed total output;
- modality cache-read totals must fit inside aggregate cache-read and their modality input totals.

The checker deliberately does not require equality. Providers can expose only part of a breakdown,
so a known component sum smaller than the aggregate is valid.

OpenTelemetry guidance says `execute_tool` spans should not report token usage. TraceCheck reports
this as the `GTC109` warning rather than discarding the observed value.

## Invalid and missing values

Negative, Boolean, floating-point, or string token values fail `GTC104` and are excluded from
metrics. Missing totals are not inferred from partial breakdowns. This keeps report arithmetic
deterministic and avoids silently changing provider data.
