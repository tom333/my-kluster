import json

import pytest

import podio


class FauxExecuteur:
    """Enregistre les appels et rejoue des réponses. Permet de tester tout le
    transport sans cluster."""

    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.appels = []

    def __call__(self, argv, stdin=None):
        self.appels.append((argv, stdin))
        if not self.reponses:
            raise AssertionError(f"appel inattendu: {argv}")
        return self.reponses.pop(0)


POD_OK = (0, b"hermes-agent-6d7f7b4c45-5hw4t   Running\n", b"")


def test_resolution_du_pod():
    pod = podio.Pod(executor=FauxExecuteur([POD_OK]))
    assert pod.name() == "hermes-agent-6d7f7b4c45-5hw4t"


def test_pod_mis_en_cache():
    faux = FauxExecuteur([POD_OK])
    pod = podio.Pod(executor=faux)
    pod.name()
    pod.name()
    assert len(faux.appels) == 1, "le nom du pod doit être résolu une seule fois"


def test_pod_non_running_rejete():
    pod = podio.Pod(executor=FauxExecuteur([(0, b"hermes-agent-abc   Pending\n", b"")]))
    with pytest.raises(podio.PodError, match="Pending"):
        pod.name()


def test_pod_absent_rejete():
    pod = podio.Pod(executor=FauxExecuteur([(0, b"autre-chose   Running\n", b"")]))
    with pytest.raises(podio.PodError, match="aucun pod"):
        pod.name()


def test_kubectl_en_echec_rejete():
    pod = podio.Pod(executor=FauxExecuteur([(1, b"", b"connection refused")]))
    with pytest.raises(podio.PodError, match="connection refused"):
        pod.name()


def test_lecture():
    pod = podio.Pod(executor=FauxExecuteur([POD_OK, (0, b"contenu du fichier", b"")]))
    assert pod.read("/opt/data/SOUL.md") == b"contenu du fichier"


def test_lecture_en_echec_leve():
    faux = FauxExecuteur([POD_OK, (1, b"", b"cat: /x: No such file or directory")])
    pod = podio.Pod(executor=faux)
    with pytest.raises(podio.PodError, match="No such file"):
        pod.read("/x")


def test_ecriture_chown_et_verifie():
    faux = FauxExecuteur([
        POD_OK,             # name()
        (0, b"", b""),      # cat > tmp
        (0, b"", b""),      # mv + chown
        (0, b"nouveau", b""),  # relecture
    ])
    pod = podio.Pod(executor=faux)
    pod.write("/opt/data/SOUL.md", b"nouveau")
    scripts = [a[0][-1] for a in faux.appels[1:]]
    assert any("chown 10000:10000" in s for s in scripts), "le chown est obligatoire"
    assert any("mv -f" in s for s in scripts), "l'écriture doit être atomique"


def test_ecriture_passe_les_donnees_en_stdin():
    """Les données ne doivent JAMAIS transiter par la ligne de commande :
    un contenu avec des guillemets ou des retours ligne casserait le shell."""
    faux = FauxExecuteur([POD_OK, (0, b"", b""), (0, b"", b""), (0, b'a"b\nc', b"")])
    pod = podio.Pod(executor=faux)
    pod.write("/opt/data/x", b'a"b\nc')
    stdins = [a[1] for a in faux.appels]
    assert b'a"b\nc' in stdins, "le contenu doit être passé en stdin"


def test_ecriture_leve_si_chown_echoue():
    faux = FauxExecuteur([POD_OK, (0, b"", b""), (1, b"", b"chown: Operation not permitted")])
    pod = podio.Pod(executor=faux)
    with pytest.raises(podio.PodError, match="chown"):
        pod.write("/opt/data/SOUL.md", b"x")


def test_ecriture_leve_si_relecture_differente():
    faux = FauxExecuteur([POD_OK, (0, b"", b""), (0, b"", b""), (0, b"autre chose", b"")])
    pod = podio.Pod(executor=faux)
    with pytest.raises(podio.PodError, match="relecture"):
        pod.write("/opt/data/SOUL.md", b"attendu")


def test_listage_arbre():
    faux = FauxExecuteur([POD_OK, (0, b"SKILL.md\nreferences/github-releases-api.md\n", b"")])
    pod = podio.Pod(executor=faux)
    assert pod.list_tree("/opt/data/skills/veille-digest") == [
        "SKILL.md", "references/github-releases-api.md"]


def test_listage_arbre_absent_rend_liste_vide():
    """Un répertoire absent n'est pas une erreur : `diff` doit pouvoir dire
    « absent du pod » plutôt que de planter."""
    pod = podio.Pod(executor=FauxExecuteur([POD_OK, (1, b"", b"")]))
    assert pod.list_tree("/opt/data/skills/inexistant") == []


def test_exists():
    pod = podio.Pod(executor=FauxExecuteur([POD_OK, (0, b"", b"")]))
    assert pod.exists("/opt/data/SOUL.md") is True


def test_exists_faux():
    pod = podio.Pod(executor=FauxExecuteur([POD_OK, (1, b"", b"")]))
    assert pod.exists("/opt/data/absent") is False


def test_read_json_retry_reussit_du_premier_coup():
    faux = FauxExecuteur([POD_OK, (0, b'{"a": 1}', b"")])
    dormi = []
    pod = podio.Pod(executor=faux)
    assert pod.read_json_retry("/x", json.loads, dormir=dormi.append) == {"a": 1}
    assert dormi == [], "aucune attente si le JSON est valide"


def test_read_json_retry_retente_une_fois():
    """jobs.json peut être lu pendant une écriture d'Hermes : on retente."""
    faux = FauxExecuteur([POD_OK, (0, b'{"a": tronq', b""), (0, b'{"a": 1}', b"")])
    dormi = []
    pod = podio.Pod(executor=faux)
    assert pod.read_json_retry("/x", json.loads, attente=9, dormir=dormi.append) == {"a": 1}
    assert dormi == [9], "doit avoir attendu une fois avant de retenter"


def test_read_json_retry_abandonne_apres_deux_echecs():
    """Committer un JSON tronqué serait pire que de rater la capture."""
    faux = FauxExecuteur([POD_OK, (0, b"tronq", b""), (0, b"tronq", b"")])
    pod = podio.Pod(executor=faux)
    with pytest.raises(podio.PodError, match="JSON invalide"):
        pod.read_json_retry("/x", json.loads, dormir=lambda _: None)
