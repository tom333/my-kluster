"""PORTE D'ENTRÉE d'un nouveau modèle : ses tool-calls sont-ils parsés, oui ou non ?

Motif (2026-08-06, calibration de KAT-Coder-V2.5-Dev). Sa fiche officielle
recommande `--tool-call-parser qwen3_coder`, un drapeau de vLLM/SGLang que
llama.cpp n'a pas : il s'appuie sur le gabarit Jinja embarqué dans le GGUF
(`--jinja`). Rien ne garantit que les deux chemins produisent le même résultat.

Or `call_format: text_fallback` dans un résultat de banc veut dire que le modèle a
DÉCRIT ses appels en prose au lieu de les émettre : le score qui en sort ne mesure
plus le modèle, il mesure notre tolérance au repli. Cette sonde le tranche en une
requête, avant d'engager des heures de campagne.

On envoie les SCHÉMAS RÉELS du harnais, pas un jouet — c'est leur nombre et leur
forme qui font le comportement. Et on compare les deux régimes de la fiche :
pensée active (temp 1.0 / top_p 0.95) contre mode instruct (temp 0.7 / top_p 0.8,
`enable_thinking: false`).

    python3 sonde_outils.py
    python3 sonde_outils.py --port 8080 --max-tokens 2048
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

# Les schemas du harnais lui-meme : la sonde doit tester ce que le banc envoie.
sys.path.insert(0, "/data/projets/perso/harnais-nu")
from outils import SCHEMAS  # noqa: E402

# Tache choisie pour qu'un seul appel d'outil soit la reponse EVIDENTE. Si le modele
# n'appelle pas `read` ici, il n'appellera rien sur une tache reelle.
TACHE = (
    "Le fichier `diff/lessons.py` de ce depot contient une fonction `_content_key`. "
    "Lis-la et dis-moi ce qu'elle renvoie. N'invente rien : lis le fichier."
)

# Les deux regimes DOCUMENTES sur la fiche du modele, pas des valeurs inventees.
REGIMES = (
    (
        "pensée active",
        {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "presence_penalty": 1.5},
        None,
    ),
    (
        "mode instruct",
        {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 1.5},
        {"enable_thinking": False},
    ),
)


def sonde(client, echantillonnage, gabarit, max_tokens):
    charge = {
        "model": "x",
        "messages": [{"role": "user", "content": TACHE}],
        "tools": SCHEMAS,
        "max_tokens": max_tokens,
    }
    charge.update(echantillonnage)
    if gabarit:
        charge["chat_template_kwargs"] = gabarit
    try:
        rep = client.post("/v1/chat/completions", json=charge)
    except httpx.HTTPError as exc:
        return {"panne": str(exc)}
    if rep.status_code != 200:
        # Le CORPS, jamais la seule ligne de statut : c'est lui qui dit pourquoi.
        return {"panne": "HTTP %d — %s" % (rep.status_code, rep.text[:300])}
    d = rep.json()
    choix = (d.get("choices") or [{}])[0]
    msg = choix.get("message") or {}
    pensee = msg.get("reasoning_content") or ""
    t = d.get("timings") or {}
    return {
        "tool_calls": [
            (c.get("function") or {}).get("name") for c in (msg.get("tool_calls") or [])
        ],
        "arguments_valides": all(
            _json_ok((c.get("function") or {}).get("arguments"))
            for c in (msg.get("tool_calls") or [])
        ),
        "contenu": len(msg.get("content") or ""),
        "pensee": len(pensee),
        "finish": choix.get("finish_reason"),
        "debit": round(t.get("predicted_per_second") or 0, 1),
        "generes": t.get("predicted_n"),
    }


def _json_ok(texte):
    """Des arguments qui ne parsent pas = un appel inutilisable, meme s'il est la.

    C'est exactement le 500 « Failed to parse tool call arguments as JSON » que la
    boucle rattrape en reessayant : le detecter ici coute une requete au lieu d'un
    tirage entier.
    """
    if not texte:
        return False
    try:
        json.loads(texte)
    except (ValueError, TypeError):
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--max-tokens", type=int, default=2048)
    args = parser.parse_args()

    client = httpx.Client(base_url="http://127.0.0.1:%d" % args.port, timeout=600)
    modele = "?"
    try:
        modele = str(
            (client.get("/v1/models").json().get("models") or [{}])[0].get("model")
        )
    except (httpx.HTTPError, ValueError, KeyError, IndexError):
        pass
    print("modele servi : %s" % Path(modele).name)
    print(
        "schemas envoyes : %d (%s)"
        % (len(SCHEMAS), ", ".join(s["function"]["name"] for s in SCHEMAS))
    )

    verdicts = []
    for nom, echantillonnage, gabarit in REGIMES:
        r = sonde(client, echantillonnage, gabarit, args.max_tokens)
        print("\n-- %s --" % nom)
        if "panne" in r:
            print("   PANNE : %s" % r["panne"])
            verdicts.append((nom, False))
            continue
        print("   tool_calls        : %s" % (r["tool_calls"] or "AUCUN"))
        print(
            "   arguments JSON    : %s"
            % ("valides" if r["arguments_valides"] else "NON")
        )
        print("   contenu / pensee  : %d / %d caracteres" % (r["contenu"], r["pensee"]))
        print("   finish_reason     : %s" % r["finish"])
        print(
            "   debit             : %s tok/s sur %s tokens" % (r["debit"], r["generes"])
        )
        ok = bool(r["tool_calls"]) and r["arguments_valides"]
        verdicts.append((nom, ok))

    print("\n=== VERDICT ===")
    for nom, ok in verdicts:
        print(
            "%-16s %s"
            % (nom, "appels d'outils NATIFS" if ok else "PAS D'APPEL EXPLOITABLE")
        )
    # Sortie non nulle si AUCUN regime ne marche : la porte doit pouvoir bloquer une
    # campagne depuis un script, pas seulement s'afficher.
    return 0 if any(ok for _, ok in verdicts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
