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
