"""Analyseurs de sortie de tests, par lanceur.

Motif (2026-08-06) : le banc devient multi-langage (scénario Flutter prévu). Ce qui
est testé ici est exactement ce qui a déjà cassé une fois côté pytest — une sortie
mal lue donne un score faux sans que rien ne le signale. Le 2026-08-05, `-q` combiné
à l'`addopts` de la fixture donnait `-qq`, supprimait la ligne de bilan, et le banc
lisait 0/5 sur un oracle qui échouait proprement à 2 échecs / 3 réussis.

    python3 -m pytest test_lanceurs.py -q
"""

from __future__ import annotations

import json

import bench


def evenements(*entrees):
    """Sortie JSON de `dart test` : une ligne par événement."""
    return "\n".join(json.dumps(e) for e in entrees)


class TestDart:
    def test_succes_et_echecs_comptes(self):
        sortie = evenements(
            {"type": "testDone", "testID": 3, "result": "success", "hidden": False},
            {"type": "testDone", "testID": 4, "result": "success", "hidden": False},
            {"type": "testDone", "testID": 5, "result": "failure", "hidden": False},
        )
        assert bench._analyse_dart(sortie) == (2, 1, False)

    def test_le_test_synthetique_est_ecarte(self):
        """`package:test` émet un « loading test/x_test.dart » par FICHIER, avec
        `hidden: true`. Sans ce filtre, chaque fichier de test ajouterait un faux
        succès au score — l'erreur croît avec la taille du projet."""
        sortie = evenements(
            {"type": "testDone", "testID": 1, "result": "success", "hidden": True},
            {"type": "testDone", "testID": 3, "result": "success", "hidden": False},
        )
        assert bench._analyse_dart(sortie) == (1, 0, False)

    def test_erreur_distincte_d_un_echec(self):
        sortie = evenements(
            {"type": "testDone", "testID": 3, "result": "error", "hidden": False}
        )
        assert bench._analyse_dart(sortie) == (0, 1, False)

    def test_aucun_testDone_signale_une_collecte_ratee(self):
        """Le cas qui compte le plus : une erreur de compilation Dart ne produit AUCUN
        `testDone`. Sans ce signal, un échec de build se lirait comme « le modèle n'a
        rien fait passer » — soit un modèle accusé pour une panne d'outil."""
        _, _, ratee = bench._analyse_dart("Error: Type 'Foo' not found.")
        assert ratee is True

    def test_sortie_vide_signale_une_collecte_ratee(self):
        assert bench._analyse_dart("") == (0, 0, True)

    def test_json_tronque_ne_leve_pas(self):
        sortie = '{"type":"testDone","testID":3,"result":"success","hidden":false}\n{"type":"testDo'
        assert bench._analyse_dart(sortie) == (1, 0, False)

    def test_lignes_non_json_ignorees(self):
        """`dart pub get` et les avertissements se mêlent au flux."""
        sortie = 'Resolving dependencies...\n{"type":"testDone","testID":3,"result":"success","hidden":false}'
        assert bench._analyse_dart(sortie) == (1, 0, False)


class TestPytestInchange:
    def test_lecture_nominale(self):
        assert bench._analyse_pytest("3 failed, 106 passed in 1.2s") == (106, 3, False)

    def test_collecte_ratee_detectee(self):
        _, _, ratee = bench._analyse_pytest("!!! error during collection !!!")
        assert ratee is True

    def test_bilan_absent_rend_zero_sans_lever(self):
        """Le cas `-qq` : la ligne de bilan a été supprimée. On rend 0 — mais on ne
        peut PAS le distinguer d'un vrai 0, d'où `-o addopts=` dans l'argv."""
        assert bench._analyse_pytest("") == (0, 0, False)


class TestArgv:
    def test_pytest_neutralise_la_config_de_la_fixture(self):
        argv = bench.LANCEURS["pytest"][0]("/bin/pytest", ("tests/",))
        assert argv[:4] == ["/bin/pytest", "-o", "addopts=", "-q"]

    def test_dart_impose_le_rapporteur_json(self):
        """Le CLI l'emporte sur `dart_test.yaml`, pour lequel il n'existe AUCUN
        équivalent de `-o addopts=`. C'est la seule parade disponible."""
        argv = bench.LANCEURS["dart"][0]("/bin/dart", ())
        assert argv == ["/bin/dart", "test", "--reporter", "json"]

    def test_les_deux_lanceurs_sont_declares(self):
        assert set(bench.LANCEURS) == {"pytest", "dart"}
