#!/usr/bin/env python3
"""Triage des échecs d'éval : dit POURQUOI un item a échoué, sans toucher au verdict.

POURQUOI CET OUTIL EXISTE. Le 2026-09-08, le harnais affichait depuis des semaines
`NameError: name 'calc' is not defined` sur trois items de codage, pour SIX
candidats d'affilée. Ça ressemblait à du code faux. C'était du code JAMAIS ÉCRIT :
le budget de 2048 tokens partait en raisonnement et `content` restait vide. Le
plafond de codage à 11/14 = 0.786 qui en résultait faisait rendre des scores
IDENTIQUES à un modèle de 2,6 Md et à un modèle de 27 Md.

Personne ne l'a vu pendant des semaines parce que le harnais rapportait un
SYMPTÔME sans sa CAUSE. Cet outil comble ce trou, et rien d'autre.

CE QU'IL N'EST PAS. Ce n'est pas un juge. Le verdict reste `run_eval.py` (asserts
dans un conteneur) puis `promote.sh`. Un modèle qui note d'autres modèles plafonne
l'évaluation à son propre niveau — et le modèle `current` de ce cluster
(gemma-4-12b-it-qat) rate lui-même des items du jeu. La règle est écrite depuis
juillet en tête de `quant-sweep.sh` : « VÉRIFICATEUR : le harness déterministe,
pas un jugement du modèle ». Le triage la respecte : il ne fait que CLASSER des
causes à partir de preuves déjà enregistrées, par des règles. Aucun token de LLM,
aucun non-déterminisme, aucune hallucination possible.

DEUX NIVEAUX.
  · par run    : classe la cause de chaque échec du candidat
  · inter-runs : signale les items SUSPECTS (ratés par presque tous les candidats
                 -> soupçonner l'item, pas le modèle) et les items INUTILES
                 (réussis par tous -> zéro information, du temps de calcul perdu)

Le second niveau est celui qui aurait révélé le plafond en un jour.

Usage :  triage.py <resultats.json>            # triage d'un run
         triage.py <resultats.json> --tous     # + analyse inter-runs
         triage.py --items                     # analyse inter-runs seule
         triage.py <resultats.json> --court    # 4 lignes, pour une notification
"""

from __future__ import annotations
import glob
import json
import os
import re
import sys

DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
CATEGORIES = ("coding", "reasoning", "format", "toolcall", "agentic")

# DEUX détecteurs, et le second est celui qui compte.
#
# Le taux global ne suffit PAS. Vérifié sur les 26 relevés : `calc_ii` est réussi
# par 19 % des candidats, `median_sorted` par 42 %, `regex_match` par 31 %. Aucun
# ne descend sous un seuil de rareté raisonnable, alors que tous les trois étaient
# cassés par un artefact de mesure. Un seuil de taux n'aurait rien vu.
#
# Ce qui saute aux yeux, c'est la SÉRIE : ces items étaient ratés par 7 candidats
# CONSÉCUTIFS. C'est ce motif-là qu'on a fini par remarquer à l'œil le 2026-09-08,
# après des semaines. Un item soluble que les N derniers candidats ratent tous
# accuse la mesure avant d'accuser les modèles.
SEUIL_SUSPECT = float(os.environ.get("TRIAGE_SEUIL_SUSPECT", "0.9"))
MIN_CANDIDATS = int(os.environ.get("TRIAGE_MIN_CANDIDATS", "8"))
SEUIL_SERIE = int(os.environ.get("TRIAGE_SEUIL_SERIE", "5"))


