import copy
import json
import pathlib

import pytest
import yaml

import normalize

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


def charger():
    return json.loads((FIXTURES / "jobs.json").read_text(encoding="utf-8"))


def test_champs_volatils_disparaissent():
    sortie = json.loads(normalize.normalize_jobs(charger()))
    assert "updated_at" not in sortie, "updated_at racine doit être écarté"
    for job in sortie["jobs"]:
        for champ in ("last_run_at", "next_run_at", "last_status", "last_error",
                      "last_delivery_error", "fire_claim", "paused_at",
                      "paused_reason", "state"):
            assert champ not in job, f"{champ} devrait être écarté"


def test_champs_de_definition_subsistent():
    sortie = json.loads(normalize.normalize_jobs(charger()))
    job = next(j for j in sortie["jobs"] if j["name"] == "llm-veille-daily")
    assert job["prompt"] == "Fais la veille LLM du jour et livre un digest."
    assert job["schedule"]["expr"] == "30 21 * * *"
    assert job["skill"] == "veille-digest"
    assert job["created_at"] == "2026-06-10T00:01:00+00:00"
    assert job["model"] == "deepseek/deepseek-v4-flash", "un modèle épinglé doit ressortir intact"


def test_tri_stable_par_id():
    sortie = json.loads(normalize.normalize_jobs(charger()))
    assert [j["id"] for j in sortie["jobs"]] == ["a1", "b2"]


def test_tri_deterministe_sans_id():
    """Sans clé secondaire, deux jobs partageant le même id (ici vide) hériteraient
    de l'ordre du fichier source via la stabilité de sort() — deux documents
    contenant les mêmes tâches en ordre source inversé doivent produire une
    sortie identique."""
    a = charger()
    for job in a["jobs"]:
        job["id"] = ""
    b = copy.deepcopy(a)
    b["jobs"] = list(reversed(b["jobs"]))
    assert normalize.normalize_jobs(a) == normalize.normalize_jobs(b)


def test_idempotence():
    une = normalize.normalize_jobs(charger())
    deux = normalize.normalize_jobs(json.loads(une))
    assert une == deux


def test_insensible_au_statut():
    """LE test critique : deux jobs.json ne différant que par le statut
    doivent produire une sortie IDENTIQUE. Sinon le cron d'export pollue
    main tous les jours."""
    a = charger()
    b = copy.deepcopy(a)
    b["updated_at"] = "2099-01-01T00:00:00+00:00"
    b["jobs"][0]["last_run_at"] = "2099-01-01T00:00:00+00:00"
    b["jobs"][0]["next_run_at"] = "2099-01-02T00:00:00+00:00"
    b["jobs"][0]["last_status"] = "error"
    b["jobs"][0]["last_error"] = "boom"
    b["jobs"][0]["fire_claim"] = "autre-machine"
    b["jobs"][0]["state"] = {"runs": 9999}
    assert normalize.normalize_jobs(a) == normalize.normalize_jobs(b)


def test_changement_de_prompt_est_visible():
    """Réciproque du test précédent : un vrai changement DOIT apparaître."""
    a = charger()
    b = copy.deepcopy(a)
    b["jobs"][0]["prompt"] = "Autre consigne."
    assert normalize.normalize_jobs(a) != normalize.normalize_jobs(b)


def test_champ_inconnu_conserve_et_signale():
    a = charger()
    a["jobs"][0]["nouveaute_hermes_2027"] = "valeur"
    avertissements = []
    sortie = json.loads(normalize.normalize_jobs(a, warn=avertissements.append))
    job = next(j for j in sortie["jobs"] if j["id"] == "b2")
    assert job["nouveaute_hermes_2027"] == "valeur", "un champ inconnu ne doit pas être perdu"
    assert any("nouveaute_hermes_2027" in m for m in avertissements)


def test_clef_racine_inconnue_conservee():
    a = charger()
    a["schema_version"] = 4
    sortie = json.loads(normalize.normalize_jobs(a))
    assert sortie["schema_version"] == 4


def test_termine_par_un_saut_de_ligne():
    assert normalize.normalize_jobs(charger()).endswith("\n")


def charger_yaml(nom):
    return yaml.safe_load((FIXTURES / nom).read_text(encoding="utf-8"))


def test_yaml_subset_ignore_les_cles_ajoutees_par_hermes():
    """plugins, _config_version, onboarding et la perte des commentaires ne
    doivent PAS être signalés : sinon l'outil crie en permanence."""
    ecarts = normalize.yaml_subset_diff(charger_yaml("config_git.yaml"),
                                       charger_yaml("config_pod.yaml"))
    assert ecarts == []


