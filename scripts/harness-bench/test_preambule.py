"""Le préambule de vérification : refuser un bras qui mesurerait le témoin.

Motif (2026-08-06). Bilan des pannes de la semaine : une vingtaine de défauts de
plomberie, dont UN SEUL relevait de l'isolation. La classe dominante est « le
levier posé ne mord pas », et son cas le plus coûteux est le bras doublon
silencieux — 40 minutes de GPU et une conclusion fausse.

Arrivé deux fois : `HARNAIS_NU_RECHERCHE` inexistant dans bench.py (bras
duplicata du témoin, rattrapé par hasard en 3 s), et `HARNAIS_NU_CONVENTION_OUTILS`
non passé à boucle.py (vu en inspectant l'argv à la main).

    python3 -m pytest test_preambule.py -q
"""

from __future__ import annotations

import os

import pytest

import bench


@pytest.fixture(autouse=True)
def env_propre(monkeypatch):
    """Aucune HARNAIS_NU_* héritée : sinon le test dépend du shell de l'appelant."""
    for cle in [c for c in os.environ if c.startswith("HARNAIS_NU_")]:
        monkeypatch.delenv(cle, raising=False)


def lance(**variables):
    for cle, valeur in variables.items():
        os.environ[cle] = valeur
    try:
        bench.preambule("nu", "m", "pronote")
    finally:
        for cle in variables:
            os.environ.pop(cle, None)


class TestVariableInconnue:
    def test_refuse_une_variable_que_le_banc_ignore(self):
        """Le cas `HARNAIS_NU_RECHERCHE` : posée, jamais lue, donc sans effet."""
        with pytest.raises(SystemExit) as sortie:
            lance(HARNAIS_NU_LEVIER_IMAGINAIRE="1")
        assert "LEVIER_IMAGINAIRE" in str(sortie.value)
        assert "inconnue" in str(sortie.value)

    def test_accepte_une_variable_reellement_cablee(self):
        lance(HARNAIS_NU_TEMPERATURE="0.7")


class TestLevierInerte:
    def test_refuse_une_variable_qui_ne_change_pas_la_commande(self, monkeypatch):
        """Le cas `CONVENTION_OUTILS` : connue du fichier, mais non passée à l'argv.

        On simule en neutralisant le passage : la variable reste « connue » (elle
        est citée dans la source) mais la commande construite est identique avec
        et sans elle. C'est exactement la signature du bras doublon.
        """
        vrai = bench.nu_command

        def sans_effet(model, workdir, prompt):
            argv, extra = vrai(model, workdir, prompt)
            return [a for a in argv if a not in ("--temperature", "0.7")], extra

        monkeypatch.setitem(bench.HARNESSES, "nu", (sans_effet, bench.nu_metrics))
        with pytest.raises(SystemExit) as sortie:
            lance(HARNAIS_NU_TEMPERATURE="0.7")
        assert "doublon" in str(sortie.value)

    def test_signale_toutes_les_variables_fautives_d_un_coup(self):
        """Une par une ferait relancer la campagne autant de fois qu'il y a de
        fautes — or chaque relance coûte le temps de découvrir la suivante."""
        with pytest.raises(SystemExit) as sortie:
            lance(HARNAIS_NU_FAUX_A="1", HARNAIS_NU_FAUX_B="2")
        message = str(sortie.value)
        assert "FAUX_A" in message and "FAUX_B" in message


class TestModeleServi:
    def test_refuse_si_le_serveur_ne_dit_pas_quel_modele_il_sert(self, monkeypatch):
        """Le 2026-08-04, gemma a été mesuré à 74,6 tok/s et le chiffre attribué à
        l'A3B (vrai débit 28,8) : le port était tenu par le serveur précédent."""
        monkeypatch.setattr(bench, "_modele_servi", lambda url: None)
        with pytest.raises(SystemExit) as sortie:
            bench.preambule("nu", "m", "pronote", "http://127.0.0.1:9/v1")
        assert "modele servi inconnu" in str(sortie.value)

    def test_affiche_le_modele_quand_il_repond(self, monkeypatch, capsys):
        monkeypatch.setattr(bench, "_modele_servi", lambda url: "un-modele.gguf")
        bench.preambule("nu", "m", "pronote", "http://127.0.0.1:9/v1")
        assert "un-modele.gguf" in capsys.readouterr().out

    def test_sonde_illisible_ne_leve_jamais(self):
        """Invariant : une sonde d'environnement ne tue pas le banc, elle rend None."""
        assert bench._modele_servi("http://127.0.0.1:1/v1") is None
        assert bench._modele_servi("pas-une-url") is None


class TestNonRegression:
    def test_scenario_courant_restaure(self):
        """Le préambule modifie SCENARIO_COURANT pour bâtir la commande : le laisser
        modifié ferait dériver le venv déclaré aux tirages suivants."""
        bench.SCENARIO_COURANT = "columns-web"
        lance(HARNAIS_NU_TEMPERATURE="0.7")
        assert bench.SCENARIO_COURANT == "columns-web"

    def test_variable_restauree_apres_le_controle(self):
        """Le contrôle 2 retire la variable pour comparer : ne pas la remettre
        lancerait la campagne sans le levier qu'on venait de valider."""
        os.environ["HARNAIS_NU_TEMPERATURE"] = "0.7"
        try:
            bench.preambule("nu", "m", "pronote")
            assert os.environ["HARNAIS_NU_TEMPERATURE"] == "0.7"
        finally:
            os.environ.pop("HARNAIS_NU_TEMPERATURE", None)

    def test_harnais_non_nu_ignore_les_variables_nu(self):
        """`aider` ou `pi` ne lisent pas HARNAIS_NU_* : les refuser bloquerait des
        campagnes légitimes."""
        os.environ["HARNAIS_NU_TEMPERATURE"] = "0.7"
        try:
            bench.preambule("aider", "m", "pronote")
        finally:
            os.environ.pop("HARNAIS_NU_TEMPERATURE", None)
