"""ÉTAGE 3 — apparition, déplacement, chute.

`colonnes.Jeu(sequence, largeur=6, hauteur=13)` où `sequence` est un itérateur de
chaînes de trois tuiles (`iter(["ABC", "DEF"])`). Aucun hasard : tout est fourni.

- `.plateau` : le plateau du jeu.
- À l'apparition, la colonne occupe les lignes 0, 1 et 2 de la colonne
  `largeur // 2`. `.ligne` est la ligne de sa tuile du HAUT, `.col` sa colonne.
- `.colonne` : la `Colonne` en cours de chute.
- `cellules() -> dict` : `{(ligne, colonne): tuile}` pour les trois tuiles de la
  colonne en chute. Ces tuiles ne sont PAS encore sur le plateau.
- `deplacer(dcol) -> bool` : décale d'une colonne si les trois cases visées sont
  libres, et rend `True` ; sinon ne bouge pas et rend `False`.
- `cycler() -> bool` : cycle la colonne en chute (cf. étage 2), rend `True`.
- `descendre() -> bool` : descend d'une ligne si c'est libre, rend `True` ; sinon
  rend `False` sans bouger.
- `chuter() -> int` : descend jusqu'au blocage, rend le NOMBRE de lignes
  parcourues, puis VERROUILLE la colonne sur le plateau.
- `tick()` : descend d'une ligne, ou verrouille si la descente est impossible.

Verrouiller signifie : poser les trois tuiles sur le plateau, résoudre les
alignements (étages 4 à 8), puis faire apparaître la colonne suivante.
"""

from colonnes import Jeu


def test_apparition_au_milieu_en_haut():
    j = Jeu(iter(["ABC"]), largeur=4, hauteur=6)
    assert j.col == 2
    assert j.ligne == 0
    assert j.colonne.tuiles == ("A", "B", "C")


def test_cellules_du_haut_vers_le_bas():
    j = Jeu(iter(["ABC"]), largeur=4, hauteur=6)
    assert j.cellules() == {(0, 2): "A", (1, 2): "B", (2, 2): "C"}


def test_la_colonne_en_chute_n_est_pas_sur_le_plateau():
    j = Jeu(iter(["ABC"]), largeur=4, hauteur=6)
    assert j.plateau.rendu() == "....\n....\n....\n....\n....\n...."


def test_deplacer_a_gauche_et_a_droite():
    j = Jeu(iter(["ABC"]), largeur=4, hauteur=6)
    assert j.deplacer(-1) is True
    assert j.col == 1
    assert j.deplacer(1) is True
    assert j.col == 2


def test_deplacer_refuse_de_sortir():
    j = Jeu(iter(["ABC"]), largeur=4, hauteur=6)
    assert j.deplacer(-1) is True
    assert j.deplacer(-1) is True
    assert j.col == 0
    assert j.deplacer(-1) is False
    assert j.col == 0


def test_deplacer_refuse_une_colonne_occupee():
    j = Jeu(iter(["ABC"]), largeur=4, hauteur=6)
    j.plateau.poser(1, 1, "Z")
    assert j.deplacer(-1) is False
    assert j.col == 2


def test_cycler_le_jeu():
    j = Jeu(iter(["ABC"]), largeur=4, hauteur=6)
    assert j.cycler() is True
    assert j.colonne.tuiles == ("C", "A", "B")


def test_descendre():
    j = Jeu(iter(["ABC"]), largeur=4, hauteur=6)
    assert j.descendre() is True
    assert j.ligne == 1
    assert j.cellules() == {(1, 2): "A", (2, 2): "B", (3, 2): "C"}


def test_descendre_bloque_par_le_fond():
    j = Jeu(iter(["ABC", "DEF"]), largeur=4, hauteur=6)
    for _ in range(3):
        assert j.descendre() is True
    assert j.ligne == 3
    assert j.descendre() is False


def test_chuter_compte_les_lignes_et_verrouille():
    j = Jeu(iter(["ABC", "DEF"]), largeur=4, hauteur=6)
    assert j.chuter() == 3
    assert j.plateau.rendu() == "....\n....\n....\n..A.\n..B.\n..C."


def test_chuter_fait_apparaitre_la_suivante():
    j = Jeu(iter(["ABC", "DEF"]), largeur=4, hauteur=6)
    j.chuter()
    assert j.colonne.tuiles == ("D", "E", "F")
    assert (j.ligne, j.col) == (0, 2)


def test_chuter_s_arrete_sur_une_pile():
    j = Jeu(iter(["ABC", "DEF"]), largeur=4, hauteur=8)
    j.plateau.poser(7, 2, "Z")
    assert j.chuter() == 4
    assert j.plateau.case(6, 2) == "C"


def test_tick_descend_puis_verrouille():
    j = Jeu(iter(["ABC", "DEF"]), largeur=4, hauteur=6)
    for _ in range(3):
        j.tick()
    assert j.ligne == 3
    assert j.plateau.rendu() == "....\n....\n....\n....\n....\n...."
    j.tick()
    assert j.plateau.case(5, 2) == "C"
