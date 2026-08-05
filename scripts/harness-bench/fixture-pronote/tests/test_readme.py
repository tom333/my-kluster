"""Guards locking the two README bugs fixed in DIST-07."""

from __future__ import annotations

from pathlib import Path

_README = Path(__file__).parent.parent / "README.md"


def test_readme_exists() -> None:
    assert _README.is_file()


def test_readme_has_no_archived_planning_links() -> None:
    text = _README.read_text(encoding="utf-8")
    assert ".planning/" not in text, "README links the archived .planning/ tree"


def test_readme_uses_underscore_repo_url() -> None:
    text = _README.read_text(encoding="utf-8")
    assert "tom333/ha-pronote" not in text, "wrong hyphenated repo URL"
    assert "tom333/ha_pronote" in text, "missing correct repo URL"


def test_readme_documents_schedule_event() -> None:
    text = _README.read_text(encoding="utf-8")
    assert "pronote_schedule_changed" in text
