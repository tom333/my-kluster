#!/usr/bin/env python3
"""Watcher : alerte quand Ternary-Bonsai-27B (Q2_0 ternaire) devient déployable
sur GPU LocalAI. Deux déclencheurs surveillés :

  1. l'image OCI du backend dédié `cuda12-bonsai` est publiée sur quay
     (aujourd'hui 404 — la gallery LocalAI la déclare mais la CI ne l'a pas
     encore poussée), OU
  2. un des PRs "Q2_0 CUDA" est mergé dans ggml-org/llama.cpp mainline
     (→ le prochain build stock `cuda12-llama-cpp` portera le kernel).

Conçu pour un cron Hermes `no_agent` : stdout NON-VIDE = message Telegram livré,
stdout VIDE = silence total. Donc on n'imprime QUE sur une transition positive
(état persisté sur PVC pour ne pas ré-alerter à chaque tick une fois publié).

Robustesse : toute erreur réseau => état "inconnu", aucun changement d'état,
exit 0 et silence (un exit non-zéro déclencherait une alerte d'erreur du cron).

Env WATCHER_VERBOSE=1 => imprime toujours l'état courant (pour test manuel ;
en exec manuel ça va sur stdout, pas sur Telegram).
"""
from __future__ import annotations
import json
import os
import sys
import urllib.error
import urllib.request

STATE = os.environ.get("BONSAI_WATCH_STATE", "/opt/data/.bonsai-watch.json")
QUAY_TAG = "latest-gpu-nvidia-cuda-12-bonsai"
QUAY_MANIFEST = f"https://quay.io/v2/go-skynet/local-ai-backends/manifests/{QUAY_TAG}"
# PRs "Q2_0 CUDA" ouverts à surveiller (#25188 fermé sans merge le 2026-07). Si
# de nouveaux PRs apparaissent, les ajouter ici — le watcher reste correct sinon.
PRS = [25603, 25707]
VERBOSE = os.environ.get("WATCHER_VERBOSE") == "1"
_MANIFEST_ACCEPT = (
    "application/vnd.oci.image.index.v1+json, "
    "application/vnd.docker.distribution.manifest.list.v2+json, "
    "application/vnd.docker.distribution.manifest.v2+json"
)


def image_published() -> bool | None:
    """True si l'image quay existe (HTTP 200), False si 404, None si inconnu."""
    req = urllib.request.Request(QUAY_MANIFEST, method="HEAD")
    req.add_header("Accept", _MANIFEST_ACCEPT)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        return None  # 401/403/5xx => on ne sait pas, ne pas alerter
    except Exception:
        return None


def pr_merged(n: int) -> bool | None:
    url = f"https://api.github.com/repos/ggml-org/llama.cpp/pulls/{n}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "bonsai-watch")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return bool(json.load(r).get("merged"))
    except Exception:
        return None


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


FORCE_SENTINEL = os.environ.get("BONSAI_WATCH_FORCE_FILE", "/opt/data/.bonsai-watch.force")


def main() -> None:
    # Hook de test one-shot : env WATCHER_FORCE=1 OU présence de la sentinelle
    # => émet une alerte de test et sort SANS toucher l'état réel. Sert à valider
    # la livraison Telegram end-to-end via `hermes cron run` sans attendre un vrai
    # déclencheur. La sentinelle est consommée (supprimée) pour rester one-shot.
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
            "reste silencieux jusqu'à ce que Ternary-Bonsai devienne déployable "
            "(image `cuda12-bonsai` sur quay ou PR Q2_0 CUDA mergé)."
        )
        return

    st = load_state()
    img = image_published()
    merged = [n for n in PRS if pr_merged(n) is True]

    hits: list[str] = []
    if img is True and not st.get("img_available"):
        hits.append(
            f"🟢 Backend **cuda12-bonsai** publié sur quay (`{QUAY_TAG}`) "
            f"→ installable dans LocalAI."
        )
    prev_merged = set(st.get("prs_merged", []))
    for n in merged:
        if n not in prev_merged:
            hits.append(
                f"🟢 PR Q2_0 CUDA **#{n}** mergé dans ggml-org/llama.cpp "
                f"→ le prochain build stock `cuda12-llama-cpp` portera le kernel."
            )

    # Persistance : on n'écrase l'état "positif" que par du positif (un blip
    # réseau qui renvoie None ne doit pas "oublier" qu'on avait déjà vu publié).
    new_state = {
        "img_available": bool(img is True) or bool(st.get("img_available")),
        "prs_merged": sorted(prev_merged | set(merged)),
    }
    save_state(new_state)

    if hits:
        print(
            "🌳 **Ternary-Bonsai-27B déblocable sur ta 3060 !**\n\n"
            + "\n".join(hits)
            + "\n\nProchaine étape : déployer le YAML LocalAI "
            "(modèle `Ternary-Bonsai-27B-Q2_0.gguf` + backend `cuda12-bonsai`). "
            "Réponds-moi pour lancer le déploiement."
        )
    elif VERBOSE:
        img_txt = {True: "PUBLIÉE", False: "404 (pas encore)", None: "inconnu"}[img]
        print(
            f"[watch] image cuda12-bonsai : {img_txt} | "
            f"PRs Q2_0 CUDA mergés : {merged or 'aucun'} — RAS (silencieux en prod)."
        )


if __name__ == "__main__":
    main()
