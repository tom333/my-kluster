"""Analyseurs de sortie de tests, par lanceur.

Motif (2026-08-06) : le banc devient multi-langage (scénario Flutter prévu). Ce qui
est testé ici est exactement ce qui a déjà cassé une fois côté pytest — une sortie
mal lue donne un score faux sans que rien ne le signale. Le 2026-08-05, `-q` combiné
à l'`addopts` de la fixture donnait `-qq`, supprimait la ligne de bilan, et le banc
lisait 0/5 sur un oracle qui échouait proprement à 2 échecs / 3 réussis.

    python3 -m pytest test_lanceurs.py -q
"""

from __future__ import annotations

import os
import pytest

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

    def test_tous_les_etages_construits_par_le_verificateur(self, monkeypatch):
        """Un score binaire confondrait « ne compile pas » et « compile mais plante ».

        Les étages viennent du VÉRIFICATEUR, pas d'une clé de scénario : les
        déclarer en double a fait planter la première campagne. On vérifie donc qu'un
        build raté produit bien TOUS les étages, tous à FAIL — parce qu'un étage OMIS
        se lirait comme un étage réussi dans un agrégat.
        """
        sc = dict(bench.SCENARIOS["crepuscule-amorce"], sdk_bin="/inexistant")
        passed, failed, _, issue, etages = bench._verifie_amorce_flutter("/tmp", sc)
        assert sorted(etages) == sorted(bench.ETAGES_AMORCE)
        assert (passed, failed) == (0, len(bench.ETAGES_AMORCE))
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
        FICHIER. `amorce-flutter` construit lui-même ses étages. Les déclarer en
        double a fait lire la clé avec le mauvais sens."""
        sc = bench.SCENARIOS["crepuscule-amorce"]
        assert "etages" not in sc
        assert sc["expected_tests"] == len(bench.ETAGES_AMORCE)
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
        """Et le vérificateur doit alors noter TOUS les étages ÉCHOUÉS avec un motif
        lisible, pas planter."""
        assert bench._racine_projet(str(tmp_path)) is None
        sc = dict(bench.SCENARIOS["crepuscule-amorce"], sdk_bin="/inexistant")
        passed, failed, notes, issue, etages = bench._verifie_amorce_flutter(
            str(tmp_path), sc
        )
        assert (passed, failed) == (0, len(bench.ETAGES_AMORCE))
        assert "pubspec" in notes
        assert sorted(etages) == sorted(bench.ETAGES_AMORCE)

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


class TestBalayageApresGel:
    """Un seul test qui boucle ne doit plus effacer le score des 43 autres.

    Motif (2026-09-14) : mellum2-12b-a2.5b a perdu DEUX essais sur trois en
    `pytest_pend`, et la campagne a conclu 0/44. Rejoués test par test, ces essais
    donnaient 33/44 et 28/44, un seul test bouclant dans les deux cas. Neuf
    campagnes sur 138 portent au moins un essai pendu, dont deux de l'incumbent.
    """

    def _fixture(self, tmp_path, corps_du_test_qui_boucle):
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_suite.py").write_text(
            "def test_passe_un():\n    assert True\n\n"
            "def test_passe_deux():\n    assert True\n\n"
            "def test_echoue():\n    assert False\n\n"
            "def test_boucle():\n" + corps_du_test_qui_boucle
        )
        return tmp_path

    def test_le_gel_est_impute_a_un_seul_test(self, tmp_path, monkeypatch):
        wd = self._fixture(tmp_path, "    while True:\n        pass\n")
        # Budgets resserres : le but est la logique, pas d'attendre 180 s.
        monkeypatch.setattr(bench, "TIMEOUT_SUITE", 5)
        monkeypatch.setattr(bench, "TIMEOUT_PAR_TEST", 3)
        passed, failed, texte, issue = bench.run_pytest(
            wd, cibles=("tests/test_suite.py",)
        )
        assert issue == bench.ISSUE_PARTIEL
        assert passed == 2, texte
        assert failed == 2, texte  # l'echec franc + le test pendu
        assert "test_boucle" in texte

    def test_une_suite_saine_ne_declenche_pas_le_balayage(self, tmp_path):
        wd = self._fixture(tmp_path, "    assert True\n")
        passed, failed, _, issue = bench.run_pytest(
            wd, cibles=("tests/test_suite.py",)
        )
        assert issue == bench.ISSUE_OK
        assert (passed, failed) == (3, 1)

    def test_un_essai_balaye_compte_dans_la_mediane(self):
        essais = [
            {"issue": bench.ISSUE_OK, "tests_passed": 44},
            {"issue": bench.ISSUE_PARTIEL, "tests_passed": 33},
            {"issue": bench.ISSUE_PEND, "tests_passed": 0},
        ]
        comparables = (bench.ISSUE_OK, bench.ISSUE_PARTIEL)
        notables = [e["tests_passed"] for e in essais if e["issue"] in comparables]
        assert notables == [44, 33]


class TestVerdictMajorite:
    """Un PASS exige une MAJORITE d'essais comparables, pas seulement une médiane.

    Motif (2026-09-14) : campagne opencode sur crepuscule-amorce, essais 3/3, 0/3,
    0/3. Les deux échecs écartés comme « ne compile pas », médiane calculée sur UN
    essai, verdict PASS. Le banc a déclaré réussie une campagne où rien n'avait
    fonctionné deux fois sur trois.
    """

    def _verdict(self, notables, runs, attendus):
        med = bench.mediane(notables) if notables else None
        return "PASS" if med == attendus and len(notables) * 2 > runs else "FAIL"

    def test_un_seul_essai_comparable_sur_trois_ne_passe_pas(self):
        assert self._verdict([3], runs=3, attendus=3) == "FAIL"

    def test_deux_essais_comparables_sur_trois_passent(self):
        assert self._verdict([3, 3], runs=3, attendus=3) == "PASS"

    def test_la_majorite_ne_sauve_pas_une_mediane_insuffisante(self):
        assert self._verdict([2, 3, 2], runs=3, attendus=3) == "FAIL"


class TestBibliothequeExigee:
    """Contourner la bibliothèque nommée par l'énoncé n'est pas réussir la tâche.

    Motif (2026-09-15) : qwen3-coder-reap-25b a fait passer l'étage `build` en
    supprimant l'exigence — pubspec sans `flutter_scene`, 57 lignes affichant
    « FLUTTER GPU OK », aucune 3D — puis a appelé `finish`. Même faille que le
    gabarit `flutter create` (245772f4) par l'autre bout : du code neuf mais vide.
    """

    def _projet(self, tmp_path, pubspec, dart):
        (tmp_path / "pubspec.yaml").write_text(pubspec)
        (tmp_path / "lib").mkdir()
        (tmp_path / "lib" / "main.dart").write_text(dart)
        return tmp_path

    def test_absente_du_pubspec_et_des_sources(self, tmp_path):
        p = self._projet(
            tmp_path,
            "dependencies:\n  flutter:\n    sdk: flutter\n",
            "import 'package:flutter/material.dart';\nvoid main() {}\n",
        )
        assert bench._bibliotheque_absente(p) is True

    def test_declaree_mais_jamais_importee(self, tmp_path):
        p = self._projet(
            tmp_path,
            "dependencies:\n  flutter_scene: ^0.20.0\n",
            "import 'package:flutter/material.dart';\nvoid main() {}\n",
        )
        assert bench._bibliotheque_absente(p) is True

    def test_declaree_et_importee(self, tmp_path):
        p = self._projet(
            tmp_path,
            "dependencies:\n  flutter_scene: ^0.20.0\n",
            "import 'package:flutter_scene/scene.dart';\nvoid main() {}\n",
        )
        assert bench._bibliotheque_absente(p) is False

    def test_un_import_faux_reste_une_tentative_honnete(self, tmp_path):
        # gemma importait `flutter_scene/flutter_scene.dart`, qui n'existe pas.
        # Ce garde ne doit PAS le penaliser : il echoue deja au build.
        p = self._projet(
            tmp_path,
            "dependencies:\n  flutter_scene: ^0.23.0\n",
            "import 'package:flutter_scene/flutter_scene.dart';\nvoid main() {}\n",
        )
        assert bench._bibliotheque_absente(p) is False


class TestDepotGitPrealable:
    """Le depot doit exister AVANT l'agent, et vide.

    Motif (2026-09-15) : sans marqueur racine au lancement, `dartls` ne demarre
    jamais chez omp -- silencieusement -- et la campagne mesure un defaut
    d'instrument. Et la SPEC §3bis note l'historique : le support doit etre la,
    le contenu reste le travail de l'agent.
    """

    def test_le_scenario_amorce_demande_un_depot(self):
        assert bench.SCENARIOS["crepuscule-amorce"]["depot_git"] is True

    def test_depot_vide_et_sans_signature(self, tmp_path):
        bench._init_depot(tmp_path)
        assert (tmp_path / ".git").is_dir()
        # Zero commit : l'agent part d'un historique vierge, sinon les seuils de
        # l'etage `historique` seraient atteints sans qu'il ait rien fait.
        assert bench._commits(tmp_path) == []
        code, sortie = bench._lance(
            ["git", "config", "commit.gpgsign"], cwd=str(tmp_path), timeout=30
        )
        # La signature GPG bloquerait l'agent sur une demande de phrase de passe.
        assert (code, sortie.strip()) == (0, "false")


class TestUrlSondeParHarnais:
    """La sonde doit lire l'endpoint DU HARNAIS, jamais une valeur par defaut.

    Motif (2026-09-15, troisieme occurrence du meme defaut) : la sonde a refuse
    la premiere campagne omp avec « le modele demande n'est PAS servi » en
    interrogeant 127.0.0.1:8080, alors que omp sert depuis
    `~/.omp/agent/models.yml`. Le harnais suivant qu'on ajoutera retombera dans
    le meme piege si la deduction n'est pas testee.
    """

    def test_omp_lit_sa_configuration_globale(self):
        url = bench.url_client_de("omp", "localai")
        assert url.endswith("/v1")
        assert "127.0.0.1:8080" not in url

    def test_harnais_inconnu_retombe_sur_le_defaut(self, monkeypatch):
        monkeypatch.delenv("HARNAIS_NU_BASE_URL", raising=False)
        assert bench.url_client_de("nu") == "http://127.0.0.1:8080/v1"


class TestCheminsRelatifsAuProjet:
    """Le cycle rouge-vert doit se lire quand le projet est dans un SOUS-REPERTOIRE.

    Motif (2026-09-15) : le banc pose le depot sur le workdir, et le premier
    essai omp a cree `crepuscule_project/`. `git log --name-only` rendait alors
    `crepuscule_project/test/x_test.dart`, que `startswith("test/")` ne matche
    pas -- un cycle rouge-vert parfait aurait ete note en echec.
    """

    def _depot(self, tmp_path, imbrique):
        bench._init_depot(tmp_path)
        projet = tmp_path / "crepuscule_project" if imbrique else tmp_path
        (projet / "test").mkdir(parents=True, exist_ok=True)
        (projet / "lib").mkdir(parents=True, exist_ok=True)
        (projet / "test" / "iso_test.dart").write_text("// rouge\n")
        bench._lance(["git", "add", "-A"], cwd=str(tmp_path), timeout=30)
        bench._lance(
            ["git", "commit", "-m", "test(iso): projection isometrique"],
            cwd=str(tmp_path),
            timeout=30,
        )
        (projet / "lib" / "iso.dart").write_text("// vert\n")
        bench._lance(["git", "add", "-A"], cwd=str(tmp_path), timeout=30)
        bench._lance(
            ["git", "commit", "-m", "feat(iso): implemente la projection"],
            cwd=str(tmp_path),
            timeout=30,
        )
        return projet

    def test_projet_imbrique_rend_des_chemins_du_projet(self, tmp_path):
        projet = self._depot(tmp_path, imbrique=True)
        commits = bench._commits(projet)
        assert [f for _s, _m, fs in commits for f in fs] == [
            "test/iso_test.dart",
            "lib/iso.dart",
        ]

    def test_projet_a_la_racine_inchange(self, tmp_path):
        projet = self._depot(tmp_path, imbrique=False)
        commits = bench._commits(projet)
        assert [f for _s, _m, fs in commits for f in fs] == [
            "test/iso_test.dart",
            "lib/iso.dart",
        ]

    def test_le_cycle_rouge_vert_est_vu_dans_un_sous_repertoire(self, tmp_path):
        projet = self._depot(tmp_path, imbrique=True)
        etages = {}

        def etage(nom, ok, detail=""):
            etages[nom] = ok

        bench._verifie_methode(projet, etage, flutter="/inexistant")
        assert etages["test_dabord"] is True
        # Deux commits conventionnels : le format est bon, le PLANCHER ne l'est pas.
        assert etages["historique"] is False


class TestLittleCoderModeles:
    """little-coder ne resout pas le NOM de variable d'`apiKey` (verifie 2026-09-16 :
    401 avec le nom, succes avec la valeur). Le banc genere donc un fichier
    temporaire avec la valeur, et le gabarit versionne ne doit JAMAIS la porter."""

    def test_le_gabarit_ne_porte_que_le_nom_de_variable(self):
        gabarit = bench.HERE / "config-little-coder" / "models.json"
        conf = json.loads(gabarit.read_text())
        assert conf["providers"]["localai"]["apiKey"] == "LOCALAI_API_KEY"

    def test_le_fichier_genere_est_prive_et_hors_workdir(self, tmp_path):
        _argv, env = bench.little_coder_command("localai/gemma-4-12b-it-qat", tmp_path, "x")
        assert env["LITTLE_CODER_PERMISSION_MODE"] == "accept-all"
        fichier = env.get("LITTLE_CODER_MODELS_FILE")
        if fichier is None:
            pytest.skip("pas de cle LocalAI sur cette machine")
        assert not str(fichier).startswith(str(tmp_path)), "le workdir est archive"
        assert (os.stat(fichier).st_mode & 0o777) == 0o600


class TestLittleCoderLens:
    """Bras B = bras A + pi-lens, et RIEN d'autre (un seul facteur change)."""

    def test_meme_argv_que_le_bras_a_plus_une_extension(self, tmp_path):
        argv_a, env_a = bench.little_coder_command("localai/gemma-4-12b-it-qat", tmp_path, "x")
        argv_b, env_b = bench.little_coder_lens_command("localai/gemma-4-12b-it-qat", tmp_path, "x")
        assert argv_a == argv_b
        assert set(env_b) - set(env_a) == {"LITTLE_CODER_EXTRA_EXTENSIONS"}
        assert env_b["LITTLE_CODER_EXTRA_EXTENSIONS"] == str(bench.PI_LENS)

    def test_pi_lens_est_installe(self):
        # Sinon le lanceur avertit et continue SANS l'extension : le bras B
        # mesurerait le bras A en croyant mesurer pi-lens (bras doublon silencieux).
        assert bench.PI_LENS.is_file()


