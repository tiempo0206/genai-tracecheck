# Compatibility matrix

The committed compatibility matrix is a reproducible evidence snapshot across every OTLP fixture in
the repository. It answers three separate questions without conflating them:

1. Does the fixture pass TraceCheck's default error gate?
2. Which GenAI signals were observed from each real instrumentation source?
3. Is an observation a required violation, a recommended/opt-in absence, a deprecation, a local
   policy finding, or an intentional negative test?

The machine-readable artifact is
[`compatibility/compatibility-matrix.json`](../compatibility/compatibility-matrix.json). It contains
metadata, counts, rule IDs, requirement levels, and attribute presence only. Captured prompt,
response, secret-shaped, trace-ID, and span-ID values are deliberately excluded.

## Standards snapshot

The matrix records OpenTelemetry GenAI semantic-convention revision
[`e57c543`](https://github.com/open-telemetry/semantic-conventions-genai/blob/e57c543b4889619eb2a05702471937db5119165d/model/gen-ai/spans.yaml),
retrieved on 2026-09-25. At that revision, the `gen_ai.inference.client` span is marked
`development` and uses these requirement levels:

| Signal | Requirement level used by the matrix |
| --- | --- |
| `gen_ai.operation.name` | required |
| `gen_ai.provider.name` | required |
| `gen_ai.request.model` | conditionally required if available |
| Response ID/model and finish reasons | recommended |
| Input/output token totals | recommended |
| `server.address` | recommended |
| `server.port` | conditionally required if `server.address` is set |
| Input/output messages | opt-in |

The framework fixtures remain pinned to instrumentation version `1.1b0`; recording a newer
standards revision does not imply those packages were built against that exact commit. The matrix
therefore reports observations and does not claim official conformance certification.

## Current result

All ten fixtures are analyzed with one default policy: fail on errors, review captured content,
enable secret detection, and allow partial exports.

| Fixture group | Files | Expected result | Actual result |
| --- | ---: | --- | --- |
| Synthetic positive | 4 | pass | 4 passed |
| Synthetic negative | 4 | fail | 4 failed as designed |
| Framework-generated | 2 | pass | 2 passed |

The snapshot covers 20 spans and 10 traces. All ten expected outcomes match. The synthetic negative
fixtures account for the deliberate structural and semantic errors; they are regression probes, not
evidence about an external exporter.

### Framework observation

| Observation | OpenAI `1.1b0` | LangChain `1.1b0` | Interpretation |
| --- | --- | --- | --- |
| Required operation/provider | present | present | no required absence |
| Request model | present | present | conditional signal observed |
| Response ID/model | present | not observed | recommended; source availability differs |
| Finish-reasons attribute | present | not observed | recommended |
| Input/output token totals | present | not observed | recommended and backend-dependent |
| Server address | present | not observed | recommended and not meaningful for an in-process fake model |
| Server port | not observed | not applicable | condition triggered only in the OpenAI fixture |
| Input/output messages | present | present | opt-in synthetic content capture |
| `GTC106` | observed | observed | deprecated nested `finish_reason`; migration evidence |
| `GTC201` | observed | observed | local privacy-review policy |

Neither framework fixture has a TraceCheck semantic error, and both contain the required operation
and provider attributes. The pinned standards revision also says `server.port` is conditionally
required when `server.address` is set. The OpenAI fixture has the address but not the port, so the
matrix records one `server.port` exporter-defect candidate. Day 13 confirmed that current upstream
source at `14c76fe` deliberately maps port 443 to `None`, while the pinned convention still
describes the port as conditionally required without a default-port exception. This remains a
clarification candidate rather than a confirmed defect because the convention is at `development`
stability and other protocol conventions sometimes omit default ports. See the
[`upstream contribution draft`](upstream-contribution-draft.md) for pinned evidence and the required
human-review boundary.

LangChain's fake model does not expose the same provider response metadata as the mocked OpenAI
response, so its six recommended absences are recorded as `recommended_not_observed`, not exporter
defects.

## Classification contract

- `candidate_required_violation`: a framework fixture violated a required or structural invariant.
  This is only a candidate until reproduced and checked against the instrumentation's supported
  scenario.
- `missing_conditionally_required`: a required condition was observed but its dependent attribute
  was absent; it enters the candidate list rather than becoming an automatic defect claim.
- `deprecated_shape`: a migration concern, kept separate from required-field failures.
- `recommended_not_observed`: absence of a recommended signal without proof that the source made
  the value available.
- `opt_in_not_observed`: a content signal may be disabled deliberately for privacy.
- `local_policy`: a TraceCheck policy decision, not an OpenTelemetry conformance claim.
- `intentional_negative_case`: a synthetic failure created to exercise a rule.

This vocabulary makes the matrix useful for upstream discussions without overclaiming that every
missing field is a library bug.

## Reproduce and inspect

After installing TraceCheck in editable mode:

```bash
python tools/compatibility-matrix/generate.py
python tools/compatibility-matrix/generate.py --check

jq '.summary' compatibility/compatibility-matrix.json
jq '.frameworks[] | {source, assessment, recommended_attributes_not_observed}' \
  compatibility/compatibility-matrix.json
```

The generator fails if an OTLP fixture is added or removed without updating its declared purpose and
expected gate. Each row includes the fixture SHA-256 digest, and CI regenerates the complete matrix
in check mode.

## Limits

- This is an independent compatibility snapshot, not OpenTelemetry's Weaver conformance suite.
- Each framework currently has one non-streaming chat scenario with synthetic content.
- The matrix does not yet cover embeddings, tools, agents, streaming, metrics, or events.
- Recommended absence cannot establish whether the provider, framework, or instrumentation omitted
  a value.
- The upstream GenAI span convention is still marked `development`, so later snapshots may change
  requirement levels or names.
