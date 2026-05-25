# Extension Ansible : `common-cli-tools` + `dev-workstation` — Design

**Date** : 2026-05-25
**Auteur** : Thomas Guyader (laboitatom@gmail.com)
**Statut** : Approuvé pour implémentation
**Spec parente** : `2026-05-25-ansible-extension-design.md` (extension Ansible initiale)

---

## 1. Contexte

Ajout d'un nouveau type de machine au périmètre Ansible : **PC de développement** (work-laptop, Linux Mint 22.3 = base Ubuntu 24.04 Noble). Pour éviter la duplication entre `k8s-node-bootstrap` (qui contient déjà les CLI tools de confort) et le futur rôle dev, on factorise dans un rôle commun.

Aussi pris en compte : extensibilité pour d'autres dev-workstations futures.

---

## 2. Objectifs

- **O1** — Déployer Beszel + outils dev standardisés sur le laptop Mint sans dupliquer la liste de packages avec k8s-node-bootstrap.
- **O2** — Permettre l'ajout futur d'autres dev-workstations avec une seule entrée d'inventaire.
- **O3** — Setup chezmoi pointé sur `tom333/dotfiles` (privé, vide à la création) pour gérer les dotfiles à terme.
- **O4** — Pas de couplage fort entre rôles (le refactor de bootstrap ne doit pas casser ce qui marche déjà).

## 3. Non-objectifs

- Pas de provisioning de l'OS lui-même (Mint doit être installé manuellement).
- Pas de gestion automatique des updates du système Mint (l'utilisateur a déjà unattended-upgrades ou équivalent).
- Pas d'init automatique de `chezmoi init <repo>` — fait manuellement par l'utilisateur après ajout de la pubkey SSH du laptop dans GitHub.
- Pas d'install des drivers GPU (le laptop n'est pas un node compute).
- Pas de dotfiles versionnés dans ce repo (vivent dans `tom333/dotfiles`).

---

## 4. Architecture

### 4.1 Trois rôles, deux nouveaux + un refactor

```
ansible/roles/
├── beszel-agent/                    # existant, inchangé
├── sealed-secrets-backup/           # existant, inchangé
├── common-cli-tools/                # NEW — factor des outils CLI partagés
├── k8s-node-bootstrap/              # MODIFIED — extract de tasks/10_packages.yml
└── dev-workstation/                 # NEW — config dev
```

### 4.2 Inventaire — nouveau groupe `dev_workstations`

```yaml
all:
  children:
    k8s_nodes:
      hosts:
        k8s-node:
          ansible_host: 192.168.88.250
          ansible_connection: local
          ansible_user: moi
          beszel_arch: amd64

    dev_workstations:
      hosts:
        work-laptop:
          ansible_host: 192.168.88.211
          ansible_user: moi
          beszel_arch: amd64

  hosts: {}   # Plus de hosts ungrouped pour l'instant
  vars:
    ansible_ssh_common_args: '-o StrictHostKeyChecking=no'
```

### 4.3 Playbook — 3 plays

```yaml
- name: Bootstrap & monitor k8s-node
  hosts: k8s_nodes
  become: true
  vars_files: [group_vars/vault.yml]
  roles:
    - { role: common-cli-tools, tags: [bootstrap, cli-tools] }
    - { role: k8s-node-bootstrap, tags: [bootstrap] }
    - sealed-secrets-backup
    - beszel-agent

- name: Provision dev workstations
  hosts: dev_workstations
  become: true
  vars_files: [group_vars/vault.yml]
  roles:
    - { role: common-cli-tools, tags: [dev, cli-tools] }
    - { role: dev-workstation, tags: [dev] }
    - beszel-agent

- name: Deploy Beszel agent on other monitored machines
  hosts: all:!k8s_nodes:!dev_workstations
  become: true
  vars_files: [group_vars/vault.yml]
  roles:
    - beszel-agent
```

Sémantique des tags :
- `--tags bootstrap` → common-cli-tools + k8s-node-bootstrap (uniquement sur k8s_nodes)
- `--tags dev` → common-cli-tools + dev-workstation (uniquement sur dev_workstations)
- `--tags cli-tools` → uniquement common-cli-tools (sur k8s_nodes ET dev_workstations)
- Aucun tag → tout

---

## 5. Rôle `common-cli-tools`

### 5.1 Responsabilités

Extrait l'intégralité du contenu actuel de `k8s-node-bootstrap/tasks/10_packages.yml`. Aucune nouveauté fonctionnelle ici — juste un déplacement + variables réorganisées.

### 5.2 Structure

```
ansible/roles/common-cli-tools/
├── defaults/main.yml
├── handlers/main.yml
├── tasks/main.yml
└── templates/
    ├── deb-get-upgrade.service.j2
    └── deb-get-upgrade.timer.j2
```

### 5.3 Tâches (tasks/main.yml)

