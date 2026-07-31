#!/usr/bin/env python3
"""Watcher : alerte quand Ternary-Bonsai-27B (Q2_0 ternaire) devient réellement
déployable sur LocalAI — c'est-à-dire quand un **runtime installable existe**.

POURQUOI CETTE VERSION. Le 2026-07-31 le watcher a livré une alerte fausse :
« PR Q2_0 CUDA #25707 mergé → le prochain build stock cuda12-llama-cpp portera le
kernel. Prochaine étape : déployer (backend cuda12-bonsai). » Trois erreurs :

  1. Un PR mergé ne rend rien déployable. Vérification faite : le tag stock
     `latest-gpu-nvidia-cuda-12-llama-cpp` datait du 15/07, soit DEUX SEMAINES
     avant le merge du 30/07. La phrase « le prochain build » était au futur et
     n'a jamais été vérifiée.
  2. Le merge mainline est de toute façon SANS OBJET pour le backend bonsai : la
     gallery LocalAI le décrit comme un « Fork of llama.cpp (PrismML) adding the
     Q1_0 and Q2_0 kernels ». Le fork a toujours eu ces kernels.
  3. Le backend recommandé, `cuda12-bonsai`, résout vers
     `latest-gpu-nvidia-cuda-12-bonsai` — tag qui n'existe pas. Seul
     `cuda12-bonsai-development` (→ `master-...`) a une image, publiée le 28/07.

Donc on ne surveille plus des intentions, on surveille des IMAGES, et on nomme le
backend réellement installable.

Conçu pour un cron Hermes `no_agent` : stdout NON-VIDE = message Telegram livré,
stdout VIDE = silence. On n'imprime QUE sur une transition positive (état persisté
sur PVC pour ne pas ré-alerter à chaque tick).

Robustesse : toute erreur réseau => état "inconnu", aucun changement d'état, exit 0
et silence (un exit non-zéro déclencherait une alerte d'erreur du cron).

Env WATCHER_VERBOSE=1 => imprime toujours l'état courant (test manuel).
"""

from __future__ import annotations
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

STATE = os.environ.get("BONSAI_WATCH_STATE", "/opt/data/.bonsai-watch.json")
DEPOT = "go-skynet/local-ai-backends"
API = f"https://quay.io/api/v1/repository/{DEPOT}/tag/"

# Correspondance VÉRIFIÉE le 2026-07-31 dans backend/index.yaml de LocalAI :
# le nom de backend qu'on écrit dans le YAML modèle -> le tag quay qu'il tire.
# C'est cette indirection qui a produit le faux positif : le tag `latest-` du
# backend stable n'est pas publié, alors que le `master-` du -development l'est.
BACKENDS = [
    ("cuda12-bonsai", "latest-gpu-nvidia-cuda-12-bonsai"),
    ("cuda12-bonsai-development", "master-gpu-nvidia-cuda-12-bonsai"),
]
# Voie stock : utilisable SEULEMENT si l'image a été reconstruite APRÈS le merge.
TAG_STOCK = "latest-gpu-nvidia-cuda-12-llama-cpp"
PRS = [25603, 25707]
VERBOSE = os.environ.get("WATCHER_VERBOSE") == "1"


