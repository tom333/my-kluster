"""Watchers Python du dépôt (porté du flux Kestra générique `watcher`).

Usage : python3 watcher.py NOM [NOM ...]
Chaque script est tiré du dépôt à l'exécution (git = source de vérité), tourne avec son fichier
d'état dans /data/etat/<cle>.json, et tout ce qu'il écrit sur stdout est une alerte Telegram.
stdout vide = silence. Un watcher en échec n'empêche pas les suivants.
"""

import os
import subprocess
import sys
import tempfile
import traceback

import commun

DEPOT = "https://raw.githubusercontent.com/tom333/my-kluster/main"
WATCHERS = {
    "bonsai": (
        "scripts/bonsai-watcher/bonsai_watch.py",
        "bonsai_watch_state",
        "BONSAI_WATCH_STATE",
    ),
    "moe-cache": (
        "scripts/moe-cache-watcher/moe_cache_watch.py",
        "moe_cache_watch_state",
        "MOE_WATCH_STATE",
    ),
}


def un_watcher(nom):
    script, cle, var = WATCHERS[nom]
    code = commun.http("%s/%s" % (DEPOT, script), timeout=30)
    os.makedirs(commun.ETAT, exist_ok=True)
    etat = os.path.join(commun.ETAT, cle + ".json")
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
    env = dict(os.environ)
    env[var] = etat
    res = subprocess.run(
        [sys.executable, f.name], env=env, capture_output=True, text=True, timeout=600
    )
    os.unlink(f.name)
    sys.stderr.write(res.stderr)
    if res.returncode != 0:
        raise RuntimeError("code %d : %s" % (res.returncode, res.stderr.strip()[-300:]))
    alerte = res.stdout.strip()
    if alerte:
        commun.telegram(alerte[:4000])
    return "alerte envoyée" if alerte else "rien de neuf"


def main():
    echecs = []
    for nom in sys.argv[1:]:
        try:
            print("  %s : %s" % (nom, un_watcher(nom)), flush=True)
        except Exception:
            echecs.append(
                "%s : %s" % (nom, traceback.format_exc().strip().splitlines()[-1][:300])
            )
    if echecs:
        commun.alerte("watcher", "\n".join(echecs))
        sys.exit(1)


if __name__ == "__main__":
    commun.principal("watcher " + " ".join(sys.argv[1:]), main)
