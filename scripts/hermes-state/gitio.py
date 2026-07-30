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
    if (
        (g / "REBASE_HEAD").exists()
        or (g / "rebase-merge").exists()
        or (g / "rebase-apply").exists()
    ):
        raise GitGuardError("rebase en cours — aucun commit automatique")
    if (g / "MERGE_HEAD").exists():
        raise GitGuardError("merge en cours — aucun commit automatique")
    if (g / "CHERRY_PICK_HEAD").exists():
        raise GitGuardError("cherry-pick en cours — aucun commit automatique")
    b = branche_courante(racine)
    if b != BRANCHE_AUTORISEE:
        raise GitGuardError(
            f"branche courante '{b}' != '{BRANCHE_AUTORISEE}' — export effectué, "
            f"commit refusé"
        )


def _lignes_sales(racine, run):
    """Fichiers SUIVIS modifiés ou indexés. Les non-suivis ne comptent pas :
    ce dépôt en a des dizaines en permanence, et ils n'empêchent pas un rebase."""
    rc, out, err = run(["git", "status", "--porcelain", "--untracked-files=no"], racine)
    if rc != 0:
        raise GitGuardError(
            f"git status a échoué: {err.decode(errors='replace')[:200]}"
        )
    return [l for l in out.decode(errors="replace").splitlines() if l.strip()]


def synchroniser_avant_push(racine, run=_run):
    """Rebase sur origin/main SI la branche est en retard, et seulement si l'arbre
    est propre. Retourne le nombre de commits rattrapés.

    POURQUOI. Ce cron pousse depuis le MÊME répertoire de travail que l'humain, et
    Renovate fusionne des PR en auto-merge. Dès que les deux arrivent entre deux
    exports, la branche diverge et le `git push` échoue en non-fast-forward — sans
    que l'export lui-même ait quoi que ce soit à se reprocher. Constaté le
    2026-07-31 : échec à 03h25, `[devant 7, derrière 5]`, les 5 étant des montées
    de version Renovate sur des fichiers totalement disjoints.

    CE QU'ON NE FAIT PAS. Pas de `--autostash` : il déplacerait le travail en cours
    de l'humain sans le lui dire. Pas de `--force`. Si l'arbre est sale, on REFUSE
    et on laisse le commit local en place — mieux vaut un export qui prévient qu'un
    export qui touche à du travail non committé.
    """
    rc, _, err = run(["git", "fetch", "origin", BRANCHE_AUTORISEE], racine)
    if rc != 0:
        raise GitGuardError(f"git fetch a échoué: {err.decode(errors='replace')[:200]}")

    rc, out, err = run(
        ["git", "rev-list", "--count", f"HEAD..origin/{BRANCHE_AUTORISEE}"], racine
    )
    if rc != 0:
        raise GitGuardError(
            f"git rev-list a échoué: {err.decode(errors='replace')[:200]}"
        )
    retard = int(out.decode(errors="replace").strip() or 0)
    if retard == 0:
        return 0

    sales = _lignes_sales(racine, run)
    if sales:
        raise GitGuardError(
            f"branche en retard de {retard} commit(s) sur origin/{BRANCHE_AUTORISEE}, "
            f"mais l'arbre de travail est SALE ({len(sales)} fichier(s) suivi(s) "
            f"modifié(s), dont {sales[0].strip()[:60]}) — rebase refusé pour ne pas "
            f"toucher à du travail en cours. Le commit d'export est en place ; "
            f"réconcilie à la main puis pousse."
        )

    rc, _, err = run(["git", "pull", "--rebase", "origin", BRANCHE_AUTORISEE], racine)
    if rc != 0:
        raise GitGuardError(
            f"git pull --rebase a échoué (conflit ?): "
            f"{err.decode(errors='replace')[:200]}. Aucun --force n'a été tenté."
        )
    return retard


def message_commit(changements):
    return (
        "chore(hermes): capture état runtime\n\n"
        + "\n".join(f"- {c}" for c in changements)
        + f"\n\n{TRAILER}\n"
    )


def commit_export(racine, chemins, changements, run=_run):
    """git add (restreint) + commit + rebase si en retard + push.

    Jamais de --force, jamais de add -A, jamais de --autostash.
    """
    verifier_etat(racine)

    rc, _, err = run(["git", "add", "--"] + list(chemins), racine)
    if rc != 0:
        raise GitGuardError(f"git add a échoué: {err.decode(errors='replace')[:200]}")

    rc, _, err = run(
        ["git", "commit", "-m", message_commit(changements), "--"] + list(chemins),
        racine,
    )
    if rc != 0:
        raise GitGuardError(
            f"git commit a échoué: {err.decode(errors='replace')[:200]}"
        )

    # Rattraper origin AVANT de pousser : sinon un auto-merge Renovate arrivé entre
    # deux exports fait échouer le push, et l'échec se répète chaque nuit.
    rattrapes = synchroniser_avant_push(racine, run=run)
    if rattrapes:
        print(
            f"rebase sur origin/{BRANCHE_AUTORISEE} : {rattrapes} commit(s) rattrapé(s)"
        )

    rc, _, err = run(["git", "push", "origin", BRANCHE_AUTORISEE], racine)
    if rc != 0:
        raise GitGuardError(
            "git push a échoué (branche probablement divergée). Le commit local "
            "existe ; résous à la main. Aucun --force n'a été tenté. "
            + err.decode(errors="replace")[:200]
        )
