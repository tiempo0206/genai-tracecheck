import subprocess
import sys
from pathlib import Path

from genai_tracecheck import __version__

ROOT = Path(__file__).parents[1]


def test_portfolio_demo_exercises_pass_failure_and_safe_sarif_paths() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "demo.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        f"GenAI TraceCheck {__version__} portfolio demo",
        "[1/3] valid fixture: PASS spans=1 findings=0",
        (
            "[2/3] risky fixture: EXPECTED FAIL errors=5 warnings=3 "
            "rules=GTC002,GTC101,GTC102,GTC103,GTC104,GTC105,GTC201,GTC202"
        ),
        "[3/3] SARIF: EXPECTED FAIL results=8 fingerprints=8 captured_secret_embedded=no",
    ]
