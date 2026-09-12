#!/usr/bin/env python3
"""Veille sur le cache LRU d'experts MoE de llama.cpp (PR ggml-org/llama.cpp#27861).

POURQUOI CE WATCHER. Sur cette carte, tout MoE plus gros que ~10 Go doit déporter
une partie de ses experts en RAM hôte, et ce déport coûte très cher : mesuré le
2026-09-11 sur `qwen3-coder-30b` à `n_cpu_moe=34`, le débit effectif tombe à
6,7 tok/s contre 25,7 mesurés au chargement — 74 % du temps part à relire les
poids des experts depuis la RAM à chaque token.

La PR #27861 sert les experts RÉCEMMENT UTILISÉS depuis la VRAM au lieu de la RAM.
Mesuré par son auteur sur Qwen3.8-Flash-Next : décodage 18,4 -> 24,2 tok/s (+31 %)
avec 48 emplacements par couche (~4,1 Gio de VRAM).

Ce que ça débloquerait ICI : `google/gemma-4-26B-A4B-it-qat` (13770 Mio, MoE 128
experts, officiel, QAT) est le dernier candidat qui remplit nos critères, et c'est
précisément le coût du déport qui le condamne aujourd'hui.

CE QUE LA PR A DÉJÀ TRANCHÉ, ET QU'IL NE FAUT PAS RE-EXPLORER. Son auteur a
instrumenté le routage sur 54 000 requêtes mêlant code, maths, prose et
multilingue : « a top-32 hot expert list learned on half the workload covers only
~10% of the other half (uniform = 6.2%). Static pinning of experts is a dead end. »
Autrement dit, épingler en VRAM « les experts de codage » — identifiés à l'avance
ou par profilage a posteriori — ne vaut presque rien. Il n'y a pas de biais
statique exploitable ; il y a de la localité TEMPORELLE, et c'est elle que le
cache exploite.

LES QUATRE MAILLONS, dans l'ordre où ils doivent tomber :
  1. la PR quitte l'état brouillon et fusionne dans `master`
  2. le drapeau apparaît dans les sources de `master`
  3. une release llama.cpp l'embarque
  4. l'image LocalAI est reconstruite APRÈS cette release

Contrat de sortie, identique aux autres watchers : stdout non vide = message livré
sur Telegram, stdout vide = silence. Les logs vont sur stderr. Le script sort
toujours en 0 pour qu'un incident réseau ne passe pas pour une panne de cron.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

STATE = os.environ.get("MOE_WATCH_STATE", "/opt/data/.moe-cache-watch.json")
FORCE_SENTINEL = os.environ.get(
    "MOE_WATCH_FORCE_FILE", "/opt/data/.moe-cache-watch.force"
)
VERBOSE = os.environ.get("WATCHER_VERBOSE") == "1"

PR = 27861
API_PR = f"https://api.github.com/repos/ggml-org/llama.cpp/pulls/{PR}"
API_RELEASES = "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=100"
RAW = "https://raw.githubusercontent.com/ggml-org/llama.cpp/{ref}/{path}"

# Le drapeau CLI est déclaré dans l'analyseur d'arguments. On cherche le NOM DE
# L'OPTION plutôt qu'un identifiant C++ : un renommage interne ne doit pas produire
# un faux négatif, alors que le nom d'option est une interface publique.
MOTIF_DRAPEAU = re.compile(r"moe[-_]expert[-_]cache", re.IGNORECASE)
FICHIER_ARGS = "common/arg.cpp"

DEPOT_QUAY = "go-skynet/local-ai-backends"
API_QUAY = f"https://quay.io/api/v1/repository/{DEPOT_QUAY}/tag/"
TAG_STOCK = "latest-gpu-nvidia-cuda-12-llama-cpp"


def _get(url: str, json_attendu: bool):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "moe-cache-watch")
    req.add_header("Accept", "application/json" if json_attendu else "text/plain")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.load(r) if json_attendu else r.read().decode("utf-8", "replace")
    except Exception as e:
        if VERBOSE:
            print(f"[watch] lecture échouée {url}: {e!r}", file=sys.stderr)
        return None


def _en_utc(dt):
    """quay renvoie un offset `-0000`, que la RFC 5322 définit comme « offset local
    inconnu » : parsedate_to_datetime rend alors une date NAÏVE, et la comparer à
    une date UTC lève TypeError."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def etat_pr() -> dict:
    """État de la PR. `None` partout si l'API est illisible — distinguer « pas encore
    fusionnée » de « je n'ai pas pu lire » est ce qui évite d'annoncer un blocage
    qui n'existe pas."""
    d = _get(API_PR, True)
    if not isinstance(d, dict):
        return {"lisible": False}
    return {
        "lisible": True,
        "etat": d.get("state"),
        "brouillon": bool(d.get("draft")),
        "fusionnee": bool(d.get("merged")),
        "fusionnable": d.get("mergeable_state"),
        "maj": d.get("updated_at"),
        "commentaires": d.get("comments"),
    }


