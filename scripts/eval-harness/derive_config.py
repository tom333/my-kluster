#!/usr/bin/env python3
"""Déduit la config LocalAI d'un GGUF depuis son EN-TÊTE, au lieu de la deviner.

POURQUOI. `stage_candidate.sh` écrivait la même config pour tout candidat :
`ctx` venu de la file, `gpu_layers: 99`, `flash_attention`, KV en q8_0. Or le
`tok/s` mesuré n'est PAS une propriété du modèle, c'est celle d'un couple
modèle × config. Mesuré le 2026-09-08 :

    gemma-4-26b   n-cpu-moe:17 + parallel:1 + fit   23,9 -> 36,4 tok/s   (+52 %)
    gsq-rco-iq2s  parallel 4 -> 1                   plantage -> fonctionne
    ornith        tête MTP activée                  61 tok/s
    ornith        Q4_K_M -> Q6_K                    agentic 0 -> 6/6  (cf. quant-sweep.sh)

Comparer des candidats sur des configs arbitraires est donc aussi invalide que le
plafond de codage qu'on vient de corriger.

CE QUI EST DÉDUCTIBLE DE L'EN-TÊTE (vérifié sur 5 modèles du PVC le 2026-09-08) :

    tenseurs `*_exps`   -> mélange d'experts (MoE) -> candidat à --n-cpu-moe
    tenseurs `ssm_*`    -> hybride attention/SSM -> le KV ne compte QUE les couches
                           d'attention, et `parallel` doit rester à 1 (l'état
                           récurrent est alloué PAR SLOT : 4 slots coûtaient ~600 Mio
                           pour rien et faisaient planter le backend à ctx 32768)
    `nextn` / `mtp`     -> tête de prédiction multi-tokens -> décodage spéculatif
    offsets des tenseurs-> taille EXACTE de chaque tenseur, sans table de types :
                           taille(i) = offset(i+1) - offset(i). C'est ce qui permet
                           de CALCULER combien de couches d'experts déporter au lieu
                           de tâtonner (le 17 de gemma-4-26b a été trouvé à la main).

CE QUI N'EST PAS DÉDUCTIBLE. Le tampon de calcul de llama.cpp. On réserve donc une
marge mesurée (cf. RESERVE_MIO) et on considère que ce script propose un POINT DE
DÉPART à VÉRIFIER en chargeant, pas une config optimale prouvée. Le balayage qui
suit tranche par la mesure.

Usage :  derive_config.py <url-ou-chemin> [--vram-libre-mio N] [--ctx-max N] [--yaml]
"""

from __future__ import annotations
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gguf_preflight import FIXE, Source  # noqa: E402


def valeur2(s: Source, t: int):
    """Comme `valeur` du preflight, mais CONSERVE le contenu des tableaux.

    Nécessaire : `gemma4.attention.head_count_kv` est un tableau de 30 entrées (une
    par couche), et le preflight, qui n'a qu'à valider des types, jetait le contenu
    en rendant la chaîne "array[30]". Comparer cette chaîne à un entier plantait.
    """
    if t in FIXE:
        fmt, n = FIXE[t]
        return s.nb(fmt, n)
    if t == 8:
        return s.chaine()
    if t == 9:
        ti = s.nb("I", 4)
        c = s.nb("Q", 8)
        return [valeur2(s, ti) for _ in range(c)]
    raise SystemExit("type de métadonnée inconnu: %r" % t)

# Marge pour le tampon de calcul et le surcoût LocalAI.
# MESURÉE le 2026-09-08 sur Qwen3.8-27B-GSQ-RCO-IQ2_S à ctx 32768 :
#     nvidia-smi total occupé ....... 11516 Mio
#     dont bureau ................... ~1350 Mio
#     donc LocalAI .................. ~10166 Mio
#     poids .........................  8831 Mio
#     KV q8_0 (32 Kio/token) ........  1024 Mio
#     -> tampon réel ................ ~ 311 Mio
# Et le pic sous un prompt de ~5000 tokens n'était que 11554 Mio : le tampon est
# alloué au chargement et ne grandit pas avec le prompt.
# ATTENTION au piège dans lequel je suis tombé en écrivant ce script : j'avais
# calculé 1661 en oubliant de retirer le bureau, soit une réserve 5 fois trop
# grande, qui déduisait ctx=8192 là où 32768 est MESURÉ comme fonctionnant.
RESERVE_MIO = int(os.environ.get("DERIVE_RESERVE_MIO", "500"))
# VRAM de la carte moins ce que prend le bureau (mesuré ~1350-1430 Mio sur pc).
VRAM_DEFAUT_MIO = int(os.environ.get("DERIVE_VRAM_LIBRE_MIO", "10800"))
CTX_PLANCHER = 4096


