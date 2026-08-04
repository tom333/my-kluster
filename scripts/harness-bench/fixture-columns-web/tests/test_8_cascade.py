"""ÉTAGE 8 — gravité et cascades.

Après une suppression, ce qui restait au-dessus TOMBE, et cette chute peut créer de
nouveaux alignements, qui sont supprimés à leur tour : c'est une cascade.

- `Plateau.tasser()` : dans chaque colonne, les tuiles tombent jusqu'à reposer sur
  le fond ou sur une autre tuile. Leur ORDRE relatif est conservé. Les colonnes
  sont indépendantes : rien ne se déplace latéralement.
- Au verrouillage d'une colonne, le jeu répète : chercher les alignements, les
  supprimer tous, tasser — jusqu'à ce qu'il n'y ait plus d'alignement.
- `Jeu.chaine_max` : le plus grand nombre de passages consécutifs qu'un
  verrouillage a déclenché. Un verrouillage sans alignement laisse `chaine_max`
  à 0 ; un verrouillage qui supprime une fois le met à 1 ; une cascade à 2.
- `Jeu.tuiles_supprimees` : le total des cases supprimées depuis le début.
"""

from colonnes import Jeu, Plateau


def test_tasser_fait_tomber_une_tuile_isolee():
    p = Plateau(3, 4)
    p.poser(0, 1, "A")
    p.tasser()
    assert p.case(3, 1) == "A"
    assert p.libre(0, 1)


def test_tasser_conserve_l_ordre():
    p = Plateau(2, 5)
    p.poser(0, 0, "A")
    p.poser(2, 0, "B")
    p.poser(4, 0, "C")
    p.tasser()
    assert [p.case(l, 0) for l in range(5)] == [None, None, "A", "B", "C"]


def test_tasser_ne_deplace_pas_lateralement():
    p = Plateau(3, 3)
    p.poser(0, 2, "A")
    p.tasser()
    assert p.case(2, 2) == "A"
    assert all(p.libre(l, 0) for l in range(3))


def test_un_verrouillage_sans_alignement_ne_declenche_rien():
    j = Jeu(iter(["ABC", "DEF"]), largeur=4, hauteur=6)
    j.chuter()
    assert j.chaine_max == 0
    assert j.tuiles_supprimees == 0


def test_une_suppression_simple_compte_une_chaine():
    j = Jeu(iter(["XYA", "DEF"]), largeur=4, hauteur=6)
    j.plateau.poser(5, 1, "A")
    j.plateau.poser(5, 3, "A")
    j.chuter()
    assert j.chaine_max == 1
    assert j.tuiles_supprimees == 3


def test_cascade_de_deux_passages():
    """Le B qui coupait la suite verticale des A part avec un alignement
    horizontal ; les trois A se rejoignent en tombant."""
    j = Jeu(iter(["XYB", "DEF"]), largeur=4, hauteur=8)
    p = j.plateau
    p.poser(4, 0, "A")
    p.poser(5, 0, "B")
    p.poser(6, 0, "A")
    p.poser(7, 0, "A")
    p.poser(5, 1, "B")
    p.poser(6, 2, "P")
    p.poser(7, 2, "Q")
    assert j.chuter() == 3
    assert j.chaine_max == 2
    assert j.tuiles_supprimees == 6
    assert p.rendu() == "....\n....\n....\n....\n..X.\n..Y.\n..P.\n..Q."
