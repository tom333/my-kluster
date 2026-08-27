#!/usr/bin/env python3
"""Indexe les transcripts Claude Code (~/.claude/projects/**/*.jsonl) dans txtai.

Phase 1 du "second-brain multi-surface" : parse chaque session, jette le spam
tool-calls, garde le texte user/assistant + métadonnées (session_id, projet,
date, titre, url), chunk, et POST vers l'API txtai (/add + /upsert).

Usage :
  # valider le parsing sans rien envoyer :
  ./index_sessions.py --dry-run
  # indexer pour de vrai :
  TXTAI_URL=http://txtai.tgu.ovh TXTAI_TOKEN=xxx ./index_sessions.py

Idempotent : id = "<session_id>:<chunk>", ré-exécuter met à jour (upsert).
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

# Bruit injecté par le harness (wrappers non-conversationnels) — retiré avant indexation.
_PAIRED = re.compile(
    r"<(system-reminder|local-command-caveat|command-contents|bash-stdout|bash-stderr|local-command-stdout)>.*?</\1>",
    re.DOTALL,
)
_TAGS = re.compile(r"</?(command-name|command-message|command-args|bash-input|local-command-stdout)>")


def scrub(txt: str) -> str:
    txt = _PAIRED.sub("", txt)
    txt = _TAGS.sub("", txt)
    return txt.strip()

PROJECTS_DIR = Path(os.environ.get("CLAUDE_PROJECTS_DIR", Path.home() / ".claude" / "projects"))
# Manifest de resumabilité {chemin_fichier: mtime} — ne ré-indexe/ré-embed que
# les sessions nouvelles ou modifiées (une session active grossit → mtime change).
MANIFEST = Path(os.environ.get("INDEX_MANIFEST", Path.home() / ".claude" / ".txtai-index-manifest.json"))
CHUNK_CHARS = 1500
CHUNK_OVERLAP = 200
BATCH = 200


def _text_from_content(content) -> str:
    """Extrait le texte utile d'un message.content (str ou liste de blocs).
    Jette tool_use / tool_result / image / thinking — que du texte lisible."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text", "")
                if isinstance(t, str):
                    out.append(t)
        return "\n".join(out)
    return ""


