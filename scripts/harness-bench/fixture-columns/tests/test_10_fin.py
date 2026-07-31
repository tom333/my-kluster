"""ÉTAGE 10 — fin de partie.

`Jeu.partie_terminee` passe à `True` dans deux cas, tous deux constatés au moment
de faire apparaître la colonne suivante :

- la séquence est ÉPUISÉE : il n'y a plus de colonne à faire tomber. `Jeu.colonne`
  vaut alors `None` ;
- l'APPARITION est bloquée : les lignes 0, 1 ou 2 de la colonne `largeur // 2` ne
  sont pas libres. La colonne suivante existe mais ne peut pas entrer.

Une fois la partie terminée, plus rien ne bouge : `deplacer`, `descendre` et
`cycler` rendent `False`, `chuter` rend `0`, `tick` ne fait rien.
"""

from colonnes import Jeu


def test_partie_non_terminee_au_depart():
    assert Jeu(iter(["ABC"]), largeur=4, hauteur=6).partie_terminee is False


def test_sequence_epuisee():
    j = Jeu(iter(["ABC"]), largeur=4, hauteur=6)
    j.chuter()
    assert j.partie_terminee is True
    assert j.colonne is None


def test_sequence_vide_des_le_depart():
    j = Jeu(iter([]), largeur=4, hauteur=6)
    assert j.partie_terminee is True
    assert j.colonne is None


def test_apparition_bloquee():
    """La colonne du milieu est bouchée par trois tuiles DIFFÉRENTES (trois
    identiques s'aligneraient et disparaîtraient)."""
    j = Jeu(iter(["ABC", "DEF"]), largeur=4, hauteur=6)
    for ligne, tuile in ((0, "X"), (1, "Y"), (2, "Z")):
        j.plateau.poser(ligne, 2, tuile)
    j.deplacer(-1)
    j.chuter()
    assert j.partie_terminee is True
    assert j.plateau.rendu() == "..X.\n..Y.\n..Z.\n.A..\n.B..\n.C.."


def test_plus_rien_ne_bouge_apres_la_fin():
    j = Jeu(iter(["ABC"]), largeur=4, hauteur=6)
    j.chuter()
    assert j.partie_terminee is True
    assert j.deplacer(-1) is False
    assert j.deplacer(1) is False
    assert j.descendre() is False
    assert j.cycler() is False
    assert j.chuter() == 0


def test_tick_ne_fait_rien_apres_la_fin():
    j = Jeu(iter(["ABC"]), largeur=4, hauteur=6)
    j.chuter()
    avant = j.plateau.rendu()
    j.tick()
    assert j.plateau.rendu() == avant


def test_cellules_vides_apres_la_fin():
    j = Jeu(iter(["ABC"]), largeur=4, hauteur=6)
    j.chuter()
    assert j.cellules() == {}
