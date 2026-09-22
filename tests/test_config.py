import json
from pathlib import Path

import pytest

from genai_tracecheck.analysis import analyze_spans
from genai_tracecheck.cli import main
from genai_tracecheck.config import ConfigurationError, load_policy_config
from genai_tracecheck.loader import load_otlp_json
from genai_tracecheck.models import (
    ContentPolicy,
    FailureThreshold,
    Policy,
    Severity,
    TraceCompleteness,
)

ROOT = Path(__file__).parents[1]
EXAMPLES = ROOT / "examples"


def _config(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "tracecheck.toml"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_policy_config_maps_every_supported_setting(tmp_path: Path) -> None:
    path = _config(
        tmp_path,
        """
schema_version = "1.0"

[policy]
fail_on = "warning"
content_policy = "forbid"
detect_secret_values = false
trace_completeness = "complete"

[rules.GTC102]
enabled = false

[rules.GTC005]
severity = "error"
""",
    )

    policy = load_policy_config(path)

    assert policy.fail_on is FailureThreshold.WARNING
    assert policy.content_policy is ContentPolicy.FORBID
    assert policy.detect_secret_values is False
    assert policy.trace_completeness is TraceCompleteness.COMPLETE
    assert policy.disabled_rules == frozenset({"GTC102"})
    assert policy.severity_overrides == {"GTC005": Severity.ERROR}


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ('schema_version = "2.0"', "schema_version"),
        ('schema_version = "1.0"\nunknown = true', "unknown"),
        ('schema_version = "1.0"\n[policy]\nunknown = true', "policy.unknown"),
        ('schema_version = "1.0"\n[rules.GTC005]\nunknown = true', "unknown"),
        ('schema_version = "1.0"\n[rules.GTC999]\nenabled = false', "GTC999"),
        (
            'schema_version = "1.0"\n[rules.GTC005]\nenabled = false\nseverity = "error"',
            "disabled rule",
        ),
        ('schema_version = "1.0"\n[rules.GTC005', "invalid TOML"),
    ],
)
def test_config_rejects_unknown_or_ambiguous_content(
    tmp_path: Path, content: str, message: str
) -> None:
    path = _config(tmp_path, content)

    with pytest.raises(ConfigurationError, match=message):
        load_policy_config(path)


def test_disabled_rule_is_removed_before_summary_and_failure_evaluation(tmp_path: Path) -> None:
    path = _config(
        tmp_path,
        'schema_version = "1.0"\n[rules.GTC201]\nenabled = false\n',
    )
    spans = load_otlp_json(EXAMPLES / "structured-content.otlp.json")

    report = analyze_spans(spans, source="fixture", policy=load_policy_config(path))

    assert report.passed is True
    assert report.findings == []
    assert report.summary.warnings == 0
    assert report.disabled_rules == ["GTC201"]


def test_severity_override_changes_summary_order_and_quality_gate(tmp_path: Path) -> None:
    path = _config(
        tmp_path,
        'schema_version = "1.0"\n[rules.GTC201]\nseverity = "error"\n',
    )
    spans = load_otlp_json(EXAMPLES / "structured-content.otlp.json")

    report = analyze_spans(spans, source="fixture", policy=load_policy_config(path))

    assert report.passed is False
    assert report.summary.errors == 1
    assert report.summary.warnings == 0
    assert report.findings[0].severity is Severity.ERROR
    assert report.severity_overrides == {"GTC201": Severity.ERROR}


def test_explicit_cli_policy_flag_overrides_config(tmp_path: Path, capsys) -> None:
    path = _config(
        tmp_path,
        """
schema_version = "1.0"
[policy]
fail_on = "warning"
detect_secret_values = false
""",
    )
    fixture = str(EXAMPLES / "structured-content.otlp.json")

    configured_exit = main(["check", fixture, "--config", str(path)])
    configured = json.loads(capsys.readouterr().out)
    overridden_exit = main(
        [
            "check",
            fixture,
            "--config",
            str(path),
            "--fail-on",
            "error",
            "--secret-detection",
        ]
    )
    overridden = json.loads(capsys.readouterr().out)

    assert configured_exit == 1
    assert configured["fail_on"] == "warning"
    assert configured["detect_secret_values"] is False
    assert overridden_exit == 0
    assert overridden["fail_on"] == "error"
    assert overridden["detect_secret_values"] is True


def test_invalid_config_is_a_controlled_cli_error(tmp_path: Path, capsys) -> None:
    path = _config(tmp_path, 'schema_version = "1.0"\nunexpected = true\n')

    exit_code = main(["check", str(EXAMPLES / "valid.otlp.json"), "--config", str(path)])

    assert exit_code == 2
    error = capsys.readouterr().err
    assert "invalid configuration" in error
    assert "unexpected" in error


def test_programmatic_policy_rejects_unknown_and_conflicting_rule_settings() -> None:
    with pytest.raises(ValueError, match="GTC999"):
        Policy(disabled_rules=frozenset({"GTC999"}))
    with pytest.raises(ValueError, match="cannot override severity"):
        Policy(
            disabled_rules=frozenset({"GTC005"}),
            severity_overrides={"GTC005": Severity.ERROR},
        )
