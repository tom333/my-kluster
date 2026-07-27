# hermes-state Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Outiller la réconciliation Git ↔ PVC de la configuration Hermes, avec une propriété déclarée artefact par artefact, pour que les 8 crons (~18 000 caractères de prompts) cessent de n'exister qu'en un seul exemplaire et que la dérive devienne visible.

**Architecture:** Trois modules aux responsabilités disjointes. `normalize.py` contient toute la logique sous forme de fonctions **pures** (aucun I/O) — c'est là que porte l'essentiel des tests. `podio.py` isole le transport `kubectl` derrière un exécuteur **injectable**, ce qui permet de tester les garde-fous sans jamais toucher le cluster. `hermes_state.py` est la CLI qui orchestre trois verbes (`diff`, `export`, `apply`) en lisant `manifest.yaml`, seule source de la propriété.

**Tech Stack:** Python 3.10 (hôte), `uv` 0.11 pour l'exécution et les dépendances éphémères, PyYAML 6, pytest via `uv run --with pytest` (aucune installation sur le poste), `kubectl` pour le transport.

**Spec:** `docs/superpowers/specs/2026-07-27-hermes-state-design.md`

---

## Contexte indispensable pour qui n'a jamais vu ce dépôt

- **Dépôt GitOps** : `/data/projets/perso/my-kluster`, branche `main`, compte Git **perso** (`tom333`) résolu automatiquement par `~/.gitconfig`. Ne pose aucun override d'identité.
- **Le pod cible** : namespace `hermes`, nom commençant par `hermes-agent`, conteneur `main`.
- **Piège central, à ne jamais oublier** : `kubectl exec` tourne en **root**, l'agent Hermes tourne en **uid 10000**. Tout fichier écrit sans `chown 10000:10000` est **invisible pour l'agent, sans aucune erreur**. C'est pour ça que `Pod.write()` chown puis relit.
- **Il n'existe aucun test Python dans ce dépôt aujourd'hui.** Ce plan en introduit les premiers. La commande de test est toujours :
  ```bash
  cd /data/projets/perso/my-kluster/scripts/hermes-state
  uv run --quiet --with pytest --with pyyaml pytest tests/ -v
  ```
  `uv` télécharge pytest dans un environnement éphémère : rien n'est installé sur le poste.
- **pre-commit** est actif avec `gitleaks` et `forbid-plain-k8s-secrets`. Les fixtures de test contiennent le `chat_id` Telegram `843341688` — ce n'est pas un secret (il figure déjà en clair dans 8 scripts committés) et ne déclenche pas gitleaks. En revanche **ne mets jamais de token dans une fixture**.

---

## Structure des fichiers

| Fichier | Responsabilité |
|---|---|
| `scripts/hermes-state/manifest.yaml` | **Données.** Déclare chaque artefact : chemin pod, chemin Git, propriétaire, mode de comparaison. Seule source de la propriété. |
| `scripts/hermes-state/normalize.py` | **Fonctions pures.** Normalisation JSON/texte, comparaison YAML par sous-ensemble. Aucun I/O, aucun import de `podio`. |
| `scripts/hermes-state/podio.py` | **Transport.** Résolution du pod, lecture, écriture atomique + chown + vérification, listage d'arbre. Exécuteur injectable. |
| `scripts/hermes-state/hermes_state.py` | **CLI.** `diff`, `export`, `apply`. Charge le manifeste, applique les garde-fous, orchestre. Point d'entrée `uv` PEP723. |
| `scripts/hermes-state/gitio.py` | **Commit automatique.** Garde-fous Git (rebase en cours, branche, add restreint, jamais de force). Isolé pour être testable seul. |
| `scripts/hermes-state/README.md` | Mode d'emploi + avertissement uid 10000. |
| `scripts/hermes-state/tests/` | `test_normalize.py`, `test_manifest.py`, `test_guards.py`, `test_gitio.py`, `fixtures/`. |

`normalize.py` ne doit **jamais** importer `podio.py` ni `hermes_state.py`. Cette direction unique de dépendance est ce qui rend le cœur testable sans cluster.

---

## Task 1: Squelette et manifeste

**Files:**
- Create: `scripts/hermes-state/manifest.yaml`
- Create: `scripts/hermes-state/normalize.py`
- Create: `scripts/hermes-state/tests/test_manifest.py`

- [ ] **Step 1: Créer le manifeste**

Crée `scripts/hermes-state/manifest.yaml` :

```yaml
# Qui possède quoi. Source UNIQUE de la propriété des artefacts Hermes.
#   owner: git     -> Git fait foi, `apply` écrase le pod
#   owner: hermes  -> le pod fait foi, `export` capture vers Git, `apply` n'y touche JAMAIS
# mode: text | tree | yaml-subset | json-spec | json
# Chemins `git` relatifs à la racine du dépôt.
artifacts:
  - name: soul
    pod: /opt/data/SOUL.md
    git: hermes-runtime/SOUL.md
    owner: git
    mode: text

  - name: hermes-md
    pod: /workspace/HERMES.md
    git: hermes-runtime/HERMES.md
    owner: git
    mode: text
    also:
      - /workspace/AGENTS.md

  - name: skill-eval-modeles
    pod: /opt/data/skills/eval-modeles/SKILL.md
    git: hermes-runtime/skills/eval-modeles.SKILL.md
    owner: git
    mode: text

  - name: skill-decouvertes
    pod: /opt/data/skills/decouvertes/SKILL.md
    git: hermes-runtime/skills/decouvertes.SKILL.md
    owner: git
    mode: text

  - name: skill-web-fetch
    pod: /opt/data/skills/web-fetch/SKILL.md
    git: hermes-runtime/skills/web-fetch.SKILL.md
    owner: git
    mode: text

  - name: skill-veille-digest
    pod: /opt/data/skills/veille-digest
    git: hermes-runtime/skills/veille-digest
    owner: git
    mode: tree

  - name: script-index-digests
    pod: /opt/data/scripts/index_digests.py
    git: scripts/veille-digest-indexer/index_digests.py
    owner: git
    mode: text

  - name: script-index-telegram
    pod: /opt/data/scripts/index_telegram.py
    git: scripts/telegram-indexer/index_telegram.py
    owner: git
    mode: text

  - name: script-bonsai-watch
    pod: /opt/data/scripts/bonsai_watch.py
    git: scripts/bonsai-watcher/bonsai_watch.py
    owner: git
    mode: text

  # Cas spécial : la source Git est le bloc YAML inline du manifeste ArgoCD,
  # chemin configMaps.bootstrap.data["config.yaml"] dans spec.source.helm.values.
  # `apply` est REFUSÉ sur cet artefact : son seul chemin d'écriture légitime est
  # ArgoCD puis le re-seed par l'initContainer au boot.
  - name: config
    pod: /opt/data/config.yaml
    git: argocd/argocd-apps/hermes-agent-app.yaml
    owner: git
    mode: yaml-subset
    apply_forbidden: true
    restart_required: true

  - name: crons
    pod: /opt/data/cron/jobs.json
    git: hermes-runtime/state/jobs.json
    owner: hermes
    mode: json-spec
```

- [ ] **Step 2: Écrire le test qui échoue**

Crée `scripts/hermes-state/tests/test_manifest.py` :

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest
import normalize


MANIFEST = pathlib.Path(__file__).resolve().parents[1] / "manifest.yaml"


def test_load_manifest_reel():
    arts = normalize.load_manifest(MANIFEST)
    noms = [a["name"] for a in arts]
    assert "crons" in noms
    assert "soul" in noms
    assert len(noms) == len(set(noms)), "noms d'artefacts en doublon"


def test_crons_appartient_a_hermes():
    arts = {a["name"]: a for a in normalize.load_manifest(MANIFEST)}
    assert arts["crons"]["owner"] == "hermes"
    assert arts["config"]["apply_forbidden"] is True