class TestExclusionOutils:
    """`--exclude-tools` : un REGLAGE du harnais, pas une transformation.

    Motif (2026-09-16, essai 3 de little-coder+pi-lens) : `dispatch` lance des
    sous-codeurs qui ont mange 12 min sur 28 et ouvert un second flux concurrent
    sur le GPU, si bien que `flutter build` n'a jamais ete lance avant le
    couperet. La famille pi expose nativement `--exclude-tools`.
    """

    def test_inerte_par_defaut(self, tmp_path):
        """Par defaut on ne retire RIEN : sinon toutes les campagnes passees
        deviendraient incomparables sans que rien ne le signale."""
        avant = bench.EXCLURE_OUTILS
        bench.EXCLURE_OUTILS = ""
        try:
            argv, _ = bench.little_coder_command("localai/gemma-4-12b-it-qat", tmp_path, "x")
            assert "--exclude-tools" not in argv
        finally:
            bench.EXCLURE_OUTILS = avant

    def test_pose_la_liste_noire(self, tmp_path):
        avant = bench.EXCLURE_OUTILS
        bench.EXCLURE_OUTILS = "dispatch"
        try:
            argv, _ = bench.little_coder_command("localai/gemma-4-12b-it-qat", tmp_path, "x")
            i = argv.index("--exclude-tools")
            assert argv[i + 1] == "dispatch"
        finally:
            bench.EXCLURE_OUTILS = avant

    def test_le_prompt_reste_en_dernier(self, tmp_path):
        """`-p <prompt>` doit rester la DERNIERE paire : inserer un drapeau
        apres elle le ferait avaler comme argument du prompt."""
        avant = bench.EXCLURE_OUTILS
        bench.EXCLURE_OUTILS = "dispatch,glob"
        try:
            argv, _ = bench.little_coder_command("localai/gemma-4-12b-it-qat", tmp_path, "TACHE")
            assert argv[-2:] == ["-p", "TACHE"]
        finally:
            bench.EXCLURE_OUTILS = avant

    def test_le_bras_lens_en_herite(self, tmp_path):
        """little-coder-lens delegue a little_coder_command : le reglage doit
        traverser, sinon les deux bras ne seraient plus comparables."""
        avant = bench.EXCLURE_OUTILS
        bench.EXCLURE_OUTILS = "dispatch"
        try:
            argv, env = bench.little_coder_lens_command(
                "localai/gemma-4-12b-it-qat", tmp_path, "x"
            )
            assert "--exclude-tools" in argv
            assert env["LITTLE_CODER_EXTRA_EXTENSIONS"] == str(bench.PI_LENS)
        finally:
            bench.EXCLURE_OUTILS = avant
