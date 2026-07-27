import pathlib

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


def test_champ_requis_manquant_rejete(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text("artifacts:\n  - name: x\n    pod: /a\n    owner: git\n    mode: text\n")
    with pytest.raises(ValueError, match="manquant"):
        normalize.load_manifest(p)


def test_artifacts_absent_rejete(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text("autre_cle: 1\n")
    with pytest.raises(ValueError, match="aucun artefact déclaré"):
        normalize.load_manifest(p)


def test_artifacts_vide_rejete(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text("artifacts: []\n")
    with pytest.raises(ValueError, match="aucun artefact déclaré"):
        normalize.load_manifest(p)


def test_nom_en_doublon_rejete(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text(
        "artifacts:\n"
        "  - name: a\n    pod: /a\n    git: chemin-a\n    owner: git\n    mode: text\n"
        "  - name: a\n    pod: /b\n    git: chemin-b\n    owner: git\n    mode: text\n"
    )
    with pytest.raises(ValueError, match="doublon"):
        normalize.load_manifest(p)


def test_valeurs_par_defaut(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text("artifacts:\n  - name: x\n    pod: /a\n    git: b\n    owner: git\n    mode: text\n")
    arts = normalize.load_manifest(p)
    assert arts[0]["also"] == []
    assert arts[0]["apply_forbidden"] is False
    assert arts[0]["restart_required"] is False


def test_entree_non_mapping_rejetee(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text("artifacts:\n  - juste-une-chaine\n")
    with pytest.raises(ValueError, match="index"):
        normalize.load_manifest(p)
