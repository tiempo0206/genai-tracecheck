# Portfolio demo

This deterministic demo runs locally, makes no network request, and takes a few seconds. Start from
the repository after installing development dependencies:

```bash
python tools/demo.py
```

Expected output for version `1.0.0`:

```text
GenAI TraceCheck 1.0.0 portfolio demo
[1/3] valid fixture: PASS spans=1 findings=0
[2/3] risky fixture: EXPECTED FAIL errors=5 warnings=3 rules=GTC002,GTC101,GTC102,GTC103,GTC104,GTC105,GTC201,GTC202
[3/3] SARIF: EXPECTED FAIL results=8 fingerprints=8 captured_secret_embedded=no
```

The three lines demonstrate separate product contracts:

1. A valid OTLP/HTTP JSON export passes with exit code `0`.
2. A deliberately risky export is analyzed successfully but fails the quality gate with exit code
   `1`; the result exposes rule identifiers without echoing the secret-shaped value.
3. The same findings convert to SARIF 2.1.0 with one stable fingerprint per result and still omit the
   captured secret.

The script treats the expected quality-gate failures as successful demo behavior. It exits non-zero
only if the CLI, JSON contract, finding set, SARIF shape, fingerprints, or non-disclosure property
does not match expectations. CI runs this script on every supported Python version.
