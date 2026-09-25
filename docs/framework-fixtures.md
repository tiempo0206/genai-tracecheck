# Framework-generated fixtures

The two fixtures in `examples/framework/` exercise the same synthetic chat scenario through two
real OpenTelemetry instrumentation packages. They provide inspectable evidence that TraceCheck can
consume telemetry produced outside this repository while keeping the experiment offline and
repeatable. Both packages come from the
[OpenTelemetry Python GenAI repository](https://github.com/open-telemetry/opentelemetry-python-genai)
and are beta releases, so the exact versions are part of the evidence.

## Sources and scenario

| Fixture | Instrumentation | Offline boundary |
| --- | --- | --- |
| `openai-chat.otlp.json` | `opentelemetry-instrumentation-genai-openai` | OpenAI SDK with an `httpx.MockTransport` response |
| `langchain-chat.otlp.json` | `opentelemetry-instrumentation-genai-langchain` | LangChain `FakeMessagesListChatModel` |

Both scenarios send the synthetic user message `What is two plus two?` and receive the synthetic
answer `The answer is four.` Content capture is enabled only for these invented strings. No real
provider credential is required, and fixture generation performs no model-provider network request.

`tools/framework-fixtures/requirements.txt` pins every direct generator dependency. The generated
`manifest.json` records the installed package versions, scenario descriptions, normalization steps,
and a SHA-256 digest for each fixture.

## Reproduce the fixtures

Use a separate environment so the relatively heavy framework dependencies do not become runtime or
development dependencies of TraceCheck:

```bash
python -m venv .fixture-venv
source .fixture-venv/bin/activate
python -m pip install -r tools/framework-fixtures/requirements.txt
python tools/framework-fixtures/generate.py
python tools/framework-fixtures/generate.py --check
```

The first command regenerates the artifacts. The `--check` run performs the same instrumented calls
in memory and exits non-zero if any committed fixture or manifest differs. Review the resulting diff
before updating a pinned package version.

Ordinary CI does not install the generator environment. Instead, lightweight tests validate the
manifest, fixture digests, credential absence, semantic expectations, and TraceCheck results. This
keeps the main package dependency-neutral while making intentional regeneration explicit.

## Sanitization and determinism

The generator exports finished OpenTelemetry SDK spans to canonical OTLP/HTTP JSON and then applies
only these deterministic transformations:

1. Replace runtime trace and span IDs with source-specific SHA-256-derived IDs.
2. Replace wall-clock timestamps with fixed 10 ms intervals.
3. Retain only the synthetic `service.name` resource attribute.
4. Sort scopes, spans, and attributes before rendering JSON.

Instrumentation-produced span names and GenAI attributes remain unchanged. Tests also reject the
placeholder SDK credential and common authorization markers if they ever reach a committed fixture.

## Observed semantic differences

These observations describe the pinned versions and synthetic scenario; they are not a quality
ranking and should not be generalized to every model or application.

| Signal | OpenAI fixture | LangChain fixture |
| --- | --- | --- |
| Operation | `chat` | `chat` |
| Provider | `openai` | `fixturechatmodel` |
| Request model | present | present |
| Response ID/model | present | absent |
| Input/output token totals | `9` / `5` | absent |
| Top-level response finish reasons | present | absent |
| Server address | synthetic mock host | absent |

Both fixtures include structured input and output messages and pass TraceCheck's default error
threshold. Both currently produce `GTC106` because their output-message payload contains the
deprecated nested `finish_reason`, plus `GTC201` because deliberately captured synthetic content
still requires an explicit privacy decision. The OpenAI fixture also provides the replacement
`gen_ai.response.finish_reasons` attribute.

Missing response metadata or token totals are not automatically instrumentation defects: the
LangChain fake model did not provide those values to its instrumentation. Day 9 uses this evidence
to build a machine-readable compatibility matrix that distinguishes required checks from optional
or unavailable signals.
