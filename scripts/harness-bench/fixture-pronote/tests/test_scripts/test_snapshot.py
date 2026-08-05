"""Smoke tests for scripts/snapshot.py — the anonymizer is contract-tested.

D-13: snapshot.py is NOT a tested code surface. We test ONLY:
  1. anonymize() is deterministic (same input + same replacements -> same output).
  2. no_pii() is the documented invariant (returns True iff PII allowlist absent).
  3. walk_and_replace() handles str/dict/list/passthrough recursively.
  4. _read_env() handles missing files, comments, blank lines, quoted values.
  5. CLI --help works and --scenario/--phase choices are enforced.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

# scripts/ is outside custom_components/ — direct import via REPO_ROOT.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.snapshot import (  # noqa: E402
    _build_replacements,
    _load_replacements_file,
    _read_env,
    anonymize,
    no_pii,
    walk_and_replace,
)


def test_walk_and_replace_replaces_in_string():
    assert walk_and_replace("Alice was here", {"Alice": "Eleve"}) == "Eleve was here"


def test_walk_and_replace_recurses_into_dict():
    out = walk_and_replace({"name": "Alice", "school": "X"}, {"Alice": "Eleve"})
    assert out == {"name": "Eleve", "school": "X"}


def test_walk_and_replace_recurses_into_list():
    assert walk_and_replace(["Alice", "Bob"], {"Alice": "Eleve"}) == ["Eleve", "Bob"]


def test_walk_and_replace_recurses_nested():
    inp = {"k": [{"name": "Alice"}, {"name": "Bob"}]}
    out = walk_and_replace(inp, {"Alice": "Eleve"})
    assert out == {"k": [{"name": "Eleve"}, {"name": "Bob"}]}


def test_walk_and_replace_passes_through_non_str():
    assert walk_and_replace(42, {"x": "y"}) == 42
    assert walk_and_replace(None, {"x": "y"}) is None
    assert walk_and_replace(True, {"x": "y"}) is True


def test_anonymize_is_deterministic():
    raw = {"name": "Alice Dupont", "school": "Lycée Katiramona"}
    repls = {"Alice Dupont": "Eleve Test", "Lycée Katiramona": "Établissement Test"}
    out1 = anonymize(raw, repls)
    out2 = anonymize(raw, repls)
    assert out1 == out2
    assert out1 == {"name": "Eleve Test", "school": "Établissement Test"}


def test_no_pii_returns_true_when_allowlist_absent():
    cleaned = anonymize({"name": "Alice"}, {"Alice": "Eleve"})
    assert no_pii(cleaned, ["Alice"]) is True


def test_no_pii_returns_false_when_allowlist_present():
    assert no_pii({"name": "Alice"}, ["Alice"]) is False


def test_no_pii_ignores_empty_strings_in_blocklist():
    # Defensive: empty string would always match — guard against it.
    assert no_pii({"name": "Alice"}, ["", "Alice"]) is False
    assert no_pii({"name": "Eleve"}, ["", "Alice"]) is True


def test_read_env_returns_empty_for_missing_file(tmp_path):
    assert _read_env(tmp_path / "no.env") == {}


def test_read_env_parses_key_value_pairs(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# comment\n"
        "PRONOTE_URL=https://example.com/pronote\n"
        "PRONOTE_USERNAME=alice\n"
        "\n"
        'PRONOTE_PASSWORD="quoted-secret"\n'
        "PRONOTE_ACCOUNT_TYPE='eleve'\n",
        encoding="utf-8",
    )
    env = _read_env(env_path)
    assert env["PRONOTE_URL"] == "https://example.com/pronote"
    assert env["PRONOTE_USERNAME"] == "alice"
    assert env["PRONOTE_PASSWORD"] == "quoted-secret"
    assert env["PRONOTE_ACCOUNT_TYPE"] == "eleve"


def test_build_replacements_includes_username_and_host():
    env = {
        "PRONOTE_URL": "https://demo.example.com/pronote/eleve.html",
        "PRONOTE_USERNAME": "demonstration",
    }
    repls = _build_replacements(env)
    assert repls["demonstration"] == "Eleve Test"
    assert repls["demo.example.com"] == "pronote.example.fr"


def test_build_replacements_merges_extra_replacements():
    """Extra replacements (from the gitignored .replacements.json) override
    nothing built-in but extend the map for teacher/classroom anonymization."""
    env = {"PRONOTE_USERNAME": "demonstration"}
    extra = {"REAL TEACHER": "prof 1", "Salle Z9": "Salle Test"}
    repls = _build_replacements(env, extra=extra)
    assert repls["demonstration"] == "Eleve Test"
    assert repls["REAL TEACHER"] == "prof 1"
    assert repls["Salle Z9"] == "Salle Test"


def test_load_replacements_returns_empty_when_file_missing(tmp_path: Path):
    """SECURITY: missing .replacements.json is the normal case for fresh
    checkouts and CI — must degrade gracefully (no PII assumed)."""
    assert _load_replacements_file(tmp_path / "absent.json") == {}


def test_load_replacements_parses_flat_string_dict(tmp_path: Path):
    p = tmp_path / ".replacements.json"
    p.write_text('{"REAL NAME": "stand-in", "Salle B204": "Salle Test"}', encoding="utf-8")
    out = _load_replacements_file(p)
    assert out == {"REAL NAME": "stand-in", "Salle B204": "Salle Test"}


def test_load_replacements_rejects_non_dict_payload(tmp_path: Path):
    p = tmp_path / ".replacements.json"
    p.write_text('["not", "a", "dict"]', encoding="utf-8")
    assert _load_replacements_file(p) == {}


def test_load_replacements_rejects_non_string_values(tmp_path: Path):
    p = tmp_path / ".replacements.json"
    p.write_text('{"key": 42}', encoding="utf-8")
    assert _load_replacements_file(p) == {}


def test_load_replacements_handles_invalid_json(tmp_path: Path):
    p = tmp_path / ".replacements.json"
    p.write_text("{ not valid json", encoding="utf-8")
    assert _load_replacements_file(p) == {}


def test_replacements_json_is_gitignored():
    """SECURITY (T-02-02-02): .replacements.json must be gitignored — same
    threat class as .env. The file holds real teacher/classroom names that
    must never enter the committed source tree."""
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".replacements.json" in gitignore


@pytest.mark.timeout(5)
def test_cli_help_exits_zero():
    # @pytest.mark.timeout(5) overrides the global pyproject.toml `timeout = 1`
    # (D-28, PC-02-02): subprocess CLI startup can spend more than 1s in cold imports.
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "snapshot.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0
    assert "--scenario" in result.stdout
    assert "--phase" in result.stdout


@pytest.mark.timeout(5)
def test_cli_rejects_invalid_scenario():
    # @pytest.mark.timeout(5) overrides the global pyproject.toml `timeout = 1`
    # (D-28, PC-02-02): subprocess CLI startup can spend more than 1s in cold imports.
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "snapshot.py"),
            "--scenario",
            "invalid",
            "--phase",
            "T0",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode != 0
    assert "invalid choice" in result.stderr or "invalid" in result.stderr


def test_env_example_does_not_contain_real_school_url():
    """SECURITY (security_gate threat #1): .env.example must NOT leak the
    author's real ac-noumea.nc URL. Real URL lives in the gitignored .env.
    """
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "ac-noumea.nc" not in env_example
    assert "katiramona" not in env_example
    # Demo or example URLs are fine; real ones are not.
    assert "demo.index-education.net" in env_example or "example" in env_example
