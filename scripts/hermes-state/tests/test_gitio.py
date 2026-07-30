import gitio
import pytest


def depot(tmp_path, branche="main", rebase=False, merge=False, cherry=False):
    (tmp_path / ".git").mkdir()
    if rebase:
        (tmp_path / ".git" / "REBASE_HEAD").write_text("x")
    if merge:
        (tmp_path / ".git" / "MERGE_HEAD").write_text("x")
    if cherry:
        (tmp_path / ".git" / "CHERRY_PICK_HEAD").write_text("x")
    (tmp_path / ".git" / "HEAD").write_text(f"ref: refs/heads/{branche}\n")
    return tmp_path


def test_refuse_si_rebase_en_cours(tmp_path):
    with pytest.raises(gitio.GitGuardError, match="rebase"):
        gitio.verifier_etat(depot(tmp_path, rebase=True))


def test_refuse_si_merge_en_cours(tmp_path):
    with pytest.raises(gitio.GitGuardError, match="merge"):
        gitio.verifier_etat(depot(tmp_path, merge=True))


def test_refuse_si_cherry_pick_en_cours(tmp_path):
    with pytest.raises(gitio.GitGuardError, match="cherry-pick"):
        gitio.verifier_etat(depot(tmp_path, cherry=True))


def test_refuse_si_branche_autre_que_main(tmp_path):
    with pytest.raises(gitio.GitGuardError, match="branche"):
        gitio.verifier_etat(depot(tmp_path, branche="une-feature"))


def test_refuse_si_tete_detachee(tmp_path):
    d = depot(tmp_path)
    (d / ".git" / "HEAD").write_text("a1b2c3d4\n")
    with pytest.raises(gitio.GitGuardError, match="branche"):
        gitio.verifier_etat(d)


def test_accepte_main_propre(tmp_path):
    gitio.verifier_etat(depot(tmp_path))  # ne lève pas


def test_message_de_commit_liste_les_changements():
    m = gitio.message_commit(["crons (llm-veille-daily)", "skill-veille-digest"])
    assert m.startswith("chore(hermes): capture état runtime")
    assert "llm-veille-daily" in m
    assert "skill-veille-digest" in m
    assert m.rstrip().endswith(gitio.TRAILER), "le trailer de session est obligatoire"


def test_add_restreint_aux_chemins_donnes(tmp_path):
    """Un working tree sale par ailleurs ne doit être ni committé ni perturbé :
    d'où `git add -- <chemins>` et jamais `git add -A`."""
    appels = []

    def run(argv, cwd):
        appels.append(argv)
        return 0, b"", b""

    gitio.commit_export(depot(tmp_path), ["a/b.json", "c/d.md"], ["crons"], run=run)
    add = next(a for a in appels if a[:2] == ["git", "add"])
    assert add[2:] == ["--", "a/b.json", "c/d.md"], "git add doit être restreint"
    commit = next(a for a in appels if a[:2] == ["git", "commit"])
    assert commit[-2:] == ["a/b.json", "c/d.md"], "git commit doit être restreint aussi"
    assert not any("-A" in a or "--all" in a for a in appels), "jamais de add -A"
    assert not any("--force" in a or "-f" in a for a in appels), "jamais de push --force"


def test_push_en_echec_n_est_pas_force(tmp_path):
    def run(argv, cwd):
        if argv[1] == "push":
            return 1, b"", b"rejected: non-fast-forward"
        return 0, b"", b""

    with pytest.raises(gitio.GitGuardError, match="push"):
        gitio.commit_export(depot(tmp_path), ["a"], ["crons"], run=run)


def test_commit_en_echec_remonte(tmp_path):
    def run(argv, cwd):
        if argv[1] == "commit":
            return 1, b"", b"nothing to commit"
        return 0, b"", b""

    with pytest.raises(gitio.GitGuardError, match="commit"):
        gitio.commit_export(depot(tmp_path), ["a"], ["crons"], run=run)


def test_aucun_git_si_l_etat_est_mauvais(tmp_path):
    """Le garde-fou doit trancher AVANT le premier appel git."""
    def run(argv, cwd):
        raise AssertionError(f"aucun git ne devait tourner, reçu: {argv}")

    with pytest.raises(gitio.GitGuardError):
        gitio.commit_export(depot(tmp_path, branche="autre"), ["a"], ["c"], run=run)


# --- rattrapage d'origin avant le push (ajouté le 2026-07-31) ----------------
#
# Motif : le cron d'export pousse depuis le même répertoire de travail que
# l'humain, et Renovate auto-merge. Dès que les deux se croisent, la branche
# diverge et le push échoue en non-fast-forward chaque nuit.


def _faux_run(retard=0, sale=(), echecs=()):
    """Simulateur de git. `appels` collecte les argv pour les assertions."""
    appels = []

    def run(argv, cwd):
        appels.append(argv)
        sous = argv[1]
        if sous in echecs:
            return 1, b"", b"boom " + sous.encode()
        if sous == "rev-list":
            return 0, str(retard).encode(), b""
        if sous == "status":
            return 0, "\n".join(sale).encode(), b""
        return 0, b"", b""

    run.appels = appels
    return run


def test_rebase_seulement_si_en_retard(tmp_path):
    run = _faux_run(retard=0)
    assert gitio.synchroniser_avant_push(depot(tmp_path), run=run) == 0
    assert not any(a[:2] == ["git", "pull"] for a in run.appels), \
        "a jour : aucun pull ne doit etre tente"


def test_rebase_si_en_retard_et_arbre_propre(tmp_path):
    run = _faux_run(retard=5)
    assert gitio.synchroniser_avant_push(depot(tmp_path), run=run) == 5
    pull = next(a for a in run.appels if a[:2] == ["git", "pull"])
    assert "--rebase" in pull
    assert "--autostash" not in pull, \
        "autostash deplacerait le travail en cours de l'humain sans le dire"


def test_refuse_le_rebase_si_arbre_sale(tmp_path):
    run = _faux_run(retard=5, sale=[" M charts/localai/values.yaml"])
    with pytest.raises(gitio.GitGuardError, match="SALE"):
        gitio.synchroniser_avant_push(depot(tmp_path), run=run)
    assert not any(a[:2] == ["git", "pull"] for a in run.appels), \
        "arbre sale : aucun pull ne doit etre tente"


def test_les_non_suivis_ne_rendent_pas_l_arbre_sale(tmp_path):
    """Ce depot a des dizaines de non-suivis en permanence : ils n'empechent
    pas un rebase, donc --untracked-files=no est obligatoire."""
    run = _faux_run(retard=3)
    gitio.synchroniser_avant_push(depot(tmp_path), run=run)
    statut = next(a for a in run.appels if a[:2] == ["git", "status"])
    assert "--untracked-files=no" in statut


def test_le_push_est_precede_du_rattrapage(tmp_path):
    run = _faux_run(retard=2)
    gitio.commit_export(depot(tmp_path), ["a"], ["crons"], run=run)
    verbes = [a[1] for a in run.appels]
    assert verbes.index("pull") < verbes.index("push"), \
        "le rebase doit precede le push, sinon il ne sert a rien"
    assert not any("--force" in a for a in run.appels)


def test_echec_du_fetch_remonte(tmp_path):
    run = _faux_run(echecs=("fetch",))
    with pytest.raises(gitio.GitGuardError, match="fetch"):
        gitio.synchroniser_avant_push(depot(tmp_path), run=run)
