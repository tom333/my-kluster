"""Fonctions PURES : normalisation, comparaison, chargement du manifeste.

Contrainte structurelle : ce module ne fait AUCUN I/O réseau et n'importe NI
podio NI hermes_state. C'est ce qui permet de tester toute la logique sans
cluster. Seule exception tolérée : lire le manifeste depuis le disque.
"""
import json

import yaml

OWNERS = frozenset({"git", "hermes"})
MODES = frozenset({"text", "tree", "yaml-subset", "json-spec"})

# Champs de statut, réécrits en permanence par l'ordonnanceur. Les écarter est ce
# qui fait qu'un commit n'apparaît QUE si la définition d'un job a changé.
VOLATILE_JOB_FIELDS = frozenset({
    "last_run_at", "next_run_at", "last_status", "last_error",
    "last_delivery_error", "fire_claim", "paused_at", "paused_reason", "state",
})
# `updated_at` est à la RACINE de jobs.json, pas dans les jobs. Oublier celui-ci
# suffit à produire un commit quotidien vide de sens.
VOLATILE_ROOT_FIELDS = frozenset({"updated_at"})

DEFINITION_JOB_FIELDS = frozenset({
    "id", "name", "schedule", "schedule_display", "prompt", "model", "provider",
    "base_url", "skill", "skills", "script", "enabled", "deliver", "workdir",
    "context_from", "enabled_toolsets", "no_agent", "repeat", "profile",
    "origin", "created_at",
})
KNOWN_JOB_FIELDS = DEFINITION_JOB_FIELDS | VOLATILE_JOB_FIELDS


def load_manifest(path):
    """Charge et VALIDE le manifeste. Lève ValueError sur toute incohérence."""
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    arts = doc.get("artifacts") or []
    if not arts:
        raise ValueError(f"{path}: aucun artefact déclaré")

    vus_noms, vus_git = set(), set()
    for i, a in enumerate(arts):
        if not isinstance(a, dict):
            raise ValueError(f"artefact à l'index {i}: entrée invalide (attendu un mapping)")
        for champ in ("name", "pod", "git", "owner", "mode"):
            if not a.get(champ):
                raise ValueError(f"artefact {a.get('name', '?')}: champ '{champ}' manquant")
        if a["owner"] not in OWNERS:
            raise ValueError(f"{a['name']}: owner '{a['owner']}' inconnu (attendu: {sorted(OWNERS)})")
        if a["mode"] not in MODES:
            raise ValueError(f"{a['name']}: mode '{a['mode']}' inconnu (attendu: {sorted(MODES)})")
        if a["name"] in vus_noms:
            raise ValueError(f"nom d'artefact en doublon: {a['name']}")
        if a["git"] in vus_git:
            raise ValueError(f"chemin git en doublon: {a['git']} ({a['name']})")
        vus_noms.add(a["name"])
        vus_git.add(a["git"])
        a.setdefault("also", [])
        a.setdefault("apply_forbidden", False)
        a.setdefault("restart_required", False)
    return arts


def _dump(obj):
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def normalize_jobs(raw, warn=None):
    """jobs.json -> texte JSON stable ne contenant que la DÉFINITION.

    raw  : dict {"jobs": [...], "updated_at": ...} (forme réelle) ou liste de jobs.
    warn : callable(str), appelé pour chaque champ inconnu — qui est CONSERVÉ.
           Perdre silencieusement un champ d'une future version de Hermes serait
           pire que d'en capturer un de trop.

    L'ORDRE des listes internes d'un job (`skills`, `enabled_toolsets`...) est
    délibérément PRÉSERVÉ, jamais trié : la capture doit rester directement
    restaurable telle quelle. Trier ces listes ferait dévier le fichier
    versionné du contenu réel du pod, et une restauration réordonnerait les
    listes de l'agent — un vrai risque contre un risque hypothétique. Si
    Hermes se met un jour à réordonner ces listes sans raison fonctionnelle,
    ce sera un faux positif à traiter à ce moment-là, pas par anticipation.
    """
    jobs = raw.get("jobs", []) if isinstance(raw, dict) else list(raw)

    propres = []
    for job in jobs:
        inconnus = set(job) - KNOWN_JOB_FIELDS
        if inconnus and warn:
            etiquette = job.get("name") or job.get("id") or "?"
            warn(f"{etiquette}: champ(s) inconnu(s) conservé(s): {', '.join(sorted(inconnus))}")
        propres.append({k: v for k, v in job.items() if k not in VOLATILE_JOB_FIELDS})

    # Clé secondaire (name) : sans elle, deux jobs partageant le même id (vide
    # ou dupliqué) retomberaient sur la stabilité de sort() et hériteraient de
    # l'ordre du fichier source — exactement le commit fantôme que cette
    # fonction existe pour éliminer.
    propres.sort(key=lambda j: (str(j.get("id", "")), str(j.get("name", ""))))

    racine = {}
    if isinstance(raw, dict):
        racine = {k: v for k, v in raw.items()
                  if k != "jobs" and k not in VOLATILE_ROOT_FIELDS}
    racine["jobs"] = propres
    return _dump(racine)