def parse_session(path: Path) -> dict | None:
    """Un fichier .jsonl -> {session_id, project, date, title, url, text}."""
    session_id = path.stem
    project = None
    date = None
    title = None
    url = None
    turns: list[str] = []
    msgs: list[dict] = []

    for line in path.open(encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue

        # métadonnées glanées au fil de l'eau
        if project is None and o.get("cwd"):
            project = o["cwd"]
        ts = o.get("timestamp")
        if ts and date is None:
            date = ts[:10]  # YYYY-MM-DD
        if o.get("customTitle"):
            title = o["customTitle"]
        elif o.get("aiTitle") and not title:
            title = o["aiTitle"]
        if o.get("url") and not url:
            url = o["url"]

        # contenu conversationnel uniquement
        t = o.get("type")
        if t in ("user", "assistant"):
            msg = o.get("message")
            if isinstance(msg, dict):
                txt = scrub(_text_from_content(msg.get("content")))
                if txt:
                    role = "User" if t == "user" else "Claude"
                    turns.append(f"{role}: {txt}")
                    # Tours structurés pour OpenViking : `remember` attend des messages
                    # {role, content} avec role ∈ {user, assistant}, pas du texte préfixé.
                    msgs.append({"role": "user" if t == "user" else "assistant",
                                 "content": txt})

    if not turns:
        return None
    if project is None:
        # fallback : dérive du nom de dossier (lossy)
        project = path.parent.name.lstrip("-").replace("-", "/")

    return {
        "session_id": session_id,
        "project": project,
        "date": date or "",
        "title": title or "(sans titre)",
        "url": url or "",
        "text": "\n\n".join(turns),
        "msgs": msgs,
    }


def chunk(text: str) -> list[str]:
    if len(text) <= CHUNK_CHARS:
        return [text]
    out, i = [], 0
    while i < len(text):
        out.append(text[i : i + CHUNK_CHARS])
        i += CHUNK_CHARS - CHUNK_OVERLAP
    return out


def session_to_docs(s: dict) -> list[dict]:
    docs = []
    # En-tête métadonnées bakée dans le texte : un search "plain" ne renvoie que
    # {id,text,score} (pas les colonnes). En la mettant dans le texte, Hermes lit
    # session/projet/date/titre directement dans le résultat → pas de script python.
    header = (
        f"[Session Claude Code — projet: {s['project']} · date: {s['date']} · "
        f"titre: {s['title']} · session_id: {s['session_id']}]"
    )
    for idx, ch in enumerate(chunk(s["text"])):
        docs.append({
            "id": f"{s['session_id']}:{idx:04d}",
            "text": f"{header}\n\n{ch}",
            "session_id": s["session_id"],
            "project": s["project"],
            "date": s["date"],
            "title": s["title"],
            "url": s["url"],
        })
    return docs


# ─────────────────────────── puits OpenViking ───────────────────────────
# OPTIONNEL : sans OPENVIKING_URL ni OPENVIKING_TOKEN, rien ne change.
# txtai reste le moteur de recherche ; OpenViking recoit en plus la conversation
# pour en extraire entites et evenements.
#
# On passe par l'outil MCP `remember` plutot que par /api/v1/resources :
#   - une session EST une conversation user/assistant, la forme exacte qu'il attend ;
#   - c'est du JSON simple, pas de televersement multipart ;
#   - il est ASYNCHRONE — 0,06 s mesure le 2026-08-27, il repond « committed for
#     memory extraction » et le travail se fait en tache de fond. Le cout GPU est
#     donc porte par la file du serveur, pas par ce script.
# D'ou le plafond par execution : ne pas inonder cette file.
OV_MAX_CHARS = int(os.environ.get("OPENVIKING_MAX_CHARS", "24000"))
OV_LIMIT = int(os.environ.get("OPENVIKING_LIMIT", "20"))


def _ov_trim(msgs: list[dict]) -> list[dict]:
    """Borne la taille en gardant le DEBUT et la FIN de la session.

    Le debut porte la tache demandee, la fin porte le resultat ; c'est le milieu
    (exploration, essais) qui est le moins informatif. Tronquer par la fin seule
    perdrait l'intention, tronquer par le debut perdrait la conclusion.
    """
    total = sum(len(m["content"]) for m in msgs)
    if total <= OV_MAX_CHARS or len(msgs) < 4:
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


def push_openviking(sessions: list[dict], dry_run: bool = False) -> None:
    url = os.environ.get("OPENVIKING_URL")
    token = os.environ.get("OPENVIKING_TOKEN")
    if not url or not token:
        return
    envoyes = 0
    for s in sessions[:OV_LIMIT]:
        msgs = _ov_trim(s.get("msgs") or [])
        if not msgs:
            continue
        # En-tete en premier message : sans lui, une session deracinee n'est pas
        # rattachable a un projet ni a une date une fois en memoire.
        entete = {"role": "user", "content":
                  f"Session Claude Code du {s['date']} sur le projet {s['project']} "
                  f"(titre: {s['title']}, session_id: {s['session_id']})."}
        corps = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                 "params": {"name": "remember", "arguments": {"messages": [entete] + msgs}}}
        if dry_run:
            print(f"  [dry-run] remember {s['session_id']} ({len(msgs)} messages)")
            envoyes += 1
            continue
        try:
            data = json.dumps(corps).encode()
            req = urllib.request.Request(url.rstrip("/") + "/mcp", data=data, method="POST")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "application/json, text/event-stream")
            with urllib.request.urlopen(req, timeout=120) as r:
                r.read()
            envoyes += 1
        except Exception as e:
            # Un echec ne doit PAS faire echouer l'indexation txtai : les deux puits
            # sont independants. La session repartira au prochain run (le manifest
            # OpenViking n'est avance que sur succes).
            print(f"  WARN openviking {s['session_id']}: {e}", file=sys.stderr)
    reste = max(0, len(sessions) - OV_LIMIT)
    print(f"OpenViking : {envoyes} session(s) envoyee(s)"
          + (f", {reste} reportee(s) au prochain run (plafond {OV_LIMIT})" if reste else ""))


