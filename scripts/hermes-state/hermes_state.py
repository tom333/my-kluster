# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""hermes-state — réconciliation Git <-> PVC de la configuration Hermes.

    hermes-state diff              observe, ne modifie rien. Code retour 1 si dérive.

Spec: docs/superpowers/specs/2026-07-27-hermes-state-design.md
"""
import argparse
import json
import pathlib
import sys

import yaml

import normalize
import podio

ICI = pathlib.Path(__file__).resolve().parent
RACINE_DEPOT = ICI.parents[1]
MANIFEST = ICI / "manifest.yaml"

IDENTIQUE, DIVERGE, ABSENT_POD, ABSENT_GIT = "=", "~", "+", "-"


class GuardError(RuntimeError):
    pass


def ligne_statut(nom, statut, detail=""):
    return f"{statut}  {nom}" + (f"  — {detail}" if detail else "")


def check_appliable(a):
    """Lève GuardError si l'artefact ne doit PAS être écrit dans le pod.

    Appelé AVANT tout accès au cluster : c'est la garantie qu'une commande mal
    tapée ne peut pas détruire un cron édité au dashboard.
    """
    if a["owner"] == "hermes":
        raise GuardError(
            f"{a['name']}: owner=hermes — le pod fait foi, apply est refusé. "
            f"Utilise `export` pour capturer vers Git.")
    if a["apply_forbidden"]:
        raise GuardError(
            f"{a['name']}: apply_forbidden — son seul chemin d'écriture est "
            f"ArgoCD puis le re-seed au boot (cf. spec §3.2).")


def apply_artifact(pod, a, donnees, oui=False):
    """Écrit un artefact dans le pod. Vérifie les garde-fous AVANT tout kubectl."""
    check_appliable(a)
    cibles = [a["pod"]] + list(a["also"])
    if not oui:
        for c in cibles:
            print(f"   [dry-run] écrirait {c} ({len(donnees)} octets)")
        return
    for c in cibles:
        pod.write(c, donnees)
        print(f"   écrit {c} (chown {podio.AGENT_UID})")


def chemin_git(a):
    return RACINE_DEPOT / a["git"]


def contenu_git(a):
    """Contenu côté Git, normalisé, ou None s'il est absent."""
    p = chemin_git(a)
    if a["mode"] == "yaml-subset":
        return normalize.extract_config_from_argocd(p) if p.exists() else None
    if not p.exists():
        return None
    if a["mode"] == "tree":
        return {f.relative_to(p).as_posix(): normalize.normalize_text(f.read_text("utf-8"))
                for f in sorted(p.rglob("*")) if f.is_file()}
    return normalize.normalize_text(p.read_text("utf-8"))


def contenu_pod(pod, a):
    """Contenu côté pod, normalisé, ou None s'il est absent."""
    if not pod.exists(a["pod"]):
        return None
    if a["mode"] == "tree":
        return {rel: normalize.normalize_text(pod.read(f"{a['pod']}/{rel}"))
                for rel in pod.list_tree(a["pod"])}
    if a["mode"] == "yaml-subset":
        return yaml.safe_load(pod.read(a["pod"]))
    if a["mode"] == "json-spec":
        brut = pod.read_json_retry(a["pod"], json.loads)
        return normalize.normalize_jobs(
            brut, warn=lambda m: print(f"   avertissement: {m}", file=sys.stderr))
    return normalize.normalize_text(pod.read(a["pod"]))