1. APT packages :
   - jq, curl, git, python3-kubernetes, age, nfs-common, ca-certificates, apt-transport-https, gnupg
   - htop, btop, ncdu, ripgrep, fd-find, bat
   - pipx (NEW — utilisé par dev-workstation pour installer uv/ruff)
2. Symlinks fd→fdfind, bat→batcat
3. Install deb-get script si absent
4. `deb-get update`
5. Install packages deb-get listés dans `cli_deb_get_packages` (defaults = du-dust + github-cli)
6. Install systemd service unit `deb-get-upgrade.service`
7. Install systemd timer `deb-get-upgrade.timer`
8. Enable + start timer (avec `when: not ansible_check_mode`)

### 5.4 Variables (defaults/main.yml)

```yaml
---
# APT packages installed unconditionally (CLI tools shared across all hosts).
cli_apt_packages:
  - jq
  - curl
  - git
  - python3-kubernetes
  - age
  - nfs-common
  - ca-certificates
  - apt-transport-https
  - gnupg
  - htop
  - btop
  - ncdu
  - ripgrep
  - fd-find
  - bat
  - pipx

# Packages installed via deb-get (https://github.com/wimpysworld/deb-get).
cli_deb_get_packages:
  - { name: du-dust, binary: dust }
  - { name: github-cli, binary: gh }

# deb-get script URL (pinned to main HEAD; review changes periodically).
cli_deb_get_url: "https://raw.githubusercontent.com/wimpysworld/deb-get/main/deb-get"
```

### 5.5 Impact sur les rôles existants

