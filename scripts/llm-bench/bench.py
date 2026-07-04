#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27"]
# ///
"""
LLM bench harness — compare two OpenAI-compatible endpoints on the my-kluster
cron-agent workload (tool-calling, big system prompt, long browser-snapshot ctx).

Measures, per scenario, end-to-end AS DEPLOYED (HTTP stack included):
  - TTFT          time to first token (s)         -> latency, dominated by prefill
  - prefill tok/s prompt_tokens / TTFT            -> cost of swallowing the ~46k prompt
  - decode tok/s  completion_tokens / (t - TTFT)  -> the headline speed number
  - tool_ok       tool_calls emitted as valid JSON with expected fn (S1/S3 only)

Server-reported `timings` (llama-server / ik_llama.cpp) are captured when present
and preferred over client-side math; LocalAI usually strips them -> client math.

Two endpoints, configured by env (CLI can override the URL):
  LOCALAI  -> prod qwen3-8b           default https://localai.tgu.ovh/v1
  OPTIONB  -> ik_llama.cpp standalone default http://localhost:8080/v1

Usage:
  export LOCALAI_API_KEY=...                 # Bearer for localai.tgu.ovh
  ./bench.py --endpoint both --runs 5 --out results.json
  ./bench.py --endpoint optionb --optionb-url http://192.168.88.x:8080/v1
  ./bench.py --endpoint localai --scenario S1,S3
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field

import httpx

# --------------------------------------------------------------------------- #
# Synthetic fixtures — realistic shapes for the NC job-hunt / Hermes crons.
# Sizes target ~tokens assuming ~4 chars/token.
# --------------------------------------------------------------------------- #

_AGENT_RULES = """\
You are Hermes Agent, an autonomous job-hunting assistant operating on New \
Caledonia (NC) employment sources. You run unattended on a cron schedule. \
You must always reason step by step, then act through the provided tools. \
Never fabricate listings. When a tool is available for an action, you MUST \
call the tool rather than describing the action in prose. Respect rate limits, \
deduplicate offers by (employer, title, location), and normalise salaries to \
XPF monthly. Locations of interest: Nouméa, Dumbéa, Païta, Mont-Dore. \
Prefer permanent (CDI) contracts but record CDD and missions. If a page is \
paginated, follow up to 5 pages. Output strictly via tool calls; free text is \
only allowed for the final human-readable summary. """


def _system_prompt(target_tokens: int) -> str:
    """Build a ~target_tokens system prompt by stacking numbered policy clauses."""
    target_chars = target_tokens * 4
    out = [_AGENT_RULES]
    i = 0
    while sum(len(s) for s in out) < target_chars:
        i += 1
        out.append(
            f"Policy clause {i}: when evaluating an offer against the candidate "
            f"profile, weight required experience, contract type, commute distance "
            f"from Nouméa centre, and stated salary band; discard offers older than "
            f"30 days; flag duplicates already present in the tracker; record the "
            f"source URL and the snapshot timestamp for audit. "
        )
    return "".join(out)


def _browser_snapshot(target_tokens: int) -> str:
    """Build a ~target_tokens fake job-board HTML dump (browser_snapshot shape)."""
    target_chars = target_tokens * 4
    head = (
        "<html><head><title>Offres d'emploi - NC</title></head><body>"
        "<div id='app'><header><nav>Accueil Offres Entreprises Contact</nav>"
        "</header><main><section class='results'>"
    )
    cards = []
    n = 0
    titles = ["Développeur Python", "Data Engineer", "Administrateur Système",
              "Technicien Réseau", "Chef de Projet IT", "Analyste BI"]
    employers = ["OPT-NC", "Enercal", "CANL", "Gouvernement NC", "OCEF", "CCI-NC"]
    while len(head) + sum(len(c) for c in cards) < target_chars:
        t = titles[n % len(titles)]
        e = employers[n % len(employers)]
        cards.append(
            f"<article class='offer' data-id='{1000 + n}'>"
            f"<h2 class='title'>{t}</h2>"
            f"<span class='employer'>{e}</span>"
            f"<span class='location'>Nouméa</span>"
            f"<span class='contract'>{'CDI' if n % 3 else 'CDD'}</span>"
            f"<span class='salary'>{350000 + (n * 1000) % 200000} XPF/mois</span>"
            f"<p class='desc'>Poste basé à Nouméa. Expérience {n % 8} ans requise. "
            f"Maîtrise des outils standards du domaine. Equipe dynamique. "
            f"Candidature via le portail. Référence OFFRE-{2000 + n}.</p>"
            f"<a href='/offre/{1000 + n}'>Voir l'offre</a></article>"
        )
        n += 1
    return head + "".join(cards) + "</section></main></body></html>"


_TOOLS_JOBS = [{
    "type": "function",
    "function": {
        "name": "save_jobs",
        "description": "Persist extracted job offers to the tracker.",
        "parameters": {
            "type": "object",
            "properties": {
                "jobs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "employer": {"type": "string"},
                            "location": {"type": "string"},
                            "contract": {"type": "string"},
                            "salary_xpf": {"type": "integer"},
                        },
                        "required": ["title", "employer"],
                    },
                }
            },
            "required": ["jobs"],
        },
    },
}]

_TOOLS_WEATHER = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
}]


@dataclass
class Scenario:
    id: str
    desc: str
    messages: list
    tools: list | None = None
    expect_tool: str | None = None   # function name we expect a valid call for
    max_tokens: int = 512


def build_scenarios() -> dict[str, Scenario]:
    sys_small = "You are a helpful assistant with access to tools. Call a tool when relevant."
    sys_16k = _system_prompt(16_000)
    # HTML tokenises denser than ~4 chars/tok; 15k-est lands ~21k real tokens so
    # S3 total (~34k real) fits qwen3-8b's effective 40960 ctx -> both endpoints
    # run the identical prompt. (Real crons can exceed this; see README finding.)
    snap_30k = _browser_snapshot(15_000)
    return {
        # S0: tiny prompt + long generation -> total ≈ pure decode. The only
        # honest speed metric for models LocalAI buffers (gemma reasoning, tools),
        # where streaming gives TTFT==total and decode_tps can't be isolated.
        # Compare gen_tps (= completion_tokens / total_s) across configs.
        "S0": Scenario(
            id="S0",
            desc="tiny prompt, long generation (decode proxy via total wall-clock)",
            messages=[
                {"role": "system", "content": "Tu es un assistant concis."},
                {"role": "user", "content":
                    "Écris une courte histoire de 400 mots sur un robot jardinier en Nouvelle-Calédonie."},
            ],
            max_tokens=512,
        ),
        # S1: short tool-call -> decode speed + tool JSON validity
        "S1": Scenario(
            id="S1",
            desc="short tool-call (weather)",
            messages=[
                {"role": "system", "content": sys_small},
                {"role": "user", "content": "Quel temps fait-il à Nouméa aujourd'hui ?"},
            ],
            tools=_TOOLS_WEATHER,
            expect_tool="get_weather",
            max_tokens=256,
        ),
        # S2: big system prompt -> prefill stress, no tool
        "S2": Scenario(
            id="S2",
            desc="~16k system prompt, plain answer",
            messages=[
                {"role": "system", "content": sys_16k},
                {"role": "user", "content": "Résume en 3 phrases ta politique de déduplication des offres."},
            ],
            max_tokens=256,
        ),
        # S3: 16k system + 30k snapshot + tool -> the real cron stress
        "S3": Scenario(
            id="S3",
            desc="~16k system + ~21k browser_snapshot + tool-call (~34k total)",
            messages=[
                {"role": "system", "content": sys_16k},
                {"role": "user", "content":
                    "Voici un browser_snapshot d'un portail d'emploi NC. Extrais uniquement "
                    "les 5 PREMIÈRES offres et enregistre-les via l'outil save_jobs.\n\n" + snap_30k},
            ],
            tools=_TOOLS_JOBS,
            expect_tool="save_jobs",
            max_tokens=2048,  # qwen3 thinking-mode needs headroom to reach the tool call
        ),
    }


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #

@dataclass
class Endpoint:
    name: str
    base_url: str
    model: str
    api_key: str | None
    temperature: float
    seed: int = 42  # pinned for reproducible output length across runs


def build_endpoints(args) -> dict[str, Endpoint]:
    return {
        "localai": Endpoint(
            name="localai",
            base_url=args.localai_url,
            model=args.localai_model,
            api_key=os.environ.get("LOCALAI_API_KEY"),
            temperature=0.7,  # qwen3-8b reco
            seed=args.seed,
        ),
        "optionb": Endpoint(
            name="optionb",
            base_url=args.optionb_url,
            model=args.optionb_model,
            api_key=os.environ.get("OPTIONB_API_KEY"),
            temperature=0.6,  # Qwen3.6 reco
            seed=args.seed,
        ),
    }


# --------------------------------------------------------------------------- #
# One streaming run
# --------------------------------------------------------------------------- #

@dataclass
class RunResult:
    ttft: float = 0.0
    total: float = 0.0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    server_prefill_tps: float | None = None   # from llama-server `timings`
    server_decode_tps: float | None = None
    tool_ok: bool | None = None
    error: str | None = None
    text_chars: int = 0


def _accumulate_tool_args(store: dict, tool_deltas: list) -> None:
    for d in tool_deltas:
        idx = d.get("index", 0)
        slot = store.setdefault(idx, {"name": None, "args": ""})
        fn = d.get("function") or {}
        if fn.get("name"):
            slot["name"] = fn["name"]
        if fn.get("arguments"):
            slot["args"] += fn["arguments"]


def run_once(client: httpx.Client, ep: Endpoint, sc: Scenario) -> RunResult:
    payload = {
        "model": ep.model,
        "messages": sc.messages,
        "temperature": ep.temperature,
        "max_tokens": sc.max_tokens,
        "seed": ep.seed,  # reproducible sampling
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if sc.tools:
        payload["tools"] = sc.tools
        payload["tool_choice"] = "auto"
    headers = {"Content-Type": "application/json"}
    if ep.api_key:
        headers["Authorization"] = f"Bearer {ep.api_key}"

    r = RunResult()
    tools_store: dict = {}
    usage = None
    timings = None
    start = time.perf_counter()
    first = None
    try:
        with client.stream("POST", f"{ep.base_url}/chat/completions",
                            json=payload, headers=headers) as resp:
            if resp.status_code != 200:
                body = resp.read().decode("utf-8", "replace")[:300]
                r.error = f"HTTP {resp.status_code}: {body}"
                return r
            for line in resp.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if chunk.get("error"):
                    err = chunk["error"]
                    r.error = err.get("message") if isinstance(err, dict) else str(err)
                    return r
                if chunk.get("usage"):
                    usage = chunk["usage"]
                if chunk.get("timings"):
                    timings = chunk["timings"]
                for ch in chunk.get("choices", []):
                    delta = ch.get("delta") or {}
                    got = False
                    if delta.get("content"):
                        r.text_chars += len(delta["content"])
                        got = True
                    if delta.get("tool_calls"):
                        _accumulate_tool_args(tools_store, delta["tool_calls"])
                        got = True
                    if got and first is None:
                        first = time.perf_counter()
        end = time.perf_counter()
    except httpx.HTTPError as e:
        r.error = f"{type(e).__name__}: {e}"
        return r

    r.ttft = (first - start) if first else (end - start)
    r.total = end - start
    if usage:
        r.prompt_tokens = usage.get("prompt_tokens")
        r.completion_tokens = usage.get("completion_tokens")
    if timings:
        r.server_prefill_tps = timings.get("prompt_per_second")
        r.server_decode_tps = timings.get("predicted_per_second")

    if sc.expect_tool is not None:
        r.tool_ok = False
        for slot in tools_store.values():
            if slot["name"] == sc.expect_tool:
                try:
                    json.loads(slot["args"] or "{}")
                    r.tool_ok = True
                except json.JSONDecodeError:
                    pass
    return r


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #

def _med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def summarize(runs: list[RunResult]) -> dict:
    ok = [r for r in runs if r.error is None]
    if not ok:
        return {"error": runs[0].error if runs else "no runs"}
    prefill, decode = [], []
    for r in ok:
        if r.server_prefill_tps:
            prefill.append(r.server_prefill_tps)
        elif r.prompt_tokens and r.ttft > 0:
            prefill.append(r.prompt_tokens / r.ttft)
        dt = r.total - r.ttft
        if r.server_decode_tps:
            decode.append(r.server_decode_tps)
        elif r.completion_tokens and r.completion_tokens >= 8 and dt >= 0.1:
            # guard: tool-call bursts arrive ~all-at-once (dt≈0) -> bogus tok/s
            decode.append(r.completion_tokens / dt)
    tool_flags = [r.tool_ok for r in ok if r.tool_ok is not None]
    return {
        "n_ok": len(ok),
        "ttft_s": _med([r.ttft for r in ok]),
        "total_s": _med([r.total for r in ok]),
        "prefill_tps": _med(prefill),
        "decode_tps": _med(decode),
        "prompt_tokens": _med([r.prompt_tokens for r in ok]),
        "completion_tokens": _med([r.completion_tokens for r in ok]),
        "tool_ok_rate": (sum(tool_flags) / len(tool_flags)) if tool_flags else None,
        "server_timed": any(r.server_decode_tps for r in ok),
    }


def fmt(v, nd=1):
    return f"{v:.{nd}f}" if isinstance(v, (int, float)) else "—"


def print_table(results: dict) -> None:
    eps = list(results.keys())
    scs = sorted({s for e in results for s in results[e]})
    rows = [
        ("decode tok/s", "decode_tps", 1),
        ("prefill tok/s", "prefill_tps", 1),
        ("TTFT s", "ttft_s", 2),
        ("total s", "total_s", 2),
        ("prompt tok", "prompt_tokens", 0),
        ("compl tok", "completion_tokens", 0),
        ("tool_ok %", "tool_ok_rate", 2),
    ]
    for sc in scs:
        print(f"\n=== {sc} ===")
        hdr = f"{'metric':<16}" + "".join(f"{e:>16}" for e in eps)
        print(hdr)
        print("-" * len(hdr))
        for label, key, nd in rows:
            line = f"{label:<16}"
            for e in eps:
                s = results[e].get(sc, {})
                val = s.get(key)
                if key == "tool_ok_rate" and val is not None:
                    val = val * 100
                line += f"{fmt(val, nd):>16}"
            print(line)
        timed = [results[e].get(sc, {}).get("server_timed") for e in eps]
        if any(timed):
            print(f"  (server timings used: {dict(zip(eps, timed))})")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def _git_sha() -> str:
    """Short HEAD sha of this repo (+ '-dirty' if the tree has changes), for provenance."""
    try:
        root = os.path.dirname(os.path.abspath(__file__))
        sha = subprocess.check_output(
            ["git", "-C", root, "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, text=True).strip()
        dirty = subprocess.call(
            ["git", "-C", root, "diff", "--quiet"], stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL) != 0
        return sha + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


def append_history(path: str, summary: dict, endpoints: dict, note: str, seed: int) -> None:
    """Append one JSONL row per (endpoint, scenario) — append-only time series."""
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    sha = _git_sha()
    n = 0
    with open(path, "a") as f:
        for ename, scens in summary.items():
            for sid, s in scens.items():
                f.write(json.dumps({
                    "ts": ts, "git_sha": sha, "note": note, "seed": seed,
                    "endpoint": ename, "model": endpoints[ename].model, "scenario": sid,
                    "decode_tps": s.get("decode_tps"), "prefill_tps": s.get("prefill_tps"),
                    "ttft_s": s.get("ttft_s"), "total_s": s.get("total_s"),
                    # gen_tps = completion/total ≈ decode on S0 (tiny prompt), robust to buffering
                    "gen_tps": (s.get("completion_tokens") / s.get("total_s"))
                               if s.get("total_s") else None,
                    "prompt_tokens": s.get("prompt_tokens"),
                    "completion_tokens": s.get("completion_tokens"),
                    "tool_ok_rate": s.get("tool_ok_rate"), "n_ok": s.get("n_ok"),
                    "server_timed": s.get("server_timed"),
                }) + "\n")
                n += 1
    print(f"\nappended {n} rows to {path} (git={sha})", file=sys.stderr)


def main() -> int:
    p = argparse.ArgumentParser(description="LLM bench: localai vs ik_llama.cpp Option B")
    p.add_argument("--endpoint", default="both", choices=["localai", "optionb", "both"])
    p.add_argument("--scenario", default="all", help="comma list of S1,S2,S3 or 'all'")
    p.add_argument("--runs", type=int, default=5, help="runs per scenario (run 1 dropped as warmup)")
    p.add_argument("--timeout", type=float, default=600.0)
    p.add_argument("--localai-url", default=os.environ.get("LOCALAI_URL", "https://localai.tgu.ovh/v1"))
    p.add_argument("--localai-model", default=os.environ.get("LOCALAI_MODEL", "qwen3-8b"))
    p.add_argument("--optionb-url", default=os.environ.get("OPTIONB_URL", "http://localhost:8080/v1"))
    p.add_argument("--optionb-model", default=os.environ.get("OPTIONB_MODEL", "qwen3.6-35b-a3b"))
    p.add_argument("--out", default=None, help="write raw+summary JSON here")
    p.add_argument("--history", default=None,
                   help="append one JSONL row per (endpoint,scenario) with ts+git_sha (time series)")
    p.add_argument("--note", default="", help="free-text tag stored in each history row (e.g. 'fit-only THREADS5')")
    p.add_argument("--seed", type=int, default=42, help="pinned sampling seed for reproducibility")
    args = p.parse_args()

    all_scen = build_scenarios()
    if args.scenario == "all":
        scen_ids = list(all_scen)
    else:
        scen_ids = [s.strip().upper() for s in args.scenario.split(",")]
        bad = [s for s in scen_ids if s not in all_scen]
        if bad:
            print(f"unknown scenarios: {bad}", file=sys.stderr)
            return 2

    endpoints = build_endpoints(args)
    sel = ["localai", "optionb"] if args.endpoint == "both" else [args.endpoint]

    raw: dict = {}
    summary: dict = {}
    with httpx.Client(timeout=args.timeout) as client:
        for ename in sel:
            ep = endpoints[ename]
            raw[ename], summary[ename] = {}, {}
            print(f"\n### {ename}  {ep.base_url}  model={ep.model}", file=sys.stderr)
            for sid in scen_ids:
                sc = all_scen[sid]
                runs: list[RunResult] = []
                for i in range(args.runs):
                    res = run_once(client, ep, sc)
                    tag = "warmup" if i == 0 else f"run{i}"
                    if res.error:
                        print(f"  {sid} {tag}: ERROR {res.error}", file=sys.stderr)
                    else:
                        print(f"  {sid} {tag}: ttft={res.ttft:.2f}s total={res.total:.2f}s "
                              f"ptok={res.prompt_tokens} ctok={res.completion_tokens} "
                              f"tool_ok={res.tool_ok}", file=sys.stderr)
                    if i > 0:  # drop warmup
                        runs.append(res)
                raw[ename][sid] = [vars(r) for r in runs]
                summary[ename][sid] = summarize(runs)

    print_table(summary)
    if args.out:
        with open(args.out, "w") as f:
            json.dump({"summary": summary, "raw": raw}, f, indent=2)
        print(f"\nwrote {args.out}", file=sys.stderr)
    if args.history:
        append_history(args.history, summary, endpoints, args.note, args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
