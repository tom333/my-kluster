#!/usr/bin/env python3
"""Indexe les digests de veille (sorties des crons Hermes) dans txtai.

Capture FIABLE non-agent : lit directement `state.db` de Hermes (source de vérité).
Chaque session cron (`sessions.source='cron'`, id=`cron_<jobid>_<ts>`) a pour
dernier message assistant le digest livré → on l'indexe avec métadonnées.

Conçu pour tourner DANS le pod hermes (a state.db + $TXTAI_MCP_TOKEN + accès txtai) :
  kubectl exec -n hermes <pod> -c main -- \
    env TXTAI_URL=http://txtai.txtai.svc.cluster.local:8000 \
    python3 /tmp/index_digests.py

Idempotent : id = "digest:<session_id>:<chunk>" (upsert). Backfill + ré-exécutable.
"""
from __future__ import annotations
import json
import os
import sqlite3
import sys
import urllib.request

STATE_DB = os.environ.get("HERMES_STATE_DB", "/opt/data/state.db")
# Resumabilité : ne traite que les sessions cron démarrées APRÈS le dernier run
# (les digests sont immuables une fois la session finie). Manifest = {last_started_at}.
MANIFEST = os.environ.get("DIGEST_MANIFEST", "/opt/data/.txtai-digest-manifest.json")
CHUNK_CHARS = 1500
CHUNK_OVERLAP = 200
BATCH = 100
MIN_DIGEST_CHARS = 40  # ignore les runs sans vrai digest (erreurs, "rien de neuf" ultra-court)


def chunk(text: str) -> list[str]:
    if len(text) <= CHUNK_CHARS:
        return [text]
    out, i = [], 0
    while i < len(text):
        out.append(text[i : i + CHUNK_CHARS])
        i += CHUNK_CHARS - CHUNK_OVERLAP
    return out


def post(url: str, token: str, path: str, payload=None, method="POST"):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url.rstrip("/") + path, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=900) as r:
        return r.status


def _load_since() -> float:
    try:
        return float(json.load(open(MANIFEST)).get("last_started_at", 0))
    except Exception:
        return 0.0


def collect(since: float) -> tuple[list[dict], float]:
    c = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True)
    docs = []
    max_started = since
    rows = c.execute(
        "SELECT id, title, started_at FROM sessions WHERE source='cron' AND started_at > ? ORDER BY started_at",
        (since,),
    ).fetchall()
    for sid, title, started in rows:
        # dernier message assistant = le digest livré
        m = c.execute(
            "SELECT content FROM messages WHERE session_id=? AND role='assistant' "
            "AND content IS NOT NULL AND length(content)>0 ORDER BY id DESC LIMIT 1",
            (sid,),
        ).fetchone()
        if started and started > max_started:
            max_started = started
        if not m or not m[0] or len(m[0].strip()) < MIN_DIGEST_CHARS:
            continue
        digest = m[0].strip()
        # id cron = cron_<jobid>_<ts> ; title = "<nom job> · <date>"
        parts = sid.split("_")
        job_id = parts[1] if len(parts) >= 2 and parts[0] == "cron" else ""
        job_name = (title or "").split(" · ")[0]
        import datetime
        date = datetime.datetime.fromtimestamp(started, datetime.timezone.utc).strftime("%Y-%m-%d") if started else ""
        header = (
            f"[Digest veille — job: {job_name} · date: {date} · "
            f"job_id: {job_id} · session_id: {sid}]"
        )
        for idx, ch in enumerate(chunk(digest)):
            docs.append({
                "id": f"digest:{sid}:{idx:04d}",
                "text": f"{header}\n\n{ch}",
                "source": "veille",
                "job": job_name,
                "job_id": job_id,
                "date": date,
                "session_id": sid,
            })
    c.close()
    return docs, max_started


def main():
    url = os.environ.get("TXTAI_URL", "http://txtai.txtai.svc.cluster.local:8000")
    token = os.environ.get("TXTAI_TOKEN") or os.environ.get("TXTAI_MCP_TOKEN")
    if not token:
        print("TXTAI_TOKEN / TXTAI_MCP_TOKEN requis", file=sys.stderr)
        sys.exit(2)
    full = "--full" in sys.argv
    since = 0.0 if full else _load_since()
    docs, max_started = collect(since)
    print(f"Digests nouveaux -> documents : {len(docs)} (since={since:.0f})")
    if not docs:
        print("Rien de nouveau.")
        return
    for i in range(0, len(docs), BATCH):
        b = docs[i : i + BATCH]
        post(url, token, "/add", b)
        post(url, token, "/upsert", method="GET")
        print(f"  indexed {i + len(b)}/{len(docs)}")
    try:
        json.dump({"last_started_at": max_started}, open(MANIFEST, "w"))
    except Exception as e:
        print(f"WARN manifest non sauvé: {e}", file=sys.stderr)
    print("digests indexés (incrémental).")


if __name__ == "__main__":
    main()
