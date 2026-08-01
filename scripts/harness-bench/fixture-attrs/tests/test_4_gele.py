"""ÉTAGE 4 — `inventaire.gele`.

`Reference(code, revision)` : une classe **gelée** (immuable).

- Toute affectation d'attribut lève une erreur d'attrs (`FrozenInstanceError`,
  qui dérive d'`AttributeError`).
- Une instance gelée est **hachable** : utilisable en clé de dictionnaire et
  dans un ensemble, deux instances égales donnant le même hachage.
- `suivante(reference)` → copie avec `revision` incrémentée de 1.
"""

import pytest

from inventaire.gele import Reference, suivante


def test_construction():
    r = Reference("AB-12", 1)
    assert (r.code, r.revision) == ("AB-12", 1)


def test_affectation_refusee():
    r = Reference("AB-12", 1)
    with pytest.raises(AttributeError):
        r.revision = 2


def test_hachable():
    assert {Reference("AB-12", 1): "ok"}[Reference("AB-12", 1)] == "ok"


def test_egales_donnent_le_meme_hachage():
    assert hash(Reference("AB-12", 1)) == hash(Reference("AB-12", 1))


def test_ensemble_dedoublonne():
    assert len({Reference("A", 1), Reference("A", 1), Reference("B", 1)}) == 2


def test_suivante_incremente_sans_muter():
    r = Reference("AB-12", 1)
    s = suivante(r)
    assert s.revision == 2
    assert r.revision == 1
    assert s.code == "AB-12"
