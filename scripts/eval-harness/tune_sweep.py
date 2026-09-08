#!/usr/bin/env python3
"""Vérifie la config déduite en CHARGEANT, et essaie deux variantes autour.

POURQUOI. `derive_config.py` calcule un point de départ depuis l'en-tête GGUF, mais
le tampon de calcul de llama.cpp n'est pas déductible : la config déduite est une
hypothèse. Et l'écart mesuré entre une config quelconque et une config réglée est
énorme — gemma-4-26b passe de 23,9 à 36,4 tok/s (+52 %) et qwen3.8-27b-gsq-rco
passe d'un backend mort à un modèle qui génère. Comparer des candidats sur des
configs non réglées est aussi invalide que le plafond de codage corrigé ce matin.

L'ARBITRAGE CENTRAL, découvert le 2026-09-08 : le contexte coûte de la VRAM qui
aurait pu tenir des experts sur la carte. Sur un MoE, réduire `ctx` permet de
déporter MOINS de couches, donc d'aller plus vite. Le balayage explore justement
cet échange, qu'aucun calcul d'en-tête ne peut trancher.

CE QU'IL MESURE, par config : est-ce que ça CHARGE, la VRAM occupée, et le débit en
tok/s sur un prompt fixe. Trois grandeurs objectives, aucun jugement.

COÛT. Chaque config = un redémarrage de LocalAI (~40 à 90 s) plus une génération.
Compter ~2 min par config, soit ~6 min pour trois — contre 11 à 40 min d'éval
gaspillés sur une mauvaise config, ou un plantage comme celui de gsq-rco.

⚠ Il redémarre LocalAI plusieurs fois : le service est indisponible par
intermittence pendant le balayage. C'est déjà ce que fait `stage_candidate.sh`.

Usage :  tune_sweep.py --name <modele-servi> [--ctx-max N] [--go]
         sans --go : affiche le plan sans rien toucher
"""

from __future__ import annotations
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

NS = "localai"
BASE = os.environ.get("LOCALAI_URL", "https://localai.tgu.ovh/v1")
PROMPT = ("Écris une fonction Python qui fusionne deux listes triées en une seule "
          "liste triée, sans utiliser sorted(). Explique brièvement.")
MAX_TOKENS = int(os.environ.get("TUNE_MAX_TOKENS", "300"))
ATTENTE_PRET = int(os.environ.get("TUNE_ATTENTE_PRET", "600"))


def sh(cmd: list[str], timeout: int = 120) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip()


def pvc() -> str:
    d = sh(["sh", "-c", "ls -d /data/kube/default-storage/localai-localai-models-pvc-* "
                        "2>/dev/null | head -1"])
    if not d:
        raise SystemExit("PVC localai-models introuvable")
    return d


def pod() -> str:
    return sh(["sh", "-c", "kubectl get pods -n %s --no-headers 2>/dev/null | "
                           "awk '/^localai-[0-9a-f]/{print $1}' | head -1" % NS])


def cle_api() -> str:
    return sh(["sh", "-c", "kubectl get secret -n %s localai-api-key "
                           "-o jsonpath='{.data.api-key}' | base64 -d" % NS])


def vram_mio() -> int:
    v = sh(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"])
    return int(v.splitlines()[0]) if v else -1


def redemarre_et_attend() -> str:
    p = pod()
    if p:
        sh(["kubectl", "delete", "pod", "-n", NS, p], timeout=180)
    t0 = time.time()
    while time.time() - t0 < ATTENTE_PRET:
        p = pod()
        if p:
            etat = sh(["sh", "-c", "kubectl get pod -n %s %s --no-headers 2>/dev/null | "
                                   "awk '{print $2}'" % (NS, p)])
            if etat == "1/1":
                return p
        time.sleep(10)
    return ""


def genere(nom: str, cle: str, tokens: int | None = None) -> dict:
    """(ok, tokps, erreur). Une erreur de CHARGEMENT est un résultat, pas un incident."""
    corps = {"model": nom, "messages": [{"role": "user", "content": PROMPT}],
             "max_tokens": tokens or MAX_TOKENS, "temperature": 0.0}
    req = urllib.request.Request(BASE + "/chat/completions",
                                 data=json.dumps(corps).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + cle})
    t0 = time.time()
    try:
        d = json.load(urllib.request.urlopen(req, timeout=900))
    except Exception as e:
        msg = str(e)
        try:
            msg = e.read().decode("utf-8", "replace")[:220]  # type: ignore[attr-defined]
        except Exception:
            pass
        return {"ok": False, "tokps": 0.0, "erreur": msg[:220]}
    dt = time.time() - t0
    ct = d.get("usage", {}).get("completion_tokens", 0)
    return {"ok": ct > 0, "tokps": (ct / dt) if dt > 0 and ct else 0.0,
            "tokens": ct, "erreur": "" if ct else "aucun token généré"}


