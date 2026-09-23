# Version 0.2.0 release-candidate review

Date: 2026-09-23

## Result

The release candidate satisfies the Day 7 gate. Version `0.2.0` can be tagged after its review
commit is merged to `main`.

| Gate | Required | Result |
| --- | --- | --- |
| Ruff lint and formatting | pass | pass |
| Unit and CLI tests | pass | 105 passed |
| Combined statement/branch coverage | at least 95% | 98% |
| Supported Python CI | 3.11 and 3.12 | pass |
| Positive/negative CLI smoke tests | pass | pass |
| sdist and wheel build | pass | pass |
| Clean wheel installation and version command | pass | pass |
| Input/output overwrite protection | single and batch | pass |

## Mutation-oriented review

The review used small hypothetical code mutations to identify tests that should fail if important
logic is accidentally inverted or removed:

| Mutation hypothesis | Killing assertion |
| --- | --- |
| Change a strict `>` token-subset check to `>=` | Exact-boundary token test remains valid |
| Accept Boolean token or latency values as numbers | Boolean boundary tests emit `GTC104`/`GTC107` |
| Stop requiring known content-part fields | Per-part path tests reject mutated blob/file/server parts |
| Ignore malformed OTLP nesting | Loader tests reject each resource/scope/span boundary |
| Count a batch as passed when any file passes | Mixed batch test requires one failed file and exit `1` |
| Ignore a disabled rule | `GTC201` disablement test requires no finding or warning count |
| Apply severity after pass/fail evaluation | Promoted `GTC201` must fail the default error gate |
| Let CLI defaults erase TOML values | Field-wise precedence test preserves unrelated file settings |
| Permit `--force` to overwrite an input | Single and batch alias tests require exit `2` and unchanged input |
| Leave a temporary report after atomic replace failure | Cleanup test requires an empty output directory |

These are mutation-oriented tests, not a claimed mutation-score benchmark. A dedicated mutation
runner can be added later if its runtime and maintenance cost are justified.

## Coverage analysis

Coverage uses Coverage.py with branch measurement enabled for `genai_tracecheck`. CI runs:

```bash
coverage run -m pytest
coverage report
```

The configured `fail_under = 95` turns regression in aggregate coverage into a CI failure. The
remaining uncovered branches are defensive race/error paths or narrow structural guards; they are
listed by `coverage report` and are not excluded from measurement.

## Release scope

This is an alpha-quality portfolio release, not the final two-week `v1.0.0` target. It establishes a
tested core, deterministic batch workflow, and reusable configuration contract. Framework-derived
fixtures, SARIF, compatibility evidence, and benchmarks remain Week 2 work.
