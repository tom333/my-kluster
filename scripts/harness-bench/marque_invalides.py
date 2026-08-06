"""Marque les campagnes mesurees SOUS UN DEFAUT DU BANC, sans les supprimer.

Motif (2026-08-06). La fuite d'environnement corrigee en 365f9e8 / 0ec9e4f5 faisait
heriter l'agent du venv DU HARNAIS : son `python` n'avait pas `homeassistant`, il en
deduisait qu'il devait simuler les imports, et brulait des dizaines d'appels `bash`
a fabriquer des `MockHA`. Effet mesure sur a3b/pronote, memes graines :
PASS 2/5 -> 4/5, mediane 3/5 -> 5/5.

POURQUOI MARQUER ET NON SUPPRIMER. Supprimer detruirait la seule preuve de ce que
le correctif a achete : la comparaison 2/5 contre 4/5 n'existe QUE parce que la
campagne polluee a ete gardee. Mais les laisser sans marque est un vrai risque, et
pas theorique -- `inventaire.py` lit tous les `results/*.json` sans distinction et
les a deja moyennes une fois ce matin.

On ne marque que ce qui est MESURE, pas ce qui est suppose : les campagnes du
scenario `pronote` anterieures au correctif. Les autres scenarios ne declarent
aucun venv (`columns-web` tournait sur `/usr/bin/pytest`), la fuite y mordait donc
probablement moins -- mais ce n'est pas mesure, et c'est dit plutot que suppose.

    python3 marque_invalides.py --verifier   # liste sans rien ecrire
    python3 marque_invalides.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"

# Correctif de la fuite : commits 365f9e8 (harnais-nu) et 0ec9e4f5 (banc).
BASCULE = "20260806-1808"  # horodatage de la 1re campagne mesuree en env propre
MOTIF = (
    "fuite d'environnement : l'agent heritait du venv du harnais (sans "
    "homeassistant) au lieu de celui du sujet. Corrige le 2026-08-06 "
    "(harnais-nu 365f9e8, banc 0ec9e4f5). Effet mesure sur a3b/pronote memes "
    "graines : PASS 2/5 -> 4/5. Conserve comme mesure de la FUITE, pas du modele."
)


def concernees():
    """Campagnes `pronote` anterieures a la bascule. L'horodatage est dans le nom."""
    for chemin in sorted(RESULTS.glob("pronote-*.json")):
        horo = chemin.stem.rsplit("-", 2)[-2:]
        if len(horo) != 2:
            continue
        if "-".join(horo) < BASCULE:
            yield chemin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verifier", action="store_true", help="liste sans ecrire")
    args = parser.parse_args()

    for chemin in concernees():
        try:
            d = json.loads(chemin.read_text())
        except (ValueError, OSError) as exc:
            print("  ILLISIBLE %s : %s" % (chemin.name, exc))
            continue
        deja = d.get("invalide")
        print("  %-58s %s" % (chemin.name, "deja marque" if deja else "A MARQUER"))
        if deja or args.verifier:
            continue
        d["invalide"] = MOTIF
        chemin.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