def vram_prevue(c: dict, a: dict) -> int:
    """VRAM prévue en Mio pour une config, à partir des mesures d'en-tête."""
    poids = a["poids_octets"] / 1048576
    if c.get("n_cpu_moe") and a.get("exps_par_couche"):
        ordre = sorted(a["exps_par_couche"].items(), key=lambda kv: -kv[1])
        for _, oct_ in ordre[:c["n_cpu_moe"]]:
            poids -= oct_ / 1048576
    import derive_config as dc
    return int(poids + c["ctx"] * a["kv_par_token"] / 1048576 + dc.RESERVE_MIO)


def variantes(base: dict, moe: bool, a: dict | None = None,
              budget_mio: int | None = None) -> list[dict]:
    """Le plan de balayage. Trois configs au plus : chacune coûte un redémarrage.

    ON NE TESTE PAS CE QUE L'ARITHMÉTIQUE RÉFUTE DÉJÀ. Le 2026-09-08, la variante
    ctx=262144 sur deepseek-v4-pro-qwen3.5-9b-mtp demandait 12317 Mio prévus pour
    10800 disponibles — un calcul d'une ligne le disait. La tester n'a rien appris
    et a poussé la machine en swap saturé (15/15 Go, charge 10,2), ce qui a affamé
    kubelite : le serveur d'API a REFUSÉ LES CONNEXIONS pendant plusieurs minutes,
    et des dizaines de pods sont passés en Terminating. Un balayage doit rester
    inoffensif pour le plan de contrôle.
    """
    v = [dict(base, etiquette="A/déduite")]
    if moe and base.get("n_cpu_moe", 0) > 2:
        # Déporter MOINS = plus rapide si ça tient encore. C'est l'échange central :
        # on rend au GPU la VRAM du contexte pour y garder des experts.
        v.append(dict(base, n_cpu_moe=base["n_cpu_moe"] - 2,
                      ctx=max(4096, base["ctx"] // 2),
                      etiquette="B/moins de déport, ctx moitié"))
        v.append(dict(base, n_cpu_moe=base["n_cpu_moe"] + 2,
                      etiquette="C/plus de déport (repli sûr)"))
    else:
        # Sans MoE, le seul levier restant est le contexte : on teste si la réserve
        # VRAM était trop prudente. Si ça ne charge pas, la réponse est non.
        v.append(dict(base, ctx=base["ctx"] * 2, etiquette="B/ctx doublé"))
    if a and budget_mio:
        gardees = []
        for x in v:
            prevu = vram_prevue(x, a)
            if prevu > budget_mio:
                print("  · variante ÉCARTÉE sans essai : %s -> %d Mio prévus pour %d "
                      "disponibles (l'arithmétique suffit)"
                      % (x["etiquette"], prevu, budget_mio))
                continue
            gardees.append(x)
        return gardees
    return v


def ecris_yaml(chemin: str, nom: str, fichier_gguf: str, c: dict) -> str:
    opts = ["  - use_jinja:true", "  - parallel:1"]
    if c.get("n_cpu_moe"):
        opts.append('  - "--n-cpu-moe:%d"' % c["n_cpu_moe"])
        opts.append("  - fit:on")
    y = ("name: %s\nbackend: llama-cpp\nknown_usecases: [chat]\n"
         "context_size: %d\ngpu_layers: 99\nf16: true\nflash_attention: true\n"
         "mmap: true\ncache_type_k: q8_0\ncache_type_v: q8_0\n"
         "parameters:\n  model: %s\n  temperature: 0.6\n"
         "options:\n%s\n"
         "template:\n  use_tokenizer_template: true\n"
         % (nom, c["ctx"], fichier_gguf, "\n".join(opts)))
    open(chemin, "w").write(y)
    return y


def main() -> int:
    def opt(nom, defaut=None):
        for i, a in enumerate(sys.argv):
            if a == nom and i + 1 < len(sys.argv):
                return sys.argv[i + 1]
        return defaut

    nom = opt("--name")
    if not nom:
        print(__doc__.strip().splitlines()[-2], file=sys.stderr)
        return 2
    go = "--go" in sys.argv
    ctx_max = int(opt("--ctx-max", "32768"))

    P = pvc()
    yaml_actuel = os.path.join(P, nom + ".yaml")
    if not os.path.exists(yaml_actuel):
        print("ERREUR: %s absent — le candidat doit être servi (stage_candidate.sh)"
              % yaml_actuel, file=sys.stderr)
        return 2
    m = re.search(r"^\s*model:\s*(\S+)", open(yaml_actuel).read(), re.M)
    if not m:
        print("ERREUR: pas de `model:` dans %s" % yaml_actuel, file=sys.stderr)
        return 2
    fichier = m.group(1)
    gguf = os.path.join(P, fichier)

    import derive_config as dc
    e = dc.lire_entete(gguf)
    taille = os.path.getsize(gguf)
    dc.tailles_exactes(e, taille)
    a = dc.analyse(e, taille)
    c = dc.derive(a, dc.VRAM_DEFAUT_MIO, ctx_max)

    if c["confiance"] == "basse":
        # Point de départ = la config EN PLACE, pas une déduction non fiable.
        ctx_actuel = re.search(r"^context_size:\s*(\d+)", open(yaml_actuel).read(), re.M)
        base = {"ctx": int(ctx_actuel.group(1)) if ctx_actuel else 8192, "n_cpu_moe": 0}
        print("déduction ABSTENUE (%s) → point de départ = la config en place (ctx %d)"
              % (c["raisons"][0][:70], base["ctx"]))
    else:
        base = {"ctx": c["ctx"], "n_cpu_moe": c["n_cpu_moe"]}

    plan = variantes(base, a["moe"], a, dc.VRAM_DEFAUT_MIO)
    print("=== plan de balayage pour %s (%s, MoE=%s, SSM=%s, MTP=%s) ==="
          % (nom, a["arch"], a["moe"], a["ssm"], a["mtp"]))
    for v in plan:
        print("  %-30s ctx=%-6d n_cpu_moe=%d" % (v["etiquette"], v["ctx"], v["n_cpu_moe"]))
    print("  coût estimé : ~%d min (un redémarrage LocalAI par config)" % (2 * len(plan)))
    if not go:
        print("\n  Rien n'a été modifié. Ajouter --go pour exécuter.")
        return 0

    cle = cle_api()
    sauvegarde = open(yaml_actuel).read()
    resultats = []
    try:
        for v in plan:
            print("\n--- %s : ctx=%d n_cpu_moe=%d" % (v["etiquette"], v["ctx"], v["n_cpu_moe"]))
            ecris_yaml(yaml_actuel, nom, fichier, v)
            p = redemarre_et_attend()
            if not p:
                resultats.append(dict(v, ok=False, tokps=0.0, vram=-1,
                                      erreur="pod jamais prêt"))
                print("    pod jamais prêt")
                continue
            # PRÉCHAUFFAGE obligatoire. Sans lui, la requête chronométrée inclut le
            # chargement des poids en VRAM (9,26 Go pour gsq-rco) et le débit est
            # sous-estimé de moitié : 9,1 tok/s mesuré contre 19,9 réels, constaté au
            # premier essai de ce script le 2026-09-08. `run_eval.py` fait le même
            # préchauffage, pour la même raison.
            # LocalAI met un modèle en RETENUE (503 "load is in cooldown") après un
            # échec de chargement, et refuse de réessayer pendant un temps. Un 503 de
            # retenue n'est donc PAS un verdict sur la config : au premier essai de ce
            # script, la variante ctx=262144 a été rapportée en échec avec ce message
            # alors que la vraie cause était ailleurs. On patiente et on réessaie, et
            # si ça persiste on le dit INDÉTERMINÉ plutôt que de conclure.
            genere(nom, cle, tokens=8)
            r = genere(nom, cle)
            # « load is in cooldown AFTER A RECENT FAILURE » : le message dit lui-même
            # qu'un chargement a échoué. C'est donc un verdict, pas un contretemps —
            # et réessayer relance le chargement fautif, ce qui creuse la pression
            # mémoire et allonge le recul (10s -> 20s -> 40s, constaté le 2026-09-08).
            if not r["ok"] and "cooldown after a recent failure" in r["erreur"].lower():
                r["erreur"] = "chargement ÉCHOUÉ (LocalAI en retenue après échec) — " \
                              "config trop grosse pour la carte"
            vr = vram_mio()
            resultats.append(dict(v, ok=r["ok"], tokps=r["tokps"], vram=vr,
                                  erreur=r["erreur"]))
            print("    %s  %.1f tok/s  VRAM %d Mio  %s"
                  % ("CHARGE" if r["ok"] else "ÉCHEC", r["tokps"], vr, r["erreur"][:90]))
    finally:
        gagnante = max((r for r in resultats if r["ok"]), key=lambda r: r["tokps"],
                       default=None)
        if gagnante:
            ecris_yaml(yaml_actuel, nom, fichier, gagnante)
            dest = os.path.join(HERE, "results", nom + ".tuned.yaml")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            open(dest, "w").write(open(yaml_actuel).read())
            print("\n=== config RETENUE : %s — %.1f tok/s, VRAM %d Mio"
                  % (gagnante["etiquette"], gagnante["tokps"], gagnante["vram"]))
            print("    consignée dans results/%s.tuned.yaml (c'est CELLE-LÀ qu'il faut "
                  "déployer si le candidat est promu)" % nom)
        else:
            # Aucune config ne charge : on remet l'état d'origine plutôt que de
            # laisser le modèle inservable.
            open(yaml_actuel, "w").write(sauvegarde)
            print("\n=== aucune config n'a chargé — config d'origine restaurée")
        redemarre_et_attend()

    print("\n%-30s %-8s %-9s %s" % ("config", "tok/s", "VRAM", "état"))
    for r in resultats:
        print("%-30s %-8.1f %-9d %s" % (r["etiquette"], r["tokps"], r["vram"],
                                        "ok" if r["ok"] else "échec: " + r["erreur"][:60]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
