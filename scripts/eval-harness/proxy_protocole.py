#!/usr/bin/env python3
"""Proxy qui traduit le protocole agentique PROPRE d'un modèle en `tool_calls`.

POURQUOI. `lfm2.5-8b-a1b` a rendu le meilleur relevé de codage du banc d'éval
(16/18) à 144,6 tok/s, et 0/44 au tetris sur neuf essais. Motif mesuré : il
ALTERNE entre deux formats. Son format natif —
`<|tool_call_start|>[bash(command='ls')]<|tool_call_end|>` — que LocalAI parse
déjà, et une enveloppe JSON de son cru déposée dans `content` :

    {"analysis": "...", "plan": "...",
     "commands": [{"command": "ls -la", "timeout": 0}],
     "edits": []}

Taux mesuré par `porte_protocole.py` : 5/5 à contexte vide, 3/5 une fois le
contrat de 14 Ko lu. Il ne parle donc pas un protocole étranger, il en a deux.
Ce proxy accepte le second ; la conformité devrait monter à ~100 %.

POURQUOI PAS EN YAML LOCALAI. `function.response_regex` exige deux groupes
nommés, `function` et `arguments`. L'enveloppe ne contient JAMAIS le nom de
l'outil : `bash` est implicite, porté par la clé `commands`. Une expression
régulière ne peut pas fabriquer une constante absente du texte, et le client
rejetterait un outil `command` qu'il n'a pas déclaré. D'où ce code.

PRINCIPE DE SÛRETÉ : en cas de doute, on NE TOUCHE À RIEN. Une réponse déjà
pourvue de `tool_calls`, un JSON qu'on ne reconnaît pas, une forme d'`edits`
inattendue — tout cela repart tel quel. Fabriquer un appel d'outil faux serait
pire que de laisser passer l'enveloppe : on mesurerait le proxy, pas le modèle.

TRAÇABILITÉ. Chaque conversion est journalisée sur stderr et comptée. La leçon
du 2026-09-11 : une extension de vérification a été créditée d'un effet alors
qu'elle n'avait jamais tourné. Un levier sans trace n'a pas agi.

RÉSULTAT DU 2026-09-13, à lire avant de le rebrancher sur lfm2.5-8b-a1b. La porte
de protocole passée AU TRAVERS de ce proxy rend exactement le même taux que sans
lui — 5/5 à froid, 3/5 à chaud — et le journal du proxy montre ZÉRO conversion.
Les deux échecs ne sont pas des enveloppes : ce sont des « budget épuisé sans un
mot », c'est-à-dire de la rumination.

Ce modèle a donc DEUX défauts indépendants. L'enveloppe JSON est bien réelle, mais
elle n'apparaît que sous le prompt système de `pi` ; à prompt vide il rumine à la
place. Réparer le protocole ne le sauve pas : la rumination seule suffit à donner
0,6 par tour, soit 0,13 % de chances de tenir treize tours.

Le proxy reste utile pour un FUTUR candidat qui déposerait ses appels dans
`content` — il est testé unitairement sur six cas, dont trois qui doivent rester
intacts. Mais il ne rachète pas lfm, et la porte n'est pas l'instrument qui le
valide : il faudrait une campagne `pi`, seule à faire apparaître l'enveloppe.

Usage :
    LOCALAI_URL=https://localai.tgu.ovh/v1 python3 proxy_protocole.py [--port 8088]
    # puis, dans un autre terminal :
    LOCALAI_URL=http://127.0.0.1:8088/v1 python3 porte_protocole.py lfm2.5-8b-a1b
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AMONT = os.environ.get("LOCALAI_URL", "https://localai.tgu.ovh/v1").rstrip("/")
CLE = pathlib.Path(os.path.expanduser("~/.config/brain/localai-key"))
TIMEOUT = int(os.environ.get("PROXY_TIMEOUT", "900"))

# Compteurs, lus à l'arrêt. Sans eux on ne saurait pas distinguer « le proxy a
# tout réparé » de « le modèle n'a jamais eu besoin de lui ».
STATS = {"requetes": 0, "deja_conformes": 0, "converties": 0, "laissees": 0}


def _cle() -> str | None:
    if CLE.is_file():
        return CLE.read_text().strip()
    return None


def enveloppe_agent(texte: str):
    """Rend l'objet si `texte` est l'enveloppe agentique, sinon None.

    On exige la présence de `commands` OU `edits` : un JSON quelconque dans
    `content` (une réponse structurée demandée par l'utilisateur, par exemple) ne
    doit pas être transformé en appels d'outils.
    """
    t = (texte or "").strip()
    if t.startswith("```"):
        # Clôture de code : on retire la première et la dernière ligne.
        lignes = t.splitlines()
        t = "\n".join(lignes[1:-1] if len(lignes) > 2 else lignes).strip()
    if not t.startswith("{"):
        return None
    try:
        obj = json.loads(t)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    if not isinstance(obj.get("commands"), list) and not isinstance(
        obj.get("edits"), list
    ):
        return None
    return obj


def en_tool_calls(obj: dict):
    """Traduit l'enveloppe en appels d'outils. Rend None si RIEN n'est traduisible.

    Les noms d'outils sont ceux que `pi` déclare : `bash`, `write`, `edit`. Une
    entrée dont la forme ne correspond à aucun des trois est IGNORÉE plutôt que
    devinée — et si toutes le sont, on rend None et la réponse repart intacte.
    """
    appels = []
    for i, c in enumerate(obj.get("commands") or []):
        cmd = (
            c.get("command")
            if isinstance(c, dict)
            else (c if isinstance(c, str) else None)
        )
        if not cmd:
            continue
        appels.append(("bash", {"command": cmd}))
    for e in obj.get("edits") or []:
        if not isinstance(e, dict):
            continue
        chemin = e.get("path") or e.get("file") or e.get("filename")
        if not chemin:
            continue
        if e.get("content") is not None:
            appels.append(("write", {"path": chemin, "content": e["content"]}))
        elif e.get("oldText") is not None and e.get("newText") is not None:
            appels.append(
                (
                    "edit",
                    {"path": chemin, "oldText": e["oldText"], "newText": e["newText"]},
                )
            )
        # Toute autre forme : ignorée volontairement.
    if not appels:
        return None
    return [
        {
            "index": i,
            "id": "proxy_%d" % i,
            "type": "function",
            "function": {
                "name": nom,
                "arguments": json.dumps(args, ensure_ascii=False),
            },
        }
        for i, (nom, args) in enumerate(appels)
    ]


def traduire(reponse: dict) -> dict:
    """Réécrit la réponse en place si l'enveloppe est reconnue."""
    for choix in reponse.get("choices") or []:
        msg = choix.get("message") or {}
        if msg.get("tool_calls"):
            STATS["deja_conformes"] += 1
            continue
        obj = enveloppe_agent(msg.get("content") or "")
        if obj is None:
            STATS["laissees"] += 1
            continue
        appels = en_tool_calls(obj)
        if appels is None:
            STATS["laissees"] += 1
            print(
                "[proxy] enveloppe reconnue mais RIEN de traduisible — laissée "
                "telle quelle",
                file=sys.stderr,
            )
            continue
        msg["tool_calls"] = appels
        msg["content"] = ""
        choix["finish_reason"] = "tool_calls"
        STATS["converties"] += 1
        print(
            "[proxy] enveloppe -> %d appel(s) : %s"
            % (len(appels), ", ".join(a["function"]["name"] for a in appels)),
            file=sys.stderr,
        )
    return reponse


def sse(reponse: dict):
    """Rejoue une réponse complète en un flux SSE minimal.

    Le proxy demande TOUJOURS du non-flux à l'amont : on ne peut pas réécrire une
    enveloppe qu'on n'a pas encore reçue en entier. Si le client voulait du flux,
    on le lui resynthétise ici. C'est suffisant pour un client qui accumule les
    deltas, et ça ne prétend pas reproduire la granularité d'origine.
    """
    choix = (reponse.get("choices") or [{}])[0]
    msg = choix.get("message") or {}
    base = {
        "id": reponse.get("id", "proxy"),
        "object": "chat.completion.chunk",
        "created": reponse.get("created", 0),
        "model": reponse.get("model", ""),
    }
    morceaux = [
        {
            **base,
            "choices": [
                {"index": 0, "finish_reason": None, "delta": {"role": "assistant"}}
            ],
        }
    ]
    if msg.get("tool_calls"):
        morceaux.append(
            {
                **base,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": None,
                        "delta": {"tool_calls": msg["tool_calls"]},
                    }
                ],
            }
        )
    elif msg.get("content"):
        morceaux.append(
            {
                **base,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": None,
                        "delta": {"content": msg["content"]},
                    }
                ],
            }
        )
    morceaux.append(
        {
            **base,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": choix.get("finish_reason", "stop"),
                }
            ],
            "usage": reponse.get("usage"),
        }
    )
    out = b""
    for m in morceaux:
        out += b"data: " + json.dumps(m, ensure_ascii=False).encode() + b"\n\n"
    return out + b"data: [DONE]\n\n"


