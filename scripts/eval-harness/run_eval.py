# /// script
# requires-python = ">=3.10"
# dependencies = ["mlflow", "boto3"]
# ///
"""Harness d'éval modèles LocalAI (P1 du pipeline auto-deploy).

Batterie DÉTERMINISTE (pas de LLM-juge → pas de biais) : coding (tests unitaires
en sandbox docker --network none), tool-calling (validation schéma), format
(validateurs), + perf (tok/s, latence, erreurs). Log MLflow pour comparer
candidat vs baseline. Le modèle courant ORCHESTRE (lance ce script), il ne JUGE pas.

Usage :
  uv run run_eval.py --model ornith-1.0-9b-mtp --tag baseline
  uv run run_eval.py --model <candidat> --tag candidate --compare-to ornith-1.0-9b-mtp

Env : LOCALAI_URL, LOCALAI_KEY (ou ~/.config/brain/localai-key), MLFLOW_TRACKING_URI.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, tempfile, time, urllib.request
from pathlib import Path

HERE = Path(__file__).parent
LOCALAI_URL = os.environ.get("LOCALAI_URL", "https://localai.tgu.ovh/v1")
MLFLOW_URI = os.environ.get("MLFLOW_TRACKING_URI", "https://mlflow.tgu.ovh")
SANDBOX_IMAGE = os.environ.get("EVAL_SANDBOX_IMAGE", "python:3.12-slim")


def localai_key() -> str:
    k = os.environ.get("LOCALAI_KEY")
    if k:
        return k
    f = Path.home() / ".config" / "brain" / "localai-key"
    return f.read_text().strip() if f.exists() else ""


def chat(model, messages, tools=None, max_tokens=2048, temp=0.0, timeout=300):
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temp}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    req = urllib.request.Request(LOCALAI_URL.rstrip("/") + "/chat/completions",
                                 data=json.dumps(body).encode(), method="POST")
    req.add_header("Authorization", f"Bearer {localai_key()}")
    req.add_header("Content-Type", "application/json")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
    except Exception as e:
        return {"error": str(e)[:200], "latency": time.time() - t0}
    dt = time.time() - t0
    msg = d["choices"][0]["message"]
    return {"content": msg.get("content") or "", "tool_calls": msg.get("tool_calls") or [],
            "usage": d.get("usage", {}), "latency": dt, "finish": d["choices"][0].get("finish_reason")}


def warmup(model, budget=180):
    """Health-gate : le modèle génère-t-il des tokens sur une requête triviale ?
    (cold-load inclus). Évite de griller 300s × N tâches sur un modèle qui ne charge
    pas (quant/backend incompatible, ex Q2_0 ternaire hors mainline). Liveness =
    completion_tokens>0 : un modèle reasoning peut mettre ses tokens dans `reasoning`
    (content vide) tout en étant bien vivant. budget total borné."""
    deadline = time.time() + budget
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        left = max(20, int(deadline - time.time()))
        r = chat(model, [{"role": "user", "content": "Reply with one word: ready"}],
                 max_tokens=64, timeout=left)
        alive = not r.get("error") and (r.get("content") or r.get("tool_calls")
                                        or r.get("usage", {}).get("completion_tokens", 0) > 0)
        if alive:
            print(f"warmup OK (essai {attempt}, {r.get('latency', 0):.1f}s)")
            return True
        print(f"warmup essai {attempt}: {r.get('error', 'réponse vide')[:80]}")
        time.sleep(5)  # anti busy-loop sur échec/erreur rapide
    return False


def extract_code(text: str) -> str:
    blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return blocks[-1] if blocks else text


def run_in_sandbox(code: str, test: str) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "sol.py").write_text(code + "\n\n" + test + "\nprint('PASS')\n")
        try:
            r = subprocess.run(
                ["docker", "run", "--rm", "--network", "none", "--memory", "512m",
                 "--cpus", "1", "--ulimit", "cpu=10", "-v", f"{td}:/w:ro", "-w", "/w",
                 SANDBOX_IMAGE, "python", "sol.py"],
                capture_output=True, text=True, timeout=60)
            ok = r.returncode == 0 and "PASS" in r.stdout
            return ok, (r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "")[:200]
        except subprocess.TimeoutExpired:
            return False, "timeout"
        except Exception as e:
            return False, str(e)[:200]


def score_coding(model, tasks):
    res, tokps = [], []
    for t in tasks:
        r = chat(model, [{"role": "user", "content": t["prompt"]}])
        if r.get("error"):
            res.append({"id": t["id"], "pass": False, "detail": r["error"]}); continue
        ok, detail = run_in_sandbox(extract_code(r["content"]), t["test"])
        ct = r["usage"].get("completion_tokens", 0)
        if r["latency"] > 0 and ct:
            tokps.append(ct / r["latency"])
        res.append({"id": t["id"], "pass": ok, "detail": detail})
    return res, tokps


def score_toolcall(model, tasks):
    res = []
    for t in tasks:
        r = chat(model, [{"role": "user", "content": t["prompt"]}], tools=t["tools"])
        if r.get("error"):
            res.append({"id": t["id"], "pass": False, "detail": r["error"]}); continue
        tc = r["tool_calls"]
        ok, detail = False, "no tool_call"
        if tc:
            fn = tc[0].get("function", {})
            name = fn.get("name")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except Exception:
                args = {}
            name_ok = name == t["expect_name"]
            args_ok = all(str(args.get(k, "")).strip().lower() == str(v).strip().lower()
                          for k, v in t["expect_args"].items())
            ok = name_ok and args_ok
            detail = f"name={name} args={args}"
        res.append({"id": t["id"], "pass": ok, "detail": detail})
    return res


def score_format(model, tasks):
    res = []
    for t in tasks:
        r = chat(model, [{"role": "user", "content": t["prompt"]}])
        if r.get("error"):
            res.append({"id": t["id"], "pass": False, "detail": r["error"]}); continue
        c = (r["content"] or "").strip()
        ok, detail = False, c[:80]
        if t["check"] == "equals":
            ok = c == t["value"]
        elif t["check"] == "regex":
            ok = bool(re.search(t["pattern"], c))
        elif t["check"] == "json_keys":
            try:
                m = re.search(r"\{.*\}", c, re.DOTALL)
                obj = json.loads(m.group(0)) if m else {}
                ok = all(k in obj for k in t["keys"])
                if ok and t.get("expect"):
                    ok = all(str(obj.get(k)).lower() == str(v).lower() for k, v in t["expect"].items())
            except Exception as e:
                detail = f"json err: {e}"
        res.append({"id": t["id"], "pass": ok, "detail": detail})
    return res


def score_reasoning(model, tasks):
    res = []
    for t in tasks:
        prompt = t["prompt"] + "\nEnd your reply with a line 'ANSWER: <number>'."
        r = chat(model, [{"role": "user", "content": prompt}])
        if r.get("error"):
            res.append({"id": t["id"], "pass": False, "detail": r["error"]}); continue
        c = r["content"] or ""
        m = re.findall(r"ANSWER:\s*(-?\d+(?:\.\d+)?)", c)
        if not m:
            m = re.findall(r"(-?\d+(?:\.\d+)?)", c)  # fallback: dernier nombre
        got = m[-1] if m else None
        ok = got is not None and abs(float(got) - float(t["answer"])) < 1e-6
        res.append({"id": t["id"], "pass": ok, "detail": f"got={got} exp={t['answer']}"})
    return res


def load(name):
    f = HERE / "tasks" / name
    if not f.exists():
        return []
    return [json.loads(l) for l in f.read_text().splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tag", default="run")
    ap.add_argument("--compare-to", default=None)
    args = ap.parse_args()

    print(f"== éval {args.model} ({args.tag}) ==")
    if not warmup(args.model):
        print("MODÈLE INJOIGNABLE (warmup échoué) — reject rapide (metrics=0)")
        metrics = {"coding_pass_rate": 0.0, "toolcall_acc": 0.0, "format_acc": 0.0,
                   "reasoning_acc": 0.0, "mean_tokps": 0.0, "overall": 0.0, "unreachable": 1}
        results = {"model": args.model, "tag": args.tag, "metrics": metrics, "unreachable": True}
        outdir = HERE / "results"
        outdir.mkdir(exist_ok=True)
        (outdir / f"{args.model}-{args.tag}.json").write_text(json.dumps(results, indent=2))
        print(json.dumps(metrics, indent=2))
        return

    coding, tokps = score_coding(args.model, load("coding.jsonl"))
    toolcall = score_toolcall(args.model, load("toolcall.jsonl"))
    fmt = score_format(args.model, load("format.jsonl"))
    reasoning = score_reasoning(args.model, load("reasoning.jsonl"))

    def rate(rs): return sum(1 for r in rs if r["pass"]) / len(rs) if rs else 0.0
    metrics = {
        "coding_pass_rate": rate(coding),
        "toolcall_acc": rate(toolcall),
        "format_acc": rate(fmt),
        "reasoning_acc": rate(reasoning),
        "mean_tokps": (sum(tokps) / len(tokps)) if tokps else 0.0,
    }
    cats = [metrics["coding_pass_rate"], metrics["toolcall_acc"], metrics["format_acc"], metrics["reasoning_acc"]]
    metrics["overall"] = round(sum(cats) / len(cats), 4)
    results = {"model": args.model, "tag": args.tag, "metrics": metrics,
               "coding": coding, "toolcall": toolcall, "format": fmt, "reasoning": reasoning}

    # Fallback local : toujours écrire results.json (l'artefact S3/MLflow peut échouer
    # faute de creds rustfs — les métriques passent, le détail non).
    outdir = HERE / "results"
    outdir.mkdir(exist_ok=True)
    (outdir / f"{args.model}-{args.tag}.json").write_text(json.dumps(results, indent=2))

    print(json.dumps(metrics, indent=2))
    for cat, rs in [("coding", coding), ("toolcall", toolcall), ("format", fmt), ("reasoning", reasoning)]:
        for r in rs:
            print(f"  [{cat}] {'✅' if r['pass'] else '❌'} {r['id']}  {r['detail'][:70]}")

    # MLflow
    try:
        import mlflow, datetime
        mlflow.set_tracking_uri(MLFLOW_URI)
        mlflow.set_experiment("localai-model-eval")
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        with mlflow.start_run(run_name=f"{args.model}-{args.tag}-{stamp}"):
            mlflow.log_params({"model": args.model, "tag": args.tag})
            mlflow.log_metrics(metrics)
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                json.dump(results, f, indent=2); tmp = f.name
            mlflow.log_artifact(tmp, "results")
        print(f"→ loggé MLflow ({MLFLOW_URI}, exp localai-model-eval)")
    except Exception as e:
        print(f"WARN MLflow: {e}")

    if args.compare_to:
        try:
            import mlflow
            mlflow.set_tracking_uri(MLFLOW_URI)
            exp = mlflow.get_experiment_by_name("localai-model-eval")
            df = mlflow.search_runs([exp.experiment_id],
                                    filter_string=f"params.model = '{args.compare_to}'",
                                    order_by=["start_time DESC"], max_results=1)
            if len(df):
                base = df.iloc[0]
                print(f"\n== vs {args.compare_to} (baseline) ==")
                for k in ["overall", "coding_pass_rate", "toolcall_acc", "format_acc", "reasoning_acc", "mean_tokps"]:
                    b = base.get(f"metrics.{k}", float("nan"))
                    print(f"  {k}: {metrics[k]:.3f}  (baseline {b:.3f}, Δ {metrics[k]-b:+.3f})")
        except Exception as e:
            print(f"WARN compare: {e}")


if __name__ == "__main__":
    main()
