"""Aligne les jobs Dkron sur jobs.json (git = source de vérité).

Upsert de chaque job déclaré (POST /v1/jobs crée ou met à jour), suppression des jobs absents
du fichier. Lancé au démarrage du pod (attend que l'API réponde) puis toutes les 10 min par le
job `sync-jobs` lui-même : un changement poussé dans git arrive par le ConfigMap, puis ici.
"""

import json
import os
import sys
import time

import commun

API = "http://localhost:8080/v1/jobs"


def main():
    attendre = "--attendre" in sys.argv
    for _ in range(60 if attendre else 1):
        try:
            existants = {j["name"]: j for j in commun.http(API, timeout=10)}
            break
        except Exception:
            if not attendre:
                raise
            time.sleep(5)
    else:
        raise RuntimeError("API Dkron injoignable")
    voulus = json.load(open(os.path.join(commun.CODE, "jobs.json"), encoding="utf-8"))
    for j in voulus:
        commun.http(API, j, timeout=30)
    for nom in set(existants) - {j["name"] for j in voulus}:
        commun.http("%s/%s" % (API, nom), method="DELETE", timeout=30)
        print("  supprimé : %s" % nom)
    print("  %d job(s) synchronisé(s)" % len(voulus), flush=True)


if __name__ == "__main__":
    commun.principal("sync-jobs", main)
