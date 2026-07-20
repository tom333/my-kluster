#!/usr/bin/env python3
"""Indexe un repo GitOps (my-kluster) dans txtai → config cluster cherchable.

"Phase 2" du second-brain : la doc/config du cluster (CLAUDE.md, docs, apps
ArgoCD, values charts, config) devient interrogeable via /recall SANS être
dupliquée dans le vault. Toujours = l'état git réel (≈ le déployé, ArgoCD selfHeal).

Skip : sealed/ (chiffré = bruit), secrets/, .git, binaires. source='repo'.
Incrémental via manifest. Tourne sur pc (a le repo + token). Cron 6h.
"""
from __future__ import annotations
import json, os, sys, urllib.request
from pathlib import Path

REPO = Path(os.environ.get("REPO_DIR", "/data/projets/perso/my-kluster"))
REPO_NAME = os.environ.get("REPO_NAME", REPO.name)
MANIFEST = Path(os.environ.get("REPO_MANIFEST", Path.home() / ".cache" / "repo-txtai-manifest.json"))
CHUNK, OVERLAP, BATCH = 1500, 200, 100
SKIP_DIRS = {".git", "sealed", "secrets", ".github", "node_modules"}
# extensions indexées (doc + config lisible)
KEEP_EXT = {".md", ".yaml", ".yml"}
# on garde les values de charts mais pas les templates Helm verbeux
SKIP_NAME_SUFFIX = (".disable", ".old")


def wanted(p: Path) -> bool:
    rel = p.relative_to(REPO)
    if any(part in SKIP_DIRS for part in rel.parts):
        return False
    if p.suffix.lower() not in KEEP_EXT:
        return False
    if p.name.endswith(SKIP_NAME_SUFFIX):
        return False
    # charts : garder values*.yaml + Chart.yaml, sauter templates/
    if "charts" in rel.parts and "templates" in rel.parts:
        return False
    return True


def chunk(t: str) -> list[str]:
    if len(t) <= CHUNK:
        return [t]
    out, i = [], 0
    while i < len(t):
        out.append(t[i:i + CHUNK]); i += CHUNK - OVERLAP
    return out


def post(url, token, path, payload=None, method="POST"):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url.rstrip("/") + path, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=900) as r:
        return r.status


def main():
    full = "--full" in sys.argv
    url = os.environ.get("TXTAI_URL", "https://txtai.tgu.ovh")
    token = os.environ.get("TXTAI_TOKEN")
    if not token:
        tf = Path.home() / ".config" / "brain" / "txtai-token"
        token = tf.read_text().strip() if tf.exists() else None
    if not token:
        print("TXTAI_TOKEN (ou ~/.config/brain/txtai-token) requis", file=sys.stderr); sys.exit(2)

    manifest = {}
    if not full and MANIFEST.exists():
        try: manifest = json.loads(MANIFEST.read_text())
        except Exception: manifest = {}
    fresh = dict(manifest)
    docs, n, skip = [], 0, 0
    for p in sorted(REPO.rglob("*")):
        if not p.is_file() or not wanted(p):
            continue
        rel = str(p.relative_to(REPO))
        key = f"{REPO_NAME}/{rel}"
        mt = p.stat().st_mtime
        if not full and manifest.get(key) == mt:
            skip += 1; continue
        try:
            body = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if not body.strip():
            continue
        n += 1; fresh[key] = mt
        header = f"[Repo {REPO_NAME} — {rel}]"
        for i, ch in enumerate(chunk(body)):
            docs.append({
                "id": f"repo:{key}:{i:04d}", "text": f"{header}\n\n{ch}",
                "source": "repo", "repo": REPO_NAME, "path": rel,
            })
    print(f"Fichiers repo à (ré)indexer : {n} (inchangés: {skip}) → {len(docs)} chunks")
    if not docs:
        print("Rien de nouveau."); return
    for i in range(0, len(docs), BATCH):
        b = docs[i:i + BATCH]
        post(url, token, "/add", b)
        post(url, token, "/upsert", method="GET")
        print(f"  indexed {i + len(b)}/{len(docs)}")
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(fresh))
    print(f"repo {REPO_NAME} indexé (incrémental).")


if __name__ == "__main__":
    main()
