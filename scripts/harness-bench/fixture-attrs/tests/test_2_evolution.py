"""ÉTAGE 2 — `inventaire.evolution`.

Modifier une pièce sans jamais la muter (attrs sait faire une copie modifiée).

- `renommer(piece, etiquette)` → copie avec la nouvelle étiquette.
- `redimensionner(piece, taille)` → copie avec la nouvelle taille. Les
  validateurs et convertisseurs de `Piece` s'appliquent ENCORE à la copie.
- `lot(piece, n)` → liste de `n` copies indépendantes.
"""

import pytest

from inventaire.evolution import lot, redimensionner, renommer
from inventaire.piece import Piece


def test_renommer_rend_une_copie():
    p = Piece("rouge", 2)
    q = renommer(p, "neuve")
    assert q.etiquette == "neuve"
    assert q is not p


def test_renommer_ne_mute_pas_l_original():
    p = Piece("rouge", 2, etiquette="ancienne")
    renommer(p, "neuve")
    assert p.etiquette == "ancienne"


def test_renommer_conserve_le_reste():
    q = renommer(Piece("bleu", 5), "x")
    assert (q.couleur, q.taille) == ("bleu", 5)


def test_redimensionner_convertit_aussi():
    """La copie repasse par le convertisseur : `"9"` doit devenir `9`."""
    assert redimensionner(Piece("vert", 1), "9").taille == 9


def test_redimensionner_valide_aussi():
    with pytest.raises(ValueError):
        redimensionner(Piece("vert", 1), 0)


def test_lot_rend_n_copies_egales():
    p = Piece("rouge", 2)
    copies = lot(p, 3)
    assert len(copies) == 3
    assert all(c == p for c in copies)


def test_lot_rend_des_objets_distincts():
    copies = lot(Piece("rouge", 2), 2)
    assert copies[0] is not copies[1]