**`k8s-node-bootstrap`** :
- Suppression de `tasks/10_packages.yml` entier
- Suppression de `templates/deb-get-upgrade.service.j2` et `deb-get-upgrade.timer.j2` (déplacés dans common-cli-tools)
- Suppression de la section "deb-get + packages" dans `defaults/main.yml`
- `tasks/main.yml` réordonné : le `import_tasks 10_packages.yml` est retiré (le rôle common-cli-tools s'exécute avant via le playbook)

**Cohabitation k8s-node et dev-workstation** :
- Sur k8s-node : common-cli-tools tourne avant k8s-node-bootstrap (cf. playbook). Idempotent : ne réinstalle pas ce qui est déjà là.
- Sur work-laptop : common-cli-tools tourne avant dev-workstation. Pareil.

---

## 6. Rôle `dev-workstation`

### 6.1 Responsabilités

Setup d'un environnement de développement standardisé. Suppose que `common-cli-tools` a déjà tourné (CLI tools de base + pipx déjà installés).

### 6.2 Structure

```
ansible/roles/dev-workstation/
├── defaults/main.yml
├── handlers/main.yml
└── tasks/
    ├── main.yml
    ├── 00_preflight.yml
    ├── 10_pipx_python_tools.yml
    ├── 20_deb_get_extras.yml      # VS Code, lazygit, chezmoi
    ├── 30_wezterm.yml              # wezterm terminal (Fury apt repo)
    └── 40_git_config.yml
```

### 6.3 Décomposition par task file

#### `00_preflight.yml`
- Ubuntu 24+ ou Linux Mint 22+ (`ansible_distribution in ['Ubuntu','Linuxmint']`)
- x86_64
- pipx installé (sera fait par common-cli-tools, mais sanity check)

#### `10_pipx_python_tools.yml`
- Loop sur `dev_pipx_packages` (default : `[uv, ruff]`)
- `pipx install` chacun, `creates:` pour idempotence
- Run en tant que `ansible_user` (pas root), via `become_user`

Note : pipx installe **dans le home du user**, pas globalement. C'est volontaire — `uv` et `ruff` accompagnent l'utilisateur, pas le système.

#### `20_deb_get_extras.yml`
- Loop sur `dev_deb_get_packages` :
  - `{ name: code, binary: code }` — VS Code Microsoft officiel
  - `{ name: lazygit, binary: lazygit }`
  - `{ name: chezmoi, binary: chezmoi }`
- Réutilise le pattern de common-cli-tools (deb-get install avec `creates:`)

#### `30_wezterm.yml`
- Add wezterm Fury apt repo key (idempotent via `creates:`)
- Add wezterm Fury apt repo (`/etc/apt/sources.list.d/wezterm.list`)
- `apt install wezterm`
- Pas de config par défaut (`~/.config/wezterm/wezterm.lua` viendra via chezmoi)

#### `40_git_config.yml`
- Set `git config --global user.name` et `user.email` pour le user
- Set core.editor (à choisir : `code --wait` ou `vim` ou autre)

### 6.4 Variables (defaults/main.yml)

```yaml
---
# Python tools installed via pipx (in the user's home, not system-wide).
dev_pipx_packages:
  - uv
  - ruff

# Extra deb-get packages specific to dev workstations.
dev_deb_get_packages:
  - { name: code, binary: code }         # VS Code (Microsoft)
  - { name: lazygit, binary: lazygit }
  - { name: chezmoi, binary: chezmoi }

# Git global config (set for the ansible_user, not root).
dev_git_user_name: "Thomas Guyader"
dev_git_user_email: "laboitatom@gmail.com"
dev_git_editor: "nano"   # convivial pour le remote coding SSH
dev_git_commit_gpgsign: true   # requires GPG key + user.signingkey set manually post-bootstrap

# Wezterm apt repository (Fury) — see https://wezfurlong.org/wezterm/install/linux.html
dev_wezterm_apt_key_url: "https://apt.fury.io/wez/gpg.key"
dev_wezterm_apt_key_path: "/usr/share/keyrings/wezterm-fury.gpg"
dev_wezterm_apt_repo: "deb [signed-by=/usr/share/keyrings/wezterm-fury.gpg] https://apt.fury.io/wez/ * *"

# OS guards
dev_workstation_allowed_distros: ["Ubuntu", "Linuxmint"]
```

### 6.5 Actions humaines requises (après ansible-playbook)

L'utilisateur doit **manuellement** :

1. **Générer une clé SSH sur le laptop** (pour pousser vers GitHub) :
   ```bash
   ssh-keygen -t ed25519 -C "moi@work-laptop"
   ```

2. **Ajouter la clé publique au compte GitHub** :
   ```bash
   gh ssh-key add ~/.ssh/id_ed25519.pub --title "work-laptop"
   ```
   (gh est déjà installé par common-cli-tools, mais nécessite `gh auth login` une fois.)

3. **Initialiser chezmoi sur le repo dotfiles** :
   ```bash
   chezmoi init git@github.com:tom333/dotfiles.git
   chezmoi apply
   ```
   Le repo étant vide à la création, rien ne s'applique. À mesure que tu ajoutes des dotfiles, ils seront répliqués.

4. **Ajouter ton premier dotfile** :
   ```bash
   chezmoi add ~/.zshrc       # ou .bashrc, .gitconfig, etc.
   chezmoi cd                 # va dans le repo chezmoi local
   git add . && git commit -m "Initial zshrc"
   git push
   ```

---

## 7. Sécurité

| Élément | Niveau | Mitigation |
|---|---|---|
| Repo dotfiles privé | Bien | Les configs personnelles ne fuitent pas en public |
| Pas de chezmoi init auto via Ansible | Bien | Demande de l'humain confirme la chaîne SSH-GitHub |
| VS Code (Microsoft binary) | Acceptable | Source officielle via deb-get, signé Microsoft |
| pipx user-scope | Bien | uv/ruff dans `~/.local/`, pas de pollution système |
| Tools deb-get auto-update hebdo | Vigilance | Déjà couvert par le timer de common-cli-tools (alerte Beszel si une commande plante après upgrade silencieux) |

---

## 8. Tests d'acceptation

- [ ] `ansible-playbook ... --check --diff` ne montre aucun changement sur k8s-node (refactor invisible, tout déjà installé).
- [ ] `ansible-playbook ... --limit work-laptop` :
  - Installe les packages common-cli-tools (changement attendu)
  - Installe pipx + uv + ruff
  - Installe VS Code, lazygit, chezmoi via deb-get
  - Installe tmux
  - Configure git global
- [ ] Re-run sur work-laptop : changed=0.
- [ ] `which code lazygit chezmoi uv ruff dust gh wezterm` → tous trouvés.
- [ ] `git config --global user.email` → `laboitatom@gmail.com`.
- [ ] L'utilisateur peut faire `chezmoi init git@github.com:tom333/dotfiles.git` après avoir ajouté la pubkey du laptop à GitHub.

---

## 9. Plan de phasage

| Phase | Étape | Durée |
|---|---|---|
| 1 | Subagent crée le rôle `common-cli-tools` (copy depuis bootstrap/10_packages) | 30 min |
| 2 | Subagent refactor `k8s-node-bootstrap` (suppression de 10_packages, templates deb-get-upgrade) | 20 min |
| 3 | Subagent crée le rôle `dev-workstation` (5 sous-task files) | 45 min |
| 4 | Mise à jour `inventory.yml` (groupe `dev_workstations`) et `playbook.yml` (3 plays) | 10 min |
| 5 | Test `--check --diff` sur k8s-node (vérifier no-op du refactor) | 10 min |
| 6 | Test `--check --diff` sur work-laptop | 10 min |
| 7 | Exécution réelle sur work-laptop | 5 min |
| 8 | Vérifications manuelles + commit + push | 15 min |

Total estimé : ~2h30.

---

## 10. Limites assumées

- Pas de support des distros hors Ubuntu/Mint (Fedora, Arch, etc.).
- pipx user-scope → si tu utilises un autre user pour tester, il aura ses propres uv/ruff. Acceptable.
- VS Code est l'unique IDE supporté. Pas de Cursor pour l'instant (non packagé deb-get).
- Pas de gestion des extensions VS Code via Ansible (peut être ajouté plus tard via `code --install-extension`).
- chezmoi est installé mais l'init reste manuel (par design — auth GitHub avant init).
