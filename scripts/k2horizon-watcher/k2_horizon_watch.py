#!/usr/bin/env python3
"""Watcher : alerte quand K2-Horizon-MoVA-36B-A4B devient réellement exploitable
sur ce cluster — c'est-à-dire quand llama.cpp AMONT connaît son architecture, puis
quand l'image LocalAI stock l'embarque.

CONTEXTE (relevé le 2026-09-08). Le modèle est séduisant sur le papier :
Terminal-Bench 2.1 à 58,6 et GPQA Diamond à 80,8 pour 4 Md de paramètres actifs,
licence Apache 2.0. Mais il est INEXPLOITABLE ici pour une raison unique et nette :
llama.cpp amont ne connaît pas l'architecture `k2_horizon`. Il n'existe même pas de
PR, seulement la discussion #28308 ouverte le 2026-09-03, bloquée sur un désaccord
de version transformers. Le seul code qui charge ces poids est le fork
MBZUAI-IFM/llama.cpp branche `model/K2Horizon`.

Or LocalAI embarque llama.cpp amont. Tant que le merge n'a pas eu lieu, servir ce
modèle imposerait de builder et maintenir un backend fork à la main, hors chart et
hors Renovate — exactement ce qui a fait écarter Ternary-Bonsai.

LA LEÇON REPRISE DE `bonsai_watch.py`. Ce watcher-là avait livré une fausse alerte
en confondant une intention (« PR mergé, le prochain build portera le kernel ») avec
un artefact. On ne surveille donc QUE des choses vérifiables, maillon par maillon,
sans jamais en sauter un :

    arch dans master  ->  arch dans une RELEASE  ->  image LocalAI reconstruite après

Un merge ne prouve pas une release ; une release ne prouve pas que l'image
l'embarque (LocalAI épingle sa version de llama.cpp).

TROISIÈME AXE, indépendant : le dépôt GGUF OFFICIEL d'IFM ne contient aujourd'hui
que du BF16 (74,9 Go). Tous les quants utilisables sont tiers et non validés. Qu'un
quant officiel apparaisse change la donne côté confiance, sans rien changer côté
runtime — d'où une transition distincte.

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
import re
import sys
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

STATE = os.environ.get("K2_WATCH_STATE", "/opt/data/.k2horizon-watch.json")

# On cherche l'architecture sous toutes ses graphies plausibles : le nom retenu par
# llama.cpp n'est pas encore fixé (pas de PR), donc figer une seule chaîne
# produirait un faux négatif permanent le jour du merge.
MOTIF_ARCH = re.compile(r"k2[-_ ]?horizon", re.IGNORECASE)

# Deux fichiers, deux rôles distincts qu'il ne faut pas confondre :
#   - convert_hf_to_gguf.py : sait CONVERTIR les safetensors en GGUF
#   - src/llama-arch.cpp    : sait EXÉCUTER l'architecture
# Le second est celui qui décide. Le premier peut arriver en avance.
FICHIER_RUNTIME = "src/llama-arch.cpp"
FICHIER_CONVERSION = "convert_hf_to_gguf.py"
RAW = "https://raw.githubusercontent.com/ggml-org/llama.cpp/{ref}/{path}"

DEPOT_QUAY = "go-skynet/local-ai-backends"
API_QUAY = f"https://quay.io/api/v1/repository/{DEPOT_QUAY}/tag/"
TAG_STOCK = "latest-gpu-nvidia-cuda-12-llama-cpp"

DEPOT_GGUF_OFFICIEL = "IFM/K2-Horizon-MoVA-36B-A4B-GGUF"
API_HF = f"https://huggingface.co/api/models/{DEPOT_GGUF_OFFICIEL}/tree/main?recursive=1"

VERBOSE = os.environ.get("WATCHER_VERBOSE") == "1"
FORCE_SENTINEL = os.environ.get("K2_WATCH_FORCE_FILE", "/opt/data/.k2horizon-watch.force")


def _en_utc(dt):
    """Rend la date comparable. quay renvoie un offset `-0000`, que la RFC 5322
    définit comme « offset local inconnu » : parsedate_to_datetime rend alors une
    date NAÏVE, et la comparer à une date UTC lève TypeError."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _get(url: str, json_attendu: bool):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "k2horizon-watch")
    req.add_header("Accept", "application/json" if json_attendu else "text/plain")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.load(r) if json_attendu else r.read().decode("utf-8", "replace")
    except Exception:
        return None


def arch_presente(ref: str, chemin: str):
    """(present: bool|None, ...) — None si la source n'a pas pu être lue.

    Distinguer « absent » de « illisible » est ce qui empêche une panne réseau,
    ou un fichier renommé en amont, de passer pour « pas encore mergé ».
    """
    txt = _get(RAW.format(ref=ref, path=chemin), json_attendu=False)
    if txt is None:
        return None
    return bool(MOTIF_ARCH.search(txt))