def classe(cat: str, r: dict) -> tuple[str, str]:
    """(classe, explication). Règles ordonnées du plus certain au plus général."""
    detail = str(r.get("detail") or "")
    tronque = bool(r.get("tronque"))
    rais = r.get("raisonnement")
    bloc = r.get("bloc")
    toks = r.get("tokens")

    # --- causes qui NE SONT PAS une faiblesse du modèle sur la tâche ---------
    if re.search(r"HTTP|Connection|timed out|502|503|500", detail, re.I) and "assert" not in detail.lower():
        return ("SERVEUR", "erreur de transport, la tâche n'a pas été jugée : %s" % detail[:80])

    if tronque and bloc is False:
        sup = " (%d car. de raisonnement, %s tokens)" % (rais, toks) if rais is not None else ""
        return ("TRONQUÉ", "budget épuisé avant d'écrire la réponse%s — ce n'est pas une "
                           "erreur de contenu, c'est une absence de contenu" % sup)

    if tronque:
        return ("TRONQUÉ_PARTIEL", "réponse coupée mais un bloc a été extrait — le "
                                   "jugement porte sur du contenu incomplet")

    if re.search(r"NameError: name '([^']+)' is not defined", detail):
        if bloc is False:
            return ("RIEN_ÉCRIT", "aucun bloc de code extrait ; le NameError vient du vide, "
                                  "pas d'un code fautif")
        if bloc is None:
            # Relevé antérieur à l'enregistrement des preuves. On NE DEVINE PAS : un
            # NameError peut venir d'un code absent (troncature) comme d'un mauvais nom
            # de fonction, et confondre les deux est exactement l'erreur que cet outil
            # existe pour empêcher.
            return ("INDÉTERMINÉ", "NameError sans preuve enregistrée : code absent "
                                   "(troncature) ou mauvais nom, impossible de trancher "
                                   "— relevé antérieur au 2026-09-08, relancer pour savoir")

    # --- vraies faiblesses, par nature -------------------------------------
    if cat == "coding":
        if "AssertionError" in detail:
            return ("CODE_FAUX", "code écrit, exécuté, et faux sur au moins une assertion "
                                 "— vraie faiblesse")
        if "SyntaxError" in detail:
            return ("CODE_INVALIDE", "le code ne compile pas ; vérifier qu'il n'a pas été "
                                     "coupé ou noyé dans de la prose")
        if "timeout" in detail.lower():
            return ("BOUCLE", "le code tourne sans fin ou dépasse la limite CPU")
        if re.search(r"NameError|AttributeError|TypeError", detail):
            return ("MAUVAIS_NOM", "fonction ou signature qui ne correspond pas à l'énoncé")

    if cat == "toolcall":
        if "abstention" in detail:
            return ("A_SUR-APPELÉ", "a appelé un outil là où il fallait s'abstenir")
        if detail.strip() in ("no tool_call", "") or "no tool_call" in detail:
            return ("AUCUN_APPEL", "n'a émis aucun appel d'outil")
        m = re.search(r"name=(\S+)\s+args=(.*)", detail)
        if m:
            return ("MAUVAIS_APPEL", "outil ou arguments incorrects : %s" % detail[:90])

    if cat == "reasoning":
        if re.search(r"got=None", detail):
            return ("PAS_DE_RÉPONSE", "aucun nombre extrait de la réponse — format ou "
                                      "réponse absente, pas forcément un calcul faux")
        return ("CALCUL_FAUX", detail[:80])

    if cat == "format":
        return ("FORMAT_NON_RESPECTÉ", "sortie non conforme : %s" % detail[:80])

    if cat == "agentic":
        if re.search(r"boucle épuisée|max_turns|tours", detail, re.I):
            return ("TOURS_ÉPUISÉS", "n'a pas conclu dans le budget de tours")
        return ("TÂCHE_NON_CONCLUE", detail[:80])

    return ("AUTRE", detail[:90] or "sans détail")


def triage_run(chemin: str) -> dict:
    j = json.load(open(chemin))
    nom = j.get("model", os.path.basename(chemin))
    if j.get("unreachable"):
        return {"modele": nom, "injoignable": True, "echecs": [], "classes": {}}
    echecs = []
    for cat in CATEGORIES:
        for r in j.get(cat, []):
            if not r.get("pass"):
                c, exp = classe(cat, r)
                echecs.append({"cat": cat, "id": r.get("id"), "classe": c, "explication": exp})
    classes: dict[str, int] = {}
    for e in echecs:
        classes[e["classe"]] = classes.get(e["classe"], 0) + 1
    return {"modele": nom, "injoignable": False, "echecs": echecs, "classes": classes,
            "metrics": j.get("metrics", {})}