def test_yaml_subset_detecte_une_valeur_declaree_modifiee():
    pod = charger_yaml("config_pod.yaml")
    pod["agent"]["max_turns"] = 20
    ecarts = normalize.yaml_subset_diff(charger_yaml("config_git.yaml"), pod)
    assert len(ecarts) == 1
    assert "agent.max_turns" in ecarts[0]


def test_yaml_subset_detecte_une_cle_declaree_absente():
    pod = charger_yaml("config_pod.yaml")
    del pod["model"]["provider"]
    ecarts = normalize.yaml_subset_diff(charger_yaml("config_git.yaml"), pod)
    assert len(ecarts) == 1
    assert "model.provider" in ecarts[0]
    assert "absent" in ecarts[0]


def test_yaml_subset_compare_les_listes_en_entier():
    pod = charger_yaml("config_pod.yaml")
    pod["platform_toolsets"]["telegram"] = ["web"]
    ecarts = normalize.yaml_subset_diff(charger_yaml("config_git.yaml"), pod)
    assert len(ecarts) == 1
    assert "platform_toolsets.telegram" in ecarts[0]


def test_yaml_subset_signale_un_type_incompatible():
    ecarts = normalize.yaml_subset_diff({"agent": {"max_turns": 90}}, {"agent": "oui"})
    assert len(ecarts) == 1
    assert "agent" in ecarts[0]


def test_extract_config_from_argocd_cas_nominal():
    config = normalize.extract_config_from_argocd(FIXTURES / "argocd-app-minimal.yaml")
    assert config["model"]["default"] == "deepseek/deepseek-v4-flash"
    assert config["agent"]["max_turns"] == 90


def test_extract_config_from_argocd_signale_un_bloc_values_vide(tmp_path):
    """Cas piégeux : `helm.values` vide donne None, et yaml.safe_load(None) prend
    None pour un flux -> AttributeError AVANT toute indexation. Un except sur
    (KeyError, TypeError) seul laisserait donc filer une erreur illisible."""
    p = tmp_path / "app.yaml"
    p.write_text("spec:\n  source:\n    helm:\n      values:\n", encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        normalize.extract_config_from_argocd(p)
    assert str(p) in str(excinfo.value)
    assert "configMaps.bootstrap.data" in str(excinfo.value)


def test_extract_config_from_argocd_signale_une_cle_manquante(tmp_path):
    """Verrouille le message d'erreur : un chart ArgoCD qui change de forme doit
    produire un ValueError nommant le fichier et le chemin attendu, pas un
    KeyError brut illisible dans un log de cron nocturne."""
    manifeste_casse = tmp_path / "argocd-app-casse.yaml"
    manifeste_casse.write_text(
        "spec:\n"
        "  source:\n"
        "    helm:\n"
        "      values: |\n"
        "        autreChose: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as exc_info:
        normalize.extract_config_from_argocd(manifeste_casse)
    message = str(exc_info.value)
    assert str(manifeste_casse) in message
    assert "configMaps.bootstrap.data" in message


def test_compteur_imbrique_dans_repeat_est_ecarte():
    """repeat.completed s'incremente a CHAQUE execution. Observe en production :
    les 8 taches sont passees de N a N+1 apres un tour d'ordonnanceur. Sans son
    retrait, le cron nocturne committerait chaque nuit sans changement reel.
    repeat.times, lui, est bien de la definition et doit survivre."""
    a = charger()
    b = copy.deepcopy(a)
    b["jobs"][0]["repeat"]["completed"] += 1
    assert normalize.normalize_jobs(a) == normalize.normalize_jobs(b)

    sortie = json.loads(normalize.normalize_jobs(a))
    job = next(j for j in sortie["jobs"] if j["id"] == "b2")
    assert "completed" not in job["repeat"], "le compteur doit disparaitre"
    assert job["repeat"] == {"times": None}, "repeat.times doit survivre"


def test_repeat_null_ne_casse_pas():
    """repeat vaut null sur la plupart des taches reelles : le retrait imbrique
    ne doit pas planter dessus."""
    a = charger()
    a["jobs"][0]["repeat"] = None
    sortie = json.loads(normalize.normalize_jobs(a))
    job = next(j for j in sortie["jobs"] if j["id"] == "b2")
    assert job["repeat"] is None
