"""ÉTAGE 2 — la colonne qui tombe.

`colonnes.Colonne(tuiles)` : la pièce du jeu, TROIS tuiles empilées dans une seule
colonne de la grille.

- `.tuiles` : un tuple de trois tuiles, `tuiles[0]` en HAUT, `tuiles[2]` en BAS.
- Un nombre de tuiles différent de trois → `ValueError`.
- `cycler()` : rend une NOUVELLE colonne où la tuile du BAS est remontée au
  sommet, les deux autres descendant d'un cran. `('A','B','C')` devient
  `('C','A','B')`. La colonne d'origine n'est pas modifiée.
- Deux colonnes portant les mêmes tuiles dans le même ordre sont égales (`==`).
"""

import pytest

from colonnes import Colonne


def test_trois_tuiles_du_haut_vers_le_bas():
    c = Colonne(("A", "B", "C"))
    assert c.tuiles == ("A", "B", "C")


def test_accepte_une_chaine_de_trois():
    assert Colonne("ABC").tuiles == ("A", "B", "C")


def test_refuse_un_autre_nombre():
    for mauvais in ("AB", "ABCD", ""):
        with pytest.raises(ValueError):
            Colonne(mauvais)


def test_cycler_remonte_la_tuile_du_bas():
    assert Colonne("ABC").cycler().tuiles == ("C", "A", "B")


def test_cycler_trois_fois_revient_au_depart():
    c = Colonne("ABC")
    assert c.cycler().cycler().cycler().tuiles == ("A", "B", "C")


def test_cycler_ne_modifie_pas_l_original():
    c = Colonne("ABC")
    c.cycler()
    assert c.tuiles == ("A", "B", "C")


def test_egalite():
    assert Colonne("ABC") == Colonne("ABC")
    assert Colonne("ABC") != Colonne("CAB")


def test_egalite_avec_autre_chose():
    assert Colonne("ABC") != "ABC"
