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


class TestVerifieurAmorce:
    """L'oracle d'AMORCE DE PROJET : trois assertions, deux mécaniques, une heuristique.

    On ne teste pas ici le chemin complet (il exige un émulateur et ~70 s de build)
    mais les décisions qui rendraient le score faux sans le signaler.
    """

    def test_seuil_issu_d_une_mesure(self):
        """0,90 n'est pas choisi au doigt mouillé : une scène `flutter_scene` VIDE
        capturée sur l'émulateur le 2026-08-06 met 98,0 % de ses pixels dans une seule
        couleur. Le seuil doit rester sous cette valeur, sinon l'oracle validerait un
        écran vide."""
        assert bench.PART_DOMINANTE_MAX < 0.98

    def test_identifiant_lu_et_non_suppose(self, tmp_path):
        """C'est l'AGENT qui crée le projet, donc lui qui choisit le nom du paquet.
        Le coder en dur ferait échouer l'oracle sur un projet par ailleurs correct."""
        (tmp_path / "android" / "app").mkdir(parents=True)
        (tmp_path / "android" / "app" / "build.gradle.kts").write_text(
            'android {\n  defaultConfig {\n    applicationId = "ovh.tgu.autre"\n  }\n}\n'
        )
        assert bench._identifiant_application(str(tmp_path)) == "ovh.tgu.autre"

    def test_identifiant_gradle_groovy_aussi(self, tmp_path):
        (tmp_path / "android" / "app").mkdir(parents=True)
        (tmp_path / "android" / "app" / "build.gradle").write_text(
            "defaultConfig {\n    applicationId \"ovh.tgu.groovy\"\n}\n"
        )
        assert bench._identifiant_application(str(tmp_path)) == "ovh.tgu.groovy"

    def test_identifiant_absent_rend_none(self, tmp_path):
        assert bench._identifiant_application(str(tmp_path)) is None

    def test_image_illisible_rend_none_pas_zero(self):
        """None, pas 0,0 : « je ne sais pas lire l'image » n'est pas « écran uniforme ».
        Un 0,0 ferait passer l'étage `rendu` sur une capture corrompue."""
        assert bench._part_dominante(b"pas une image") is None
        assert bench._part_dominante(b"") is None

    def test_part_dominante_sur_une_image_unie(self, tmp_path):
        from PIL import Image

        import io

        tampon = io.BytesIO()
        Image.new("RGB", (10, 10), (255, 255, 255)).save(tampon, format="PNG")
        assert bench._part_dominante(tampon.getvalue()) == 1.0

    def test_part_dominante_sur_une_image_variee(self):
        from PIL import Image

        import io

        image = Image.new("RGB", (10, 10), (255, 255, 255))
        for x in range(10):
            for y in range(5):
                image.putpixel((x, y), (x * 20, y * 40, 7))
        tampon = io.BytesIO()
        image.save(tampon, format="PNG")
        assert bench._part_dominante(tampon.getvalue()) < bench.PART_DOMINANTE_MAX

    def test_le_scenario_declare_trois_etages_independants(self):
        """Un score binaire confondrait « ne compile pas » et « compile mais plante ».
        Trois étages rendent les tirages comparables."""
        sc = bench.SCENARIOS["crepuscule-amorce"]
        assert sc["expected_tests"] == 3
        assert [nom for nom, _, _ in sc["etages"]] == ["build", "lancement", "rendu"]
        assert sc["verifieur"] in bench.VERIFIEURS

    def test_la_fixture_ne_contient_que_la_spec(self):
        """C'est TOUT l'intérêt du scénario : l'agent part d'un répertoire nu. Y
        glisser un squelette retirerait de la mesure la capacité « créer un projet »."""
        contenu = sorted(p.name for p in bench.SCENARIOS["crepuscule-amorce"]["fixture"].iterdir())
        assert contenu == ["SPEC.md"]
