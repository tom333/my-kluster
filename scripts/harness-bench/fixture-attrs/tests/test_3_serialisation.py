"""ÉTAGE 3 — `inventaire.serialisation`.

- `en_dict(piece)` → dictionnaire de tous les champs.
- `sans_etiquette(piece)` → même chose, mais le champ `etiquette` est EXCLU
  (attrs sait filtrer à la sérialisation).
- `Caisse(nom, pieces)` : une caisse contenant des `Piece`. `en_dict(caisse)`
  doit descendre RÉCURSIVEMENT : les pièces y sont des dictionnaires, pas des
  objets.
"""

from inventaire.piece import Piece
from inventaire.serialisation import Caisse, en_dict, sans_etiquette


def test_en_dict_rend_les_champs():
    assert en_dict(Piece("rouge", 2)) == {
        "couleur": "rouge",
        "taille": 2,
        "etiquette": None,
    }


def test_sans_etiquette_exclut_le_champ():
    d = sans_etiquette(Piece("rouge", 2, etiquette="x"))
    assert "etiquette" not in d
    assert d == {"couleur": "rouge", "taille": 2}


def test_caisse_porte_ses_pieces():
    c = Caisse("A", [Piece("rouge", 1)])
    assert c.nom == "A"
    assert c.pieces[0].couleur == "rouge"


def test_en_dict_descend_recursivement():
    d = en_dict(Caisse("A", [Piece("rouge", 1)]))
    assert d["nom"] == "A"
    assert isinstance(d["pieces"][0], dict)
    assert d["pieces"][0]["couleur"] == "rouge"


def test_caisse_vide():
    assert en_dict(Caisse("vide", []))["pieces"] == []
