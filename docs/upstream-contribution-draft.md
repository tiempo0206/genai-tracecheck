# Upstream contribution draft: OpenAI default HTTPS port

> [!CAUTION]
> This is an internal research artifact. It has **not** been posted upstream. The owner must inspect
> the reproduction, rewrite the public message in their own words, and choose whether to ask in the
> GenAI SIG or open an issue. The upstream repository explicitly prohibits AI-generated issue and
> pull-request comments.

## Why this is the right upstream target

The maintained GenAI instrumentation packages moved out of
`open-telemetry/opentelemetry-python-contrib` into
[`open-telemetry/opentelemetry-python-genai`](https://github.com/open-telemetry/opentelemetry-python-genai).
Day 13 therefore checked the new repository rather than preparing a patch against the former
location.

Research was performed on 2026-09-26 against these immutable revisions:

| Evidence | Pinned value |
| --- | --- |
| Python GenAI repository | [`14c76fe`](https://github.com/open-telemetry/opentelemetry-python-genai/tree/14c76fee1a5270d194bfada07f711352a2d3aa4d) |
| OpenAI instrumentation version at that revision | `1.2b0` |
| GenAI semantic conventions | [`e57c543`](https://github.com/open-telemetry/semantic-conventions-genai/tree/e57c543b4889619eb2a05702471937db5119165d) |
| TraceCheck OpenAI fixture instrumentation | `1.1b0` |
| Fixture SHA-256 | `a7975404962e7aa0b06c5b28bb91c64773fb10062bb37a04452ea65530daa00f` |

The machine-readable snapshot is
[`upstream/openai-default-port-evidence.json`](../upstream/openai-default-port-evidence.json).

## Reproducible observation

TraceCheck's frozen OpenAI fixture is generated through the official OpenAI instrumentation and an
`httpx.MockTransport`, so it performs no provider network request. Its base URL is
`https://openai.fixture.invalid/v1`, which implies port 443. The resulting span contains
`server.address` but not `server.port`.

This is not only a historical `1.1b0` fixture behavior. At the pinned current upstream revision:

- [`get_server_address_and_port`](https://github.com/open-telemetry/opentelemetry-python-genai/blob/14c76fee1a5270d194bfada07f711352a2d3aa4d/instrumentation/opentelemetry-instrumentation-genai-openai/src/opentelemetry/instrumentation/genai/openai/utils.py#L71-L91)
  obtains the parsed port and deliberately converts 443 to `None`;
- [the corresponding test](https://github.com/open-telemetry/opentelemetry-python-genai/blob/14c76fee1a5270d194bfada07f711352a2d3aa4d/instrumentation/opentelemetry-instrumentation-genai-openai/tests/test_utils.py#L389-L438)
  checks `server.port` only when the value is positive and not 443; and
- [the pinned GenAI span model](https://github.com/open-telemetry/semantic-conventions-genai/blob/e57c543b4889619eb2a05702471937db5119165d/model/gen-ai/spans.yaml#L27-L36)
  says `server.port` is conditionally required when `server.address` is set, without stating a
  default-port exception.

The OpenAI package changelog notes a prior fix for recording server address and port with OpenAI v3,
but the current source still deliberately elides 443. This evidence establishes a narrow,
reproducible specification/implementation mismatch candidate. It does **not** establish that the
implementation is definitively wrong: the GenAI convention is still at development stability, and
other protocol conventions sometimes omit default ports.

## Duplicate search

The following GitHub issue searches found no matching report on 2026-09-26:

- [`is:issue "server.port" OpenAI`](https://github.com/open-telemetry/opentelemetry-python-genai/issues?q=is%3Aissue+%22server.port%22+OpenAI)
- [`is:issue OpenAI default port 443`](https://github.com/open-telemetry/opentelemetry-python-genai/issues?q=is%3Aissue+OpenAI+default+port+443)

Search results change over time. The owner should repeat both searches immediately before posting.

## Human-ready discussion draft

The text below follows the upstream bug form and stays below the repository's requested 200-word PR
description limit. It is a factual starting point, not text to paste unchanged.

**Title:** OpenAI instrumentation omits `server.port=443` when `server.address` is emitted

**Environment:** `opentelemetry-instrumentation-genai-openai` 1.1b0 reproduces this in a local
`httpx.MockTransport` scenario on Python 3.11. Current main at `14c76fe` appears to retain the same
behavior in `get_server_address_and_port`.

**What happened:** An OpenAI client with an implicit HTTPS base URL emits `server.address` but omits
`server.port`. Current source explicitly maps parsed port 443 to `None`, and its test skips the port
assertion for 443.

**Steps:** Configure the instrumented client with `https://example.invalid/v1`, use a local mock
transport, perform one chat completion, and inspect the exported client span.

**Expected:** The current GenAI span model says `server.port` is conditionally required when
`server.address` is set, so I expected `server.port=443`.

**Actual:** `server.address` is present and `server.port` is absent.

**Question:** Should the instrumentation emit 443 to follow the current GenAI model, or should the
semantic convention document a default-port exception? I am happy to prepare a small change after
the intended behavior is confirmed.

## Proposed patch after maintainer direction

If maintainers confirm that 443 should be emitted, keep the change narrow:

1. Remove the special conversion from 443 to `None`.
2. Add focused tests for implicit HTTPS 443, explicit 443, and a non-default port.
3. Add the required Towncrier fragment; do not edit the changelog directly.
4. Run `uv sync --frozen --all-packages`, `uv run tox -e precommit`, `uv run tox -e typecheck`, and
   the OpenAI latest/oldest/conformance test environments named by upstream.

If maintainers instead confirm that default ports should be omitted, the appropriate contribution
belongs in semantic-convention wording and/or an explicit instrumentation test comment—not a
behavior change in isolation.

## Owner review checklist

- [ ] Re-run the reproduction against the latest upstream revision.
- [ ] Re-run the duplicate searches and read any newly related issue.
- [ ] Read the latest upstream `AGENTS.md` and `CONTRIBUTING.md`.
- [ ] Remove any fixture-specific detail that is not needed publicly.
- [ ] Rewrite the question in your own words; do not post AI-generated discussion text.
- [ ] Prefer the `#otel-genai-instrumentation` channel if the intent is still ambiguous.
- [ ] Wait for maintainer direction before implementing a broad semantic change.
