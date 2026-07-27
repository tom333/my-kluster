import hermes_state
import pytest


class ExecuteurInterdit:
    """Échoue si on l'appelle. Prouve qu'aucun kubectl n'a lieu."""

    def __call__(self, argv, stdin=None):
        raise AssertionError(f"aucun appel kubectl ne devait avoir lieu, reçu: {argv}")


def art(**kw):
    base = {"name": "x", "pod": "/opt/data/x", "git": "g/x", "owner": "git",
            "mode": "text", "also": [], "apply_forbidden": False,
            "restart_required": False}
    base.update(kw)
    return base


def test_apply_refuse_owner_hermes():
    with pytest.raises(hermes_state.GuardError, match="owner=hermes"):
        hermes_state.check_appliable(art(name="crons", owner="hermes", mode="json-spec"))


def test_apply_refuse_config():
    with pytest.raises(hermes_state.GuardError, match="apply_forbidden"):
        hermes_state.check_appliable(art(name="config", apply_forbidden=True))


def test_apply_accepte_un_artefact_git():
    hermes_state.check_appliable(art(name="soul"))  # ne lève pas


def test_le_refus_precede_tout_appel_kubectl():
    """Le garde-fou doit trancher AVANT de toucher au cluster : sinon une
    commande mal tapée aurait déjà écrit quand l'erreur remonte."""
    pod = hermes_state.podio.Pod(executor=ExecuteurInterdit())
    with pytest.raises(hermes_state.GuardError):
        hermes_state.apply_artifact(pod, art(owner="hermes"), b"peu importe", oui=True)


def test_apply_dry_run_n_ecrit_rien():
    pod = hermes_state.podio.Pod(executor=ExecuteurInterdit())
    hermes_state.apply_artifact(pod, art(name="soul"), b"contenu", oui=False)
    # ExecuteurInterdit lèverait si un kubectl avait lieu


def test_apply_ecrit_aussi_les_destinations_also():
    ecrits = []
    pod = hermes_state.podio.Pod(executor=ExecuteurInterdit())
    pod.write = lambda chemin, donnees: ecrits.append(chemin)
    hermes_state.apply_artifact(
        pod, art(name="hermes-md", pod="/workspace/HERMES.md",
                 also=["/workspace/AGENTS.md"]), b"x", oui=True)
    assert ecrits == ["/workspace/HERMES.md", "/workspace/AGENTS.md"]


def test_mode_tree_signale_les_fichiers_en_trop_sans_les_supprimer():
    """Spec §3.3 : `apply` en mode tree n'efface JAMAIS les fichiers
    surnuméraires du pod. Supprimer dans le pod depuis Git n'est pas un pouvoir
    qu'on donne à une commande de synchronisation."""
    a = art(name="skill-veille-digest", pod="/opt/data/skills/veille-digest",
            git="hermes-runtime/skills/veille-digest", mode="tree")
    cote_git = {"SKILL.md": "contenu\n"}
    cote_pod = {"SKILL.md": "contenu\n", "brouillon.md": "résidu\n"}
    statut, detail = hermes_state.comparer(a, cote_git, cote_pod)
    assert statut == hermes_state.DIVERGE
    assert "en trop dans le pod" in detail
    assert "brouillon.md" in detail


def test_comparer_absent_du_pod():
    statut, detail = hermes_state.comparer(art(), "contenu\n", None)
    assert statut == hermes_state.ABSENT_POD


def test_comparer_absent_de_git_suggere_adopt_pour_owner_git():
    statut, detail = hermes_state.comparer(art(owner="git"), None, "contenu\n")
    assert statut == hermes_state.ABSENT_GIT
    assert "--adopt" in detail


def test_comparer_absent_de_git_suggere_export_seul_pour_owner_hermes():
    """`export` sans --adopt suffit pour un artefact que Hermes possede :
    suggerer --adopt enverrait l'utilisateur vers une commande plus large que
    necessaire."""
    statut, detail = hermes_state.comparer(art(owner="hermes", mode="json-spec"),
                                          None, "contenu\n")
    assert statut == hermes_state.ABSENT_GIT
    assert "--adopt" not in detail
    assert "`export`" in detail


def test_comparer_texte_identique():
    statut, _ = hermes_state.comparer(art(), "meme\n", "meme\n")
    assert statut == hermes_state.IDENTIQUE


def test_comparer_yaml_subset_ignore_les_ajouts_du_pod():
    a = art(name="config", mode="yaml-subset")
    statut, _ = hermes_state.comparer(a, {"agent": {"max_turns": 90}},
                                      {"agent": {"max_turns": 90}, "_config_version": 33})
    assert statut == hermes_state.IDENTIQUE


def test_ligne_statut():
    assert hermes_state.ligne_statut("soul", "=") == "=  soul"
    assert "~" in hermes_state.ligne_statut("soul", "~", "contenu différent")