def drapeau_present(ref: str):
    """(bool | None) — None si la source n'a pas pu être lue."""
    txt = _get(RAW.format(ref=ref, path=FICHIER_ARGS), json_attendu=False)
    if txt is None:
        return None
    return bool(MOTIF_DRAPEAU.search(txt))


def premiere_release_avec_drapeau():
    """(tag, date) de la PREMIÈRE release qui embarque le drapeau.

    Pas « la dernière release » : llama.cpp en publie une par jour, et comparer la
    date de l'image LocalAI à celle de la dernière reviendrait à courir après une
    cible qui avance plus vite que les reconstructions d'image — le maillon 4 ne
    serait jamais satisfait.

    Recherche dichotomique : une fois le code fusionné il ne disparaît plus, donc la
    présence est monotone sur les tags triés par date et ~7 lectures suffisent pour
    100 releases.
    """
    d = _get(API_RELEASES, True)
    if not isinstance(d, list):
        return None, None
    rels = []
    for r in d:
        # On ne filtre QUE les brouillons : 100 % des releases llama.cpp portent
        # `prerelease: true`. Les écarter reviendrait à n'avoir aucune release.
        if r.get("draft"):
            continue
        try:
            pub = datetime.fromisoformat(r["published_at"].replace("Z", "+00:00"))
        except Exception:
            continue
        rels.append((pub, r.get("tag_name")))
    if not rels:
        return None, None
    rels.sort()

    if drapeau_present(rels[0][1]):
        return rels[0][1], rels[0][0]
    lo, hi = 0, len(rels) - 1
    if not drapeau_present(rels[hi][1]):
        return None, None
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        p = drapeau_present(rels[mid][1])
        if p is None:
            return None, None
        if p:
            hi = mid
        else:
            lo = mid
    return rels[hi][1], rels[hi][0]


def date_image_localai():
    """(date, statut) — statut ∈ present / absent / inconnu."""
    d = _get(API_QUAY + f"?specificTag={TAG_STOCK}&limit=1", True)
    if not isinstance(d, dict):
        return None, "inconnu"
    tags = d.get("tags") or []
    if not tags:
        return None, "absent"
    brut = tags[0].get("last_modified")
    try:
        return _en_utc(parsedate_to_datetime(brut)), "present"
    except Exception:
        return None, "inconnu"


