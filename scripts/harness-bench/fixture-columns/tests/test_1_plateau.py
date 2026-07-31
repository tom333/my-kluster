"""ÉTAGE 1 — le plateau.

`colonnes.Plateau(largeur=6, hauteur=13)` : une grille de cases, chacune vide ou
portant une TUILE (une lettre majuscule de `'A'` à `'F'`). Les lignes sont
numérotées de haut en bas, la ligne 0 est en haut.

- `.largeur`, `.hauteur` : les dimensions.
- `dedans(ligne, colonne) -> bool` : la case est-elle dans la grille.
- `case(ligne, colonne)` : la tuile, ou `None` si la case est vide OU hors grille.
- `libre(ligne, colonne) -> bool` : dans la grille ET vide.
- `poser(ligne, colonne, tuile)` : place une tuile. Hors grille → `IndexError`.
- `rendu() -> str` : `hauteur` lignes de `largeur` caractères, de la ligne 0 vers
  le bas, séparées par `"\\n"`, sans saut de ligne final. Une case vide s'écrit
  `'.'`, une case occupée s'écrit sa tuile.
"""

import pytest

from colonnes import Plateau


def test_dimensions_par_defaut():
    p = Plateau()
    assert (p.largeur, p.hauteur) == (6, 13)


def test_dimensions_choisies():
    p = Plateau(4, 3)
    assert (p.largeur, p.hauteur) == (4, 3)


def test_plateau_neuf_est_vide():
    p = Plateau(4, 3)
    assert all(p.libre(l, c) for l in range(p.hauteur) for c in range(p.largeur))
    assert p.case(0, 0) is None


def test_dedans():
    p = Plateau(4, 3)
    assert p.dedans(0, 0)
    assert p.dedans(2, 3)
    assert not p.dedans(3, 0)
    assert not p.dedans(0, 4)
    assert not p.dedans(-1, 0)
    assert not p.dedans(0, -1)


def test_poser_puis_lire():
    p = Plateau(4, 3)
    p.poser(1, 2, "A")
    assert p.case(1, 2) == "A"
    assert not p.libre(1, 2)


def test_case_hors_plateau_rend_none():
    p = Plateau(4, 3)
    assert p.case(9, 9) is None


def test_libre_hors_plateau_est_faux():
    """Hors grille n'est pas « libre » : c'est ce qui borne les chutes."""
    p = Plateau(4, 3)
    assert not p.libre(3, 0)
    assert not p.libre(0, 4)


def test_poser_hors_plateau_leve():
    p = Plateau(4, 3)
    with pytest.raises(IndexError):
        p.poser(3, 0, "A")


def test_rendu_plateau_vide():
    assert Plateau(4, 3).rendu() == "....\n....\n...."


def test_rendu_avec_tuiles():
    p = Plateau(4, 3)
    p.poser(0, 0, "A")
    p.poser(2, 3, "B")
    assert p.rendu() == "A...\n....\n...B"


def test_rendu_sans_saut_de_ligne_final():
    assert not Plateau(4, 3).rendu().endswith("\n")


def test_rendu_dimensions():
    lignes = Plateau(6, 13).rendu().split("\n")
    assert len(lignes) == 13
    assert all(len(ligne) == 6 for ligne in lignes)
