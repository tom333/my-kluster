"""Watcher modèles Hugging Face : nouveaux GGUF, fiche de faits, verdict face au modèle en place.

Usage : python3 modeles.py [--jours N] [--max N]
Sources : dépôts GGUF récents d'auteurs de confiance + top trending GGUF. Seul filtre dur :
un fichier GGUF mono-fichier ≤ TAILLE_MAX (sinon ça ne tourne pas sur 12 Go). Pour chaque
dépôt nouveau : métadonnées Hub (paramètres, architecture, contexte, template d'outils,
licence, modèle de base) + début du README → UN appel gemma avec le profil → Telegram.
Le verdict « à évaluer » donne la ligne `nom|url` à coller dans la file d'éval de pc
(~/.config/brain/model-candidates.queue). État : /data/etat/modeles.json (dépôts vus).
"""

import datetime as dt
import json
import re
import sys
from html import unescape

import commun

SENTINELLE = "RIEN_DE_NEUF"
HF = "https://huggingface.co"
AUTEURS = [
    "google",
    "unsloth",
    "Qwen",
    "ggml-org",
    "bartowski",
    "LiquidAI",
    "mistralai",
    "deepseek-ai",
    "nvidia",
    "microsoft",
    "ibm-granite",
    "allenai",
    "NousResearch",
    "openai",
    "meta-llama",
    "zai-org",
    "MiniMaxAI",
    "moonshotai",
]
TAILLE_MAX = 9.5e9
COMPAGNON = re.compile(
    r"mmproj|projector|mtp|draft|lora|adapter|imatrix|bf16|f16|f32|-\d{5}-of-", re.I
)
CONSIGNE = (
    "CONTRAT DE SORTIE. Texte brut Telegram en français, sans Markdown. Un bloc par modèle, "
    "séparés par une ligne '———'. Lien EXACT sur une ligne '🔗 '. N'invente aucun chiffre : "
    "ce qui n'est pas dans la fiche est « non précisé ». Sous 3500 caractères.\n\n"
    "PROFIL DE L'UTILISATEUR :\n%s\n\n"
    "Tu reçois des fiches de dépôts GGUF récents. Pour CHAQUE fiche, dans l'ordre :\n"
    "1. '🤗 <id du dépôt>' puis une ligne de faits : paramètres, architecture, contexte, "
    "appel d'outils (template), licence, fichier retenu et sa taille.\n"
    "2. Deux phrases : en quoi ce modèle est intéressant POUR LUI (code local, appel d'outils, "
    "cerveau Hermes, ou autre usage réel comme la vision ou le multilingue) — ou pourquoi il ne "
    "l'est pas (finetune communautaire, base déjà connue, usage hors profil).\n"
    "3. Une phrase face à gemma-4-12b-it-qat : sur quoi il serait mieux, pire, ou inconnu.\n"
    "4. Verdict : '✅ À évaluer' suivi de la ligne exacte 'file: <nom>|<url du fichier>' "
    "fournie dans la fiche, ou '⏭️ Ignorer : <raison en 5 mots>'.\n"
    "Si AUCUNE fiche n'est fournie : réponds exactement %s."
)


def hub(chemin):
    return commun.http(HF + chemin, timeout=60)


def candidats(jours, maximum):
    depuis = commun.maintenant().timestamp() - jours * 86400
    vus = set(commun.lire_etat("modeles", {}).get("vus", []))
    out = []
    for a in AUTEURS:
        for m in hub(
            "/api/models?author=%s&filter=gguf&sort=createdAt&direction=-1&limit=10" % a
        ):
            cree = m.get("createdAt", "")
            if m["id"] not in vus and cree and _epoch(cree) >= depuis:
                out.append(m["id"])
    for m in hub("/api/models?filter=gguf&sort=trendingScore&direction=-1&limit=20"):
        if m["id"] not in vus and m["id"] not in out:
            out.append(m["id"])
    return out[:maximum], vus


def _epoch(iso):
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def fichier(rid):
    """Plus gros GGUF mono-fichier ≤ TAILLE_MAX (fidélité max qui tient en VRAM)."""
    meilleur = None
    for f in hub("/api/models/%s/tree/main" % rid):
        p, taille = f.get("path", ""), f.get("size") or 0
        if not p.lower().endswith(".gguf") or "/" in p or COMPAGNON.search(p):
            continue
        if 5e8 <= taille <= TAILLE_MAX and (meilleur is None or taille > meilleur[1]):
            meilleur = (p, taille)
    return meilleur


def fiche(rid):
    f = fichier(rid)
    if not f:
        return None
    d = hub(
        "/api/models/%s?expand[]=gguf&expand[]=cardData&expand[]=downloads&expand[]=likes&expand[]=createdAt"
        % rid
    )
    g, c = d.get("gguf") or {}, d.get("cardData") or {}
    try:
        readme = commun.http(HF + "/%s/raw/main/README.md" % rid, timeout=60)
        readme = " ".join(unescape(re.sub(r"<[^>]+>", " ", readme)).split())[:1800]
    except Exception as e:
        readme = "(README illisible : %s)" % e
    nom = re.sub(r"-gguf$", "", rid.split("/")[-1], flags=re.I).lower()
    return {
        "id": rid,
        "lien": HF + "/" + rid,
        "cree": (d.get("createdAt") or "")[:10],
        "telechargements": d.get("downloads"),
        "likes": d.get("likes"),
        "parametres_total": g.get("total"),
        "architecture": g.get("architecture"),
        "contexte": g.get("context_length"),
        "template_outils": bool(g.get("chat_template"))
        and "tool" in (g.get("chat_template") or "").lower(),
        "licence": c.get("license"),
        "modele_de_base": c.get("base_model"),
        "fichier": f[0],
        "taille_go": round(f[1] / 1e9, 1),
        "file": "%s|%s/%s/resolve/main/%s" % (nom, HF, rid, f[0]),
        "readme": readme,
    }


def main():
    arg = lambda k, d: int(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
    ids, vus = candidats(arg("--jours", 2), arg("--max", 6))
    fiches, ecartes = [], []
    for rid in ids:
        f = fiche(rid)
        (fiches if f else ecartes).append(f or rid)
    print(
        "  %d dépôt(s) nouveau(x), %d fiche(s), %d sans GGUF ≤ %.1f Go"
        % (len(ids), len(fiches), len(ecartes), TAILLE_MAX / 1e9),
        flush=True,
    )
    bilan = "rien de neuf"
    if fiches:
        texte = commun.llm(
            CONSIGNE % (commun.profil(), SENTINELLE),
            json.dumps(fiches, ensure_ascii=False),
            max_tokens=3072,
        )
        if not texte:
            raise RuntimeError("le modèle a rendu un contenu vide")
        n = commun.telegram(texte)
        try:
            docs = commun.indexer("modeles", texte)
        except Exception as e:
            docs = "échec (%s)" % e
        bilan = "%d message(s), %d car., txtai %s" % (n, len(texte), docs)
    # Vus écrits APRÈS l'envoi ; les écartés (pas de GGUF qui tient) sont vus aussi.
    vus = (list(vus) + ids)[-2000:]
    commun.ecrire_etat("modeles", {"vus": vus})
    print("  bilan : " + bilan, flush=True)


if __name__ == "__main__":
    commun.principal("modeles", main)
