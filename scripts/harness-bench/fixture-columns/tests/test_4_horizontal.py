"""ÉTAGE 4 — alignements horizontaux.

`colonnes.alignements(plateau)` rend l'ensemble des couples `(ligne, colonne)` des
cases appartenant à au moins une SUITE de trois tuiles identiques ou plus.

Cet étage ne juge que l'axe horizontal (de gauche à droite). Une suite de quatre
ou de cinq compte entièrement, pas seulement ses trois premières cases. Les cases
vides ne forment jamais de suite.
"""

from colonnes import Plateau, alignements


def remplir(plateau, ligne, depart, tuiles):
    for i, tuile in enumerate(tuiles):
        plateau.poser(ligne, depart + i, tuile)


def test_aucun_alignement_sur_un_plateau_vide():
    assert set(alignements(Plateau(5, 3))) == set()


def test_deux_tuiles_ne_suffisent_pas():
    p = Plateau(5, 3)
    remplir(p, 1, 0, "AA")
    assert set(alignements(p)) == set()


def test_trois_tuiles_alignees():
    p = Plateau(5, 3)
    remplir(p, 2, 0, "AAA")
    assert set(alignements(p)) == {(2, 0), (2, 1), (2, 2)}


def test_trois_tuiles_au_milieu():
    p = Plateau(5, 3)
    remplir(p, 1, 1, "BBB")
    assert set(alignements(p)) == {(1, 1), (1, 2), (1, 3)}


def test_suite_de_quatre_compte_entierement():
    p = Plateau(5, 2)
    remplir(p, 1, 0, "CCCC")
    assert set(alignements(p)) == {(1, 0), (1, 1), (1, 2), (1, 3)}


def test_suite_de_cinq():
    p = Plateau(5, 2)
    remplir(p, 0, 0, "DDDDD")
    assert len(set(alignements(p))) == 5


def test_tuiles_differentes_ne_s_alignent_pas():
    p = Plateau(5, 3)
    remplir(p, 1, 0, "ABA")
    assert set(alignements(p)) == set()


def test_une_case_vide_coupe_la_suite():
    p = Plateau(6, 3)
    p.poser(1, 0, "A")
    p.poser(1, 1, "A")
    p.poser(1, 3, "A")
    p.poser(1, 4, "A")
    assert set(alignements(p)) == set()


def test_deux_suites_sur_deux_lignes():
    p = Plateau(5, 3)
    remplir(p, 0, 0, "AAA")
    remplir(p, 2, 1, "BBB")
    assert set(alignements(p)) == {
        (0, 0),
        (0, 1),
        (0, 2),
        (2, 1),
        (2, 2),
        (2, 3),
    }
