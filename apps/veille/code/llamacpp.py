"""Watcher llama.cpp + LocalAI : ce qui arrive dans MON backend d'inférence.

Usage : python3 llamacpp.py [--jours N]
llama.cpp tague chaque commit (b12xxx, ~20 par jour) : le flux RSS brut est illisible.
Ici : releases GitHub depuis le dernier tag vu → préfiltre déterministe par mots-clés
(ce qui touche un backend CUDA, un serveur, gemma, le cache KV, les outils…) → UN appel
gemma avec le profil → Telegram. Les releases LocalAI (ce qui atterrit réellement dans le
cluster) sont toujours rapportées. État : /data/etat/llamacpp.json (dernier tag par dépôt).
"""

import datetime as dt
import json
import os
import re
import sys

import commun

SENTINELLE = "RIEN_DE_NEUF"
DEPOTS = {"llamacpp": "ggml-org/llama.cpp", "localai": "mudler/LocalAI"}
# Ce qui peut toucher le backend cuda12-llama-cpp, le serveur ou gemma-4 chez nous.
GARDE = re.compile(
    r"cuda|cublas|mmq|mma|flash.?att|kv.?cache|\bkv\b|gemma|gguf|quant|q4_0|q4_k|imatrix"
    r"|server|tool.?call|grammar|jinja|template|chat|specul|draft|\bmtp\b|\bswa\b|context"
    r"|rope|sampl|embedd|rerank|batch|\boom\b|vram|memory leak|multimodal|mmproj|vision",
    re.I,
)
# Un titre qui ne parle que d'un AUTRE backend : hors sujet, quel que soit le reste.
AUTRE_BACKEND = re.compile(
    r"metal|apple|macos|\bios\b|\bhip\b|rocm|musa|sycl|vulkan|opencl|webgpu|cann|openvino"
    r"|zdnn|\brpc\b|android|kleidi|\barm\b|aarch64|riscv|wasm|s390|ppc|\bcpu\b",
    re.I,
)
CONSIGNE = (
    "CONTRAT DE SORTIE. Texte brut Telegram en français, sans Markdown. Blocs séparés par une "
    "ligne '———'. Chaque item porte son lien EXACT sur une ligne '🔗 '. N'invente ni version "
    "ni chiffre. Sous 3000 caractères. Aucune introduction ni conclusion.\n\n"
    "PROFIL DE L'UTILISATEUR :\n%s\n\n"
    "Tu reçois des releases récentes de llama.cpp (déjà préfiltrées : titre + description de "
    "la PR) et de LocalAI. Chez l'utilisateur, llama.cpp n'arrive que par le backend "
    "cuda12-llama-cpp de LocalAI : un changement llama.cpp est un gain FUTUR, pas immédiat.\n"
    "🧰 LocalAI — pour CHAQUE release : version, ce qui change concrètement pour sa config "
    "(backend llama.cpp, gemma-4, API), s'il doit agir.\n"
    "🔧 llama.cpp — max 5 items qui changent VRAIMENT quelque chose pour un backend CUDA sur "
    "RTX 3060 servant gemma-4-12b-it-qat en appel d'outils. Chaque item : une ligne de titre "
    "avec emoji qui nomme le changement, puis une phrase « chez nous : » (effet concret, réglage "
    "à toucher, risque). Exemple de forme, à ne pas recopier : « 🧩 Parseur PEG des arguments "
    "d'outils » / « chez nous : appels d'outils gemma plus fiables au prochain backend ; risque : "
    "schémas plus stricts ». Ignore les items périphériques (refactor, CI, "
    "autres backends, conversion de modèles qu'il n'utilise pas). Le titre exact de la PR "
    "n'est pas requis, le lien l'est.\n"
    "Si rien ne mérite d'être rapporté dans les deux sections : réponds exactement %s."
)


def releases(depot, dernier_tag, depuis_iso, maximum=300):
    """Releases plus récentes que `dernier_tag` (ou que `depuis_iso` sans état)."""
    h = {"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"]}
    out, page = [], 1
    while len(out) < maximum:
        lot = commun.http(
            "https://api.github.com/repos/%s/releases?per_page=100&page=%d"
            % (depot, page),
            headers=h,
            timeout=60,
        )
        if not lot:
            break
        for r in lot:
            if r["tag_name"] == dernier_tag or r["published_at"] < depuis_iso:
                return out
            out.append(r)
        page += 1
    return out


def pr_texte(corps):
    """Titre + description de la PR (bloc <details>), sans la liste des binaires."""
    m = re.search(r"<details open>(.*?)</details>", corps or "", re.S)
    t = (m.group(1) if m else corps or "").strip()
    t = re.sub(r"^Title:\s*", "", t)
    return " ".join(t.split())[:600]


def main():
    jours = int(sys.argv[sys.argv.index("--jours") + 1]) if "--jours" in sys.argv else 2
    depuis_iso = (commun.maintenant() - dt.timedelta(days=jours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    etat = commun.lire_etat("llamacpp", {})
    neuf = {k: releases(v, etat.get(k), depuis_iso) for k, v in DEPOTS.items()}
    gardes = [
        r
        for r in neuf["llamacpp"]
        if GARDE.search(pr_texte(r["body"]))
        and not AUTRE_BACKEND.search(pr_texte(r["body"])[:120])
    ]
    print(
        "  llama.cpp : %d release(s), %d gardée(s) ; LocalAI : %d"
        % (len(neuf["llamacpp"]), len(gardes), len(neuf["localai"])),
        flush=True,
    )
    bilan = "rien de neuf"
    if gardes or neuf["localai"]:
        items = {
            "localai": [
                {
                    "version": r["tag_name"],
                    "date": r["published_at"][:10],
                    "lien": r["html_url"],
                    "notes": " ".join((r["body"] or "").split())[:1500],
                }
                for r in neuf["localai"]
            ],
            "llamacpp": [
                {
                    "tag": r["tag_name"],
                    "date": r["published_at"][:10],
                    "lien": r["html_url"],
                    "pr": pr_texte(r["body"]),
                }
                for r in gardes
            ],
        }
        texte = commun.llm(
            CONSIGNE % (commun.profil(), SENTINELLE),
            json.dumps(items, ensure_ascii=False),
        )
        if not texte:
            raise RuntimeError("le modèle a rendu un contenu vide")
        if SENTINELLE in texte[:80] and len(texte) < 120:
            bilan = "silence (rien de notable)"
        else:
            n = commun.telegram(texte)
            try:
                docs = commun.indexer("llamacpp", texte)
            except Exception as e:
                docs = "échec (%s)" % e
            bilan = "%d message(s), %d car., txtai %s" % (n, len(texte), docs)
    # État écrit APRÈS l'envoi : un envoi raté rejoue les mêmes releases au run suivant.
    for k in DEPOTS:
        if neuf[k]:
            etat[k] = neuf[k][0]["tag_name"]
    commun.ecrire_etat("llamacpp", etat)
    print("  bilan : " + bilan, flush=True)


if __name__ == "__main__":
    commun.principal("llamacpp", main)