def post(url: str, token: str, path: str, payload=None, method="POST"):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url.rstrip("/") + path, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=900) as r:
        return r.status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="parse + stats, aucun POST")
    ap.add_argument("--full", action="store_true", help="ignore le manifest, ré-indexe tout")
    ap.add_argument("--project", help="filtre : ne traite que les dirs contenant cette chaîne")
    args = ap.parse_args()

    files = sorted(PROJECTS_DIR.glob("*/*.jsonl"))
    if args.project:
        files = [f for f in files if args.project in f.parent.name]
    if not files:
        print(f"Aucun .jsonl sous {PROJECTS_DIR}", file=sys.stderr)
        sys.exit(1)

    # Resumabilité : skip les fichiers inchangés depuis la dernière indexation.
    manifest = {}
    if not args.full and MANIFEST.exists():
        try:
            manifest = json.loads(MANIFEST.read_text())
        except Exception:
            manifest = {}

    all_docs, sessions, n_sessions, n_empty, n_skip = [], [], 0, 0, 0
    fresh_manifest = dict(manifest)
    for f in files:
        mtime = f.stat().st_mtime
        if not args.full and manifest.get(str(f)) == mtime:
            n_skip += 1
            continue
        s = parse_session(f)
        if not s:
            n_empty += 1
            continue
        n_sessions += 1
        sessions.append(s)
        all_docs.extend(session_to_docs(s))
        fresh_manifest[str(f)] = mtime

    print(f"Sessions à (ré)indexer : {n_sessions} (skip inchangées: {n_skip}, vides: {n_empty})")
    print(f"Documents (chunks) : {len(all_docs)}")

    if args.dry_run:
        if all_docs:
            d = all_docs[0]
            print("\n--- doc échantillon (métadonnées + extrait) ---")
            print(f"id={d['id']}  project={d['project']}  date={d['date']}")
            print(f"title={d['title']}")
            print(f"url={d['url']}")
            print(f"text[:300]={d['text'][:300]!r}")
        push_openviking(sessions, dry_run=True)
        return

    url = os.environ.get("TXTAI_URL")
    token = os.environ.get("TXTAI_TOKEN")
    if not url or not token:
        print("TXTAI_URL et TXTAI_TOKEN requis (ou --dry-run)", file=sys.stderr)
        sys.exit(2)

    # Commit INCRÉMENTAL : add + upsert par batch. Chaque upsert n'embed que le
    # batch bufferisé (txtai merge par id) → commits courts, robuste au timeout,
    # reprenable. Un seul upsert géant sur 2 cœurs CPU dépasse le timeout client.
    if not all_docs:
        print("Rien de nouveau à indexer.")
        return
    for i in range(0, len(all_docs), BATCH):
        batch = all_docs[i : i + BATCH]
        post(url, token, "/add", batch)
        post(url, token, "/upsert", method="GET")
        print(f"  indexed {i + len(batch)}/{len(all_docs)}")
    # manifest sauvé seulement après succès → un run échoué se reprend au prochain
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(fresh_manifest))
    print(f"index persisté (incrémental). manifest: {MANIFEST}")

    # APRES txtai, volontairement : txtai porte la recherche, c'est lui qui ne doit
    # pas etre prive d'une indexation si OpenViking est indisponible.
    push_openviking(sessions)


if __name__ == "__main__":
    main()