def recommandations(t: dict) -> list[str]:
    """Ce qu'il faut FAIRE, dérivé des classes rencontrées."""
    out = []
    c = t["classes"]
    n_tronque = c.get("TRONQUÉ", 0) + c.get("TRONQUÉ_PARTIEL", 0) + c.get("RIEN_ÉCRIT", 0)
    if n_tronque:
        out.append("%d item(s) sans réponse écrite : le score de capacité est SOUS-ESTIMÉ. "
                   "Monter EVAL_CODING_MAX_TOKENS, ou constater que ce modèle s'emballe "
                   "(raisonnement qui ne converge pas)." % n_tronque)
    if c.get("SERVEUR"):
        out.append("%d item(s) perdus sur erreur de transport : relancer, ces items n'ont "
                   "pas été jugés." % c["SERVEUR"])
    if c.get("AUCUN_APPEL"):
        out.append("%d appel(s) d'outil absents : vérifier le gabarit de conversation et "
                   "`automatic_tool_parsing_fallback`. Ce défaut est réparable par la "
                   "plomberie (cf. forge), il ne mesure pas la décision." % c["AUCUN_APPEL"])
    if c.get("A_SUR-APPELÉ"):
        out.append("a appelé un outil hors sujet : défaut de DÉCISION, qu'aucune couche "
                   "externe ne répare.")
    if c.get("PAS_DE_RÉPONSE"):
        out.append("%d réponse(s) numériques non extraites : format, pas calcul." % c["PAS_DE_RÉPONSE"])
    if c.get("INDÉTERMINÉ"):
        out.append("%d échec(s) INDÉTERMINÉS : relevé antérieur à l'enregistrement des "
                   "preuves. Ne pas conclure sur ce candidat, le relancer." % c["INDÉTERMINÉ"])
    if c.get("CODE_FAUX") and not n_tronque:
        out.append("%d échec(s) de code propres (écrit, exécuté, faux) : c'est une vraie "
                   "mesure de capacité, exploitable telle quelle." % c["CODE_FAUX"])
    return out