def load_state() -> dict:
    try:
        with open(STATE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(st: dict) -> None:
    try:
        with open(STATE, "w") as f:
            json.dump(st, f)
    except Exception as e:
        print(f"[watch] WARN état non sauvé: {e}", file=sys.stderr)


def main() -> None:
    forced = os.environ.get("WATCHER_FORCE") == "1"
    if os.path.exists(FORCE_SENTINEL):
        forced = True
        try:
            os.remove(FORCE_SENTINEL)
        except OSError:
            pass

    pr = etat_pr()
    master = drapeau_present("master")
    rel_tag, rel_date = (None, None)
    img_date, img_statut = (None, "inconnu")
    if master:
        rel_tag, rel_date = premiere_release_avec_drapeau()
        img_date, img_statut = date_image_localai()

    # Le maillon qui bloque, du plus amont au plus aval. Nommer le blocage courant
    # évite de reposer la question à chaque exécution.
    if not pr.get("lisible") and master is None:
        blocage = "sources illisibles (réseau ou API)"
    elif not master:
        if pr.get("fusionnee"):
            blocage = "fusionnée mais drapeau absent de master (renommé ?)"
        elif pr.get("brouillon"):
            blocage = "PR encore en brouillon"
        else:
            blocage = "PR pas encore fusionnée"
    elif not rel_tag:
        blocage = "aucune release ne l'embarque encore"
    elif img_statut != "present":
        blocage = f"image LocalAI {img_statut}"
    elif img_date and rel_date and img_date < rel_date:
        blocage = "image LocalAI antérieure à la release"
    else:
        blocage = None

    st = load_state()
    signature = {
        "brouillon": pr.get("brouillon"),
        "fusionnee": pr.get("fusionnee"),
        "master": master,
        "release": rel_tag,
        "blocage": blocage,
    }
    if not forced and st.get("signature") == signature:
        if VERBOSE:
            print(f"[watch] inchangé — blocage: {blocage or 'aucun'}", file=sys.stderr)
        return
    save_state({"signature": signature, "vu": datetime.now(timezone.utc).isoformat()})

    if blocage is None:
        print(
            f"🟢 **Cache LRU d'experts MoE disponible** (llama.cpp PR #{PR})\n\n"
            f"Le drapeau `--moe-expert-cache` est dans `master`, embarqué depuis la "
            f"release **{rel_tag}** ({rel_date:%Y-%m-%d}), et l'image "
            f"`{TAG_STOCK}` a été reconstruite après ({img_date:%Y-%m-%d}).\n\n"
            "Ce que ça débloque : le déport d'experts coûte aujourd'hui 74 % du temps "
            "de `qwen3-coder-30b` (6,7 tok/s effectifs contre 25,7 au chargement). La "
            "mesure de la PR annonce +31 % en décodage avec ~4,1 Gio de cache.\n\n"
            "Candidat à rejouer en premier : `google/gemma-4-26B-A4B-it-qat` "
            "(13770 Mio, MoE 128 experts, officiel, QAT) — le dernier modèle qui "
            "remplit nos critères et que le coût du déport condamnait.\n\n"
            "⚠️ Deux réserves de la PR elle-même : le cache ne s'active qu'en décodage "
            "MONO-TOKEN, donc il contourne le MTP — à vérifier sur un modèle qui en "
            "dépend. Et il n'a été mesuré que sur Qwen3.8-Flash-Next.\n\n"
            "Rien n'est établi tant que le banc n'a pas tranché : mesurer AVANT de "
            "déployer."
        )
    elif pr.get("fusionnee") and not st.get("annonce_fusion"):
        print(
            f"🔧 **PR #{PR} fusionnée** — cache LRU d'experts MoE dans `master`.\n\n"
            f"Maillon restant : {blocage}.\n\n"
            "Le watcher continue et préviendra quand une image LocalAI l'embarquera."
        )
    elif VERBOSE:
        print(
            f"[watch] PR: brouillon={pr.get('brouillon')} fusionnée={pr.get('fusionnee')} "
            f"état={pr.get('fusionnable')} maj={pr.get('maj')}\n"
            f"        drapeau dans master : {master}\n"
            f"        première release : {rel_tag} ({rel_date})\n"
            f"        image {TAG_STOCK} : {img_statut} ({img_date})\n"
            f"        blocage : {blocage} — RAS (silencieux en prod).",
            file=sys.stderr,
        )


if __name__ == "__main__":
    # Un plantage sortirait en code non-zéro et ferait croire au cron à une panne,
    # alors que le contrat est « stdout vide = silence ».
    try:
        main()
    except Exception as e:  # noqa: BLE001 — volontaire, cf. commentaire ci-dessus
        print(f"[watch] ERREUR non fatale, aucun état modifié: {e!r}", file=sys.stderr)
        sys.exit(0)