def _en_utc(dt):
    """Rend la date comparable. quay renvoie un offset `-0000`, que la RFC 5322
    définit comme « offset local inconnu » : parsedate_to_datetime rend alors une
    date NAÏVE, et la comparer à une date UTC lève TypeError. Constaté au premier
    essai de cette réécriture le 2026-07-31."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _get_json(url: str, ua: str = "bonsai-watch"):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", ua)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.load(r)
    except Exception:
        return None


def tag_date(tag: str):
    """Date de dernière modification du tag, ou None si absent/inconnu.

    L'API v1 de quay répond 200 avec une liste VIDE pour un tag inexistant — d'où
    la distinction absent (liste vide) / inconnu (requête ratée). Le distinguer
    est ce qui empêche une panne réseau de passer pour « pas encore publié ».
    """
    d = _get_json(f"{API}?specificTag={tag}&onlyActiveTags=true")
    if d is None:
        return None, "inconnu"
    tags = d.get("tags") or []
    if not tags:
        return None, "absent"
    brut = tags[0].get("last_modified")
    try:
        return _en_utc(parsedate_to_datetime(brut)), "present"
    except Exception:
        return None, "present"


def pr_info(n: int):
    """(merged: bool|None, merged_at: datetime|None)."""
    d = _get_json(f"https://api.github.com/repos/ggml-org/llama.cpp/pulls/{n}")
    if d is None:
        return None, None
    if not d.get("merged"):
        return False, None
    try:
        return True, datetime.fromisoformat(d["merged_at"].replace("Z", "+00:00"))
    except Exception:
        return True, None


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


FORCE_SENTINEL = os.environ.get(
    "BONSAI_WATCH_FORCE_FILE", "/opt/data/.bonsai-watch.force"
)


def main() -> None:
    forced = os.environ.get("WATCHER_FORCE") == "1"
    if os.path.exists(FORCE_SENTINEL):
        forced = True
        try:
            os.remove(FORCE_SENTINEL)
        except Exception:
            pass
    if forced:
        print(
            "🧪 **Test watcher `bonsai-backend-watch`** — la livraison Telegram "
            "fonctionne. Déclenchement manuel ; en fonctionnement normal le watcher "
            "reste silencieux jusqu'à ce qu'un **runtime installable** existe pour "
            "Ternary-Bonsai (image bonsai publiée, ou image stock reconstruite après "
            "un merge Q2_0 CUDA)."
        )
        return

    st = load_state()

    # 1) Backends bonsai dédiés : une image publiée = directement installable.
    dispos: list[tuple[str, str]] = []  # (nom_backend, tag)
    etats: list[str] = []
    for nom, tag in BACKENDS:
        _, statut = tag_date(tag)
        etats.append(f"{nom}={statut}")
        if statut == "present":
            dispos.append((nom, tag))

    # 2) Voie stock : le kernel n'arrive QUE si l'image est reconstruite après le
    #    merge. On compare les dates au lieu de promettre un « prochain build ».
    stock_date, stock_statut = tag_date(TAG_STOCK)
    stock_pret: list[int] = []
    stock_en_attente: list[int] = []
    for n in PRS:
        merged, quand = pr_info(n)
        if merged is not True:
            continue
        if stock_date and quand and stock_date > quand:
            stock_pret.append(n)
        elif stock_date and quand:
            stock_en_attente.append(n)

    hits: list[str] = []
    vus = set(st.get("backends_dispo", []))
    for nom, tag in dispos:
        if nom not in vus:
            hits.append(
                f"🟢 Runtime **installable** : backend `{nom}` (image `{tag}` "
                f"publiée sur quay). C'est ce nom-là qu'il faut écrire dans le YAML "
                f"du modèle — pas un autre."
            )
    vus_stock = set(st.get("stock_pret", []))
    for n in stock_pret:
        if n not in vus_stock:
            hits.append(
                f"🟢 Image stock `{TAG_STOCK}` reconstruite APRÈS le merge du PR "
                f"#{n} → le backend `llama-cpp` standard porte maintenant le kernel "
                f"Q2_0. Plus besoin d'un backend dédié."
            )

    save_state(
        {
            "backends_dispo": sorted(vus | {n for n, _ in dispos}),
            "stock_pret": sorted(vus_stock | set(stock_pret)),
        }
    )

    if hits:
        # Le rappel de fenêtre : mesuré au banc le 2026-07-31, Bonsai-27B-Q1_0 fait
        # 18/44 de médiane contre 34-41/44 au gemma-4-12b-it-qat deja deploye. Le
        # watcher signale une POSSIBILITE technique, pas une amelioration.
        print(
            "🌳 **Ternary-Bonsai-27B : un runtime est disponible**\n\n"
            + "\n".join(hits)
            + "\n\n⚠️ Rappel de mesure : Bonsai-27B-Q1_0 fait **18/44** de médiane au "
            "banc tetris (n=3), contre **34-41/44** pour `gemma-4-12b-it-qat` déjà "
            "déployé. Son template n'expose pas de tokens d'appel d'outil, et sa "
            "fenêtre d'entraînement est de 4096. Le ternaire reste à mesurer : c'est "
            "une possibilité technique, pas une amélioration établie.\n\n"
            "Prochaine étape si tu veux essayer : installer le backend nommé "
            "ci-dessus, puis `Ternary-Bonsai-27B-Q2_0.gguf` "
            "(prism-ml/Ternary-Bonsai-27B-gguf), et passer `tool_call_gate.sh` "
            "AVANT toute éval."
        )
    elif VERBOSE:
        st_txt = {
            "present": f"présent ({stock_date})",
            "absent": "absent",
            "inconnu": "inconnu",
        }[stock_statut]
        print(
            f"[watch] backends bonsai : {', '.join(etats)} | "
            f"stock {TAG_STOCK} : {st_txt} | "
            f"PRs mergés mais image stock trop ancienne : {stock_en_attente or 'aucun'} | "
            f"PRs couverts par l'image stock : {stock_pret or 'aucun'} "
            f"— RAS (silencieux en prod)."
        )


if __name__ == "__main__":
    # Garde-fou de dernier recours : un plantage sortirait en code non-zéro et
    # ferait croire au cron à une panne, alors que le contrat est « stdout vide =
    # silence ». On loge sur STDERR (qui ne part PAS sur Telegram) et on sort 0.
    # Motif : le premier essai de cette réécriture plantait sur une comparaison de
    # dates et sortait en 1.
    try:
        main()
    except Exception as e:  # noqa: BLE001 — volontaire, cf. commentaire ci-dessus
        print(f"[watch] ERREUR non fatale, aucun état modifié: {e!r}", file=sys.stderr)
        sys.exit(0)
