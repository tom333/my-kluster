"""Fonctions PURES : normalisation, comparaison, chargement du manifeste.

Contrainte structurelle : ce module ne fait AUCUN I/O réseau et n'importe NI
podio NI hermes_state. C'est ce qui permet de tester toute la logique sans
cluster. Seule exception tolérée : lire le manifeste depuis le disque.
"""
import json

import yaml

OWNERS = frozenset({"git", "hermes"})
MODES = frozenset({"text", "tree", "yaml-subset", "json-spec", "json"})


def load_manifest(path):
    """Charge et VALIDE le manifeste. Lève ValueError sur toute incohérence."""
    doc = yaml.safe_load(open(path, encoding="utf-8")) or {}
    arts = doc.get("artifacts") or []
    if not arts:
        raise ValueError(f"{path}: aucun artefact déclaré")

    vus_noms, vus_git = set(), set()
    for a in arts:
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
