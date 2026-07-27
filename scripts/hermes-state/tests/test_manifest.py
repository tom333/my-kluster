import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest
import normalize


MANIFEST = pathlib.Path(__file__).resolve().parents[1] / "manifest.yaml"


def test_load_manifest_reel():
    arts = normalize.load_manifest(MANIFEST)
    noms = [a["name"] for a in arts]
    assert "crons" in noms
    assert "soul" in noms
    assert len(noms) == len(set(noms)), "noms d'artefacts en doublon"


def test_crons_appartient_a_hermes():
    arts = {a["name"]: a for a in normalize.load_manifest(MANIFEST)}
    assert arts["crons"]["owner"] == "hermes"
    assert arts["config"]["apply_forbidden"] is True


def test_owner_inconnu_rejete(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text("artifacts:\n  - name: x\n    pod: /a\n    git: b\n    owner: personne\n    mode: text\n")
    with pytest.raises(ValueError, match="owner"):
        normalize.load_manifest(p)


def test_mode_inconnu_rejete(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text("artifacts:\n  - name: x\n    pod: /a\n    git: b\n    owner: git\n    mode: braille\n")
    with pytest.raises(ValueError, match="mode"):
        normalize.load_manifest(p)


def test_chemin_git_en_doublon_rejete(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text(
        "artifacts:\n"
        "  - name: a\n    pod: /a\n    git: meme/chemin\n    owner: git\n    mode: text\n"
        "  - name: b\n    pod: /b\n    git: meme/chemin\n    owner: git\n    mode: text\n"
    )
    with pytest.raises(ValueError, match="doublon"):
        normalize.load_manifest(p)
