"""ÉTAGE 9 — score et multiplicateurs de chaîne.

À chaque passage d'une cascade, le score augmente de :

    nombre de cases supprimées à ce passage  ×  10  ×  multiplicateur

où le multiplicateur dépend du RANG du passage dans la cascade :

| passage | 1 | 2 | 3 | 4 | 5 et au-delà |
|---|---|---|---|---|---|
| multiplicateur | 1 | 2 | 4 | 8 | 16 |

`Jeu.score` part de 0 et cumule sur toute la partie.
"""

from colonnes import Jeu


def test_score_initial():
    assert Jeu(iter(["ABC"]), largeur=4, hauteur=6).score == 0


def test_un_verrouillage_sans_alignement_ne_marque_rien():
    j = Jeu(iter(["ABC", "DEF"]), largeur=4, hauteur=6)
    j.chuter()
    assert j.score == 0


def test_trois_tuiles_en_un_passage():
    j = Jeu(iter(["XYA", "DEF"]), largeur=4, hauteur=6)
    j.plateau.poser(5, 1, "A")
    j.plateau.poser(5, 3, "A")
    j.chuter()
    assert j.score == 30


def test_quatre_tuiles_en_un_passage():
    """Le score est proportionnel au nombre de CASES, pas au nombre de suites."""
    j = Jeu(iter(["XYA", "DEF"]), largeur=5, hauteur=6)
    for c in (0, 1, 3):
        j.plateau.poser(5, c, "A")
    j.chuter()
    assert j.score == 40


def test_cascade_applique_le_multiplicateur():
    """Six cases au premier passage (60), quatre au second (4 × 10 × 2 = 80)."""
    j = Jeu(iter(["BXB", "DEF"]), largeur=4, hauteur=8)
    p = j.plateau
    for ligne, tuile in ((2, "A"), (3, "B"), (4, "A"), (5, "B"), (6, "A"), (7, "A")):
        p.poser(ligne, 0, tuile)
    p.poser(3, 1, "B")
    p.poser(5, 1, "B")
    p.poser(6, 2, "P")
    p.poser(7, 2, "Q")
    j.chuter()
    assert j.chaine_max == 2
    assert j.tuiles_supprimees == 10
    assert j.score == 140


def test_le_score_cumule_sur_plusieurs_verrouillages():
    """Deux suppressions dans deux zones distinctes du plateau : le score
    s'ajoute. On décale la seconde colonne pour ne pas retomber sur les restes
    de la première."""
    j = Jeu(iter(["XYA", "XYA", "DEF"]), largeur=7, hauteur=6)
    p = j.plateau
    p.poser(5, 2, "A")
    p.poser(5, 4, "A")
    j.chuter()
    assert j.score == 30
    for _ in range(3):
        j.deplacer(-1)
    p.poser(5, 1, "A")
    p.poser(5, 2, "A")
    j.chuter()
    assert j.score == 60
