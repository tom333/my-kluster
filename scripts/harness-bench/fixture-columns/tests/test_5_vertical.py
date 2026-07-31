"""ÉTAGE 5 — alignements verticaux.

Même fonction `colonnes.alignements(plateau)`, axe vertical (de haut en bas).
Les mêmes règles s'appliquent : trois tuiles identiques minimum, une suite plus
longue compte entièrement, une case vide coupe la suite.
"""

from colonnes import Plateau, alignements


def empiler(plateau, colonne, depart, tuiles):
    for i, tuile in enumerate(tuiles):
        plateau.poser(depart + i, colonne, tuile)


def test_deux_tuiles_ne_suffisent_pas():
    p = Plateau(3, 5)
    empiler(p, 1, 0, "AA")
    assert set(alignements(p)) == set()


def test_trois_tuiles_empilees():
    p = Plateau(3, 5)
    empiler(p, 1, 0, "AAA")
    assert set(alignements(p)) == {(0, 1), (1, 1), (2, 1)}


def test_trois_tuiles_au_fond():
    p = Plateau(3, 5)
    empiler(p, 2, 2, "BBB")
    assert set(alignements(p)) == {(2, 2), (3, 2), (4, 2)}


def test_suite_de_quatre_compte_entierement():
    p = Plateau(2, 5)
    empiler(p, 0, 1, "CCCC")
    assert set(alignements(p)) == {(1, 0), (2, 0), (3, 0), (4, 0)}


def test_tuiles_differentes_ne_s_alignent_pas():
    p = Plateau(3, 5)
    empiler(p, 1, 0, "ABA")
    assert set(alignements(p)) == set()


def test_une_case_vide_coupe_la_suite():
    p = Plateau(3, 6)
    p.poser(0, 1, "A")
    p.poser(1, 1, "A")
    p.poser(3, 1, "A")
    p.poser(4, 1, "A")
    assert set(alignements(p)) == set()


def test_deux_colonnes_independantes():
    p = Plateau(3, 4)
    empiler(p, 0, 0, "AAA")
    empiler(p, 2, 1, "BBB")
    assert set(alignements(p)) == {
        (0, 0),
        (1, 0),
        (2, 0),
        (1, 2),
        (2, 2),
        (3, 2),
    }