class Poignee(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # silence : on journalise nous-mêmes
        pass

    def _amont(self, chemin: str, corps: bytes | None, methode: str):
        req = urllib.request.Request(AMONT + chemin, data=corps, method=methode)
        req.add_header("Content-Type", "application/json")
        cle = _cle()
        if cle:
            req.add_header("Authorization", "Bearer " + cle)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read(), r.status

    def _repondre(
        self, corps: bytes, statut: int = 200, ctype: str = "application/json"
    ):
        self.send_response(statut)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        chemin = self.path.split("/v1", 1)[-1] if "/v1" in self.path else self.path
        try:
            brut, statut = self._amont(chemin, None, "GET")
            self._repondre(brut, statut)
        except (urllib.error.URLError, OSError) as e:
            self._repondre(json.dumps({"error": str(e)}).encode(), 502)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        brut = self.rfile.read(n)
        chemin = self.path.split("/v1", 1)[-1] if "/v1" in self.path else self.path
        try:
            charge = json.loads(brut)
        except json.JSONDecodeError:
            charge = None

        flux_demande = bool(isinstance(charge, dict) and charge.get("stream"))
        if isinstance(charge, dict) and flux_demande:
            # On ne peut pas réécrire ce qu'on n'a pas reçu en entier.
            charge = {**charge, "stream": False}
            charge.pop("stream_options", None)
            brut = json.dumps(charge).encode()

        STATS["requetes"] += 1
        try:
            rep_brute, statut = self._amont(chemin, brut, "POST")
        except urllib.error.HTTPError as e:
            self._repondre(e.read(), e.code)
            return
        except (urllib.error.URLError, OSError) as e:
            self._repondre(json.dumps({"error": str(e)}).encode(), 502)
            return

        if "chat/completions" not in chemin:
            self._repondre(rep_brute, statut)
            return
        try:
            rep = traduire(json.loads(rep_brute))
        except json.JSONDecodeError:
            self._repondre(rep_brute, statut)  # illisible : on ne bricole pas
            return
        if flux_demande:
            self._repondre(sse(rep), statut, "text/event-stream")
        else:
            self._repondre(json.dumps(rep, ensure_ascii=False).encode(), statut)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--port", type=int, default=int(os.environ.get("PROXY_PORT", "8088"))
    )
    args = ap.parse_args()
    print("[proxy] %s  ->  %s" % (args.port, AMONT), file=sys.stderr)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Poignee)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        print(
            "[proxy] %d requête(s) : %d déjà conformes, %d converties, %d laissées"
            % (
                STATS["requetes"],
                STATS["deja_conformes"],
                STATS["converties"],
                STATS["laissees"],
            ),
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
