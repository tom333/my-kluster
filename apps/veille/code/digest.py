"""Digest de veille : non-lus d'une catégorie Miniflux → UN appel gemma → Telegram → txtai → marqué lu.

Usage : python3 digest.py THEME [THEME ...] [--force]
  Les thèmes s'enchaînent EN SÉRIE dans un seul processus : gemma est chargé une fois et
  aucun digest ne l'évince (LocalAI ne garde qu'un backend résident). Un thème en échec
  n'arrête pas les suivants ; l'alerte liste les échecs, puis le job sort en erreur.
  Un thème n'a lieu que les jours listés dans `jours` (0 = lundi) ; --force ignore ce filtre.
  Fenêtre glissante : seuls les non-lus publiés depuis `fenetre_jours` (défaut : 2 pour un thème
  quotidien, 8 pour un hebdo) sont candidats, les plus récents d'abord, au plus `max_entrees`.
  Les non-lus plus anciens sont expirés (marqués lus) sans être traités : une veille en retard
  n'a pas de valeur, et sans cette expiration un flux volumineux creusait un retard sans fin
  (harnais-agents lisait des items vieux de six semaines le 2026-11-13).
"""

import json
import os
import re
import sys
import time
import traceback
from html import unescape

import commun

SENTINELLE = "RIEN_DE_NEUF"
CONTRAT = (
    "CONTRAT DE SORTIE. Tu écris un digest Telegram en français à partir UNIQUEMENT des items "
    "fournis (source, titre, lien, date, résumé). Texte brut : pas de Markdown, pas d'astérisques, "
    "pas de crochets. Chaque item retenu porte son lien EXACT sur une ligne commençant par '🔗 '. "
    "N'invente ni lien, ni version, ni chiffre. Sépare les blocs par une ligne '———'. Longueur "
    "totale sous 3000 caractères. Aucune introduction, aucune conclusion, aucune description de "
    "ta démarche. Si, après application de la consigne ci-dessous, il n'y a RIEN à rapporter, "
    "réponds exactement et uniquement : %s\n\nCONSIGNE DU THÈME (%s) :\n%s"
)


def sans_html(s):
    return " ".join(
        unescape(re.sub(r"<[^>]+>", " ", s or "")).replace("\xa0", " ").split()
    )


def indexer(categorie, texte):
    """Mémoire txtai, un document par bloc. Un échec ici n'empêche pas le marquage lu."""
    date = commun.maintenant().strftime("%Y-%m-%d")
    exe = commun.maintenant().strftime("%Y%m%dT%H%M")
    entete = "[Digest veille — thème: %s · date: %s · execution: %s]" % (
        categorie,
        date,
        exe,
    )
    docs = [
        {
            "id": "digest:%s:%s:%04d" % (categorie, exe, i),
            "text": entete + "\n\n" + b,
            "source": "veille",
            "job": categorie,
            "date": date,
        }
        for i, b in enumerate(b.strip() for b in texte.split("———") if b.strip())
    ]
    h = {"Authorization": "Bearer " + os.environ["TXTAI_TOKEN"]}
    commun.http(commun.TXTAI + "/add", docs, headers=h, timeout=300)
    commun.http(commun.TXTAI + "/upsert", headers=h, timeout=300)
    return len(docs)


def expirer(cat, avant):
    """Marque lus les non-lus publiés avant `avant` (epoch) : hors fenêtre, jamais traités."""
    n = 0
    while True:
        d = commun.miniflux(
            "/v1/categories/%d/entries?status=unread&before=%d&limit=500" % (cat, avant)
        )
        ids = [e["id"] for e in d.get("entries", [])]
        if not ids:
            return n
        commun.miniflux(
            "/v1/entries", {"entry_ids": ids, "status": "read"}, method="PUT"
        )
        n += len(ids)


def un_theme(nom, t):
    cats = commun.miniflux("/v1/categories")
    cat = next((c["id"] for c in cats if c["title"] == t["categorie"]), None)
    if cat is None:
        raise RuntimeError("catégorie Miniflux « %s » introuvable" % t["categorie"])
    fenetre = t.get("fenetre_jours", 8 if "jours" in t else 2)
    depuis = int(time.time()) - fenetre * 86400
    expires = expirer(cat, depuis)
    d = commun.miniflux(
        "/v1/categories/%d/entries?status=unread&after=%d&order=published_at&direction=desc&limit=%d"
        % (cat, depuis, t["max_entrees"])
    )
    entrees = d.get("entries", [])
    print(
        "  %s : %d entrée(s) non lue(s) traitée(s) sur %d j, %d expirée(s)"
        % (nom, len(entrees), fenetre, expires),
        flush=True,
    )
    if not entrees:
        return "rien à lire"
    items = [
        {
            "source": (e.get("feed") or {}).get("title", ""),
            "titre": (e.get("title") or "").strip(),
            "lien": e.get("url"),
            "date": (e.get("published_at") or "")[:10],
            "resume": sans_html(e.get("content"))[:700],
        }
        for e in entrees
    ]
    texte = commun.llm(
        CONTRAT % (SENTINELLE, t["categorie"], t["consigne"]),
        json.dumps(items, ensure_ascii=False),
    )
    if not texte:
        raise RuntimeError("le modèle a rendu un contenu vide")
    if SENTINELLE in texte[:80] and len(texte) < 120:
        bilan = "silence (rien de notable)"
    else:
        n = commun.telegram(texte)
        try:
            docs = indexer(t["categorie"], texte)
        except Exception as e:
            docs = "échec (%s)" % e
        bilan = "%d message(s), %d car., txtai %s" % (n, len(texte), docs)
    # Marqué lu APRÈS l'envoi : un envoi raté laisse les entrées non lues pour le run suivant.
    commun.miniflux(
        "/v1/entries",
        {"entry_ids": [e["id"] for e in entrees], "status": "read"},
        method="PUT",
    )
    return bilan


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    themes = json.load(open(os.path.join(commun.CODE, "themes.json"), encoding="utf-8"))
    jour = commun.maintenant().weekday()
    echecs = []
    for nom in args:
        t = themes[nom]
        if not force and "jours" in t and jour not in t["jours"]:
            print("  %s : pas aujourd'hui (jours %s)" % (nom, t["jours"]), flush=True)
            continue
        try:
            print("  %s : %s" % (nom, un_theme(nom, t)), flush=True)
        except Exception:
            tb = traceback.format_exc()
            print(tb, file=sys.stderr, flush=True)
            echecs.append("%s : %s" % (nom, tb.strip().splitlines()[-1][:300]))
    if echecs:
        commun.alerte("digest " + " ".join(args), "\n".join(echecs))
        sys.exit(1)


if __name__ == "__main__":
    commun.principal("digest " + " ".join(sys.argv[1:]), main)
