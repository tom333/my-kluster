#!/usr/bin/env python3
"""Édite charts/localai/values.yaml : ajoute un modelsConfig (depuis un fichier de
config brut) et/ou retire un modelsConfig par clé. Utilisé par promote.sh (P3)."""
from __future__ import annotations
import argparse, re, sys, yaml
from pathlib import Path

VALUES = Path("/data/projets/perso/my-kluster/charts/localai/values.yaml")
KEY_RE = re.compile(r"^  ([A-Za-z0-9.\-]+): \|$")
COMMENT_RE = re.compile(r"^  #")


def remove_block(lines, key):
    n = len(lines); rm = [False] * n; i = 0
    while i < n:
        m = KEY_RE.match(lines[i])
        if m and m.group(1) == key:
            start = i; j = i - 1
            while j >= 0 and COMMENT_RE.match(lines[j]):
                start = j; j -= 1
            k = i + 1
            while k < n:
                if KEY_RE.match(lines[k]) or COMMENT_RE.match(lines[k]):
                    break
                if lines[k] and not lines[k].startswith("  "):
                    break
                k += 1
            if start > 0 and lines[start - 1] == "":
                start -= 1
            for x in range(start, k):
                rm[x] = True
            i = k
        else:
            i += 1
    return [l for idx, l in enumerate(lines) if not rm[idx]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--add-file", help="fichier config modèle brut à ajouter")
    ap.add_argument("--add-name", help="clé modelsConfig du modèle ajouté")
    ap.add_argument("--remove", help="clé modelsConfig à retirer")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    text = VALUES.read_text()
    lines = text.split("\n")

    if args.remove:
        before = len(lines)
        lines = remove_block(lines, args.remove)
        if len(lines) == before:
            print(f"WARN: clé '{args.remove}' introuvable", file=sys.stderr)

    if args.add_file:
        assert args.add_name, "--add-name requis avec --add-file"
        body = Path(args.add_file).read_text().rstrip("\n")
        block = f"  {args.add_name}: |\n" + "\n".join("    " + l for l in body.split("\n"))
        # insérer avant le 1er bloc flux (image gen à la fin), sinon avant ingress
        out, inserted = [], False
        for l in lines:
            if not inserted and (l.startswith("  flux") and l.endswith(": |")):
                out.append(block); out.append(""); inserted = True
            out.append(l)
        if not inserted:  # fallback : avant 'ingress:'
            out = []
            for l in lines:
                if not inserted and l.startswith("ingress:"):
                    out.append(block); out.append(""); inserted = True
                out.append(l)
        lines = out

    new = "\n".join(lines)
    # validation
    d = yaml.safe_load(new)
    keys = list(d["modelsConfigs"].keys())
    for k, v in d["modelsConfigs"].items():
        yaml.safe_load(v)  # chaque sous-config valide
    print(f"modelsConfigs après édition ({len(keys)}): {keys}")

    if args.dry_run:
        print("[dry-run] values.yaml NON écrit")
    else:
        VALUES.write_text(new)
        print("values.yaml écrit")


if __name__ == "__main__":
    main()
