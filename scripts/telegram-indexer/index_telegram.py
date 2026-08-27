#!/usr/bin/env python3
"""Indexe les conversations Telegram ↔ Hermes dans txtai (surface manquante).

Lit state.db (sessions source='telegram') → conversation complète (user+assistant)
→ chunk → txtai avec source='telegram'. Rend les échanges Hermes cherchables via
/recall + brain-search.sh, comme les sessions Claude.

Tourne DANS le pod hermes (state.db + $TXTAI_MCP_TOKEN + accès txtai). Incrémental
via manifest (last_started_at) — ne réindexe que les sessions plus récentes.
"""
from __future__ import annotations
import datetime
import json
import os
import sqlite3
import sys
import urllib.request

STATE_DB = os.environ.get("HERMES_STATE_DB", "/opt/data/state.db")
MANIFEST = os.environ.get("TELEGRAM_MANIFEST", "/opt/data/.txtai-telegram-manifest.json")
CHUNK, OVERLAP, BATCH = 1500, 200, 100
MIN_CHARS = 60  # ignore les sessions quasi vides


def chunk(t: str) -> list[str]:
    if len(t) <= CHUNK:
        return [t]
    out, i = [], 0
    while i < len(t):
        out.append(t[i:i + CHUNK])
        i += CHUNK - OVERLAP
    return out


def post(url, token, path, payload=None, method="POST"):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url.rstrip("/") + path, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=900) as r:
        return r.status


def load_since() -> float:
    try:
        return float(json.load(open(MANIFEST)).get("last_started_at", 0))
    except Exception:
        return 0.0


def collect(since: float):
    c = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True)
    docs, convos, max_started = [], [], since
    rows = c.execute(
        "SELECT id, title, started_at FROM sessions "
        "WHERE source='telegram' AND started_at > ? ORDER BY started_at",
        (since,),
    ).fetchall()
    for sid, title, started in rows:
        if started and started > max_started:
            max_started = started
        msgs = c.execute(
            "SELECT role, content FROM messages WHERE session_id=? "
            "AND content IS NOT NULL AND length(content)>0 "
            "AND role IN ('user','assistant') ORDER BY id",
            (sid,),
        ).fetchall()
        turns, struct = [], []
        for role, content in msgs:
            who = "Moi" if role == "user" else "Hermes"
            turns.append(f"{who}: {content.strip()}")
            # Tours structures pour OpenViking : `remember` attend {role, content}.
            struct.append({"role": role, "content": content.strip()})
        convo = "\n\n".join(turns)
        if len(convo) < MIN_CHARS:
            continue
        date = (datetime.datetime.fromtimestamp(started, datetime.timezone.utc)
                .strftime("%Y-%m-%d") if started else "")
        header = f"[Conversation Telegram Hermes — {title or sid} · {date} · session:{sid}]"
        convos.append({"sid": sid, "title": title or "", "date": date, "msgs": struct})
        for i, ch in enumerate(chunk(convo)):
            docs.append({
                "id": f"tg:{sid}:{i:04d}", "text": f"{header}\n\n{ch}",
                "source": "telegram", "session_id": sid,
                "title": title or "", "date": date,
            })
    c.close()
    return docs, convos, max_started


# ─────────────────────────── puits OpenViking ───────────────────────────
# OPTIONNEL et OPT-IN : sans OPENVIKING_URL, rien ne change. Le jeton retombe sur
# OPENVIKING_API_KEY, deja present dans l'environnement du pod hermes via envFrom
# (hermes-secrets) — donc seule l'URL est a ajouter pour activer.
#
# `remember` plutot que /api/v1/resources : une conversation Telegram EST une suite
# user/assistant, la forme exacte qu'il attend. Il est ASYNCHRONE (0,06 s mesure le
# 2026-08-27, « committed for memory extraction ») : le cout GPU est porte par la
# file du serveur, pas par ce script. D'ou le plafond par execution.
OV_MAX_CHARS = int(os.environ.get("OPENVIKING_MAX_CHARS", "24000"))
OV_LIMIT = int(os.environ.get("OPENVIKING_LIMIT", "20"))


def _ov_trim(msgs):
    """Borne la taille en gardant le DEBUT et la FIN : la demande et le resultat."""
    if sum(len(m["content"]) for m in msgs) <= OV_MAX_CHARS or len(msgs) < 4:
        return msgs
    moitie, tete, queue, pris = OV_MAX_CHARS // 2, [], [], 0
    for m in msgs:
        if pris + len(m["content"]) > moitie:
            break
        tete.append(m); pris += len(m["content"])
    pris = 0
    for m in reversed(msgs[len(tete):]):
        if pris + len(m["content"]) > moitie:
            break
        queue.insert(0, m); pris += len(m["content"])
    coupe = len(msgs) - len(tete) - len(queue)
    if coupe > 0:
        tete.append({"role": "user", "content": f"[... {coupe} tours omis ...]"})
    return tete + queue


def push_openviking(convos):
    url = os.environ.get("OPENVIKING_URL")
    token = os.environ.get("OPENVIKING_TOKEN") or os.environ.get("OPENVIKING_API_KEY")
    if not url or not token:
        return
    envoyes = 0
    for c in convos[:OV_LIMIT]:
        msgs = _ov_trim(c["msgs"])
        if not msgs:
            continue
        entete = {"role": "user", "content":
                  f"Conversation Telegram avec Hermes du {c['date']} "
                  f"(titre: {c['title'] or c['sid']}, session: {c['sid']})."}
        corps = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                 "params": {"name": "remember", "arguments": {"messages": [entete] + msgs}}}
        try:
            req = urllib.request.Request(url.rstrip("/") + "/mcp",
                                         data=json.dumps(corps).encode(), method="POST")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "application/json, text/event-stream")
            with urllib.request.urlopen(req, timeout=120) as r:
                r.read()
            envoyes += 1
        except Exception as e:
            # Independant de txtai : un echec ici ne prive pas de recherche.
            print(f"  WARN openviking {c['sid']}: {e}", file=sys.stderr)
    reste = max(0, len(convos) - OV_LIMIT)
    print(f"OpenViking : {envoyes} conversation(s) envoyee(s)"
          + (f", {reste} reportee(s) (plafond {OV_LIMIT})" if reste else ""))


def main():
    url = os.environ.get("TXTAI_URL", "http://txtai.txtai.svc.cluster.local:8000")
    token = os.environ.get("TXTAI_TOKEN") or os.environ.get("TXTAI_MCP_TOKEN")
    if not token:
        print("TXTAI token requis", file=sys.stderr); sys.exit(2)
    full = "--full" in sys.argv
    since = 0.0 if full else load_since()
    docs, convos, max_started = collect(since)
    print(f"Telegram → documents : {len(docs)} (since={since:.0f})")
    if not docs:
        print("Rien de nouveau."); return
    for i in range(0, len(docs), BATCH):
        b = docs[i:i + BATCH]
        post(url, token, "/add", b)
        post(url, token, "/upsert", method="GET")
        print(f"  indexed {i + len(b)}/{len(docs)}")
    try:
        json.dump({"last_started_at": max_started}, open(MANIFEST, "w"))
    except Exception as e:
        print(f"WARN manifest: {e}", file=sys.stderr)
    print("conversations Telegram indexées.")
    # APRES txtai : c'est lui qui porte la recherche et ne doit pas etre prive
    # d'une indexation si OpenViking est indisponible.
    push_openviking(convos)


if __name__ == "__main__":
    main()
