"""Briques communes de la veille (stdlib seulement) : HTTP, Telegram, LLM, état, alertes.

Tourne dans le conteneur Dkron (exécuteur shell). Les secrets arrivent par l'environnement
du pod (Secret `veille-secrets` en envFrom) ; l'exécuteur shell les hérite.
"""

import json
import os
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

NC = ZoneInfo("Pacific/Noumea")
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"

MINIFLUX = os.environ.get(
    "MINIFLUX_URL", "http://miniflux.miniflux.svc.cluster.local:8080"
)
LOCALAI = os.environ.get(
    "LOCALAI_URL", "http://localai.localai.svc.cluster.local:8080/v1/chat/completions"
)
TXTAI = os.environ.get("TXTAI_URL", "http://txtai.txtai.svc.cluster.local:8000")
MODELE = os.environ.get("MODELE", "gemma-4-12b-it-qat")
CHAT_ID = os.environ.get("CHAT_ID", "843341688")
ETAT = os.environ.get("ETAT_DIR", "/data/etat")
CODE = os.path.dirname(os.path.abspath(__file__))


def maintenant():
    return datetime.now(NC)


def http(url, data=None, headers=None, method=None, timeout=60, essais=1, pause=60):
    """Requête HTTP ; JSON décodé si la réponse en est. `essais` > 1 réessaie après `pause` s."""
    h = {"User-Agent": UA}
    h.update(headers or {})
    if data is not None and not isinstance(data, bytes):
        data = json.dumps(data, ensure_ascii=False).encode()
        h.setdefault("Content-Type", "application/json")
    for n in range(1, essais + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=h, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                corps = r.read()
                if "json" in r.headers.get("Content-Type", ""):
                    return json.loads(corps)
                return corps.decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError) as e:
            if n == essais:
                raise
            print(
                "  essai %d/%d échoué (%s), nouvel essai dans %d s"
                % (n, essais, e, pause),
                flush=True,
            )
            time.sleep(pause)


def telegram(texte):
    """Envoie un texte, découpé à ~3 800 car. sans couper au milieu d'un bloc '———'."""
    morceaux, courant = [], ""
    for b in (x.strip() for x in texte.split("———") if x.strip()):
        candidat = (courant + "\n———\n" + b) if courant else b
        if len(candidat) > 3800 and courant:
            morceaux.append(courant)
            courant = b
        else:
            courant = candidat
    if courant:
        morceaux.append(courant)
    url = "https://api.telegram.org/bot%s/sendMessage" % os.environ["TELEGRAM_TOKEN"]
    for i, m in enumerate(morceaux):
        for j in range(0, len(m), 4096):
            rep = http(
                url,
                {
                    "chat_id": CHAT_ID,
                    "text": m[j : j + 4096],
                    "disable_web_page_preview": True,
                },
                timeout=30,
            )
            if not rep.get("ok"):
                raise RuntimeError("Telegram a refusé l'envoi : %s" % rep)
        if i + 1 < len(morceaux):
            time.sleep(1)
    return len(morceaux)


def llm(systeme, utilisateur, max_tokens=2048, temperature=1.0, essais=2):
    """Un appel gemma via LocalAI. `reasoning_effort: none` est OBLIGATOIRE : sinon gemma
    passe tout le budget en raisonnement et `content` revient vide. Deux essais à une minute
    d'écart : absorbe un échec de chargement passager (VRAM prise par ComfyUI sur l'hôte)."""
    corps = {
        "model": MODELE,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "reasoning_effort": "none",
        "messages": [
            {"role": "system", "content": systeme},
            {"role": "user", "content": utilisateur},
        ],
    }
    rep = http(
        LOCALAI,
        corps,
        headers={"Authorization": "Bearer " + os.environ["LOCALAI_API_KEY"]},
        timeout=600,
        essais=essais,
        pause=60,
    )
    return (rep["choices"][0]["message"].get("content") or "").strip()


def miniflux(chemin, data=None, method=None):
    return http(
        MINIFLUX + chemin,
        data,
        headers={"X-Auth-Token": os.environ["MINIFLUX_TOKEN"]},
        method=method,
    )


def profil():
    """Profil de la stack (apps/veille/code/profil.md), injecté dans chaque prompt."""
    with open(os.path.join(CODE, "profil.md"), encoding="utf-8") as f:
        return f.read().strip()


def indexer(job, texte):
    """Mémoire txtai, un document par bloc '———'. À appeler après l'envoi Telegram."""
    date = maintenant().strftime("%Y-%m-%d")
    exe = maintenant().strftime("%Y%m%dT%H%M")
    entete = "[Digest veille — thème: %s · date: %s · execution: %s]" % (job, date, exe)
    docs = [
        {
            "id": "digest:%s:%s:%04d" % (job, exe, i),
            "text": entete + "\n\n" + b,
            "source": "veille",
            "job": job,
            "date": date,
        }
        for i, b in enumerate(b.strip() for b in texte.split("———") if b.strip())
    ]
    h = {"Authorization": "Bearer " + os.environ["TXTAI_TOKEN"]}
    http(TXTAI + "/add", docs, headers=h, timeout=300)
    http(TXTAI + "/upsert", headers=h, timeout=300)
    return len(docs)


def lire_etat(nom, defaut):
    try:
        with open(os.path.join(ETAT, nom + ".json"), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return defaut


def ecrire_etat(nom, valeur):
    os.makedirs(ETAT, exist_ok=True)
    tmp = os.path.join(ETAT, nom + ".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(valeur, f, ensure_ascii=False)
    os.replace(tmp, os.path.join(ETAT, nom + ".json"))


def alerte(job, detail):
    """Alerte Telegram d'échec. Ne doit jamais lever : c'est le dernier filet."""
    try:
        telegram(
            "🚨 Veille : %s en échec (%s)\n%s"
            % (job, maintenant().strftime("%d/%m %H:%M"), detail[-700:])
        )
    except Exception as e:
        print("alerte Telegram impossible : %s" % e, file=sys.stderr)


def principal(job, fonction):
    """Point d'entrée commun : toute exception → alerte Telegram + code de sortie 1 (échec Dkron)."""
    try:
        fonction()
    except SystemExit:
        raise
    except Exception:
        tb = traceback.format_exc()
        print(tb, file=sys.stderr, flush=True)
        alerte(job, tb.strip().splitlines()[-1])
        sys.exit(1)
