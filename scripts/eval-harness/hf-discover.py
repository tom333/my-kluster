#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["huggingface_hub>=1.20"]
# ///
"""Découverte déterministe de candidats modèles sur HuggingFace (cron pc, en amont
d'auto-eval-cycle). Remplace le sourcing freeform de la veille par une requête Hub
structurée : `hf models ls --apps llama.cpp` (backend LocalAI) trié trending, filtré
taille réelle du .gguf ≤ seuil (fit VRAM 3060 avant staging = pas de restart gâché).
Les fichiers compagnons (MTP head, draft, LoRA, mmproj) sont écartés (≠ poids).
Les quants exotiques (ternaire/2-bit) NE sont PAS écartés : Bonsai & co sont des
cibles de déploiement — si le backend cuda12 ne les charge pas encore, le staging
échoue et le done-cache les retire (cf. reference_bonsai_deploy_blocked).

Alimente la MÊME file que la veille (`~/.config/brain/model-candidates.queue`,
format `name|gguf-url`) — le harness reste seul juge, la PR reste le gate.
Le sourcing HF et le sourcing veille sont complémentaires (signaux disjoints).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

CHAT_ID = "843341688"
HERE = os.path.dirname(os.path.abspath(__file__))
VALUES = os.path.join(HERE, "..", "..", "charts", "localai", "values.yaml")
QUEUE = os.environ.get("MODEL_CANDIDATES_QUEUE",
                       os.path.expanduser("~/.config/brain/model-candidates.queue"))
DONE = os.environ.get("MODEL_CANDIDATES_DONE",
                      os.path.expanduser("~/.cache/model-candidates.done"))
TOKEN_FILE = os.path.expanduser("~/.config/brain/telegram-bot-token")

# fichiers non-quantifiés : gâchent la VRAM, on préfère toujours un quant
UNQUANTIZED = re.compile(r"\b(bf16|fp16|f16|fp32|f32)\b", re.I)
SHARDED = re.compile(r"-\d{5}-of-\d{5}")
# fichiers compagnons (≠ poids principaux) : head MTP, draft, adapter, projector vision.
# NB: "mtp"/"draft" seuls sont ambigus (le fichier principal Ornith s'appelle
# ...-MTP-Q4_K_M.gguf) → on ne cible que les marqueurs sans ambiguïté.
COMPANION = re.compile(r"(mmproj|projector|[-_.]head[-_.]|[-_.]lora[-_.]|adapter"
                       r"|control[-_]?vector|[-_.]cvec[-_.]|speculat)", re.I)
HF_BIN = shutil.which("hf") or os.path.join(os.path.dirname(sys.executable), "hf")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def hf_json(args, critical=False):
    """Appelle `hf <args> --json` et parse. [] si échec (best-effort, cron).
    critical=True → notifie Telegram (la requête principale cassée ≠ 0 trending :
    sur cron non-surveillé, une CLI/flag cassé passerait sinon inaperçu)."""
    try:
        out = subprocess.run([HF_BIN, *args, "--json"],
                             capture_output=True, text=True, timeout=120, check=True)
        return json.loads(out.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as e:
        print(f"WARN hf {' '.join(args)}: {e}", file=sys.stderr)
        if critical:
            notify(f"⚠️ hf-discover : requête HF principale échouée ({type(e).__name__}) "
                   f"— CLI/flag/réseau ? Découverte sautée ce soir.")
        return []


def deployed_names():
    """Noms des modèles déjà dans values.yaml (dedup — ne pas re-proposer)."""
    try:
        with open(VALUES) as f:
            return [norm(m) for m in re.findall(r"^    name: (.+)$", f.read(), re.M)]
    except OSError:
        return []


def known_from(path, field=lambda l: l.split("|", 1)[0]):
    """Noms normalisés déjà présents dans un fichier (file/done cache)."""
    try:
        with open(path) as f:
            return {norm(field(l.strip())) for l in f if l.strip() and not l.startswith("#")}
    except OSError:
        return set()


def is_dup(core, known):
    """core déjà connu ? match normalisé bidirectionnel (ornith109b ⊂ ornith109bmtp)."""
    n = norm(core)
    if len(n) < 6:
        return n in known
    return any(n == k or n in k or k in n for k in known)


def pick_gguf(repo_id, max_bytes):
    """Meilleur .gguf mono-fichier ≤ max_bytes (plus gros quant qui rentre = fidélité max)."""
    best = None
    for e in hf_json(["models", "ls", repo_id, "-R"]):
        path, size = e.get("path", ""), e.get("size")
        if not path.lower().endswith(".gguf") or not size or size > max_bytes:
            continue
        base = path.rsplit("/", 1)[-1]
        if path.count("/") >= 2:
            continue  # gguf niché profond = repo-collection/toolkit, pas un modèle unique
        if SHARDED.search(base) or UNQUANTIZED.search(base) or COMPANION.search(base):
            continue  # sharded=download_files unique impossible ; non-quant=gâche VRAM ; compagnon≠poids
        if best is None or size > best[1]:
            best = (path, size)
    return best


def notify(msg):
    try:
        with open(TOKEN_FILE) as f:
            tok = f.read().strip()
    except OSError:
        return
    if not tok:
        return
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": msg}).encode()
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=15).read()
    except OSError:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=25, help="modèles trending à examiner")
    ap.add_argument("--max-size-gb", type=float, default=9.0, help="taille max du .gguf (VRAM 12GB)")
    ap.add_argument("--dry-run", action="store_true", help="n'écrit pas la file, affiche seulement")
    args = ap.parse_args()
    max_bytes = int(args.max_size_gb * 1e9)

    known = set(deployed_names())
    known |= known_from(QUEUE)
    known |= known_from(DONE, field=lambda l: l.split()[1] if len(l.split()) > 1 else l)

    models = hf_json(["models", "ls", "--apps", "llama.cpp",
                      "--pipeline-tag", "text-generation",
                      "--sort", "trending_score", "--limit", str(args.limit)],
                     critical=True)
    print(f"{len(models)} modèles trending llama.cpp examinés (seuil {args.max_size_gb}GB)")

    added = []
    for m in models:
        rid = m.get("id", "")
        name = re.sub(r"-gguf$", "", rid.split("/")[-1], flags=re.I).lower()
        if is_dup(name, known):
            print(f"  skip {rid} (déjà déployé/en file)")
            continue
        picked = pick_gguf(rid, max_bytes)
        if not picked:
            print(f"  skip {rid} (aucun .gguf mono-fichier quantifié ≤ {args.max_size_gb}GB)")
            continue
        path, size = picked
        url = f"https://huggingface.co/{rid}/resolve/main/{path}"
        added.append((name, url))
        known.add(norm(name))
        print(f"  + {name} ({size/1e9:.1f}GB) {path}")

    if not added:
        print("aucun nouveau candidat HF.")
        return
    if args.dry_run:
        print(f"[dry-run] {len(added)} candidat(s) NON écrits.")
        return
    with open(QUEUE, "a") as f:
        for name, url in added:
            f.write(f"{name}|{url}\n")
    names = " ".join(n for n, _ in added)
    print(f"{len(added)} candidat(s) ajoutés à {QUEUE}:{' ' + names}")
    notify(f"🤗 Veille HF : {len(added)} modèle(s) trending en file :{' ' + names}\n"
           f"Lance l'éval : poll-candidates.sh (chaque candidat = 1 restart LocalAI ~15min).")


if __name__ == "__main__":
    main()