def lire_entete(cible: str) -> dict:
    s = Source(cible)
    if s.lire(4) != b"GGUF":
        raise SystemExit("pas un GGUF : " + cible)
    s.nb("I", 4)
    n_tens = s.nb("Q", 8)
    n_kv = s.nb("Q", 8)
    kv = {}
    for _ in range(n_kv):
        cle = s.chaine()
        kv[cle] = valeur2(s, s.nb("I", 4))
    infos = []
    for _ in range(n_tens):
        nom = s.chaine()
        nd = s.nb("I", 4)
        dims = [s.nb("Q", 8) for _ in range(nd)]
        typ = s.nb("I", 4)
        off = s.nb("Q", 8)
        infos.append({"nom": nom, "dims": dims, "type": typ, "offset": off})
    align = kv.get("general.alignment", 32)
    debut = (s.pos + align - 1) // align * align
    return {"kv": kv, "tenseurs": infos, "debut_donnees": debut, "octets_lus": s.pos,
            "local": s.local, "cible": cible}


def tailles_exactes(e: dict, taille_fichier: int | None) -> None:
    """Renseigne `octets` sur chaque tenseur, par différence d'offsets.

    Exact et sans table de types quantifiés : les tenseurs sont écrits dans
    l'ordre des offsets, donc taille(i) = offset(i+1) - offset(i). Le dernier va
    jusqu'à la fin de la section de données.
    """
    ordre = sorted(e["tenseurs"], key=lambda t: t["offset"])
    for i, t in enumerate(ordre):
        if i + 1 < len(ordre):
            t["octets"] = ordre[i + 1]["offset"] - t["offset"]
        elif taille_fichier:
            t["octets"] = (taille_fichier - e["debut_donnees"]) - t["offset"]
        else:
            t["octets"] = 0


