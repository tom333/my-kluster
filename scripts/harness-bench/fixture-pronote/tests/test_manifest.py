"""Regression contract for custom_components/ha_pronote/manifest.json (DIST-02).

Every assertion below maps to a locked decision (D-NN) in CONTEXT.md. A failing
assertion means a future PR drifted away from a Phase 1 user decision — the
test name will indicate which one.
"""

from __future__ import annotations

import json
from pathlib import Path

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "custom_components" / "ha_pronote" / "manifest.json"


def _load_manifest() -> dict:
    """Load and parse the integration manifest."""
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_is_valid_json() -> None:
    """manifest.json must parse as JSON (hassfest prerequisite)."""
    assert MANIFEST_PATH.is_file()
    _load_manifest()  # raises on parse error


def test_manifest_domain_is_ha_pronote() -> None:
    """D-01: domain is frozen to 'ha_pronote' (matches directory name)."""
    assert _load_manifest()["domain"] == "ha_pronote"


def test_manifest_name_is_ha_pronote() -> None:
    """Display name."""
    assert _load_manifest()["name"] == "HA-Pronote"


def test_manifest_codeowners_is_tom333() -> None:
    """D-04: codeowners is a single GitHub handle."""
    assert _load_manifest()["codeowners"] == ["@tom333"]


def test_manifest_documentation_url() -> None:
    """D-05: documentation URL points at the GitHub repo (underscore — matches real repo path)."""
    assert _load_manifest()["documentation"] == "https://github.com/tom333/ha_pronote"


def test_manifest_issue_tracker_url() -> None:
    """D-06: issue tracker URL points at GitHub Issues (underscore — matches real repo path)."""
    assert _load_manifest()["issue_tracker"] == "https://github.com/tom333/ha_pronote/issues"


def test_manifest_iot_class_cloud_polling() -> None:
    """D-12 / DIST-02: cloud_polling iot_class."""
    assert _load_manifest()["iot_class"] == "cloud_polling"


def test_manifest_quality_scale_bronze() -> None:
    """D-13 / DIST-02: quality_scale bronze."""
    assert _load_manifest()["quality_scale"] == "bronze"


def test_manifest_integration_type_hub() -> None:
    """D-15: hub integration (one entry per child)."""
    assert _load_manifest()["integration_type"] == "hub"


def test_manifest_config_flow_true() -> None:
    """D-16: config_flow=true; placeholder ConfigFlow ships in Phase 1."""
    assert _load_manifest()["config_flow"] is True


def test_manifest_version_placeholder() -> None:
    """D-17: 0.0.1 placeholder; release.yml rewrites this from the git tag."""
    assert _load_manifest()["version"] == "0.0.1"


def test_manifest_requirements_pin_pronotepy_2_14_6() -> None:
    """D-14 / DIST-02: pronotepy is pinned exactly to 2.14.6 (Pronote API stability)."""
    requirements = _load_manifest()["requirements"]
    assert "pronotepy==2.14.6" in requirements


def test_manifest_requirements_pin_python_slugify_8_0_4() -> None:
    """D-14: python-slugify version matches HA Core's pin."""
    requirements = _load_manifest()["requirements"]
    assert "python-slugify==8.0.4" in requirements


def test_manifest_no_unexpected_keys() -> None:
    """Phase 1 manifest has exactly 11 keys; future phases may add more.

    If this fails, a new key was added without updating the regression contract.
    """
    manifest = _load_manifest()
    expected = {
        "domain",
        "name",
        "codeowners",
        "config_flow",
        "documentation",
        "integration_type",
        "iot_class",
        "issue_tracker",
        "quality_scale",
        "requirements",
        "version",
    }
    assert set(manifest.keys()) == expected, f"Unexpected manifest keys: {set(manifest.keys()) ^ expected}"