def analyse_items() -> dict:
    """Niveau inter-runs : items suspects et items inutiles."""
    # Ordonné par DATE : la série n'a de sens que chronologiquement.
    releves = []
    for f in glob.glob(os.path.join(DOSSIER, "*-candidate.json")):
        try:
            j = json.load(open(f))
        except Exception:
            continue
        if j.get("unreachable"):
            continue
        items = {}
        for cat in CATEGORIES:
            for r in j.get(cat, []):
                items[cat + "." + r["id"]] = bool(r.get("pass"))
        if items:
            releves.append((os.path.getmtime(f), j.get("model", os.path.basename(f)), items))
    releves.sort()

    par_item: dict[str, list] = {}
    for _, _, items in releves:
        for k, v in items.items():
            par_item.setdefault(k, []).append(v)

    suspects, inutiles, series = [], [], []
    for k, v in sorted(par_item.items()):
        if len(v) < MIN_CANDIDATS:
            continue
        taux = sum(v) / len(v)
        if taux <= (1 - SEUIL_SUSPECT):
            suspects.append((k, taux, len(v)))
        elif taux == 1.0:
            inutiles.append((k, len(v)))
        # série d'échecs consécutifs la PLUS RÉCENTE
        serie = 0
        for _, _, items in reversed(releves):
            if k not in items:
                continue
            if items[k]:
                break
            serie += 1
        # `taux > 0` : un item que PERSONNE n'a jamais réussi peut être insoluble,
        # c'est un autre problème (déjà couvert par `suspects`). Ici on cherche les
        # items PROUVÉS solubles que les derniers candidats ratent tous — signature
        # d'une mesure qui a cassé, pas d'un item trop dur.
        if serie >= SEUIL_SERIE and taux > 0:
            series.append((k, serie, taux, len(v)))
    series.sort(key=lambda x: -x[1])
    return {"n_runs": len(releves), "suspects": suspects, "inutiles": inutiles,
            "series": series, "dernier": releves[-1][1] if releves else "-"}


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    court = "--court" in sys.argv
    tous = "--tous" in sys.argv
    items_seuls = "--items" in sys.argv

    if items_seuls and not args:
        a = analyse_items()
        print("=== analyse inter-runs sur %d relevés ===" % a["n_runs"])
        for k, serie, taux, n in a.get("series", []):
            print("  SÉRIE    %-34s raté par les %d DERNIERS candidats d'affilée "
                  "(réussi par %.0f%% au total) — accuser la MESURE avant les modèles"
                  % (k, serie, taux * 100))
        for k, taux, n in a["suspects"]:
            print("  SUSPECT  %-34s réussi par %.0f%% des candidats (%d) — soupçonner "
                  "l'ITEM" % (k, taux * 100, n))
        for k, n in a["inutiles"]:
            print("  INUTILE  %-34s réussi par 100%% des candidats (%d) — zéro information" % (k, n))
        if not a.get("series") and not a["suspects"] and not a["inutiles"]:
            print("  aucun item suspect, en série, ni inutile")
        return 0

    if not args:
        print(__doc__.strip().splitlines()[-4], file=sys.stderr)
        print("usage: triage.py <resultats.json> [--tous] [--court] | triage.py --items",
              file=sys.stderr)
        return 2

    t = triage_run(args[0])
    if t["injoignable"]:
        print("TRIAGE %s : MODÈLE INJOIGNABLE — aucune mesure, rien à diagnostiquer." % t["modele"])
        return 0

    recos = recommandations(t)
    if court:
        # Format compact, destiné à une notification Telegram.
        if not t["echecs"]:
            print("TRIAGE : aucun échec.")
            return 0
        resume = " · ".join("%s×%d" % (k, v) for k, v in
                            sorted(t["classes"].items(), key=lambda x: -x[1]))
        print("TRIAGE %d échec(s) — %s" % (len(t["echecs"]), resume))
        for r in recos[:2]:
            print("  → " + r)
        return 0

    print("=== TRIAGE : %s ===" % t["modele"])
    m = t["metrics"]
    if m:
        print("   overall %.3f · coding %.3f · tronqués %s · %.1f tok/s"
              % (m.get("overall", 0), m.get("coding_pass_rate", 0),
                 m.get("coding_truncated", "?"), m.get("mean_tokps", 0)))
    print()
    if not t["echecs"]:
        print("   aucun échec.")
    else:
        for e in t["echecs"]:
            print("  %-9s %-22s %-18s %s" % (e["cat"], e["id"], e["classe"], e["explication"]))
        print()
        print("   répartition : " + " · ".join("%s×%d" % (k, v) for k, v in
                                               sorted(t["classes"].items(), key=lambda x: -x[1])))
    if recos:
        print()
        print("=== à faire ===")
        for r in recos:
            print("  → " + r)
    if tous:
        print()
        a = analyse_items()
        print("=== analyse inter-runs sur %d relevés (dernier : %s) ===" % (a["n_runs"], a["dernier"]))
        for k, serie, taux, n in a.get("series", []):
            print("  SÉRIE    %-34s raté par les %d derniers d'affilée (%.0f%% au total) "
                  "— accuser la MESURE" % (k, serie, taux * 100))
        for k, taux, n in a["suspects"]:
            print("  SUSPECT  %-34s réussi par %.0f%% (%d) — soupçonner l'ITEM" % (k, taux * 100, n))
        for k, n in a["inutiles"]:
            print("  INUTILE  %-34s réussi par 100%% (%d) — zéro information" % (k, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
