"""ÉTAGE 12 — état sérialisable.

`colonnes.web.etat(jeu)` rend un `dict` que `json.dumps` accepte tel quel, décrivant
l'état complet du jeu. Clés EXACTES :

    largeur, hauteur      : les dimensions (int)
    plateau               : liste de `hauteur` chaînes de `largeur` caractères,
                            comme `Plateau.rendu()` mais découpé par ligne
    colonne               : liste des trois tuiles en chute, ou None si la partie
                            est terminée
    ligne, col            : position de la tuile du HAUT de la colonne en chute
    score                 : int
    chaine_max            : int
    tuiles_supprimees     : int
    partie_terminee       : bool

Aucune autre clé. L'ordre des clés est libre.
"""

import json

from colonnes import Jeu
from colonnes.web import etat

CLES = {
    "largeur",
    "hauteur",
    "plateau",
    "colonne",
    "ligne",
    "col",
    "score",
    "chaine_max",
    "tuiles_supprimees",
    "partie_terminee",
}


def test_cles_exactes():
    assert set(etat(Jeu(iter(["ABC"]), largeur=4, hauteur=6))) == CLES


def test_serialisable_en_json():
    e = etat(Jeu(iter(["ABC"]), largeur=4, hauteur=6))
    assert json.loads(json.dumps(e)) == e


def test_dimensions_et_plateau():
    e = etat(Jeu(iter(["ABC"]), largeur=4, hauteur=6))
    assert (e["largeur"], e["hauteur"]) == (4, 6)
    assert e["plateau"] == ["...."] * 6


def test_plateau_reflete_les_tuiles():
    j = Jeu(iter([]), largeur=4, hauteur=3)
    j.plateau.poser(0, 0, "A")
    j.plateau.poser(2, 3, "B")
    assert etat(j)["plateau"] == ["A...", "....", "...B"]


def test_colonne_et_position():
    e = etat(Jeu(iter(["ABC"]), largeur=4, hauteur=6))
    assert e["colonne"] == ["A", "B", "C"]
    assert (e["ligne"], e["col"]) == (0, 2)


def test_colonne_nulle_apres_la_fin():
    j = Jeu(iter(["ABC"]), largeur=4, hauteur=6)
    j.chuter()
    e = etat(j)
    assert e["colonne"] is None
    assert e["partie_terminee"] is True


def test_compteurs():
    j = Jeu(iter(["XYA", "DEF"]), largeur=4, hauteur=6)
    j.plateau.poser(5, 1, "A")
    j.plateau.poser(5, 3, "A")
    j.chuter()
    e = etat(j)
    assert e["score"] == 30
    assert e["chaine_max"] == 1
    assert e["tuiles_supprimees"] == 3


def test_types_json_natifs():
    """Pas de tuple ni d'objet : `json.dumps` doit passer sans `default=`."""
    e = etat(Jeu(iter(["ABC"]), largeur=4, hauteur=6))
    assert isinstance(e["plateau"], list)
    assert isinstance(e["colonne"], list)
    assert isinstance(e["partie_terminee"], bool)
    assert all(isinstance(x, int) for x in (e["score"], e["ligne"], e["col"]))
