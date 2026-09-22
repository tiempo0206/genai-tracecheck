# Batch analysis contract

The `batch` command analyzes multiple OTLP JSON exports without losing each file's identity:

```bash
genai-tracecheck batch trace.json traces/current 'traces/archive/**/*.json'
genai-tracecheck batch traces/current --output reports/batch.json
```

## Input resolution

Each positional input must resolve to at least one regular file:

- An explicit file is accepted as supplied; its content is validated by the OTLP loader.
- A directory is searched recursively for case-insensitive `.json` suffixes.
- A glob is expanded in-process. Quote it to prevent shell-specific expansion.
- Hidden files and directories are skipped during discovery.
- Directory symlinks are not followed.
- Canonical paths deduplicate overlapping files, directories, globs, and symlinks.
- The final canonical paths are sorted lexicographically before analysis.

An unmatched input is a command error and returns exit code `2`. This is intentionally stricter than
silently running a partial batch after a misspelled path.

## Report shape

Batch output has `"report_type": "batch"` and schema version `1.0`. Its aggregate summary records:

- total, analyzed, passed, and failed file counts;
- controlled file-load error count;
- analyzed span, GenAI span, and trace counts;
- error and warning finding counts.

Every `files` entry has a stable source path and one of two states:

- `analyzed`: includes that file's summary, trace measurements, and findings;
- `load_error`: includes a safe error message while summary, traces, and findings remain empty.

A malformed file therefore does not discard valid results from the same batch. Load failures count
as failed files but not as rule findings.

## Exit codes and output safety

- `0`: every resolved file was loaded and passed the configured quality threshold.
- `1`: at least one file failed its quality threshold or could not be loaded.
- `2`: the command, input resolution, or report write was invalid.

Reports use the same atomic-write behavior as single-file checks. An output path that is also a
resolved input is rejected even with `--force`, preventing a report from overwriting source data.
