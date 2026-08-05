"""Structural guards for GitHub Actions workflows (DIST-04).

These do not run the workflows — they assert the YAML declares the pieces the
design requires, so an accidental edit (wrong trigger, dropped issue step) is
caught by the test suite instead of only at 06:00 UTC.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_CANARY = Path(__file__).parent.parent / ".github" / "workflows" / "upstream-canary.yml"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_canary_workflow_exists() -> None:
    assert _CANARY.is_file(), f"missing {_CANARY}"


def test_canary_runs_daily_and_manually() -> None:
    wf = _load(_CANARY)
    # PyYAML parses the bare `on:` key as the boolean True.
    triggers = wf.get("on") or wf.get(True)
    assert triggers is not None, "workflow has no 'on:' triggers"
    assert "schedule" in triggers, "canary must be scheduled"
    assert triggers["schedule"][0]["cron"] == "0 6 * * *"
    assert "workflow_dispatch" in triggers, "canary must be manually runnable"


def test_canary_can_open_issues() -> None:
    wf = _load(_CANARY)
    assert wf["permissions"]["issues"] == "write"


def test_canary_overrides_pronotepy_from_git() -> None:
    raw = _CANARY.read_text(encoding="utf-8")
    assert "git+https://github.com/bain3/pronotepy" in raw
    assert "requirements_test.txt" in raw  # installs the pinned base first


def test_canary_opens_deduplicated_issue_on_failure() -> None:
    raw = _CANARY.read_text(encoding="utf-8")
    assert "steps.tests.outcome == 'failure'" in raw  # issue only on real test failure
    assert "pronotepy-upstream" in raw  # the dedup label
    assert "actions/github-script" in raw
