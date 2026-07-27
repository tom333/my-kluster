"""Commit automatique de l'état exporté, avec garde-fous.

Le cron commit sur main et pousse : un commit local seul ne protégerait de
rien, puisque la perte du poste emporterait l'historique — or la protection
est l'objectif. D'où des garde-fous stricts plutôt qu'un `git commit -a`.
"""
import pathlib
import subprocess

BRANCHE_AUTORISEE = "main"
TRAILER = "Claude-Session: https://claude.ai/code/session_01Cpm1giipPFNB4PvxyMP8G7"


class GitGuardError(RuntimeError):
    pass


def _run(argv, cwd):
    r = subprocess.run(argv, cwd=cwd, capture_output=True)
    return r.returncode, r.stdout, r.stderr


def branche_courante(racine):
    tete = (pathlib.Path(racine) / ".git" / "HEAD").read_text(encoding="utf-8").strip()
    return tete.split("refs/heads/", 1)[1] if "refs/heads/" in tete else "(détachée)"


def verifier_etat(racine):
    """Lève GitGuardError si l'état du dépôt interdit un commit automatique."""
    g = pathlib.Path(racine) / ".git"
    if (g / "REBASE_HEAD").exists() or (g / "rebase-merge").exists() \
            or (g / "rebase-apply").exists():
        raise GitGuardError("rebase en cours — aucun commit automatique")
    if (g / "MERGE_HEAD").exists():
        raise GitGuardError("merge en cours — aucun commit automatique")
    if (g / "CHERRY_PICK_HEAD").exists():
        raise GitGuardError("cherry-pick en cours — aucun commit automatique")
    b = branche_courante(racine)
    if b != BRANCHE_AUTORISEE:
        raise GitGuardError(
            f"branche courante '{b}' != '{BRANCHE_AUTORISEE}' — export effectué, "
            f"commit refusé")


def message_commit(changements):
    return ("chore(hermes): capture état runtime\n\n"
            + "\n".join(f"- {c}" for c in changements)
            + f"\n\n{TRAILER}\n")


def commit_export(racine, chemins, changements, run=_run):
    """git add (restreint) + commit + push. Jamais de --force, jamais de add -A."""
    verifier_etat(racine)

    rc, _, err = run(["git", "add", "--"] + list(chemins), racine)
    if rc != 0:
        raise GitGuardError(f"git add a échoué: {err.decode(errors='replace')[:200]}")

    rc, _, err = run(["git", "commit", "-m", message_commit(changements), "--"]
                     + list(chemins), racine)
    if rc != 0:
        raise GitGuardError(f"git commit a échoué: {err.decode(errors='replace')[:200]}")

    rc, _, err = run(["git", "push", "origin", BRANCHE_AUTORISEE], racine)
    if rc != 0:
        raise GitGuardError(
            "git push a échoué (branche probablement divergée). Le commit local "
            "existe ; résous à la main. Aucun --force n'a été tenté. "
            + err.decode(errors="replace")[:200])
