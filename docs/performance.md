# Reproducible performance benchmark

This benchmark measures the current in-memory OTLP/HTTP JSON pipeline at 1K, 10K, and 100K spans.
It is an engineering characterization, not a cross-project leaderboard or a universal latency
guarantee.

## Reproduce it

From an editable development installation, run:

```bash
python -m benchmarks.run
```

The command streams temporary fixtures to a system temporary directory, validates every fixture
before measuring it, and writes:

- [`benchmarks/results.json`](../benchmarks/results.json): environment, fixture digests, timings,
  throughput, and phase-local peak Python allocations;
- [`benchmarks/profile-100k.txt`](../benchmarks/profile-100k.txt): the optimized 100K end-to-end
  cumulative profile;
- [`benchmarks/profile-baseline-100k.txt`](../benchmarks/profile-baseline-100k.txt): the profile that
  justified the Day 11 token-validation optimization.

Use a smaller smoke run while changing the harness:

```bash
python -m benchmarks.run --sizes 100 --repeats 1 --warmups 0 --no-profile \
  --output /tmp/tracecheck-benchmark-smoke.json
```

CI runs that smoke command on Python 3.11 and 3.12. It deliberately does not assert a time limit:
shared runners are suitable for contract checks, not stable performance regression thresholds.

## Fixture contract

Generator version `1.0` uses seed `20260926`. Each case contains valid `chat` spans with provider,
model, input-token, output-token, timestamp, and graph data. A trace contains at most 100 spans: one
root and up to 99 children whose lifetimes are contained by the root. Therefore the 1K, 10K, and
100K cases contain 10, 100, and 1,000 complete traces respectively.

Generation is excluded from analyzer timing. Files are streamed instead of building a second large
Python object graph, and each file's SHA-256 digest is recorded. Preflight requires the requested
span count, zero findings, and a passing report before measurement begins.

## Method

- One warm-up is run for each phase and size.
- Three untraced samples use
  [`time.perf_counter_ns()`](https://docs.python.org/3.12/library/time.html#time.perf_counter_ns); the
  median is reported, with minimum and maximum retained in JSON.
- Peak memory is measured in a separate invocation with
  [`tracemalloc.get_traced_memory()`](https://docs.python.org/3.12/library/tracemalloc.html#tracemalloc.get_traced_memory).
- The 100K end-to-end path is profiled with the recommended deterministic `cProfile` implementation
  and sorted by cumulative time through `pstats` ([Python profiler documentation](https://docs.python.org/3.12/library/profile.html)).
- `load` parses JSON and creates strict `SpanRecord` objects. `analyze` starts with those records
  already resident. `end_to_end` performs both operations.

The committed run used CPython 3.13.9 on macOS 15.6.1, arm64, with 10 logical CPUs. Exact environment
metadata is part of the result document.

## Results

Times and throughput are medians. Peak MiB is the maximum Python-managed allocation attributed to
that phase, not whole-process resident memory.

| Spans | Fixture MiB | Phase | Time (s) | Spans/s | Peak MiB |
| ---: | ---: | --- | ---: | ---: | ---: |
| 1,000 | 0.58 | load | 0.005233 | 191,095 | 4.84 |
| 1,000 | 0.58 | analyze | 0.004742 | 210,881 | 0.04 |
| 1,000 | 0.58 | end-to-end | 0.009846 | 101,564 | 4.84 |
| 10,000 | 5.85 | load | 0.084380 | 118,512 | 48.37 |
| 10,000 | 5.85 | analyze | 0.050001 | 199,996 | 0.24 |
| 10,000 | 5.85 | end-to-end | 0.124605 | 80,254 | 48.37 |
| 100,000 | 58.46 | load | 1.182369 | 84,576 | 483.60 |
| 100,000 | 58.46 | analyze | 0.495828 | 201,683 | 2.29 |
| 100,000 | 58.46 | end-to-end | 1.677553 | 59,611 | 483.60 |

Analysis throughput stays close to 200K spans/s from 10K through 100K. Loading becomes the dominant
100K cost and its Python allocation peak grows with file size. The current loader intentionally uses
the standard library's full-document `json.loads`; a streaming reader is a future architectural
option, not a change justified solely by this one-machine run.

## Profile-backed optimization

The baseline 100K profile showed 1.157 seconds of cumulative time in token consistency checks and
1.8 million calls to `_valid_token`, even though the fixture contains only 200,000 token attributes.
Nine subset relationships were repeatedly validating the same values.

Day 11 changed `semantic_findings` to validate each token attribute once per span and pass the valid
counts to every subset check. Existing boundary tests continued to cover invalid Booleans, negative
values, exact limits, and tool spans.

| 100K measurement | Baseline | Optimized | Change |
| --- | ---: | ---: | ---: |
| Unprofiled analysis median | 0.621148 s | 0.495828 s | -20.2% |
| Unprofiled end-to-end median | 1.874377 s | 1.677553 s | -10.5% |
| Profiled token-check cumulative time | 1.157 s | 0.298 s | -74.2% |
| Profiled function calls | 22,926,119 | 16,026,119 | -30.1% |

The optimized profile leaves JSON loading, strict model construction, and the remaining rule work as
the main costs. No further core changes were made: replacing strict models or adding a streaming JSON
dependency would change product tradeoffs and needs broader workload evidence.

## Interpretation limits

- The result describes one machine, interpreter, fixture shape, and otherwise idle local run.
- `tracemalloc` observes Python-managed allocation blocks; it is not an operating-system RSS meter.
- The analysis peak excludes the already loaded input records by design. End-to-end peak includes the
  newly loaded raw JSON tree and normalized records.
- Synthetic spans contain no captured message bodies or secret scanning work, so content-heavy traces
  can have different costs.
- Throughput is not a CI service-level objective. Compare changes on the same machine and environment,
  keep the fixture digests constant, and examine the retained sample range before drawing conclusions.
