"""ÉTAGE 6 — alignements sur les deux diagonales.

Même fonction `colonnes.alignements(plateau)`. Deux axes de plus :

- la diagonale DESCENDANTE : en allant vers la droite, la ligne augmente
  (`(0,0), (1,1), (2,2)`) ;
- la diagonale MONTANTE : en allant vers la droite, la ligne diminue
  (`(2,0), (1,1), (0,2)`).

Les quatre axes — horizontal, vertical, et les deux diagonales — comptent tous.
"""

from colonnes import Plateau, alignements


def test_diagonale_descendante():
    p = Plateau(4, 4)
    for i in range(3):
        p.poser(i, i, "C")
    assert set(alignements(p)) == {(0, 0), (1, 1), (2, 2)}


def test_diagonale_montante():
    p = Plateau(4, 4)
    for i in range(3):
        p.poser(2 - i, i, "D")
    assert set(alignements(p)) == {(2, 0), (1, 1), (0, 2)}


def test_diagonale_descendante_decalee():
    p = Plateau(5, 5)
    for i in range(3):
        p.poser(1 + i, 2 + i, "A")
    assert set(alignements(p)) == {(1, 2), (2, 3), (3, 4)}


def test_diagonale_de_quatre():
    p = Plateau(5, 5)
    for i in range(4):
        p.poser(i, i, "B")
    assert set(alignements(p)) == {(0, 0), (1, 1), (2, 2), (3, 3)}


def test_deux_tuiles_en_diagonale_ne_suffisent_pas():
    p = Plateau(4, 4)
    p.poser(0, 0, "A")
    p.poser(1, 1, "A")
    assert set(alignements(p)) == set()


def test_diagonale_interrompue():
    p = Plateau(5, 5)
    p.poser(0, 0, "A")
    p.poser(1, 1, "B")
    p.poser(2, 2, "A")
    assert set(alignements(p)) == set()


def test_les_deux_diagonales_a_la_fois():
    """Un X de la même tuile : les deux diagonales comptent, le centre est
    partagé."""
    p = Plateau(3, 3)
    for i in range(3):
        p.poser(i, i, "E")
        p.poser(2 - i, i, "E")
    assert set(alignements(p)) == {
        (0, 0),
        (1, 1),
        (2, 2),
        (2, 0),
        (0, 2),
    }