def premiere_release_avec_arch():
    """(tag, date) de la PREMIÈRE release llama.cpp contenant l'architecture.

    POURQUOI PAS « la dernière release ». llama.cpp publie une release par JOUR
    (b10850, b10844, b10842... toutes le 2026-09-07). Comparer la date de l'image
    LocalAI à celle de la dernière release reviendrait à courir après une cible qui
    avance plus vite que les reconstructions d'image : le maillon 3 ne serait JAMAIS
    satisfait. Ce qu'il faut, c'est la première release qui embarque le code.

    Recherche dichotomique sur la liste des releases triée par date : les tags sont
    monotones (une fois l'arch mergée elle ne disparaît plus), donc ~7 lectures
    suffisent pour 100 releases. Ces lectures passent par raw.githubusercontent, qui
    n'a pas le quota de 60 requêtes/heure de l'API.

    Si TOUTES les releases de la fenêtre contiennent l'arch, la vraie première est
    plus ancienne que la fenêtre : on renvoie la plus ancienne connue. C'est un
    critère plus STRICT que nécessaire, donc sans risque de faux positif.
    """
    d = _get("https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=100", True)
    if not isinstance(d, list):
        return None, None
    rels = []
    for r in d:
        # On ne filtre QUE les brouillons : 100 % des releases llama.cpp portent
        # `prerelease: true` (vérifié le 2026-09-08). Les écarter reviendrait à
        # n'avoir aucune release et à bloquer ce maillon pour toujours.
        if r.get("draft"):
            continue
        try:
            pub = datetime.fromisoformat(r["published_at"].replace("Z", "+00:00"))
        except Exception:
            continue
        rels.append((pub, r.get("tag_name")))
    if not rels:
        return None, None
    rels.sort()  # de la plus ancienne à la plus récente

    if arch_presente(rels[0][1], FICHIER_RUNTIME):
        return rels[0][1], rels[0][0]
    lo, hi = 0, len(rels) - 1
    if not arch_presente(rels[hi][1], FICHIER_RUNTIME):
        return None, None  # aucune release ne l'a encore
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        p = arch_presente(rels[mid][1], FICHIER_RUNTIME)
        if p is None:
            return None, None  # source illisible -> on ne conclut pas
        if p:
            hi = mid
        else:
            lo = mid
    return rels[hi][1], rels[hi][0]


def date_tag_quay(tag: str):
    """(date, statut) — statut ∈ present / absent / inconnu.

    L'API v1 de quay répond 200 avec une liste VIDE pour un tag inexistant, d'où la
    distinction absent / inconnu.
    """
    d = _get(f"{API_QUAY}?specificTag={tag}&onlyActiveTags=true", True)
    if d is None:
        return None, "inconnu"
    tags = d.get("tags") or []
    if not tags:
        return None, "absent"
    try:
        return _en_utc(parsedate_to_datetime(tags[0].get("last_modified"))), "present"
    except Exception:
        return None, "present"


