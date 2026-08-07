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

    def test_trois_etages_construits_par_le_verificateur(self, monkeypatch):
        """Un score binaire confondrait « ne compile pas » et « compile mais plante ».

        Les trois étages viennent du VÉRIFICATEUR, pas d'une clé de scénario : les
        déclarer en double a fait planter la première campagne. On vérifie donc qu'un
        build raté produit bien les trois, tous à FAIL — parce qu'un étage OMIS se
        lirait comme un étage réussi dans un agrégat.
        """
        sc = dict(bench.SCENARIOS["crepuscule-amorce"], sdk_bin="/inexistant")
        passed, failed, _, issue, etages = bench._verifie_amorce_flutter("/tmp", sc)
        assert sorted(etages) == ["build", "lancement", "rendu"]
        assert (passed, failed) == (0, 3)
        assert all(e["verdict"] == "FAIL" for e in etages.values())
        assert issue == bench.ISSUE_COLLECTE

    def test_la_fixture_ne_contient_que_la_spec(self):
        """C'est TOUT l'intérêt du scénario : l'agent part d'un répertoire nu. Y
        glisser un squelette retirerait de la mesure la capacité « créer un projet »."""
        contenu = sorted(p.name for p in bench.SCENARIOS["crepuscule-amorce"]["fixture"].iterdir())
        assert contenu == ["SPEC.md"]


class TestScenarioSansPytest:
    """Un scénario noté autrement que par pytest ne doit pas passer par pytest.

    La première campagne `crepuscule-amorce` est morte là-dessus : le banc mesure un
    score de DÉPART avant de lancer l'agent, et il l'a fait en appelant pytest avec
    `cibles=[None]` (TypeError). Même sans planter, la ligne « départ » n'aurait rien
    voulu dire : le répertoire ne contient qu'une spec, aucun test ne peut exister.
    """

    def test_pas_de_faux_etages_pytest(self):
        """La clé `etages` est réservée aux scénarios notés par un appel pytest PAR
        FICHIER. `amorce-flutter` construit lui-même ses trois étages. Les déclarer en
        double a fait lire la clé avec le mauvais sens."""
        sc = bench.SCENARIOS["crepuscule-amorce"]
        assert "etages" not in sc
        assert sc["expected_tests"] == 3
        assert sc["verifieur"] == "amorce-flutter"

    def test_aucun_scenario_ne_cumule_verifieur_et_etages(self):
        """Invariant : les deux voies de notation sont exclusives. Les cumuler rend
        indéterminé qui produit le score."""
        for nom, sc in bench.SCENARIOS.items():
            assert not (sc.get("verifieur") and sc.get("etages")), nom

    def test_tout_verifieur_declare_existe(self):
        for nom, sc in bench.SCENARIOS.items():
            if sc.get("verifieur"):
                assert sc["verifieur"] in bench.VERIFIEURS, nom

    def test_un_scenario_sans_pytest_en_declare_un_autre_moyen(self):
        """Sans `pytest` ni `verifieur`, le banc retomberait sur le PYTEST global et
        noterait un projet Dart avec un outil Python."""
        for nom, sc in bench.SCENARIOS.items():
            if sc.get("verifieur"):
                continue
            # Les scénarios Python utilisent le pytest global ou le leur : dans les
            # deux cas la notation est définie. On vérifie surtout qu'aucun scénario
            # n'est muet sur la façon dont il se note.
            assert "expected_tests" in sc, nom


class TestRacineProjet:
    """Où est le projet : DÉCOUVERT, jamais supposé.

    La première campagne `crepuscule-amorce` (2026-08-07) a noté 0/3 en partie parce
    que le vérificateur cherchait l'APK à la RACINE du workdir, alors que l'agent avait
    légitimement fait `flutter create amorce_crepuscule` — donc un sous-répertoire.
    L'oracle aurait noté 0/3 sur un projet PARFAIT.
    """

    def test_projet_a_la_racine(self, tmp_path):
        (tmp_path / "pubspec.yaml").write_text("name: x\n")
        assert bench._racine_projet(str(tmp_path)) == tmp_path

    def test_projet_dans_un_sous_repertoire(self, tmp_path):
        """Le cas réel : `flutter create <nom>` crée un sous-répertoire."""
        (tmp_path / "amorce").mkdir()
        (tmp_path / "amorce" / "pubspec.yaml").write_text("name: x\n")
        assert bench._racine_projet(str(tmp_path)) == tmp_path / "amorce"

    def test_la_racine_gagne_sur_un_sous_repertoire(self, tmp_path):
        """Un projet Flutter contient des `pubspec.yaml` imbriqués (exemples,
        paquets) : le bon est le moins profond."""
        (tmp_path / "pubspec.yaml").write_text("name: racine\n")
        (tmp_path / "exemple").mkdir()
        (tmp_path / "exemple" / "pubspec.yaml").write_text("name: exemple\n")
        assert bench._racine_projet(str(tmp_path)) == tmp_path

    def test_aucun_projet_rend_none(self, tmp_path):
        """Et le vérificateur doit alors noter les trois étages ÉCHOUÉS avec un motif
        lisible, pas planter."""
        assert bench._racine_projet(str(tmp_path)) is None
        sc = dict(bench.SCENARIOS["crepuscule-amorce"], sdk_bin="/inexistant")
        passed, failed, notes, issue, etages = bench._verifie_amorce_flutter(
            str(tmp_path), sc
        )
        assert (passed, failed) == (0, 3)
        assert "pubspec" in notes
        assert sorted(etages) == ["build", "lancement", "rendu"]

    def test_identifiant_lu_depuis_la_racine_trouvee(self, tmp_path):
        """L'`applicationId` doit être cherché DANS le projet, pas dans le workdir."""
        projet = tmp_path / "amorce"
        (projet / "android" / "app").mkdir(parents=True)
        (projet / "pubspec.yaml").write_text("name: x\n")
        (projet / "android" / "app" / "build.gradle.kts").write_text(
            'applicationId = "com.crepuscule.amorce"\n'
        )
        racine = bench._racine_projet(str(tmp_path))
        assert bench._identifiant_application(racine) == "com.crepuscule.amorce"
