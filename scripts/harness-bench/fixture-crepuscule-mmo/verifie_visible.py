"""Contrôle VISIBLE. Deux joueurs entrent et bougent, c'est tout.

Il ne sonde AUCUNE des décisions de conception : ni l'autorité du serveur sur un
déplacement illégal, ni ce que reçoit un client arrivé en retard, ni la
convergence quand deux joueurs bougent en même temps, ni la reconnexion. Une
conception naïve — le serveur applique ce que le client annonce, et ne diffuse
que les changements — passe ce contrôle sans faute.

C'est la moitié du dispositif. L'autre est cachée.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from protocole import Joueur, Serveur  # noqa: E402

ICI = Path(__file__).parent


async def scenario():
    async with Serveur(ICI) as serveur:
        async with Joueur(serveur.port, "alice") as alice:
            bienvenue = await alice.entrer()
            if (bienvenue.get("x"), bienvenue.get("y")) != (0, 0):
                return "alice entre en (%s, %s), attendu (0, 0)" % (
                    bienvenue.get("x"),
                    bienvenue.get("y"),
                )
            async with Joueur(serveur.port, "bob") as bob:
                await bob.entrer()
                depart = await alice.etat_apres()
                await alice.bouger(1, 0)
                apres = await alice.etat_apres(depart["tick"])
                positions = apres.get("joueurs") or {}
                if list(positions.values()).count([1, 0]) != 1:
                    return "apres un pas vers la droite : joueurs = %s" % (positions,)
                if len(positions) != 2:
                    return "%d joueur(s) dans l'etat, 2 attendus" % len(positions)
    return None


def main():
    try:
        probleme = asyncio.run(asyncio.wait_for(scenario(), 60))
    except Exception as exc:  # noqa: BLE001 - un controle ne doit jamais tracer
        print("%s: %s" % (type(exc).__name__, exc))
        return 1
    if probleme:
        print(probleme)
        return 1
    print("controle visible : OK (deux joueurs, un deplacement legal)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
