"""ÉTAGE 7 — suppression simultanée.

Tous les alignements d'un même passage sont trouvés ENSEMBLE, puis supprimés
ensemble. `colonnes.alignements(plateau)` rend donc une UNION : une case qui
appartient à deux suites — au croisement d'une horizontale et d'une verticale, ou
à l'intersection de deux diagonales — n'apparaît qu'une fois.

Conséquence pour le compte des tuiles supprimées : c'est le nombre de CASES, pas
la somme des longueurs des suites.
"""

from colonnes import Plateau, alignements


def test_croisement_horizontal_vertical():
    """Une horizontale de trois et une verticale de trois qui partagent une case :
    cinq cases, pas six."""
    p = Plateau(5, 5)
    for c in range(3):
        p.poser(2, c, "E")
    for l in range(3):
        p.poser(l, 1, "E")
    cases = set(alignements(p))
    assert cases == {(2, 0), (2, 1), (2, 2), (0, 1), (1, 1)}
    assert len(cases) == 5


def test_croisement_en_te():
    """La case partagée est au bout de la verticale et au milieu de
    l'horizontale."""
    p = Plateau(5, 5)
    for c in range(3):
        p.poser(0, c, "A")
    for l in range(3):
        p.poser(l, 1, "A")
    assert len(set(alignements(p))) == 5


def test_deux_diagonales_partagent_leur_centre():
    p = Plateau(3, 3)
    for i in range(3):
        p.poser(i, i, "B")
        p.poser(2 - i, i, "B")
    assert len(set(alignements(p))) == 5


def test_tuiles_differentes_ne_se_melangent_pas():
    """Deux suites de tuiles différentes qui se croisent géométriquement ne
    partagent rien : la case du croisement ne peut porter qu'une tuile."""
    p = Plateau(5, 5)
    for c in range(3):
        p.poser(2, c, "A")
    p.poser(0, 4, "B")
    p.poser(1, 4, "B")
    p.poser(2, 4, "B")
    assert set(alignements(p)) == {
        (2, 0),
        (2, 1),
        (2, 2),
        (0, 4),
        (1, 4),
        (2, 4),
    }


def test_bloc_plein_de_la_meme_tuile():
    """Un carré 3x3 de la même tuile : les neuf cases sont prises, chacune une
    fois."""
    p = Plateau(3, 3)
    for l in range(3):
        for c in range(3):
            p.poser(l, c, "F")
    assert len(set(alignements(p))) == 9