def analyse(e: dict, taille_fichier: int | None) -> dict:
    kv, T = e["kv"], e["tenseurs"]
    arch = kv.get("general.architecture", "?")
    noms = [t["nom"] for t in T]

    def meta(suffixe, defaut=None):
        for k, v in kv.items():
            if k.endswith(suffixe):
                return v
        return defaut

    blocs = {int(m.group(1)) for n in noms if (m := re.match(r"blk\.(\d+)\.", n))}
    attn = {int(m.group(1)) for n in noms
            if (m := re.match(r"blk\.(\d+)\.attn_k\.weight", n))}
    moe = any("_exps" in n for n in noms)
    ssm = any(".ssm_" in n for n in noms)
    mtp = any(re.search(r"nextn|\.eh_proj", n, re.I) for n in noms) or \
        any("nextn" in k.lower() for k in kv)

    brut_kv = meta("attention.head_count_kv", 0) or 0
    k_len = meta("attention.key_length", 0) or 0
    v_len = meta("attention.value_length", 0) or 0
    if not k_len:
        emb = meta("embedding_length", 0) or 0
        heads = meta("attention.head_count", 0) or 0
        k_len = v_len = (emb // heads) if heads else 0
    # `head_count_kv` peut être PAR COUCHE (gemma-4 : tableau de 30). On somme alors
    # sur les couches, en prenant les dimensions PLEINES même si le modèle a des
    # couches à fenêtre glissante (`*_swa`, plus petites) : ça SURESTIME le KV, donc
    # ça rend un ctx prudent. Le balayage qui suit peut le remonter par la mesure —
    # sous-estimer, à l'inverse, produirait un plantage au chargement.
    par_couche = isinstance(brut_kv, list)
    if par_couche:
        n_kv_heads = sum(brut_kv) / max(1, len(brut_kv))
        n_couches_kv = len(brut_kv)
        kv_par_token = sum(h * (k_len + v_len) for h in brut_kv)
    else:
        n_kv_heads = brut_kv

    # KV par token en cache q8_0 (1 octet par valeur). Ne compte QUE les couches
    # d'attention : sur un hybride, l'état des couches SSM est de taille CONSTANTE,
    # indépendante du contexte. Ignorer ça multipliait mon estimation par 4 sur
    # Qwen3.8-27B-GSQ-RCO (64 blocs dont 16 seulement en attention).
        n_couches_kv = len(attn) if attn else len(blocs)
        kv_par_token = n_couches_kv * n_kv_heads * (k_len + v_len)  # octets, q8_0

    poids_octets = taille_fichier or 0
    exps = {}
    if moe:
        for t in T:
            m = re.match(r"blk\.(\d+)\..*_exps", t["nom"])
            if m:
                exps[int(m.group(1))] = exps.get(int(m.group(1)), 0) + t.get("octets", 0)

    # Fenêtre glissante : si le modèle déclare des dimensions `*_swa`, une partie de
    # ses couches borne son cache par la FENÊTRE et non par le contexte. L'en-tête ne
    # dit pas QUELLES couches, donc le KV n'est pas calculable de façon fiable.
    swa = any(k.endswith(("_swa", ".sliding_window")) for k in kv)

    return {"swa": swa,
            "arch": arch, "blocs": len(blocs), "attn": len(attn), "moe": moe, "ssm": ssm,
            "mtp": mtp, "n_kv_heads": n_kv_heads, "k_len": k_len, "v_len": v_len,
            "kv_par_token": kv_par_token, "n_couches_kv": n_couches_kv,
            "kv_par_couche": par_couche,
            "ctx_entraine": meta("context_length", 0) or 0,
            "experts": meta("expert_count", 0) or 0,
            "poids_octets": poids_octets, "exps_par_couche": exps,
            "octets_entete": e["octets_lus"]}


def derive(a: dict, vram_mio: int, ctx_max: int | None) -> dict:
    poids_mio = a["poids_octets"] / 1048576
    dispo = vram_mio - RESERVE_MIO
    raisons = []
    confiance = "haute"

    # ABSTENTION. Sur un modèle à fenêtre glissante, le KV par token calculé sur les
    # dimensions pleines SURESTIME massivement : sur gemma-4-26b il donnait 210
    # Kio/token, donc ctx=4096 et n_cpu_moe=9, là où la config MESURÉE le 2026-09-08
    # est ctx=32768 avec n_cpu_moe=17 à 36,4 tok/s. Un générateur qui dégrade la
    # config existante est pire que pas de générateur : on s'abstient et on le DIT.
    if a["swa"]:
        confiance = "basse"
        raisons.append("couches à fenêtre glissante détectées (`*_swa`) : leur cache est "
                       "borné par la fenêtre, pas par le contexte, et l'en-tête ne dit "
                       "pas lesquelles. ctx et n_cpu_moe NON déduits — garder la config "
                       "existante et régler par la mesure.")
        return {"ctx": ctx_max or 0, "parallel": 1, "n_cpu_moe": 0, "mtp": a["mtp"],
                "confiance": confiance, "poids_mio": round(poids_mio),
                "poids_resident_mio": round(poids_mio), "kv_mio": 0,
                "vram_prevue_mio": 0, "raisons": raisons}

    # Ordre : d'abord le KV visé (donc le ctx), ensuite le déport d'experts qui doit
    # laisser la place à ce KV. L'inverse sous-dimensionnait le déport.
    n_cpu_moe = 0
    if a["moe"] and a["exps_par_couche"] and poids_mio > dispo:
        # Déporte les couches d'experts les plus GROSSES d'abord, jusqu'à rentrer.
        ordre = sorted(a["exps_par_couche"].items(), key=lambda kv: -kv[1])
        reste = poids_mio
        for _, oct_ in ordre:
            if reste <= dispo:
                break
            reste -= oct_ / 1048576
            n_cpu_moe += 1
        raisons.append("MoE de %.0f Mio pour %.0f Mio utilisables : %d couche(s) "
                       "d'experts déportées en RAM hôte (calculé sur les tailles "
                       "exactes des tenseurs, pas estimé)" % (poids_mio, dispo, n_cpu_moe))
        poids_resident = reste
    else:
        poids_resident = poids_mio

    budget_kv_mio = max(0, dispo - poids_resident)
    if a["kv_par_token"] > 0:
        ctx = int(budget_kv_mio * 1048576 / a["kv_par_token"])
        ctx = 1 << (max(ctx, CTX_PLANCHER)).bit_length() - 1  # puissance de 2 inférieure
    else:
        ctx = CTX_PLANCHER
        raisons.append("dimensions KV illisibles : ctx laissé au plancher")
    plafonds = [x for x in (a["ctx_entraine"], ctx_max) if x]
    if plafonds:
        p = min(plafonds)
        if ctx > p:
            ctx = p
            raisons.append("ctx ramené à %d (plafond du modèle ou demandé)" % p)
    ctx = max(ctx, CTX_PLANCHER)

    if a["ssm"]:
        raisons.append("hybride attention/SSM (%d blocs d'attention sur %d) : le KV ne "
                       "compte que les couches d'attention, et `parallel` DOIT rester "
                       "à 1 — l'état récurrent est alloué par slot" % (a["attn"], a["blocs"]))
    if a["mtp"]:
        raisons.append("tête MTP détectée : décodage spéculatif activable "
                       "(mesuré ~1,5x sur gemma-4-12B, 61 tok/s sur ornith)")
    raisons.append("KV q8_0 = %d octets/token (%d couches × %d têtes × %d) -> %.0f Mio "
                   "à ctx %d" % (a["kv_par_token"], a["n_couches_kv"], a["n_kv_heads"],
                                 a["k_len"] + a["v_len"],
                                 ctx * a["kv_par_token"] / 1048576, ctx))

    return {"ctx": ctx, "parallel": 1, "n_cpu_moe": n_cpu_moe, "mtp": a["mtp"],
            "confiance": confiance,
            "poids_mio": round(poids_mio), "poids_resident_mio": round(poids_resident),
            "kv_mio": round(ctx * a["kv_par_token"] / 1048576),
            "vram_prevue_mio": round(poids_resident + ctx * a["kv_par_token"] / 1048576
                                     + RESERVE_MIO),
            "raisons": raisons}


def yaml_options(c: dict) -> str:
    opts = ["  - use_jinja:true", "  - parallel:1"]
    if c["n_cpu_moe"]:
        opts.append('  - "--n-cpu-moe:%d"' % c["n_cpu_moe"])
        opts.append("  - fit:on")
    # PAS d'option MTP ici, volontairement. Pour une tête EMBARQUÉE, LocalAI
    # l'active seul — vérifié dans son journal le 2026-09-08 :
    #   [mtp] embedded MTP head detected; enabling draft-mtp speculative decoding
    #         name="qwopus3.5-9b-coder" nextn_layers=1 spec_n_max=6 spec_p_min=0.75
    # Écrire `spec_type:draft-mtp` + `draft_max:2` par-dessus remplacerait ce
    # spec_n_max=6 auto-détecté par un 2 arbitraire : une RÉGRESSION. Dans
    # values.yaml, ces options n'existent que pour gemma-4-12b, qui a un drafter
    # SÉPARÉ (`draft_model:`) — cas que `stage_candidate.sh` traite déjà via --draft.
    # La détection reste donc informative : elle dit qu'il y a une tête, pas quoi
    # écrire. Cf. aussi les plafonds (n_max) qui se calibrent par modèle.
    return "context_size: %d\noptions:\n%s" % (c["ctx"], "\n".join(opts))


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("usage: derive_config.py <url-ou-chemin> [--vram-libre-mio N] "
              "[--ctx-max N] [--yaml]", file=sys.stderr)
        return 2
    cible = args[0]

    def opt(nom, defaut):
        for i, a in enumerate(sys.argv):
            if a == nom and i + 1 < len(sys.argv):
                return int(sys.argv[i + 1])
        return defaut

    vram = opt("--vram-libre-mio", VRAM_DEFAUT_MIO)
    ctx_max = opt("--ctx-max", 0) or None

    e = lire_entete(cible)
    taille = os.path.getsize(cible) if e["local"] else taille_distante(cible)
    tailles_exactes(e, taille)
    a = analyse(e, taille)
    c = derive(a, vram, ctx_max)

    if "--yaml" in sys.argv:
        if c["confiance"] == "basse":
            # Rien sur stdout : l'appelant garde sa config. La raison part sur stderr.
            print("derive_config: abstention — %s" % c["raisons"][0], file=sys.stderr)
            return 4
        print(yaml_options(c))
        return 0

    print("=== %s ===" % os.path.basename(cible))
    print("  arch=%s  blocs=%d (attn %d)  MoE=%s%s  SSM=%s  MTP=%s"
          % (a["arch"], a["blocs"], a["attn"], "oui" if a["moe"] else "non",
             " (%s experts)" % a["experts"] if a["experts"] else "",
             "oui" if a["ssm"] else "non", "oui" if a["mtp"] else "non"))
    print("  en-tête lu : %.2f Mio  ·  poids : %d Mio" % (a["octets_entete"] / 1048576,
                                                          c["poids_mio"]))
    print()
    if c["confiance"] == "basse":
        print("  CONFIG NON DÉDUITE (confiance basse) — voir la raison ci-dessous")
        print()
        for r in c["raisons"]:
            print("  · " + r)
        return 0
    print("  CONFIG DÉDUITE : ctx=%d  parallel=1  n_cpu_moe=%d  mtp=%s"
          % (c["ctx"], c["n_cpu_moe"], "oui" if c["mtp"] else "non"))
    print("  VRAM prévue : %d Mio (poids résidents %d + KV %d + réserve %d) sur %d libres"
          % (c["vram_prevue_mio"], c["poids_resident_mio"], c["kv_mio"], RESERVE_MIO, vram))
    print()
    for r in c["raisons"]:
        print("  · " + r)
    print()
    print("  ⚠ point de DÉPART à vérifier en chargeant : le tampon de calcul de")
    print("    llama.cpp n'est pas déductible de l'en-tête.")
    return 0


def taille_distante(url: str) -> int | None:
    import urllib.request
    req = urllib.request.Request(url, method="HEAD")
    req.add_header("User-Agent", "derive-config")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            for cle in ("x-linked-size", "content-length"):
                v = r.headers.get(cle)
                if v:
                    return int(v)
    except Exception:
        return None
    return None


if __name__ == "__main__":
    sys.exit(main())
