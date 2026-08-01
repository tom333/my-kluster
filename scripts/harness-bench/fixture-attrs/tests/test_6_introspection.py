"""ÉTAGE 6 — `inventaire.introspection`.

attrs expose la description de ses classes : on s'en sert pour inspecter
`Piece` SANS coder en dur la liste de ses champs.

- `noms_des_champs(cls)` → tuple des noms, dans l'ordre de déclaration.
- `champs_obligatoires(cls)` → tuple des noms sans valeur par défaut.
- `est_une_classe_attrs(objet)` → bool, vrai pour une classe attrs.
"""

from inventaire.introspection import (
    champs_obligatoires,
    est_une_classe_attrs,
    noms_des_champs,
)
from inventaire.piece import Piece


def test_noms_des_champs():
    assert noms_des_champs(Piece) == ("couleur", "taille", "etiquette")


def test_champs_obligatoires():
    assert champs_obligatoires(Piece) == ("couleur", "taille")


def test_reconnait_une_classe_attrs():
    assert est_une_classe_attrs(Piece) is True


def test_rejette_ce_qui_n_en_est_pas():
    class Ordinaire:
        pass

    assert est_une_classe_attrs(Ordinaire) is False
    assert est_une_classe_attrs(int) is False
