"""Petit client de protocole, PARTAGÉ par le contrôle visible et le correcteur.

Il est dans la fixture — donc visible — et c'est voulu : c'est de l'outillage de
test, pas une réponse. Il ne dit rien de l'autorité du serveur, de ce que reçoit
un client tardif, ni de l'ordre des ticks. Les cas qui sondent ça vivent dans le
correcteur caché.
"""

import asyncio
import contextlib
import json
import socket
import subprocess
import sys
from pathlib import Path

DELAI = 5.0


def port_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Serveur:
    """Lance `serveur.py` et l'arrête, quoi qu'il arrive."""

    def __init__(self, racine, port=None):
        self.racine = Path(racine)
        self.port = port or port_libre()
        self.proc = None

    async def __aenter__(self):
        self.proc = subprocess.Popen(
            [sys.executable, "serveur.py", "--port", str(self.port)],
            cwd=str(self.racine),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Attendre que le port accepte, plutôt qu'un sleep arbitraire.
        limite = asyncio.get_event_loop().time() + 15.0
        while asyncio.get_event_loop().time() < limite:
            if self.proc.poll() is not None:
                # DIRE POURQUOI. Un « s'est arrete au demarrage » nu fait passer
                # un defaut d'environnement (module absent, port pris) pour un
                # defaut du modele -- piege paye a l'ecriture meme de ce fichier.
                _, err = self.proc.communicate()
                fin = (err or b"").decode("utf-8", "replace").strip().splitlines()
                raise RuntimeError(
                    "serveur.py s'est arrete au demarrage : %s"
                    % (fin[-1] if fin else "aucune sortie d'erreur")
                )
            with contextlib.suppress(OSError), socket.socket() as s:
                s.settimeout(0.3)
                s.connect(("127.0.0.1", self.port))
                return self
            await asyncio.sleep(0.2)
        raise TimeoutError("serveur.py n'ecoute pas sur le port %d" % self.port)

    async def __aexit__(self, *_):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            with contextlib.suppress(Exception):
                self.proc.wait(timeout=5)
            if self.proc.poll() is None:
                self.proc.kill()


class Joueur:
    """Une connexion. `entrer` rend le message de bienvenue."""

    def __init__(self, port, jeton):
        self.url = "ws://127.0.0.1:%d/ws" % port
        self.jeton = jeton
        self.ws = None

    async def __aenter__(self):
        import websockets

        self.ws = await asyncio.wait_for(websockets.connect(self.url), DELAI)
        return self

    async def __aexit__(self, *_):
        if self.ws is not None:
            with contextlib.suppress(Exception):
                await self.ws.close()

    async def envoyer(self, **message):
        await asyncio.wait_for(self.ws.send(json.dumps(message)), DELAI)

    async def entrer(self):
        await self.envoyer(type="entrer", jeton=self.jeton)
        return await self.attendre("bienvenue")

    async def bouger(self, dx, dy):
        await self.envoyer(type="bouger", dx=dx, dy=dy)

    async def attendre(self, type_attendu, delai=DELAI):
        """Premier message du type demandé, en ignorant les autres."""
        limite = asyncio.get_event_loop().time() + delai
        while True:
            restant = limite - asyncio.get_event_loop().time()
            if restant <= 0:
                raise TimeoutError(
                    "aucun message `%s` en %.1fs" % (type_attendu, delai)
                )
            brut = await asyncio.wait_for(self.ws.recv(), restant)
            message = json.loads(brut)
            if message.get("type") == type_attendu:
                return message

    async def etat_apres(self, tick_minimum=0, delai=DELAI):
        """Un `etat` dont le tick dépasse `tick_minimum` : sinon on lirait l'état
        d'avant l'action qu'on vient de déclencher."""
        limite = asyncio.get_event_loop().time() + delai
        while True:
            restant = limite - asyncio.get_event_loop().time()
            if restant <= 0:
                raise TimeoutError("aucun `etat` apres le tick %d" % tick_minimum)
            message = await self.attendre("etat", restant)
            if message.get("tick", 0) > tick_minimum:
                return message