def test_owner_inconnu_rejete(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text("artifacts:\n  - name: x\n    pod: /a\n    git: b\n    owner: personne\n    mode: text\n")
    with pytest.raises(ValueError, match="owner"):
        normalize.load_manifest(p)


def test_mode_inconnu_rejete(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text("artifacts:\n  - name: x\n    pod: /a\n    git: b\n    owner: git\n    mode: braille\n")
    with pytest.raises(ValueError, match="mode"):
        normalize.load_manifest(p)


def test_chemin_git_en_doublon_rejete(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text(
        "artifacts:\n"
        "  - name: a\n    pod: /a\n    git: meme/chemin\n    owner: git\n    mode: text\n"
        "  - name: b\n    pod: /b\n    git: meme/chemin\n    owner: git\n    mode: text\n"
    )
    with pytest.raises(ValueError, match="doublon"):
        normalize.load_manifest(p)
```

- [ ] **Step 3: Lancer le test pour vérifier qu'il échoue**

```bash
cd /data/projets/perso/my-kluster/scripts/hermes-state
uv run --quiet --with pytest --with pyyaml pytest tests/test_manifest.py -v
```

Attendu : `ModuleNotFoundError: No module named 'normalize'` (collection error).

- [ ] **Step 4: Écrire `load_manifest`**

Crée `scripts/hermes-state/normalize.py` :

```python
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
```

- [ ] **Step 5: Lancer les tests**

```bash
uv run --quiet --with pytest --with pyyaml pytest tests/test_manifest.py -v
```

Attendu : `5 passed`.

- [ ] **Step 6: Commit**

```bash
cd /data/projets/perso/my-kluster
git add scripts/hermes-state/manifest.yaml scripts/hermes-state/normalize.py scripts/hermes-state/tests/test_manifest.py
git commit -m "feat(hermes-state): manifeste de propriété des artefacts + validation"
```

---

## Task 2: Normalisation de `jobs.json` — le test qui compte

C'est la tâche la plus importante du plan. Si la normalisation laisse passer un champ volatil, le cron d'export committera sur `main` tous les jours pour rien et l'outil deviendra nuisible.

**Files:**
- Modify: `scripts/hermes-state/normalize.py`
- Create: `scripts/hermes-state/tests/fixtures/jobs.json`
- Create: `scripts/hermes-state/tests/test_normalize.py`

- [ ] **Step 1: Créer la fixture**

Crée `scripts/hermes-state/tests/fixtures/jobs.json`. Deux jobs suffisent : un job d'agent et un job `no_agent`, avec les 9 champs volatils présents.

```json
{
  "jobs": [
    {
      "id": "b2",
      "name": "llm-veille-daily",
      "schedule": {"kind": "cron", "expr": "30 21 * * *", "display": "30 21 * * *"},
      "schedule_display": "30 21 * * *",
      "prompt": "Fais la veille LLM du jour et livre un digest.",
      "model": null,
      "provider": null,
      "base_url": null,
      "skill": "veille-digest",
      "skills": ["veille-digest"],
      "script": null,
      "enabled": true,
      "deliver": "origin",
      "workdir": "/workspace",
      "context_from": "self",
      "enabled_toolsets": ["web", "file"],
      "no_agent": false,
      "repeat": null,
      "profile": null,
      "origin": "telegram:843341688",
      "created_at": "2026-06-10T00:01:00+00:00",
      "last_run_at": "2026-07-26T21:34:00+00:00",
      "next_run_at": "2026-07-27T21:30:00+00:00",
      "last_status": "ok",
      "last_error": null,
      "last_delivery_error": null,
      "fire_claim": "pc-1",
      "paused_at": null,
      "paused_reason": null,
      "state": {"runs": 47}
    },
    {
      "id": "a1",
      "name": "digest-indexer",
      "schedule": {"kind": "cron", "expr": "15 * * * *", "display": "15 * * * *"},
      "schedule_display": "15 * * * *",
      "prompt": "",
      "model": null,
      "provider": null,
      "base_url": null,
      "skill": null,
      "skills": [],
      "script": "index_digests.py",
      "enabled": true,
      "deliver": "local",
      "workdir": null,
      "context_from": null,
      "enabled_toolsets": [],
      "no_agent": true,
      "repeat": null,
      "profile": null,
      "origin": null,
      "created_at": "2026-07-20T12:23:00+00:00",
      "last_run_at": "2026-07-27T03:15:23+00:00",
      "next_run_at": "2026-07-27T04:15:00+00:00",
      "last_status": "ok",
      "last_error": null,
      "last_delivery_error": null,
      "fire_claim": null,
      "paused_at": null,
      "paused_reason": null,
      "state": {}
    }
  ],
  "updated_at": "2026-07-27T03:15:23+00:00"
}
```

- [ ] **Step 2: Écrire les tests qui échouent**

Crée `scripts/hermes-state/tests/test_normalize.py` :

```python
import copy
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

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


def test_tri_stable_par_id():
    sortie = json.loads(normalize.normalize_jobs(charger()))
    assert [j["id"] for j in sortie["jobs"]] == ["a1", "b2"]


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
```

- [ ] **Step 3: Lancer les tests pour vérifier qu'ils échouent**

```bash
uv run --quiet --with pytest --with pyyaml pytest tests/test_normalize.py -v
```

Attendu : 10 échecs, `AttributeError: module 'normalize' has no attribute 'normalize_jobs'`.

- [ ] **Step 4: Implémenter la normalisation**

Ajoute à `scripts/hermes-state/normalize.py`, après les constantes `OWNERS`/`MODES` :

```python
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


def _dump(obj):
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def normalize_jobs(raw, warn=None):
    """jobs.json -> texte JSON stable ne contenant que la DÉFINITION.

    raw  : dict {"jobs": [...], "updated_at": ...} (forme réelle) ou liste de jobs.
    warn : callable(str), appelé pour chaque champ inconnu — qui est CONSERVÉ.
           Perdre silencieusement un champ d'une future version de Hermes serait
           pire que d'en capturer un de trop.
    """
    jobs = raw.get("jobs", []) if isinstance(raw, dict) else list(raw)

    propres = []
    for job in jobs:
        inconnus = set(job) - KNOWN_JOB_FIELDS
        if inconnus and warn:
            etiquette = job.get("name") or job.get("id") or "?"
            warn(f"{etiquette}: champ(s) inconnu(s) conservé(s): {', '.join(sorted(inconnus))}")
        propres.append({k: v for k, v in job.items() if k not in VOLATILE_JOB_FIELDS})

    propres.sort(key=lambda j: str(j.get("id", "")))

    racine = {}
    if isinstance(raw, dict):
        racine = {k: v for k, v in raw.items()
                  if k != "jobs" and k not in VOLATILE_ROOT_FIELDS}
    racine["jobs"] = propres
    return _dump(racine)


def normalize_json(raw):
    """Pour les états simples (seen-*.json) : tri des clés, indentation stable."""
    return _dump(raw)


def normalize_text(contenu):
    """Neutralise les fins de ligne pour que la comparaison texte soit fiable."""
    if isinstance(contenu, bytes):
        contenu = contenu.decode("utf-8")
    return contenu.replace("\r\n", "\n").replace("\r", "\n")
```

- [ ] **Step 5: Lancer les tests**

```bash
uv run --quiet --with pytest --with pyyaml pytest tests/test_normalize.py -v
```

Attendu : `10 passed`.

- [ ] **Step 6: Commit**

```bash
cd /data/projets/perso/my-kluster
git add scripts/hermes-state/normalize.py scripts/hermes-state/tests/
git commit -m "feat(hermes-state): normalisation jobs.json insensible au statut

Écarte les 9 champs volatils par job + updated_at racine. Sans ça le cron
d'export committerait sur main chaque jour sans changement réel."
```

---

## Task 3: Comparaison YAML par sous-ensemble

Hermes réécrit `config.yaml` en ajoutant `_config_version`, `plugins`, `onboarding` et en supprimant les commentaires. Une comparaison stricte signalerait une dérive permanente. On ne compare que les clés déclarées par Git.

**Files:**
- Modify: `scripts/hermes-state/normalize.py`
- Create: `scripts/hermes-state/tests/fixtures/config_git.yaml`
- Create: `scripts/hermes-state/tests/fixtures/config_pod.yaml`
- Modify: `scripts/hermes-state/tests/test_normalize.py`

- [ ] **Step 1: Créer les deux fixtures**

`scripts/hermes-state/tests/fixtures/config_git.yaml` — ce que Git déclare, avec commentaires :

```yaml
# Commentaire que Hermes supprimera à la réécriture.
model:
  default: deepseek/deepseek-v4-flash
  provider: openrouter
  context_length: 131072
agent:
  max_turns: 90
  tool_use_enforcement: auto
platform_toolsets:
  telegram: [web, browser, file, todo, cronjob, skills, terminal, code_execution]
```

`scripts/hermes-state/tests/fixtures/config_pod.yaml` — ce que Hermes a réécrit : mêmes valeurs, sans commentaires, avec ses clés à lui :

```yaml
model:
  default: deepseek/deepseek-v4-flash
  provider: openrouter
  context_length: 131072
agent:
  max_turns: 90
  tool_use_enforcement: auto
platform_toolsets:
  telegram: [web, browser, file, todo, cronjob, skills, terminal, code_execution]
plugins: {}
_config_version: 33
onboarding:
  completed: true
```

- [ ] **Step 2: Écrire les tests qui échouent**

Ajoute à `scripts/hermes-state/tests/test_normalize.py` :

```python
import yaml


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
```

- [ ] **Step 3: Lancer les tests pour vérifier qu'ils échouent**

```bash
uv run --quiet --with pytest --with pyyaml pytest tests/test_normalize.py -k yaml_subset -v
```

Attendu : 5 échecs, `AttributeError: module 'normalize' has no attribute 'yaml_subset_diff'`.

- [ ] **Step 4: Implémenter la comparaison**

Ajoute à `scripts/hermes-state/normalize.py` :

```python
def yaml_subset_diff(declare, reel, chemin=""):
    """Liste les endroits où `reel` ne respecte PAS `declare`.

    Asymétrique par conception : une clé présente dans `reel` mais absente de
    `declare` est IGNORÉE. Hermes ajoute _config_version/plugins/onboarding à
    chaque réécriture ; les signaler rendrait la sortie illisible et donc
    inutile. La question à laquelle ce mode répond est « mes valeurs déclarées
    sont-elles respectées ? », pas « les fichiers sont-ils identiques ? ».
    """
    ecarts = []
    ici = chemin or "<racine>"

    if isinstance(declare, dict):
        if not isinstance(reel, dict):
            return [f"{ici}: attendu un objet, trouvé {type(reel).__name__}"]
        for cle, attendu in declare.items():
            sous = f"{chemin}.{cle}" if chemin else cle
            if cle not in reel:
                ecarts.append(f"{sous}: absent du pod")
            else:
                ecarts.extend(yaml_subset_diff(attendu, reel[cle], sous))
    elif declare != reel:
        ecarts.append(f"{ici}: Git={declare!r} pod={reel!r}")

    return ecarts


def extract_config_from_argocd(chemin_manifeste):
    """Extrait le bloc config.yaml du manifeste ArgoCD (triple imbrication).

    spec.source.helm.values est une CHAÎNE de YAML, qui contient elle-même
    configMaps.bootstrap.data["config.yaml"], encore une chaîne de YAML.
    """
    app = yaml.safe_load(open(chemin_manifeste, encoding="utf-8"))
    values = yaml.safe_load(app["spec"]["source"]["helm"]["values"])
    brut = values["configMaps"]["bootstrap"]["data"]["config.yaml"]
    return yaml.safe_load(brut)
```

- [ ] **Step 5: Lancer les tests**

```bash
uv run --quiet --with pytest --with pyyaml pytest tests/ -v
```

Attendu : `20 passed`.

- [ ] **Step 6: Vérifier l'extraction sur le vrai manifeste**

```bash
cd /data/projets/perso/my-kluster/scripts/hermes-state
uv run --quiet --with pyyaml python -c "
import normalize
c = normalize.extract_config_from_argocd('../../argocd/argocd-apps/hermes-agent-app.yaml')
print('clés racine:', sorted(c))
print('modèle:', c['model']['default'])
"
```

Attendu : les clés racine incluent `model`, `providers`, `mcp_servers`, `agent`, `terminal`, `web`, `compression`, `platform_toolsets`, `security`, et le modèle est `deepseek/deepseek-v4-flash`.

- [ ] **Step 7: Commit**

```bash
cd /data/projets/perso/my-kluster
git add scripts/hermes-state/normalize.py scripts/hermes-state/tests/
git commit -m "feat(hermes-state): comparaison YAML par sous-ensemble pour config.yaml"
```

---

## Task 4: Transport `kubectl` avec exécuteur injectable

**Files:**
- Create: `scripts/hermes-state/podio.py`
- Create: `scripts/hermes-state/tests/test_podio.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Crée `scripts/hermes-state/tests/test_podio.py` :

```python
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest
import podio


class FauxExecuteur:
    """Enregistre les appels et rejoue des réponses. Permet de tester tout le
    transport sans cluster."""

    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.appels = []

    def __call__(self, argv, stdin=None):
        self.appels.append((argv, stdin))
        if not self.reponses:
            raise AssertionError(f"appel inattendu: {argv}")
        return self.reponses.pop(0)


def test_resolution_du_pod():
    faux = FauxExecuteur([(0, b"hermes-agent-6d7f7b4c45-5hw4t   Running\n", b"")])
    pod = podio.Pod(executor=faux)
    assert pod.name() == "hermes-agent-6d7f7b4c45-5hw4t"


def test_pod_mis_en_cache():
    faux = FauxExecuteur([(0, b"hermes-agent-abc   Running\n", b"")])
    pod = podio.Pod(executor=faux)
    pod.name()
    pod.name()
    assert len(faux.appels) == 1, "le nom du pod doit être résolu une seule fois"


def test_pod_non_running_rejete():
    faux = FauxExecuteur([(0, b"hermes-agent-abc   Pending\n", b"")])
    pod = podio.Pod(executor=faux)
    with pytest.raises(podio.PodError, match="Pending"):
        pod.name()


def test_pod_absent_rejete():
    faux = FauxExecuteur([(0, b"autre-chose   Running\n", b"")])
    pod = podio.Pod(executor=faux)
    with pytest.raises(podio.PodError, match="aucun pod"):
        pod.name()


def test_lecture():
    faux = FauxExecuteur([
        (0, b"hermes-agent-abc   Running\n", b""),
        (0, b"contenu du fichier", b""),
    ])
    pod = podio.Pod(executor=faux)
    assert pod.read("/opt/data/SOUL.md") == b"contenu du fichier"


def test_lecture_en_echec_leve():
    faux = FauxExecuteur([
        (0, b"hermes-agent-abc   Running\n", b""),
        (1, b"", b"cat: /x: No such file or directory"),
    ])
    pod = podio.Pod(executor=faux)
    with pytest.raises(podio.PodError, match="No such file"):
        pod.read("/x")


def test_ecriture_chown_et_verifie():
    faux = FauxExecuteur([
        (0, b"hermes-agent-abc   Running\n", b""),   # name()
        (0, b"", b""),                                # cat > tmp
        (0, b"", b""),                                # mv + chown
        (0, b"nouveau", b""),                         # relecture
    ])
    pod = podio.Pod(executor=faux)
    pod.write("/opt/data/SOUL.md", b"nouveau")
    scripts = [a[0][-1] for a in faux.appels[1:]]
    assert any("chown 10000:10000" in s for s in scripts), "le chown est obligatoire"
    assert any("mv -f" in s for s in scripts), "l'écriture doit être atomique"


def test_ecriture_leve_si_chown_echoue():
    faux = FauxExecuteur([
        (0, b"hermes-agent-abc   Running\n", b""),
        (0, b"", b""),
        (1, b"", b"chown: Operation not permitted"),
    ])
    pod = podio.Pod(executor=faux)
    with pytest.raises(podio.PodError, match="chown"):
        pod.write("/opt/data/SOUL.md", b"x")


def test_ecriture_leve_si_relecture_differente():
    faux = FauxExecuteur([
        (0, b"hermes-agent-abc   Running\n", b""),
        (0, b"", b""),
        (0, b"", b""),
        (0, b"autre chose", b""),
    ])
    pod = podio.Pod(executor=faux)
    with pytest.raises(podio.PodError, match="relecture"):
        pod.write("/opt/data/SOUL.md", b"attendu")


def test_listage_arbre():
    faux = FauxExecuteur([
        (0, b"hermes-agent-abc   Running\n", b""),
        (0, b"SKILL.md\nreferences/github-releases-api.md\n", b""),
    ])
    pod = podio.Pod(executor=faux)
    assert pod.list_tree("/opt/data/skills/veille-digest") == [
        "SKILL.md", "references/github-releases-api.md"]
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

```bash
uv run --quiet --with pytest --with pyyaml pytest tests/test_podio.py -v
```

Attendu : `ModuleNotFoundError: No module named 'podio'`.

- [ ] **Step 3: Implémenter le transport**

Crée `scripts/hermes-state/podio.py` :

```python
"""Transport kubectl vers le pod Hermes.

L'exécuteur est injectable : c'est ce qui permet de tester les garde-fous et
le protocole d'écriture sans jamais toucher au cluster.

PIÈGE CENTRAL : `kubectl exec` tourne en root, l'agent Hermes tourne en uid
10000. Un fichier écrit sans chown est invisible pour l'agent, SANS AUCUNE
ERREUR. D'où le chown systématique puis la relecture de vérification.
"""
import subprocess
import time

NS = "hermes"
CONTAINER = "main"
AGENT_UID = "10000:10000"
POD_PREFIX = "hermes-agent"


class PodError(RuntimeError):
    pass


def default_executor(argv, stdin=None):
    r = subprocess.run(argv, input=stdin, capture_output=True)
    return r.returncode, r.stdout, r.stderr


def _msg(flux):
    return flux.decode("utf-8", errors="replace").strip()[:200]


class Pod:
    def __init__(self, executor=default_executor, ns=NS, container=CONTAINER):
        self.exec = executor
        self.ns = ns
        self.container = container
        self._name = None

    def name(self):
        if self._name:
            return self._name
        rc, out, err = self.exec([
            "kubectl", "get", "pods", "-n", self.ns, "--no-headers",
            "-o", "custom-columns=:metadata.name,:status.phase",
        ])
        if rc != 0:
            raise PodError(f"kubectl get pods a échoué: {_msg(err)}")
        for ligne in out.decode("utf-8", errors="replace").splitlines():
            morceaux = ligne.split()
            if len(morceaux) >= 2 and morceaux[0].startswith(POD_PREFIX):
                if morceaux[1] != "Running":
                    raise PodError(f"pod {morceaux[0]} en phase {morceaux[1]}, pas Running")
                self._name = morceaux[0]
                return self._name
        raise PodError(f"aucun pod {POD_PREFIX}* trouvé dans le namespace {self.ns}")

    def sh(self, script, stdin=None):
        return self.exec([
            "kubectl", "exec", "-i", "-n", self.ns, self.name(),
            "-c", self.container, "--", "sh", "-c", script,
        ], stdin=stdin)

    def read(self, chemin):
        rc, out, err = self.sh(f'cat "{chemin}"')
        if rc != 0:
            raise PodError(f"lecture de {chemin}: {_msg(err)}")
        return out

    def read_json_retry(self, chemin, parse, attente=5.0, dormir=time.sleep):
        """Lecture d'un JSON susceptible d'être réécrit pendant la lecture.

        jobs.json est protégé par .jobs.lock côté Hermes mais rien ne garantit
        l'atomicité vue de l'extérieur. Une capture tronquée committée serait
        pire qu'une capture manquée : on retente une fois, puis on abandonne.
        """
        for tentative in (0, 1):
            brut = self.read(chemin)
            try:
                return parse(brut)
            except ValueError:
                if tentative == 0:
                    dormir(attente)
                    continue
                raise PodError(f"{chemin}: JSON invalide après 2 tentatives "
                               f"(probable lecture pendant une écriture)")

    def exists(self, chemin):
        rc, _, _ = self.sh(f'test -e "{chemin}"')
        return rc == 0

    def list_tree(self, racine):
        rc, out, _ = self.sh(
            f'cd "{racine}" 2>/dev/null && find . -type f | sed "s|^\\./||" | sort')
        if rc != 0:
            return []
        return out.decode("utf-8", errors="replace").split()

    def write(self, chemin, donnees):
        """Écriture atomique, puis chown, puis relecture de vérification."""
        tmp = f"{chemin}.hermes-state.tmp"
        rc, _, err = self.sh(f'mkdir -p "$(dirname "{chemin}")" && cat > "{tmp}"',
                             stdin=donnees)
        if rc != 0:
            raise PodError(f"écriture de {tmp}: {_msg(err)}")
        rc, _, err = self.sh(f'mv -f "{tmp}" "{chemin}" && chown {AGENT_UID} "{chemin}"')
        if rc != 0:
            raise PodError(f"mv/chown de {chemin}: {_msg(err)}")
        if self.read(chemin) != donnees:
            raise PodError(f"relecture de {chemin} ne correspond pas à la source")
```

- [ ] **Step 4: Lancer les tests**

```bash
uv run --quiet --with pytest --with pyyaml pytest tests/ -v
```

Attendu : `30 passed`.

- [ ] **Step 5: Commit**

```bash
cd /data/projets/perso/my-kluster
git add scripts/hermes-state/podio.py scripts/hermes-state/tests/test_podio.py
git commit -m "feat(hermes-state): transport kubectl (écriture atomique + chown 10000 + vérif)"
```

---

## Task 5: Le verbe `diff`

**Files:**
- Create: `scripts/hermes-state/hermes_state.py`
- Create: `scripts/hermes-state/tests/test_guards.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Crée `scripts/hermes-state/tests/test_guards.py` :

```python
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import hermes_state
import pytest


class ExecuteurInterdit:
    """Échoue si on l'appelle. Prouve qu'aucun kubectl n'a lieu."""

    def __call__(self, argv, stdin=None):
        raise AssertionError(f"aucun appel kubectl ne devait avoir lieu, reçu: {argv}")


def art(**kw):
    base = {"name": "x", "pod": "/opt/data/x", "git": "g/x", "owner": "git",
            "mode": "text", "also": [], "apply_forbidden": False,
            "restart_required": False}
    base.update(kw)
    return base


def test_apply_refuse_owner_hermes():
    with pytest.raises(hermes_state.GuardError, match="owner=hermes"):
        hermes_state.check_appliable(art(name="crons", owner="hermes", mode="json-spec"))


def test_apply_refuse_config():
    with pytest.raises(hermes_state.GuardError, match="apply_forbidden"):
        hermes_state.check_appliable(art(name="config", apply_forbidden=True))


def test_apply_accepte_un_artefact_git():
    hermes_state.check_appliable(art(name="soul"))  # ne lève pas


def test_les_garde_fous_ne_touchent_pas_le_cluster():
    """Le refus doit précéder tout appel kubectl."""
    pod = hermes_state.podio.Pod(executor=ExecuteurInterdit())
    with pytest.raises(hermes_state.GuardError):
        hermes_state.apply_artifact(pod, art(owner="hermes"), b"peu importe", oui=True)


def test_statut_ligne_de_diff():
    assert hermes_state.ligne_statut("soul", "=").startswith("=")
    assert "~" in hermes_state.ligne_statut("soul", "~")
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

```bash
uv run --quiet --with pytest --with pyyaml pytest tests/test_guards.py -v
```

Attendu : `ModuleNotFoundError: No module named 'hermes_state'`.

- [ ] **Step 3: Implémenter la CLI et le verbe `diff`**

Crée `scripts/hermes-state/hermes_state.py` :

```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""hermes-state — réconciliation Git <-> PVC de la configuration Hermes.

    hermes-state diff              observe, ne modifie rien. Code retour 1 si dérive.
    hermes-state export [--adopt] [--commit]
    hermes-state apply [--only NAME]... --yes

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
        return normalize.normalize_jobs(brut, warn=lambda m: print(f"   avertissement: {m}",
                                                                   file=sys.stderr))
    if a["mode"] == "json":
        return normalize.normalize_json(pod.read_json_retry(a["pod"], json.loads))
    return normalize.normalize_text(pod.read(a["pod"]))


def comparer(a, cote_git, cote_pod):
    """Retourne (statut, detail)."""
    if cote_pod is None:
        return ABSENT_POD, "absent du pod"
    if cote_git is None:
        return ABSENT_GIT, "absent de Git — `export --adopt` pour le capturer"
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


def construire_parseur():
    p = argparse.ArgumentParser(prog="hermes-state", description=__doc__,
                               formatter_class=argparse.RawDescriptionHelpFormatter)
    sous = p.add_subparsers(dest="verbe", required=True)
    sous.add_parser("diff", help="compare Git et le pod, ne modifie rien")
    return p


def main(argv=None):
    args = construire_parseur().parse_args(argv)
    try:
        return {"diff": cmd_diff}[args.verbe](args)
    except (podio.PodError, GuardError, ValueError) as e:
        print(f"erreur: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Ajouter `apply_artifact` (référencé par le test des garde-fous)**

Ajoute à `scripts/hermes-state/hermes_state.py`, juste après `check_appliable` :

```python
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
```

- [ ] **Step 5: Lancer les tests**

```bash
cd /data/projets/perso/my-kluster/scripts/hermes-state
uv run --quiet --with pytest --with pyyaml pytest tests/ -v
```

Attendu : `35 passed`.

- [ ] **Step 6: Exécuter `diff` contre le vrai pod (lecture seule, sans danger)**

```bash
uv run --quiet --with pyyaml python hermes_state.py diff; echo "code retour: $?"
```

Attendu, d'après l'audit du 2026-07-27 :
- `=` pour `soul`, `hermes-md`, `skill-eval-modeles`, `skill-decouvertes`, `skill-web-fetch`, `script-index-telegram`, `script-bonsai-watch`, `config`
- `~` pour `script-index-digests` (divergence connue, décision humaine en attente)
- `-` pour `skill-veille-digest` et `crons` (jamais capturés)
- code retour `1`

Si `config` ressort en `~`, lis le détail : c'est soit une vraie dérive de valeur déclarée, soit un défaut de `yaml_subset_diff` à corriger avant d'aller plus loin.

- [ ] **Step 7: Commit**

```bash
cd /data/projets/perso/my-kluster
git add scripts/hermes-state/hermes_state.py scripts/hermes-state/tests/test_guards.py
git commit -m "feat(hermes-state): verbe diff + garde-fous d'apply (refus owner=hermes et config)"
```

---

## Task 6: Le verbe `export`

**Files:**
- Modify: `scripts/hermes-state/hermes_state.py`

- [ ] **Step 1: Écrire le test qui échoue**

Ajoute à `scripts/hermes-state/tests/test_guards.py` :

```python
def test_export_ecrit_seulement_si_le_contenu_change(tmp_path):
    cible = tmp_path / "state" / "jobs.json"
    assert hermes_state.ecrire_si_different(cible, "a\n") is True
    mtime = cible.stat().st_mtime_ns
    assert hermes_state.ecrire_si_different(cible, "a\n") is False
    assert cible.stat().st_mtime_ns == mtime, "aucune réécriture si contenu identique"
    assert hermes_state.ecrire_si_different(cible, "b\n") is True
    assert cible.read_text() == "b\n"


def test_export_selectionne_les_artefacts():
    arts = [art(name="soul", owner="git"), art(name="crons", owner="hermes")]
    assert [a["name"] for a in hermes_state.a_exporter(arts, adopt=False)] == ["crons"]
    assert sorted(a["name"] for a in hermes_state.a_exporter(arts, adopt=True)) == \
        ["crons", "soul"]
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

```bash
uv run --quiet --with pytest --with pyyaml pytest tests/test_guards.py -k export -v
```

Attendu : 2 échecs, `AttributeError: module 'hermes_state' has no attribute 'ecrire_si_different'`.

- [ ] **Step 3: Implémenter `export`**

Ajoute à `scripts/hermes-state/hermes_state.py`, avant `cmd_diff` :

```python
def ecrire_si_different(chemin, contenu):
    """Écrit uniquement si le contenu change. Retourne True si écriture eut lieu.

    Sans cette condition, le cron d'export toucherait les fichiers chaque jour
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
```

Puis ajoute la commande, après `cmd_diff` :

```python
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
            ecrits = []
            for rel, texte in cote_pod.items():
                if ecrire_si_different(chemin_git(a) / rel, texte):
                    ecrits.append(rel)
            if ecrits:
                changes.append(f"{a['name']} ({', '.join(ecrits)})")
        else:
            if ecrire_si_different(chemin_git(a), cote_pod):
                changes.append(a["name"])

    if changes:
        print("capturé: " + ", ".join(changes))
    else:
        print("aucun changement à capturer")

    if args.commit and changes:
        # Import PARESSEUX volontaire : gitio n'existe qu'à partir de la Task 8.
        # `export` sans --commit fonctionne donc dès maintenant, et --commit
        # devient utilisable une fois la Task 8 terminée.
        import gitio
        chemins = [a["git"] for a in a_exporter(arts, args.adopt)]
        gitio.commit_export(RACINE_DEPOT, chemins, changes)

    return 2 if echecs else 0
```

⚠️ **N'utilise pas `--commit` avant la fin de la Task 8** : `gitio` n'existe pas encore. Les
étapes de vérification de cette tâche s'en passent volontairement.

Et enregistre le sous-parseur dans `construire_parseur`, après la ligne `diff` :

```python
    e = sous.add_parser("export", help="pod -> Git, artefacts owner=hermes")
    e.add_argument("--adopt", action="store_true",
                   help="capture aussi les artefacts owner=git absents de Git (amorçage)")
    e.add_argument("--commit", action="store_true",
                   help="git add/commit/push des chemins exportés (cf. spec §5)")
```

Enfin, ajoute `"export": cmd_export` au dictionnaire de `main`.

- [ ] **Step 4: Lancer les tests**

```bash
uv run --quiet --with pytest --with pyyaml pytest tests/ -v
```

Attendu : `37 passed`.

- [ ] **Step 5: Capturer les crons pour de vrai (sans commit)**

```bash
cd /data/projets/perso/my-kluster/scripts/hermes-state
uv run --quiet --with pyyaml python hermes_state.py export
git -C /data/projets/perso/my-kluster status --short hermes-runtime/
```

Attendu : `capturé: crons`, et `?? hermes-runtime/state/jobs.json` dans le statut Git.

- [ ] **Step 6: Vérifier que le fichier capturé est exploitable**

```bash
cd /data/projets/perso/my-kluster
python3 -c "
import json
d = json.load(open('hermes-runtime/state/jobs.json'))
print('jobs capturés:', len(d['jobs']))
print('noms:', [j['name'] for j in d['jobs']])
print('champs volatils présents:', [c for c in ('last_run_at','next_run_at','state')
                                     if any(c in j for j in d['jobs'])] or 'aucun')
print('updated_at racine:', 'présent (BUG)' if 'updated_at' in d else 'absent (correct)')
print('caractères de prompt:', sum(len(j.get('prompt') or '') for j in d['jobs']))
"
```

Attendu : 8 jobs, aucun champ volatil, `updated_at` absent, et un total de caractères de prompt de l'ordre de 12 000 à 20 000 — c'est le travail qui n'était sauvegardé nulle part.

- [ ] **Step 7: Vérifier l'idempotence sur le vrai pod**

```bash
cd /data/projets/perso/my-kluster/scripts/hermes-state
uv run --quiet --with pyyaml python hermes_state.py export
```

Attendu : `aucun changement à capturer`. **C'est la preuve empirique que l'auto-commit ne polluera pas `main`** : le second passage ne voit rien changer alors que `next_run_at` et `updated_at` ont bougé entre les deux.

- [ ] **Step 8: Commit**

```bash
cd /data/projets/perso/my-kluster
git add scripts/hermes-state/hermes_state.py scripts/hermes-state/tests/test_guards.py hermes-runtime/state/
git commit -m "feat(hermes-state): verbe export + première capture des 8 crons

jobs.json n'existait qu'sur le PVC. ~18k caractères de prompts désormais versionnés."
```

---

## Task 7: Le verbe `apply`

**Files:**
- Modify: `scripts/hermes-state/hermes_state.py`

- [ ] **Step 1: Écrire le test qui échoue**

Ajoute à `scripts/hermes-state/tests/test_guards.py` :

```python
def test_apply_dry_run_n_ecrit_rien():
    faux = ExecuteurInterdit()
    pod = hermes_state.podio.Pod(executor=faux)
    hermes_state.apply_artifact(pod, art(name="soul"), b"contenu", oui=False)
    # ExecuteurInterdit lèverait si un kubectl avait lieu — l'absence d'exception suffit


def test_apply_ecrit_aussi_les_destinations_also():
    ecrits = []
    pod = hermes_state.podio.Pod(executor=ExecuteurInterdit())
    pod.write = lambda chemin, donnees: ecrits.append(chemin)
    hermes_state.apply_artifact(
        pod, art(name="hermes-md", pod="/workspace/HERMES.md",
                 also=["/workspace/AGENTS.md"]), b"x", oui=True)
    assert ecrits == ["/workspace/HERMES.md", "/workspace/AGENTS.md"]


def test_mode_tree_signale_les_fichiers_en_trop_sans_les_supprimer():
    """Spec §3.3 : `apply` en mode tree n'efface JAMAIS les fichiers
    surnuméraires du pod. Supprimer dans le pod depuis Git n'est pas un pouvoir
    qu'on donne à une commande de synchronisation."""
    a = art(name="skill-veille-digest", pod="/opt/data/skills/veille-digest",
            git="hermes-runtime/skills/veille-digest", mode="tree")
    cote_git = {"SKILL.md": "contenu\n"}
    cote_pod = {"SKILL.md": "contenu\n", "brouillon.md": "résidu\n"}
    statut, detail = hermes_state.comparer(a, cote_git, cote_pod)
    assert statut == "~"
    assert "en trop dans le pod" in detail
    assert "brouillon.md" in detail
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

```bash
uv run --quiet --with pytest --with pyyaml pytest tests/test_guards.py -k apply -v
```

Attendu : `test_apply_ecrit_aussi_les_destinations_also` échoue si `also` n'est pas géré ; les autres passent déjà (Task 5 a introduit `apply_artifact`).

- [ ] **Step 3: Implémenter la commande `apply`**

Ajoute à `scripts/hermes-state/hermes_state.py`, après `cmd_export` :

```python
def cmd_apply(args):
    arts = normalize.load_manifest(MANIFEST)
    if args.only:
        connus = {a["name"] for a in arts}
        inconnus = set(args.only) - connus
        if inconnus:
            raise ValueError(f"artefact(s) inconnu(s): {', '.join(sorted(inconnus))}")
        arts = [a for a in arts if a["name"] in set(args.only)]

    pod = podio.Pod()
    redemarrage, echecs = [], []

    for a in arts:
        try:
            check_appliable(a)
        except GuardError as e:
            print(f"ignoré: {e}")
            continue

        cote_git = contenu_git(a)
        if cote_git is None:
            print(ligne_statut(a["name"], ABSENT_GIT, "absent de Git, rien à appliquer"))
            continue

        statut, detail = comparer(a, cote_git, contenu_pod(pod, a))
        if statut == IDENTIQUE:
            print(ligne_statut(a["name"], IDENTIQUE, "déjà aligné"))
            continue

        print(ligne_statut(a["name"], statut, detail))
        try:
            if a["mode"] == "tree":
                for rel, texte in cote_git.items():
                    apply_artifact(pod, dict(a, pod=f"{a['pod']}/{rel}", also=[]),
                                   texte.encode("utf-8"), oui=args.yes)
            else:
                apply_artifact(pod, a, cote_git.encode("utf-8"), oui=args.yes)
        except podio.PodError as e:
            print(f"erreur: {a['name']}: {e}", file=sys.stderr)
            echecs.append(a["name"])
            continue

        if a["restart_required"]:
            redemarrage.append(a["name"])

    if redemarrage:
        print(f"\nredémarrage du pod nécessaire pour: {', '.join(redemarrage)}")
        print("hermes-state ne redémarre JAMAIS de lui-même. À toi de décider :")
        print("  kubectl delete pod -n hermes -l app.kubernetes.io/name=hermes-agent")
    if not args.yes:
        print("\n(dry-run — ajoute --yes pour écrire réellement)")
    return 2 if echecs else 0
```

Enregistre le sous-parseur, après celui d'`export` :

```python
    ap = sous.add_parser("apply", help="Git -> pod, artefacts owner=git uniquement")
    ap.add_argument("--only", action="append", default=[], metavar="NAME",
                    help="limiter à cet artefact (répétable)")
    ap.add_argument("--yes", action="store_true",
                    help="écrire réellement (sans ce drapeau : dry-run)")
```

Et ajoute `"apply": cmd_apply` au dictionnaire de `main`.

- [ ] **Step 4: Lancer les tests**

```bash
uv run --quiet --with pytest --with pyyaml pytest tests/ -v
```

Attendu : `40 passed`.

- [ ] **Step 5: Vérifier le refus, en dry-run global**

```bash
cd /data/projets/perso/my-kluster/scripts/hermes-state
uv run --quiet --with pyyaml python hermes_state.py apply
```

Attendu : deux lignes `ignoré:` — une pour `crons` (`owner=hermes`) et une pour `config` (`apply_forbidden`) — puis un dry-run pour le reste, et **aucune écriture**.

- [ ] **Step 6: Validation manuelle sur un artefact inoffensif**

C'est le seul test d'écriture réelle du plan. `web-fetch` est choisi parce qu'il est déjà identique de part et d'autre : réécrire le même contenu ne change rien fonctionnellement, mais prouve que le chemin complet (écriture atomique, chown, relecture) fonctionne.

```bash
uv run --quiet --with pyyaml python hermes_state.py apply --only skill-web-fetch --yes
HPOD=$(kubectl get pods -n hermes --no-headers | awk '/hermes-agent/{print $1}' | head -1)
kubectl exec -n hermes "$HPOD" -c main -- stat -c '%U:%G %n' /opt/data/skills/web-fetch/SKILL.md
```

Attendu : la sortie de `stat` montre le propriétaire **`hermes:hermes`** (uid 10000). Si elle montre `root:root`, le chown a échoué en silence — arrête-toi et corrige `podio.write` avant d'aller plus loin.

- [ ] **Step 7: Commit**

```bash
cd /data/projets/perso/my-kluster
git add scripts/hermes-state/hermes_state.py scripts/hermes-state/tests/test_guards.py
git commit -m "feat(hermes-state): verbe apply (dry-run par défaut, --only, jamais de restart)"
```

---

## Task 8: Commit automatique avec garde-fous Git

**Files:**
- Create: `scripts/hermes-state/gitio.py`
- Create: `scripts/hermes-state/tests/test_gitio.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Crée `scripts/hermes-state/tests/test_gitio.py` :

```python
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import gitio
import pytest


def depot(tmp_path, branche="main", rebase=False, merge=False):
    (tmp_path / ".git").mkdir()
    if rebase:
        (tmp_path / ".git" / "REBASE_HEAD").write_text("x")
    if merge:
        (tmp_path / ".git" / "MERGE_HEAD").write_text("x")
    (tmp_path / ".git" / "HEAD").write_text(f"ref: refs/heads/{branche}\n")
    return tmp_path


def test_refuse_si_rebase_en_cours(tmp_path):
    with pytest.raises(gitio.GitGuardError, match="rebase"):
        gitio.verifier_etat(depot(tmp_path, rebase=True))


def test_refuse_si_merge_en_cours(tmp_path):
    with pytest.raises(gitio.GitGuardError, match="merge"):
        gitio.verifier_etat(depot(tmp_path, merge=True))


def test_refuse_si_branche_autre_que_main(tmp_path):
    with pytest.raises(gitio.GitGuardError, match="branche"):
        gitio.verifier_etat(depot(tmp_path, branche="une-feature"))


def test_accepte_main_propre(tmp_path):
    gitio.verifier_etat(depot(tmp_path))  # ne lève pas


def test_message_de_commit_liste_les_changements():
    m = gitio.message_commit(["crons (llm-veille-daily)", "skill-veille-digest"])
    assert m.startswith("chore(hermes): capture état runtime")
    assert "llm-veille-daily" in m
    assert "skill-veille-digest" in m


def test_add_restreint_aux_chemins_donnes(tmp_path):
    appels = []
    gitio.commit_export(depot(tmp_path), ["a/b.json", "c/d.md"], ["crons"],
                        run=lambda argv, cwd: appels.append(argv) or (0, b"", b""))
    add = next(a for a in appels if a[:2] == ["git", "add"])
    assert add[2:] == ["--", "a/b.json", "c/d.md"], "git add doit être restreint"
    assert not any("--force" in a for a in appels), "jamais de push --force"


def test_push_en_echec_n_est_pas_force(tmp_path):
    def run(argv, cwd):
        if argv[1] == "push":
            return 1, b"", b"rejected: non-fast-forward"
        return 0, b"", b""

    with pytest.raises(gitio.GitGuardError, match="push"):
        gitio.commit_export(depot(tmp_path), ["a"], ["crons"], run=run)
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

```bash
uv run --quiet --with pytest --with pyyaml pytest tests/test_gitio.py -v
```

Attendu : `ModuleNotFoundError: No module named 'gitio'`.

- [ ] **Step 3: Implémenter les garde-fous Git**

Crée `scripts/hermes-state/gitio.py` :

```python
"""Commit automatique de l'état exporté, avec garde-fous.

Le cron commit sur main et pousse : un commit local seul ne protégerait de
rien, puisque la perte du poste emporterait l'historique — or la protection
est l'objectif. D'où des garde-fous stricts plutôt qu'un `git commit -a`.
"""
import pathlib
import subprocess

BRANCHE_AUTORISEE = "main"


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
    if (g / "REBASE_HEAD").exists() or (g / "rebase-merge").exists() or (g / "rebase-apply").exists():
        raise GitGuardError("rebase en cours — aucun commit automatique")
    if (g / "MERGE_HEAD").exists():
        raise GitGuardError("merge en cours — aucun commit automatique")
    if (g / "CHERRY_PICK_HEAD").exists():
        raise GitGuardError("cherry-pick en cours — aucun commit automatique")
    b = branche_courante(racine)
    if b != BRANCHE_AUTORISEE:
        raise GitGuardError(
            f"branche courante '{b}' != '{BRANCHE_AUTORISEE}' — export effectué, commit refusé")


def message_commit(changements):
    return ("chore(hermes): capture état runtime\n\n"
            + "\n".join(f"- {c}" for c in changements) + "\n")


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
```

- [ ] **Step 4: Rendre les erreurs Git propres dans la CLI**

`gitio.GitGuardError` existe maintenant : la CLI doit la rattraper pour sortir en code 2 au lieu
d'afficher une trace. Dans `scripts/hermes-state/hermes_state.py`, ajoute `import gitio` à la
liste des imports locaux (après `import podio`), puis remplace la clause `except` de `main` :

```python
    except (podio.PodError, GuardError, gitio.GitGuardError, ValueError) as e:
        print(f"erreur: {e}", file=sys.stderr)
        return 2
```

L'import paresseux dans `cmd_export` devient redondant — supprime la ligne `import gitio` à
l'intérieur de la fonction ainsi que son commentaire sur la Task 8.

- [ ] **Step 5: Lancer les tests**

```bash
uv run --quiet --with pytest --with pyyaml pytest tests/ -v
```

Attendu : `47 passed`.

- [ ] **Step 6: Vérifier le garde-fou de branche pour de vrai**

```bash
cd /data/projets/perso/my-kluster
git checkout -b test-garde-fou
cd scripts/hermes-state
uv run --quiet --with pyyaml python hermes_state.py export --commit; echo "code retour: $?"
cd /data/projets/perso/my-kluster && git checkout main && git branch -D test-garde-fou
```

Attendu : `aucun changement à capturer` (donc pas de tentative de commit) et code retour `0`.
Si `export` avait quelque chose à capturer, tu verrais `erreur: branche courante
'test-garde-fou' != 'main'` et un code retour `2` — l'export a lieu, le commit est refusé.

- [ ] **Step 7: Commit**

```bash
cd /data/projets/perso/my-kluster
git add scripts/hermes-state/gitio.py scripts/hermes-state/hermes_state.py scripts/hermes-state/tests/test_gitio.py
git commit -m "feat(hermes-state): commit auto avec garde-fous (add restreint, jamais de force)"
```

---

## Task 9: Planification et documentation

**Files:**
- Create: `scripts/hermes-state/README.md`
- Modify: `hermes-runtime/README.md`

- [ ] **Step 1: Écrire le README de l'outil**

Crée `scripts/hermes-state/README.md` :

```markdown
# hermes-state — réconciliation Git ↔ PVC de la configuration Hermes

Conception : `docs/superpowers/specs/2026-07-27-hermes-state-design.md`

## Pourquoi

Hermes possède son état et le réécrit. Le dépôt veut que Git soit la vérité.
`manifest.yaml` tranche **artefact par artefact** :

- `owner: git` → Git fait foi, `apply` écrase le pod.
- `owner: hermes` → le pod fait foi, `export` capture vers Git, **`apply` n'y touche jamais**.

Concrètement : tu continues d'éditer tes crons dans le dashboard, et Git les capture seul.

## Usage

```bash
cd scripts/hermes-state

# observer (aucune modification, code retour 1 s'il y a dérive)
uv run --quiet --with pyyaml python hermes_state.py diff

# capturer l'état possédé par Hermes
uv run --quiet --with pyyaml python hermes_state.py export

# amorçage : capturer aussi les artefacts owner=git encore absents de Git
uv run --quiet --with pyyaml python hermes_state.py export --adopt

# appliquer Git -> pod (dry-run sans --yes)
uv run --quiet --with pyyaml python hermes_state.py apply --only soul --yes
```

## Tests

```bash
cd scripts/hermes-state
uv run --quiet --with pytest --with pyyaml pytest tests/ -v
```

Rien n'est installé sur le poste : `uv` monte un environnement éphémère.

## ⚠️ Le piège uid 10000

`kubectl exec` tourne en **root**, l'agent Hermes tourne en **uid 10000**. Un fichier
écrit sans `chown 10000:10000` est **invisible pour l'agent, sans aucune erreur**.
`podio.write()` chown puis relit systématiquement. Ne contourne jamais ce chemin.

## `hermes-runtime/state/` est GÉNÉRÉ

Ne l'édite pas à la main : le prochain `export` écrasera tes changements. Pour changer
un cron, passe par le dashboard Hermes ; `export` le capturera.
```

- [ ] **Step 2: Remplacer la procédure manuelle dans `hermes-runtime/README.md`**

Dans `hermes-runtime/README.md`, remplace toute la section `## Réappliquer après un rebuild` (le bloc `kubectl cp` et son avertissement) par :

```markdown
## Réappliquer après un rebuild

```bash
cd scripts/hermes-state
uv run --quiet --with pyyaml python hermes_state.py diff          # voir l'écart
uv run --quiet --with pyyaml python hermes_state.py apply --yes   # écrire dans le pod
```

L'outil gère le `chown 10000:10000` (⚠️ `kubectl exec` tourne en root, l'agent en uid
10000 : un fichier non chowné est invisible pour l'agent, sans erreur), les doubles
destinations (`HERMES.md` + `AGENTS.md`), et refuse d'écrire les artefacts que Hermes
possède. Cf. `scripts/hermes-state/README.md`.

**`jobs.json` (crons)** est désormais capturé automatiquement dans
`hermes-runtime/state/jobs.json` par le cron d'export. Ce répertoire est **généré** :
ne l'édite pas à la main.
```

- [ ] **Step 3: Écrire l'enveloppe du cron, qui ne peut pas échouer en silence**

Un cron qui ne journalise que dans un fichier est un cron dont personne ne voit l'échec — c'est
le défaut exact relevé sur `brain-digest.sh` pendant l'audit. Crée
`scripts/hermes-state/run-export.sh` :

```bash
#!/usr/bin/env bash
# Enveloppe du cron d'export. Notifie Telegram UNIQUEMENT en cas d'échec :
# le silence doit signifier "tout va bien", jamais "le cron est mort".
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
UV="${UV_BIN:-/home/moi/.local/bin/uv}"

notify() {
  local f="${TELEGRAM_TOKEN_FILE:-${HOME:-/home/moi}/.config/brain/telegram-bot-token}"
  local tok; tok="$(cat "$f" 2>/dev/null || true)"
  if [ -z "$tok" ]; then
    echo "WARN notify: token Telegram illisible ($f) — message NON envoyé" >&2; return 0
  fi
  local code
  code=$(curl -s -4 -m 20 -o /dev/null -w '%{http_code}' \
    "https://api.telegram.org/bot${tok}/sendMessage" \
    --data-urlencode "chat_id=843341688" --data-urlencode "text=$1" 2>/dev/null || echo 000)
  [ "$code" = "200" ] || echo "WARN notify: Telegram http=$code — non délivré" >&2
}

cd "$HERE" || exit 2
sortie=$("$UV" run --quiet --with pyyaml python hermes_state.py export --commit 2>&1)
rc=$?
echo "$sortie"
if [ "$rc" != "0" ]; then
  notify "⚠️ hermes-state export a échoué (code $rc)
${sortie: -400}"
fi
exit "$rc"
```

```bash
chmod +x scripts/hermes-state/run-export.sh
bash -n scripts/hermes-state/run-export.sh && echo "syntaxe OK"
```

- [ ] **Step 4: Vérifier l'enveloppe à la main**

```bash
cd /data/projets/perso/my-kluster
./scripts/hermes-state/run-export.sh; echo "code retour: $?"
```

Attendu : `aucun changement à capturer` (Task 6 a déjà tout capturé), code retour `0`, **aucun
commit** et **aucune notification**. C'est le comportement voulu au régime permanent.

- [ ] **Step 5: Vérifier que l'échec est bien notifié**

Simule un échec en pointant l'outil vers un namespace inexistant :

```bash
cd /data/projets/perso/my-kluster/scripts/hermes-state
TELEGRAM_TOKEN_FILE=/nonexistent ./run-export.sh; echo "code retour: $?"
```

Attendu : le script sort en code `2` (aucun pod trouvé dans le namespace… ou une erreur d'accès),
et affiche `WARN notify: token Telegram illisible` — ce qui prouve que la branche de notification
est bien atteinte sans envoyer de message réel pendant le test.

- [ ] **Step 6: Ajouter le cron**

```bash
crontab -l > ~/.cache/crontab.bak-hermes-state
(crontab -l; echo '25 3 * * * HOME=/home/moi /data/projets/perso/my-kluster/scripts/hermes-state/run-export.sh >> /home/moi/.cache/hermes-state.log 2>&1  # capture etat Hermes -> Git') | crontab -
crontab -l | tail -2
```

`03:25` évite le backup Sealed Secrets (03:00) et le cycle d'éval (22:00). `HOME=/home/moi` est
obligatoire : sous cron, `$HOME` peut être absent, et sans lui le token Telegram devient
introuvable — piège déjà rencontré et documenté dans `scripts/eval-harness/eval-pipeline.sh`.

- [ ] **Step 7: Commit**

```bash
cd /data/projets/perso/my-kluster
git add scripts/hermes-state/README.md scripts/hermes-state/run-export.sh hermes-runtime/README.md
git commit -m "docs(hermes-state): mode d'emploi + enveloppe cron qui notifie ses échecs"
```

---

## Task 10: Adopter les artefacts orphelins

Deux artefacts `owner: git` n'existent pas encore dans Git : le skill `veille-digest` (versionné nulle part alors qu'il alimente le pipeline d'éval) et `bonsai_watch.py` (présent dans l'arbre mais jamais committé).

**Files:**
- Create: `hermes-runtime/skills/veille-digest/SKILL.md` (via `export --adopt`)
- Create: `hermes-runtime/skills/veille-digest/references/github-releases-api.md` (idem)
- Create: `hermes-runtime/skills/web-fetch.SKILL.md` (déplacement depuis `scripts/hermes-skills/`)

- [ ] **Step 1: Déplacer le skill `web-fetch` à sa place canonique**

Il vit aujourd'hui dans un troisième emplacement non documenté, `scripts/hermes-skills/`. Le manifeste le déclare sous `hermes-runtime/skills/`.

```bash
cd /data/projets/perso/my-kluster
mkdir -p hermes-runtime/skills
git mv scripts/hermes-skills/web-fetch-SKILL.md hermes-runtime/skills/web-fetch.SKILL.md
rmdir scripts/hermes-skills 2>/dev/null || true
git commit -m "refactor(hermes): web-fetch.SKILL.md rejoint hermes-runtime/skills/"
```

- [ ] **Step 2: Adopter les orphelins**

```bash
cd scripts/hermes-state
uv run --quiet --with pyyaml python hermes_state.py export --adopt
```

Attendu : `capturé: skill-veille-digest (SKILL.md, references/github-releases-api.md)`. Les autres artefacts `owner: git` sont déjà identiques, donc non réécrits.

- [ ] **Step 3: Vérifier que `diff` est propre**

```bash
uv run --quiet --with pyyaml python hermes_state.py diff; echo "code retour: $?"
```

Attendu : `=` partout **sauf** `script-index-digests`, qui reste en `~`. Code retour `1`.

Cette divergence est **volontairement laissée ouverte** (spec §8) : la version du PVC et celle de Git diffèrent, et on ne sait pas laquelle fait foi. Ne lance pas `apply` dessus avant d'avoir tranché. Pour comparer :

```bash
HPOD=$(kubectl get pods -n hermes --no-headers | awk '/hermes-agent/{print $1}' | head -1)
kubectl exec -n hermes "$HPOD" -c main -- cat /opt/data/scripts/index_digests.py > /tmp/pod-index_digests.py
diff -u scripts/veille-digest-indexer/index_digests.py /tmp/pod-index_digests.py
```

- [ ] **Step 4: Committer l'adoption**

```bash
cd /data/projets/perso/my-kluster
git add hermes-runtime/skills/veille-digest/ scripts/bonsai-watcher/
git commit -m "feat(hermes): versionne le skill veille-digest et bonsai_watch.py

veille-digest alimentait le pipeline d'éval sans exister dans Git.
bonsai_watch.py tournait en cron Hermes sans jamais avoir été committé."
```

- [ ] **Step 5: Lancer la suite complète une dernière fois**

```bash
cd scripts/hermes-state
uv run --quiet --with pytest --with pyyaml pytest tests/ -v
```

Attendu : `47 passed`.

---

## Ce que ce plan ne fait PAS

Volontairement hors périmètre, chacun étant un travail distinct :

- **Sauvegarde des 3 tokens** de `~/.config/brain/` : ils ne peuvent pas aller dans Git en clair. Problème de sauvegarde chiffrée (le pattern existe : rôle Ansible `sealed-secrets-backup`, `age` vers le NAS).
- **Rotation du token `arrconf`** en clair dans `hermes-agent-app.yaml:420` : action mécanique urgente, sans conception.
- **Élagage des 67 skills upstream** (≈5 800 tokens par session) : action mécanique.
- **Purge des `.bak`** (79 `.env.bak`, 80 `config.yaml.bak`) : le producteur n'est **pas identifié** — le pod n'a pas redémarré depuis le 2026-07-25 alors que des sauvegardes datent du 2026-07-10, donc l'hypothèse « écrites au boot » est fausse. N'écris pas de purge automatique sur un mécanisme non compris.
- **`seen-*.json`** : déclarés dans la spec mais **absents du manifeste initial** de ce plan, volontairement. Ils sont éclatés entre `/opt/data/` et `/opt/data/veille-state/` avec un doublon (`seen-data-ia.json` des deux côtés). Ranger cette incohérence est un préalable à leur capture, et ce préalable est un choix fonctionnel qui appartient à l'utilisateur. Ajouter l'entrée au manifeste sera trivial ensuite.
