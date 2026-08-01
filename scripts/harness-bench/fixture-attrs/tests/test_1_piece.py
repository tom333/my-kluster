"""ÉTAGE 1 — `inventaire.piece.Piece`.

Une pièce d'inventaire, définie avec attrs :

- **slots** : les instances n'ont PAS de `__dict__`.
- `couleur` : chaîne, doit appartenir à `{"rouge", "vert", "bleu"}`. Sinon
  `ValueError` À LA CONSTRUCTION.
- `taille` : entier, **converti** depuis ce qu'on lui donne (`"3"` → `3`), et
  doit valoir au moins 1. Sinon `ValueError`.
- `etiquette` : optionnel, **keyword-only**, défaut `None`.

L'ordre des champs positionnels est `couleur`, puis `taille`.
"""

import pytest

from inventaire.piece import Piece


def test_construction_nominale():
    p = Piece("rouge", 3)
    assert p.couleur == "rouge"
    assert p.taille == 3
    assert p.etiquette is None


def test_les_instances_utilisent_des_slots():
    """`@define` donne des slots par défaut ; l'ancien `@attr.s` non."""
    assert not hasattr(Piece("rouge", 1), "__dict__")


def test_couleur_hors_liste_refusee():
    with pytest.raises(ValueError):
        Piece("jaune", 1)


def test_les_trois_couleurs_passent():
    for c in ("rouge", "vert", "bleu"):
        assert Piece(c, 1).couleur == c


def test_taille_convertie_depuis_une_chaine():
    p = Piece("vert", "7")
    assert p.taille == 7
    assert isinstance(p.taille, int)


def test_taille_trop_petite_refusee():
    with pytest.raises(ValueError):
        Piece("vert", 0)


def test_conversion_avant_validation():
    """La conversion passe AVANT le validateur : `"0"` doit être refusé comme
    `0`, pas accepté parce que c'est une chaîne non vide."""
    with pytest.raises(ValueError):
        Piece("vert", "0")


def test_etiquette_est_keyword_only():
    with pytest.raises(TypeError):
        Piece("bleu", 1, "trop")


def test_etiquette_nommee_acceptee():
    assert Piece("bleu", 1, etiquette="neuve").etiquette == "neuve"


def test_egalite_structurelle():
    assert Piece("rouge", 2) == Piece("rouge", 2)
    assert Piece("rouge", 2) != Piece("bleu", 2)


def test_repr_montre_les_champs():
    r = repr(Piece("rouge", 2))
    assert "Piece" in r and "rouge" in r
