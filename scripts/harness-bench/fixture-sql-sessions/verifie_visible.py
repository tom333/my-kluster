"""Contrôle VISIBLE : le modèle peut le lancer, il ne donne pas les réponses.

Contrepartie du correcteur caché. Le banc n'avait que la moitié cachée
(`scenario["oracle"]`, déposé au moment de noter) ; la moitié visible manquait, et
sans elle un modèle ne peut que deviner s'il a fini. Idée reprise de
`microbench_16` (pas de licence : rien n'en est copié, seulement la structure
`visible_check` / `grader`).

Il porte sur les données SAGES de `graine.sql` — aucun cas limite. Le passer ne
prouve rien sur 45 minutes pile, les horodatages en double ou minuit.
"""

import sqlite3
import sys
from pathlib import Path

ICI = Path(__file__).parent

ATTENDU = [
    (1, 1, "2026-03-02 08:00:00", "2026-03-02 08:40:00", 3, 40),
    (1, 2, "2026-03-02 11:15:00", "2026-03-02 11:30:00", 2, 15),
    (2, 1, "2026-03-02 09:05:00", "2026-03-02 09:47:00", 2, 42),
    (2, 2, "2026-03-02 14:00:00", "2026-03-02 14:00:00", 1, 0),
]

COLONNES = ("utilisateur", "session", "debut", "fin", "evenements", "duree_minutes")


def main():
    requete = (ICI / "reponse.sql").read_text(encoding="utf-8").strip()
    if not requete:
        print("reponse.sql est vide")
        return 1
    with sqlite3.connect(ICI / "evenements.sqlite") as base:
        curseur = base.execute(requete.rstrip(";"))
        noms = tuple(d[0] for d in curseur.description)
        lignes = curseur.fetchall()

    if noms != COLONNES:
        print("colonnes rendues : %s" % (noms,))
        print("colonnes attendues : %s" % (COLONNES,))
        return 1
    if lignes != ATTENDU:
        print("%d ligne(s) rendue(s), %d attendue(s)" % (len(lignes), len(ATTENDU)))
        for rendu, attendu in zip(lignes, ATTENDU):
            if rendu != attendu:
                print("  rendu   : %s" % (rendu,))
                print("  attendu : %s" % (attendu,))
        return 1
    print("controle visible : OK (cas simples uniquement)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
