import tomllib
from pathlib import Path

from genai_tracecheck import __version__
from genai_tracecheck.rule_catalog import SUPPORTED_RULE_IDS

ROOT = Path(__file__).parents[1]


def test_release_version_and_rule_count_are_consistent() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert __version__ == project["project"]["version"] == "1.0.0"
    assert "## 1.0.0 — 2026-09-26" in changelog
    assert "Version `1.0.0` is the portfolio release" in readme
    assert len(SUPPORTED_RULE_IDS) == 20


def test_portfolio_contains_durable_architecture_benchmark_and_demo_evidence() -> None:
    portfolio = (ROOT / "docs" / "portfolio.md").read_text(encoding="utf-8")
    demo = (ROOT / "docs" / "demo.md").read_text(encoding="utf-8")

    assert "```mermaid" in portfolio
    assert "Untrusted OTLP/HTTP JSON" in portfolio
    assert "100,000 | 1.677553 s | 59,611 spans/s | 483.60 MiB" in portfolio
    assert "improved the recorded 100K analysis median by 20.2%" in portfolio
    assert "python tools/demo.py" in portfolio
    assert "captured_secret_embedded=no" in demo