def comparer(a, cote_git, cote_pod):
    """Retourne (statut, detail)."""
    if cote_pod is None:
        return ABSENT_POD, "absent du pod"
    if cote_git is None:
        # La commande à suggérer dépend du propriétaire : `export` seul ne traite
        # que les artefacts owner=hermes, il faut --adopt pour amorcer un owner=git.
        quoi = "`export`" if a["owner"] == "hermes" else "`export --adopt`"
        return ABSENT_GIT, f"absent de Git — {quoi} pour le capturer"
    if a["mode"] == "yaml-subset":
        ecarts = normalize.yaml_subset_diff(cote_git, cote_pod)
        return (IDENTIQUE, "") if not ecarts else (DIVERGE, "; ".join(ecarts[:3]))
    if a["mode"] == "tree":
        manquants = sorted(set(cote_git) - set(cote_pod))
        surnumeraires = sorted(set(cote_pod) - set(cote_git))
        modifies = sorted(f for f in set(cote_git) & set(cote_pod)
                          if cote_git[f] != cote_pod[f])
        if not (manquants or surnumeraires or modifies):
            return IDENTIQUE, ""
        bouts = []
        if modifies:
            bouts.append("modifiés: " + ", ".join(modifies))
        if manquants:
            bouts.append("absents du pod: " + ", ".join(manquants))
        if surnumeraires:
            bouts.append("en trop dans le pod: " + ", ".join(surnumeraires))
        return DIVERGE, "; ".join(bouts)
    return (IDENTIQUE, "") if cote_git == cote_pod else (DIVERGE, "contenu différent")


def ecrire_si_different(chemin, contenu):
    """Écrit uniquement si le contenu change. Retourne True si écriture eut lieu.

    Sans cette condition, le cron d'export toucherait les fichiers chaque nuit
    et `git status` serait sale en permanence.
    """
    chemin = pathlib.Path(chemin)
    if chemin.exists() and chemin.read_text(encoding="utf-8") == contenu:
        return False
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(contenu, encoding="utf-8")
    return True


def a_exporter(arts, adopt):
    """owner=hermes toujours ; owner=git seulement en --adopt (amorçage)."""
    if adopt:
        return list(arts)
    return [a for a in arts if a["owner"] == "hermes"]


def cmd_diff(args):
    arts = normalize.load_manifest(MANIFEST)
    pod = podio.Pod()
    derive = False
    for a in arts:
        statut, detail = comparer(a, contenu_git(a), contenu_pod(pod, a))
        print(ligne_statut(a["name"], statut, detail))
        if statut != IDENTIQUE:
            derive = True
            if a["restart_required"]:
                print(f"   note: appliquer {a['name']} exige un redémarrage du pod")
    return 1 if derive else 0


def cmd_export(args):
    arts = normalize.load_manifest(MANIFEST)
    pod = podio.Pod()
    changes, echecs = [], []

    for a in a_exporter(arts, args.adopt):
        if a["mode"] == "yaml-subset":
            print(ligne_statut(a["name"], "·", "ignoré à l'export (source = manifeste ArgoCD)"))
            continue
        try:
            cote_pod = contenu_pod(pod, a)
        except podio.PodError as e:
            print(f"erreur: {a['name']}: {e}", file=sys.stderr)
            echecs.append(a["name"])
            continue
        if cote_pod is None:
            print(ligne_statut(a["name"], ABSENT_POD, "absent du pod, rien à capturer"))
            continue

        if a["mode"] == "tree":
            ecrits = [rel for rel, texte in cote_pod.items()
                      if ecrire_si_different(chemin_git(a) / rel, texte)]
            if ecrits:
                changes.append(f"{a['name']} ({', '.join(sorted(ecrits))})")
        elif ecrire_si_different(chemin_git(a), cote_pod):
            changes.append(a["name"])

    print("capturé: " + ", ".join(changes) if changes else "aucun changement à capturer")

    if args.commit and changes:
        import gitio
        chemins = [a["git"] for a in a_exporter(arts, args.adopt)]
        gitio.commit_export(RACINE_DEPOT, chemins, changes)

    return 2 if echecs else 0


def construire_parseur():
    p = argparse.ArgumentParser(prog="hermes-state", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sous = p.add_subparsers(dest="verbe", required=True)
    sous.add_parser("diff", help="compare Git et le pod, ne modifie rien")
    e = sous.add_parser("export", help="pod -> Git, artefacts owner=hermes")
    e.add_argument("--adopt", action="store_true",
                   help="capture aussi les artefacts owner=git absents de Git (amorçage)")
    e.add_argument("--commit", action="store_true",
                   help="git add/commit/push des chemins exportés (cf. spec §5)")
    return p


def main(argv=None):
    args = construire_parseur().parse_args(argv)
    try:
        return {"diff": cmd_diff, "export": cmd_export}[args.verbe](args)
    except (podio.PodError, GuardError, ValueError) as e:
        print(f"erreur: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