def quants_officiels():
    """Noms des GGUF quantifiés du dépôt OFFICIEL (BF16 exclu), ou None si illisible."""
    d = _get(API_HF, True)
    if not isinstance(d, list):
        return None
    return sorted(
        x["path"]
        for x in d
        if x.get("path", "").endswith(".gguf") and "bf16" not in x["path"].lower()
    )


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
        except Exception:
            pass
    if forced:
        print(
            "🧪 **Test watcher `k2horizon-watch`** — la livraison Telegram fonctionne. "
            "Déclenchement manuel ; en fonctionnement normal le watcher reste silencieux "
            "jusqu'à ce que llama.cpp amont connaisse l'architecture `k2_horizon`, puis "
            "que l'image LocalAI stock l'embarque."
        )
        return

    st = load_state()
    hits: list[str] = []

    # --- Maillon 1 : l'architecture est-elle dans master ? -------------------
    runtime_master = arch_presente("master", FICHIER_RUNTIME)
    conv_master = arch_presente("master", FICHIER_CONVERSION)

    if runtime_master and not st.get("merge_amont"):
        hits.append(
            "🟡 **Merge amont** : llama.cpp master connaît désormais l'architecture "
            f"(`{FICHIER_RUNTIME}`). Le fork MBZUAI-IFM n'est plus nécessaire pour "
            "exécuter le modèle. **Pas encore déployable sur LocalAI** — il faut "
            "attendre une release puis une reconstruction de l'image (le watcher "
            "le signalera séparément)."
        )
    elif conv_master and not runtime_master and not st.get("conversion_amont"):
        hits.append(
            "🔵 **Conversion amont seulement** : `convert_hf_to_gguf.py` reconnaît "
            "l'architecture, mais `src/llama-arch.cpp` non — on sait produire le GGUF, "
            "pas encore l'exécuter. Signal d'avancement, rien à déployer."
        )

    # --- Maillons 2 et 3 : release, puis image reconstruite APRÈS ------------
    # On ne saute aucun maillon : c'est le raccourci « le prochain build portera le
    # kernel » qui avait produit la fausse alerte du watcher bonsai le 2026-07-31.
    rel_tag, rel_date = (None, None)
    dans_release = None
    img_date, img_statut = (None, "inconnu")
    blocage = "arch pas encore dans master"

    if runtime_master:
        rel_tag, rel_date = premiere_release_avec_arch()
        if rel_tag is None:
            blocage = "mergé dans master, pas encore dans une release (ou source illisible)"
        else:
            dans_release = True
            if True:
                img_date, img_statut = date_tag_quay(TAG_STOCK)
                if img_statut != "present" or img_date is None:
                    blocage = f"image stock {TAG_STOCK} : {img_statut}"
                elif img_date <= rel_date:
                    blocage = (
                        f"dans la release {rel_tag}, mais l'image stock est plus ancienne"
                    )
                else:
                    blocage = None
                    if not st.get("localai_pret"):
                        hits.append(
                            f"🟢 **Déployable sur LocalAI** : les trois maillons tiennent — "
                            f"architecture dans master, présente dans la release `{rel_tag}`, "
                            f"et l'image stock `{TAG_STOCK}` a été reconstruite après cette "
                            f"release. Le backend `llama-cpp` standard suffit : **pas de "
                            f"backend fork à maintenir**."
                        )

    # --- Axe indépendant : quants OFFICIELS ----------------------------------
    quants = quants_officiels()
    vus_quants = set(st.get("quants_officiels", []))
    nouveaux_quants = sorted(set(quants) - vus_quants) if quants else []
    if nouveaux_quants:
        hits.append(
            "📦 **Quants officiels publiés** par IFM (le dépôt ne contenait que du "
            "BF16 de 74,9 Go) : "
            + ", ".join(f"`{q}`" for q in nouveaux_quants[:6])
            + ". Les quants tiers ne sont donc plus la seule option."
        )

    save_state(
        {
            "merge_amont": bool(st.get("merge_amont") or runtime_master),
            "conversion_amont": bool(st.get("conversion_amont") or conv_master),
            "localai_pret": bool(st.get("localai_pret") or blocage is None),
            "quants_officiels": sorted(vus_quants | set(quants or [])),
        }
    )

    if hits:
        # Rappel de faisabilité : même le jour où le runtime existe, la machine
        # reste le facteur limitant. Mesuré le 2026-09-03 : le bus PCIe est en gen 3
        # (limite carte mère, la 3060 sait faire gen 4) et sature déjà à ~9,5 Go/s
        # sur gemma-4-26B, qui est PLUS PETIT. Q4_K_M pèse 22,37 Go pour ~10,5 Go de
        # VRAM utilisable, soit ~12 Go d'experts à tenir en RAM hôte — sur une machine
        # qui a subi un OOM global le 2026-08-11 dont les correctifs ne sont pas posés.
        print(
            "🧭 **K2-Horizon-MoVA-36B-A4B : le verrou bouge**\n\n"
            + "\n\n".join(hits)
            + "\n\n⚠️ Rappel de faisabilité (mesuré le 2026-09-03) : Q4_K_M pèse "
            "**22,37 Go** contre ~10,5 Go de VRAM utilisable, soit ~12 Go d'experts à "
            "tenir en RAM hôte. Le bus est en **PCIe gen 3** (limite carte mère) et "
            "sature déjà à ~9,5 Go/s sur gemma-4-26B, plus petit. Et MoVA route les "
            "projections de VALEURS, dans l'attention : `--n-cpu-moe` ne déporte que "
            "les experts FFN, donc rien ne garantit que ces poids-là soient déportables.\n\n"
            "Prochaine étape : passer le banc `harness-bench` face au plancher actuel "
            "AVANT tout déploiement. Un runtime disponible n'est pas une amélioration "
            "établie."
        )
    elif VERBOSE:
        print(
            f"[watch] arch dans master — runtime({FICHIER_RUNTIME}): {runtime_master} "
            f"| conversion({FICHIER_CONVERSION}): {conv_master}\n"
            f"        dernière release : {rel_tag} ({rel_date}) — arch dedans : {dans_release}\n"
            f"        image {TAG_STOCK} : {img_statut} ({img_date})\n"
            f"        quants officiels : {quants if quants else 'aucun (ou illisible)'}\n"
            f"        blocage courant : {blocage or 'aucun — déployable'}\n"
            f"        — RAS (silencieux en prod)."
        )


if __name__ == "__main__":
    # Garde-fou de dernier recours : un plantage sortirait en code non-zéro et ferait
    # croire au cron à une panne, alors que le contrat est « stdout vide = silence ».
    # On loge sur STDERR (qui ne part PAS sur Telegram) et on sort 0.
    try:
        main()
    except Exception as e:  # noqa: BLE001 — volontaire, cf. commentaire ci-dessus
        print(f"[watch] ERREUR non fatale, aucun état modifié: {e!r}", file=sys.stderr)
        sys.exit(0)
