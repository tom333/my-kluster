"""Inventaire SYSTÉMATIQUE des échecs, sur tous les tirages archivés.

Motif (2026-08-06). Meta-Harness (arXiv:2603.28052) attribue son gain au fait que le
proposeur accède à TOUTE la preuve — code, scores et traces de tous les candidats
antérieurs — là où les optimiseurs précédents « compressent trop agressivement ».
On ne peut pas se payer leur boucle (89 tâches × 5 tirages par candidat), mais on
peut se payer l'ingrédient qui fait la différence : lire l'ensemble.

Ce que ça remplace : mes lectures de deux à trois transcripts, qui ont produit sept
leviers dont UN a survécu à l'appariement. L'inventaire est reproductible ; une
lecture anecdotique ne l'est pas.

Rien n'est déduit ici, tout est compté. Chaque chiffre est une fréquence sur les
tirages réellement archivés, avec son effectif — pas une impression.

    python3 inventaire.py                 # tous les scénarios
    python3 inventaire.py --scenario pronote
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


def tirages(scenario=None, invalides=False):
    """Un dict par tirage, depuis les agrégats de campagne (source la plus riche).

    Les campagnes tuées n'ont pas d'agrégat : leurs tirages ne sont donc PAS ici, et
    c'est dit dans le récapitulatif plutôt que masqué.
    """
    out, ecartees = [], []
    for chemin in sorted(RESULTS.glob("*.json")):
        try:
            d = json.loads(chemin.read_text())
        except (ValueError, OSError):
            continue
        if not isinstance(d, dict) or "essais" not in d:
            continue
        # Campagnes mesurees SOUS UN DEFAUT DU BANC (cf. marque_invalides.py) :
        # ecartees par defaut. Les inclure moyennerait une fuite d'environnement
        # avec des mesures propres -- ce que la premiere passe de cet inventaire a
        # fait le 2026-08-06 sans le savoir. Elles ne sont pas supprimees pour
        # autant : la comparaison 2/5 contre 4/5 qui a chiffre la fuite n'existe
        # QUE parce qu'elles ont ete gardees.
        if d.get("invalide") and not invalides:
            ecartees.append((chemin.name, d["invalide"]))
            continue
        if scenario and d.get("scenario") != scenario:
            continue
        for e in d["essais"]:
            if not isinstance(e, dict):
                continue
            out.append(
                {
                    "campagne": chemin.name,
                    "scenario": d.get("scenario"),
                    "modele": d.get("modele"),
                    "verdict": e.get("verdict"),
                    "passed": e.get("tests_passed"),
                    "attendus": e.get("tests_attendus"),
                    "arret": e.get("stop_reason"),
                    "tours": e.get("tours"),
                    "pic": e.get("pic_input"),
                    "tronques": e.get("tours_tronques"),
                    "erreur": e.get("erreur"),
                    "retries": e.get("retries_troncature"),
                    # `appels_outils` a CHANGÉ de forme en cours de route : un entier
                    # (total) dans les campagnes d'avant le 2026-08-02, un dict
                    # {outil: n} depuis. On garde le dict et on compte les entiers
                    # comme « détail perdu » plutôt que de faire semblant.
                    "outils": e.get("appels_outils")
                    if isinstance(e.get("appels_outils"), dict)
                    else {},
                    "outils_total": e.get("appels_outils")
                    if isinstance(e.get("appels_outils"), int)
                    else None,
                    "duree": e.get("duree_s"),
                    "lignes": e.get("lignes_ecrites"),
                    "verifications": e.get("verifications"),
                }
            )
    if ecartees:
        print("%d campagne(s) ecartee(s) comme invalides (--invalides pour les inclure) :"
              % len(ecartees))
        for nom, motif in ecartees:
            print("  %-58s %s" % (nom, motif[:60]))
        print()
    return out


def part(n, total):
    return "%5.1f %%" % (n / total * 100) if total else "    — "


def rapport(t):
    total = len(t)
    if not total:
        print("aucun tirage")
        return
    reussis = [x for x in t if x["verdict"] == "PASS"]
    echecs = [x for x in t if x["verdict"] != "PASS"]

    print("=" * 74)
    print(
        "%d tirages archivés | %d PASS (%s) | %d échecs"
        % (total, len(reussis), part(len(reussis), total), len(echecs))
    )
    print("=" * 74)

    print("\n-- CAUSES D'ARRÊT, et le score qu'elles donnent --")
    par_arret = defaultdict(list)
    for x in t:
        par_arret[x["arret"] or "?"].append(x)
    print("%-16s %5s %8s   %s" % ("arrêt", "n", "part", "dont PASS"))
    for arret, groupe in sorted(par_arret.items(), key=lambda kv: -len(kv[1])):
        p = sum(1 for x in groupe if x["verdict"] == "PASS")
        print(
            "%-16s %5d %8s   %d (%s)"
            % (arret, len(groupe), part(len(groupe), total), p, part(p, len(groupe)))
        )

    print("\n-- CE QUE L'ARRÊT PRÉDIT --")
    # La question qui decide : mourir empeche-t-il de reussir ?
    morts = [x for x in t if x["arret"] in ("error", "truncated", "verify_echec")]
    finis = [x for x in t if x["arret"] in ("done", "done_verifie")]
    for etiquette, groupe in (("arrêts propres", finis), ("morts en vol", morts)):
        if not groupe:
            continue
        p = sum(1 for x in groupe if x["verdict"] == "PASS")
        print(
            "%-16s %3d tirages, %s de PASS"
            % (etiquette, len(groupe), part(p, len(groupe)))
        )

    print("\n-- TRONCATURE --")
    # `tours_tronques` n'a ete propage par bench.py qu'a partir du 2026-08-06 :
    # `absent` n'est PAS `zero`, et les confondre a rendu la premiere passe de cet
    # inventaire faussement rassurante (« 0 tour tronque » sur 290 tirages).
    connus = [x for x in t if x["tronques"] is not None]
    avec = [x for x in connus if x["tronques"] > 0]
    print(
        "compteur renseigné : %d tirages sur %d%s"
        % (
            len(connus),
            total,
            "" if len(connus) == total else "  (champ absent avant le 2026-08-06)",
        )
    )
    if connus:
        print(
            "   tours coupés par max_tokens : %d (%s)"
            % (len(avec), part(len(avec), len(connus)))
        )
    rej = [x for x in t if (x["retries"] or 0) > 0]
    p = sum(1 for x in rej if x["verdict"] == "PASS")
    print(
        "reprise sur troncature déclenchée : %d tirages (%s), dont PASS %s"
        % (len(rej), part(len(rej), total), part(p, len(rej)))
    )

    print("\n-- PANNES : ce que `error` recouvre vraiment --")
    # 21 % des tirages meurent en `error` avec 1,6 % de PASS : c'est le plus gros
    # gisement. Mais une panne HTTP n'est pas une contre-performance du modele, et
    # les melanger noterait une panne d'instrument comme un score. On classe.
    motifs = (
        ("contexte dépassé", ("context", "n_ctx", "exceed", "too long", "kv cache")),
        ("connexion coupée", ("connection", "closed", "reset", "broken pipe", "eof")),
        ("délai dépassé", ("timeout", "timed out")),
        ("HTTP 500", ("500", "internal server")),
        ("outil mal formé", ("tool", "json", "parse", "decode")),
    )
    en_erreur = [x for x in t if x["erreur"]]
    classes = Counter()
    for x in en_erreur:
        texte = str(x["erreur"]).lower()
        etiquette = next(
            (nom for nom, cles in motifs if any(c in texte for c in cles)), "non classé"
        )
        classes[etiquette] += 1
    print(
        "tirages portant un message d'erreur : %d (%s)"
        % (len(en_erreur), part(len(en_erreur), total))
    )
    for nom, n in classes.most_common():
        print("   %-20s %3d  %s" % (nom, n, part(n, len(en_erreur))))
    for x in en_erreur:
        if str(x["erreur"]).lower().find("context") < 0:
            continue
        print("   exemple contexte : %s" % str(x["erreur"])[:110])
        break

    print("\n-- SATURATION : le pic de contexte contre le sort du tirage --")
    # Les deux codes HTTP ne disent pas la meme chose. Croises avec `pic_input` :
    # 400 -> pic median 47 333, 18 sur 20 au-dela de 30 000 ; 500 -> pic median
    # 45 882 mais un minimum a 651. Le 400 est donc un debordement de contexte, le
    # 500 un melange (dont le `tool_call` tranche par notre propre plafond).
    # ATTENTION a l'ordre des causes : un tirage long a un gros pic PARCE QU'il a
    # dure. La correlation ci-dessous ne prouve pas le sens ; ce qui le prouvera est
    # le corps de reponse, capture depuis le 2026-08-06 seulement.
    paliers = ((0, 10000), (10000, 20000), (20000, 30000), (30000, 10**9))
    print("%-16s %5s %10s %12s" % ("pic input", "n", "PASS", "morts HTTP"))
    for bas, haut in paliers:
        g = [x for x in t if bas <= (x["pic"] or 0) < haut]
        if not g:
            continue
        p = sum(1 for x in g if x["verdict"] == "PASS")
        h = sum(1 for x in g if x["arret"] == "error")
        print(
            "%-16s %5d %10s %12s"
            % (
                "%d-%s" % (bas, haut if haut < 10**9 else "+"),
                len(g),
                part(p, len(g)),
                part(h, len(g)),
            )
        )

    # A partir d'ici : SEULS les tirages qui portent la ventilation par outil. Les
    # compter tous ferait passer chaque vieille campagne pour un tirage « sans aucune
    # ecriture », ce qui est une conclusion fabriquee par le format, pas mesuree.
    ventiles = [x for x in t if x["outils"]]
    print(
        "\n-- OUTILS : échecs contre réussites (%d tirages ventilés sur %d) --"
        % (len(ventiles), total)
    )
    v_ok = [x for x in ventiles if x["verdict"] == "PASS"]
    v_ko = [x for x in ventiles if x["verdict"] != "PASS"]
    print("%-12s %12s %12s" % ("outil", "réussites", "échecs"))
    noms = sorted({o for x in ventiles for o in x["outils"]})
    for nom in noms:
        m_ok = median([x["outils"].get(nom, 0) for x in v_ok]) if v_ok else 0
        m_ko = median([x["outils"].get(nom, 0) for x in v_ko]) if v_ko else 0
        print("%-12s %12s %12s" % (nom, m_ok, m_ko))

    print("\n-- ZÉRO ÉCRITURE : l'échec le plus coûteux --")
    muets = [
        x for x in ventiles if not (x["outils"].get("write") or x["outils"].get("edit"))
    ]
    print(
        "tirages sans un seul write ni edit : %d sur %d ventilés (%s)"
        % (len(muets), len(ventiles), part(len(muets), len(ventiles)))
    )
    for x in muets[:6]:
        print(
            "   %-34s %s/%s  %s  %d tours"
            % (
                x["modele"][:34],
                x["passed"],
                x["attendus"],
                x["arret"],
                x["tours"] or 0,
            )
        )

    print("\n-- MÉDIANES --")
    for etiquette, groupe in (("réussites", reussis), ("échecs", echecs)):
        if not groupe:
            continue
        print(
            "%-10s tours %-5s pic %-7s durée %-7s lignes %s"
            % (
                etiquette,
                median([x["tours"] or 0 for x in groupe]),
                median([x["pic"] or 0 for x in groupe]),
                "%.0fs" % median([x["duree"] or 0 for x in groupe]),
                median([x["lignes"] or 0 for x in groupe]),
            )
        )

    print("\n-- PAR SCÉNARIO --")
    print("%-16s %5s %10s %s" % ("scénario", "n", "PASS", "arrêts dominants"))
    par_sc = defaultdict(list)
    for x in t:
        par_sc[x["scenario"] or "?"].append(x)
    for sc, groupe in sorted(par_sc.items(), key=lambda kv: -len(kv[1])):
        p = sum(1 for x in groupe if x["verdict"] == "PASS")
        top = Counter(x["arret"] for x in groupe).most_common(2)
        print(
            "%-16s %5d %10s %s"
            % (
                sc,
                len(groupe),
                part(p, len(groupe)),
                ", ".join("%s×%d" % (a, n) for a, n in top),
            )
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default=None)
    parser.add_argument(
        "--invalides",
        action="store_true",
        help="inclut les campagnes marquees comme mesurees sous un defaut du banc",
    )
    args = parser.parse_args()
    rapport(tirages(args.scenario, args.invalides))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
