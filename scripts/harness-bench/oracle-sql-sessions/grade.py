"""Correcteur CACHÉ de `sql-sessions`. Déposé dans le workdir au moment de noter
seulement — jamais pendant que le modèle travaille.

Chaque cas est un ÉTAGE indépendant, sur son propre jeu de données. Un crédit
partiel vaut mieux qu'un verdict binaire : une requête qui gère tout sauf les
horodatages en double doit se distinguer d'une requête fausse partout, et
l'inverse d'un scénario saturé comme `tetris` (44/44 chez tout le monde depuis
juillet).

Aucun de ces cas n'apparaît dans `graine.sql` ni dans `verifie_visible.py` : le
contrôle visible porte sur des données sages, celui-ci sur ce que le contrat dit
et que les données ne montrent pas. Un modèle qui lit les données au lieu du
contrat passe le premier et échoue ici.
"""

import json
import sqlite3
import sys
from pathlib import Path

SCHEMA = """CREATE TABLE evenements (
  utilisateur INTEGER NOT NULL,
  horodatage  TEXT    NOT NULL
)"""

COLONNES = ("utilisateur", "session", "debut", "fin", "evenements", "duree_minutes")

# nom -> (evenements, lignes attendues)
CAS = {
    # 45 min PILE reste dans la session, 45:01 coupe. C'est la seule phrase du
    # contrat qu'on ne peut pas deviner depuis des donnees sages.
    "frontiere": (
        [
            (1, "2026-05-01 10:00:00"),
            (1, "2026-05-01 10:45:00"),
            (1, "2026-05-01 11:30:01"),
        ],
        [
            (1, 1, "2026-05-01 10:00:00", "2026-05-01 10:45:00", 2, 45),
            (1, 2, "2026-05-01 11:30:01", "2026-05-01 11:30:01", 1, 0),
        ],
    ),
    # Ecart nul : deux lignes identiques ne creent pas de session, et comptent
    # toutes les deux.
    "doublons": (
        [
            (7, "2026-05-01 08:00:00"),
            (7, "2026-05-01 08:00:00"),
            (7, "2026-05-01 08:30:00"),
        ],
        [(7, 1, "2026-05-01 08:00:00", "2026-05-01 08:30:00", 3, 30)],
    ),
    # A cheval sur minuit : une soustraction sur l'heure seule donne -1410.
    "minuit": (
        [
            (3, "2026-05-01 23:40:00"),
            (3, "2026-05-02 00:10:00"),
        ],
        [(3, 1, "2026-05-01 23:40:00", "2026-05-02 00:10:00", 2, 30)],
    ),
    # Un seul evenement : session de duree 0, pas une ligne absente.
    "solitaire": (
        [(9, "2026-05-01 12:00:00")],
        [(9, 1, "2026-05-01 12:00:00", "2026-05-01 12:00:00", 1, 0)],
    ),
    # La numerotation repart a 1 par utilisateur, et le tri est par utilisateur
    # PUIS session -- pas l'ordre d'insertion, ici volontairement melange.
    "par_utilisateur": (
        [
            (2, "2026-05-01 09:00:00"),
            (1, "2026-05-01 09:00:00"),
            (2, "2026-05-01 10:00:00"),
            (1, "2026-05-01 09:10:00"),
        ],
        [
            (1, 1, "2026-05-01 09:00:00", "2026-05-01 09:10:00", 2, 10),
            (2, 1, "2026-05-01 09:00:00", "2026-05-01 09:00:00", 1, 0),
            (2, 2, "2026-05-01 10:00:00", "2026-05-01 10:00:00", 1, 0),
        ],
    ),
    # Les evenements arrivent en DESORDRE : le contrat dit « ordonner par
    # horodatage », pas « faire confiance a la table ».
    "desordre": (
        [
            (5, "2026-05-01 14:00:00"),
            (5, "2026-05-01 12:00:00"),
            (5, "2026-05-01 12:20:00"),
        ],
        [
            (5, 1, "2026-05-01 12:00:00", "2026-05-01 12:20:00", 2, 20),
            (5, 2, "2026-05-01 14:00:00", "2026-05-01 14:00:00", 1, 0),
        ],
    ),
}


def joue(requete, evenements):
    base = sqlite3.connect(":memory:")
    base.execute(SCHEMA)
    base.executemany("INSERT INTO evenements VALUES (?, ?)", evenements)
    curseur = base.execute(requete)
    noms = tuple(d[0] for d in curseur.description)
    lignes = curseur.fetchall()
    base.close()
    if noms != COLONNES:
        raise ValueError("colonnes %s au lieu de %s" % (noms, COLONNES))
    return lignes


def main(workdir):
    chemin = Path(workdir) / "reponse.sql"
    resultats = {}
    try:
        requete = chemin.read_text(encoding="utf-8").strip().rstrip(";")
    except OSError as exc:
        requete = ""
        resultats["_lecture"] = str(exc)
    for nom, (evenements, attendu) in CAS.items():
        if not requete:
            resultats[nom] = {"ok": False, "detail": "reponse.sql vide ou illisible"}
            continue
        try:
            rendu = joue(requete, evenements)
        except Exception as exc:  # noqa: BLE001 - un cas qui plante est un cas rate
            resultats[nom] = {
                "ok": False,
                "detail": "%s: %s" % (type(exc).__name__, exc),
            }
            continue
        ok = rendu == attendu
        resultats[nom] = {
            "ok": ok,
            "detail": "" if ok else "rendu %s / attendu %s" % (rendu, attendu),
        }
    print(json.dumps(resultats, ensure_ascii=False))
    return 0 if all(r.get("ok") for r in resultats.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
