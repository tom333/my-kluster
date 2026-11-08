"""Sentinelle : signale les jobs Dkron qui n'ont pas réussi depuis trop longtemps.

Couvre ce qu'une alerte d'échec ne voit pas : un job qui ne tourne plus du tout (bloqué,
désactivé, planification cassée). C'est exactement la panne korben de novembre sous Kestra,
restée muette 5 jours. L'âge maximal attendu est porté par chaque job (metadata.age_max_h).
"""

from datetime import datetime, timezone

import commun

API = "http://localhost:8080/v1/jobs"


def main():
    retards = []
    now = datetime.now(timezone.utc)
    for j in commun.http(API):
        age_max = float((j.get("metadata") or {}).get("age_max_h", 0) or 0)
        if not age_max or j.get("disabled"):
            continue
        ok = j.get("last_success")
        if not ok:
            retards.append("%s : jamais réussi" % j["name"])
            continue
        age = (
            now - datetime.fromisoformat(ok.replace("Z", "+00:00"))
        ).total_seconds() / 3600
        if age > age_max:
            retards.append(
                "%s : dernier succès il y a %.0f h (max %g h)"
                % (j["name"], age, age_max)
            )
    print("  %d job(s) en retard" % len(retards), flush=True)
    if retards:
        commun.telegram("⏰ Veille : jobs en retard\n" + "\n".join(retards))


if __name__ == "__main__":
    commun.principal("sentinelle", main)
