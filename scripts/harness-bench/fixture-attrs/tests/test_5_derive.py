"""ÉTAGE 5 — `inventaire.derive`.

`Etiquette(prefixe, numero)` : un champ CALCULÉ après l'initialisation.

- `complet` : n'est PAS passé au constructeur. Il vaut `"<prefixe>-<numero>"`,
  calculé à la construction (attrs offre un point d'entrée de
  post-initialisation).
- `numero` est converti en entier.
- Passer `complet` au constructeur lève `TypeError`.
"""

import pytest

from inventaire.derive import Etiquette


def test_champ_calcule():
    assert Etiquette("AB", 7).complet == "AB-7"


def test_numero_converti():
    e = Etiquette("AB", "7")
    assert e.numero == 7
    assert e.complet == "AB-7"


def test_complet_refuse_au_constructeur():
    with pytest.raises(TypeError):
        Etiquette("AB", 7, "AB-7")


def test_deux_instances_ont_leur_propre_valeur():
    assert Etiquette("A", 1).complet == "A-1"
    assert Etiquette("B", 2).complet == "B-2"


def test_egalite_tient_compte_du_calcule():
    assert Etiquette("A", 1) == Etiquette("A", "1")
