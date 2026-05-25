# dev-workstation + common-cli-tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the existing `k8s-node-bootstrap` role to extract shared CLI tooling into a new `common-cli-tools` role, then add a new `dev-workstation` role for development laptops. Update inventory & playbook to use a new `dev_workstations` group.

**Architecture:** 3 roles touched: one new shared role (`common-cli-tools`) consumed by both `k8s-node-bootstrap` (refactored — packages section removed) and `dev-workstation` (new). The playbook gains a third play for `dev_workstations` hosts. work-laptop migrates from ungrouped to the new group.

**Tech Stack:** Ansible 2.16+, `community.general`, `ansible.posix`, deb-get, pipx, apt repos (Fury for wezterm).

**Spec source:** `docs/superpowers/specs/2026-05-25-devworkstation-design.md`

---

## File Structure

```
ansible/
├── inventory.yml                                # MODIFY — add dev_workstations group
├── playbook.yml                                 # MODIFY — 3 plays
└── roles/
    ├── beszel-agent/                            # unchanged
    ├── sealed-secrets-backup/                   # unchanged
    │
    ├── common-cli-tools/                        # CREATE
    │   ├── defaults/main.yml
    │   ├── handlers/main.yml
    │   ├── tasks/main.yml
    │   └── templates/
    │       ├── deb-get-upgrade.service.j2
    │       └── deb-get-upgrade.timer.j2
    │
    ├── k8s-node-bootstrap/                      # REFACTOR
    │   ├── defaults/main.yml                    # MODIFY — remove deb-get vars
    │   ├── tasks/
    │   │   ├── main.yml                         # MODIFY — drop 10_packages import
    │   │   └── 10_packages.yml                  # DELETE
    │   └── templates/
    │       ├── deb-get-upgrade.service.j2       # DELETE (moved)
    │       └── deb-get-upgrade.timer.j2         # DELETE (moved)
    │
    └── dev-workstation/                         # CREATE
        ├── defaults/main.yml
        ├── handlers/main.yml
        └── tasks/
            ├── main.yml
            ├── 00_preflight.yml
            ├── 10_pipx_python_tools.yml
            ├── 20_deb_get_extras.yml
            ├── 30_wezterm.yml
            └── 40_git_config.yml
```

---

## Phase 1 — Create `common-cli-tools` role

### Task 1.1 — Scaffold + defaults

**Files:**
- Create: `ansible/roles/common-cli-tools/defaults/main.yml`

- [ ] **Step 1: Create file with content**

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

### Task 1.2 — Handlers

**Files:**
- Create: `ansible/roles/common-cli-tools/handlers/main.yml`

- [ ] **Step 1: Create file with content**

```yaml
---
- name: reload systemd (common-cli-tools)
  ansible.builtin.systemd:
    daemon_reload: true
```

### Task 1.3 — Templates (copy from k8s-node-bootstrap)

**Files:**
- Create: `ansible/roles/common-cli-tools/templates/deb-get-upgrade.service.j2`
- Create: `ansible/roles/common-cli-tools/templates/deb-get-upgrade.timer.j2`

- [ ] **Step 1: Copy from existing k8s-node-bootstrap templates**

```bash
cp ansible/roles/k8s-node-bootstrap/templates/deb-get-upgrade.service.j2 \
   ansible/roles/common-cli-tools/templates/deb-get-upgrade.service.j2
cp ansible/roles/k8s-node-bootstrap/templates/deb-get-upgrade.timer.j2 \
   ansible/roles/common-cli-tools/templates/deb-get-upgrade.timer.j2
```

Expected: 2 new files identical to the originals.

### Task 1.4 — Main tasks

**Files:**
- Create: `ansible/roles/common-cli-tools/tasks/main.yml`

- [ ] **Step 1: Create file with content**

```yaml
---
# common-cli-tools — CLI tooling shared by both k8s-node-bootstrap and dev-workstation.

- name: Install base APT packages
  ansible.builtin.apt:
    name: "{{ cli_apt_packages }}"
    state: present
    update_cache: true
    cache_valid_time: 3600

- name: Symlink fd → fdfind
  ansible.builtin.file:
    src: /usr/bin/fdfind
    dest: /usr/local/bin/fd
    state: link
    force: true

- name: Symlink bat → batcat
  ansible.builtin.file:
    src: /usr/bin/batcat
    dest: /usr/local/bin/bat
    state: link
    force: true

# deb-get installs packages not in Ubuntu repos as real .deb files,
# integrated with apt. Auto-update via weekly systemd timer below.
- name: Install deb-get script
  ansible.builtin.get_url:
    url: "{{ cli_deb_get_url }}"
    dest: /usr/local/bin/deb-get
    owner: root
    group: root
    mode: '0755'
    force: false

- name: Refresh deb-get package list
  ansible.builtin.command: deb-get update
  changed_when: false
  check_mode: false

- name: Install packages via deb-get
  ansible.builtin.command: "deb-get install {{ item.name }}"
  args:
    creates: "/usr/bin/{{ item.binary }}"
  environment:
    DEB_GET_NO_CONFIRM: "1"
  loop: "{{ cli_deb_get_packages }}"
  loop_control:
    label: "{{ item.name }} (binary: {{ item.binary }})"

- name: Install deb-get-upgrade systemd service unit (weekly auto-update)
  ansible.builtin.template:
    src: deb-get-upgrade.service.j2
    dest: /etc/systemd/system/deb-get-upgrade.service
    owner: root
    group: root
    mode: '0644'
  notify: reload systemd (common-cli-tools)

- name: Install deb-get-upgrade systemd timer unit
  ansible.builtin.template:
    src: deb-get-upgrade.timer.j2
    dest: /etc/systemd/system/deb-get-upgrade.timer
    owner: root
    group: root
    mode: '0644'
  notify: reload systemd (common-cli-tools)

- name: Flush handlers so daemon-reload runs before enable
  ansible.builtin.meta: flush_handlers

- name: Enable and start deb-get-upgrade.timer
  ansible.builtin.systemd:
    name: deb-get-upgrade.timer
    enabled: true
    state: started
  # In --check, the template above is simulated (not written to disk),
  # so systemd can't find the unit. Skip safely; real runs will apply it.
  when: not ansible_check_mode
```

---

## Phase 2 — Refactor `k8s-node-bootstrap`

### Task 2.1 — Remove the packages task file

**Files:**
- Delete: `ansible/roles/k8s-node-bootstrap/tasks/10_packages.yml`
- Delete: `ansible/roles/k8s-node-bootstrap/templates/deb-get-upgrade.service.j2`
- Delete: `ansible/roles/k8s-node-bootstrap/templates/deb-get-upgrade.timer.j2`

- [ ] **Step 1: Remove files**

```bash
rm ansible/roles/k8s-node-bootstrap/tasks/10_packages.yml
rm ansible/roles/k8s-node-bootstrap/templates/deb-get-upgrade.service.j2
rm ansible/roles/k8s-node-bootstrap/templates/deb-get-upgrade.timer.j2
```

### Task 2.2 — Update `tasks/main.yml`

**Files:**
- Modify: `ansible/roles/k8s-node-bootstrap/tasks/main.yml`

- [ ] **Step 1: Read current content + remove the import_tasks for 10_packages.yml**

The current file has:
```yaml
- ansible.builtin.import_tasks: 10_packages.yml
  tags: [bootstrap, packages]
```
Remove that block entirely (lines and the surrounding blank line if relevant). Keep the rest intact.

### Task 2.3 — Update `defaults/main.yml`

**Files:**
- Modify: `ansible/roles/k8s-node-bootstrap/defaults/main.yml`

- [ ] **Step 1: Remove the deb-get section**

The current file contains:
```yaml
# Packages installed via deb-get (...)
deb_get_packages:
  - { name: du-dust, binary: dust }
  - { name: github-cli, binary: gh }

# deb-get script URL (...)
deb_get_url: "https://raw.githubusercontent.com/wimpysworld/deb-get/main/deb-get"
```

Remove that section entirely. Keep `microk8s_*`, `nfs_*`, `sysctl_*`, `gpu_enabled`, `k8s_node_expected_hostname`.

---

## Phase 3 — Create `dev-workstation` role

### Task 3.1 — Defaults

**Files:**
- Create: `ansible/roles/dev-workstation/defaults/main.yml`

- [ ] **Step 1: Create file with content**

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
dev_git_editor: "nano"
dev_git_commit_gpgsign: true   # requires GPG key + user.signingkey set manually post-bootstrap

# Wezterm apt repository (Fury) — see https://wezfurlong.org/wezterm/install/linux.html
dev_wezterm_apt_key_url: "https://apt.fury.io/wez/gpg.key"
dev_wezterm_apt_key_path: "/usr/share/keyrings/wezterm-fury.gpg"
dev_wezterm_apt_repo: "deb [signed-by=/usr/share/keyrings/wezterm-fury.gpg] https://apt.fury.io/wez/ * *"

# OS guards
dev_workstation_allowed_distros: ["Ubuntu", "Linuxmint"]
```

### Task 3.2 — Handlers

**Files:**
- Create: `ansible/roles/dev-workstation/handlers/main.yml`

- [ ] **Step 1: Create file**

```yaml
---
# Empty for now — no system-wide services managed by this role.
```

### Task 3.3 — Main tasks (orchestration)

**Files:**
- Create: `ansible/roles/dev-workstation/tasks/main.yml`

- [ ] **Step 1: Create file**

```yaml
---
# dev-workstation — opinionated dev environment setup.
# Assumes common-cli-tools has already run (pipx + base CLI tools installed).

- ansible.builtin.import_tasks: 00_preflight.yml
  tags: [dev, preflight]

- ansible.builtin.import_tasks: 10_pipx_python_tools.yml
  tags: [dev, pipx]

- ansible.builtin.import_tasks: 20_deb_get_extras.yml
  tags: [dev, deb-get-extras]

- ansible.builtin.import_tasks: 30_wezterm.yml
  tags: [dev, wezterm]

- ansible.builtin.import_tasks: 40_git_config.yml
  tags: [dev, git]
```

### Task 3.4 — Preflight

**Files:**
- Create: `ansible/roles/dev-workstation/tasks/00_preflight.yml`

- [ ] **Step 1: Create file**

```yaml
---
- name: Preflight — supported distro
  ansible.builtin.assert:
    that:
      - ansible_distribution in dev_workstation_allowed_distros
      - ansible_architecture == "x86_64"
    fail_msg: "dev-workstation requires Ubuntu/Mint x86_64 (got {{ ansible_distribution }} {{ ansible_architecture }})"

- name: Preflight — pipx must already be installed (provided by common-cli-tools)
  ansible.builtin.command: pipx --version
  register: pipx_check
  changed_when: false
  check_mode: false
  failed_when: pipx_check.rc != 0
```

### Task 3.5 — pipx Python tools

**Files:**
- Create: `ansible/roles/dev-workstation/tasks/10_pipx_python_tools.yml`

- [ ] **Step 1: Create file**

```yaml
---
# pipx installs tools into the USER's $HOME/.local/, not system-wide.
# Must run as ansible_user, NOT root, otherwise installs in /root/.

- name: Ensure pipx PATH for user
  ansible.builtin.command: pipx ensurepath
  become: true
  become_user: "{{ ansible_user }}"
  register: pipx_ensurepath
  changed_when: "'is already in PATH' not in (pipx_ensurepath.stdout | default(''))"
  check_mode: false

- name: List currently pipx-installed packages
  ansible.builtin.command: pipx list --short
  become: true
  become_user: "{{ ansible_user }}"
  register: pipx_list
  changed_when: false
  check_mode: false

- name: Install Python tools via pipx
  ansible.builtin.command: "pipx install {{ item }}"
  become: true
  become_user: "{{ ansible_user }}"
  loop: "{{ dev_pipx_packages }}"
  when: item not in (pipx_list.stdout | default(''))
  changed_when: true
```

### Task 3.6 — deb-get extras

**Files:**
- Create: `ansible/roles/dev-workstation/tasks/20_deb_get_extras.yml`

- [ ] **Step 1: Create file**

```yaml
---
# Install dev-specific packages via deb-get (already provisioned by common-cli-tools).
- name: Install dev-workstation packages via deb-get
  ansible.builtin.command: "deb-get install {{ item.name }}"
  args:
    creates: "/usr/bin/{{ item.binary }}"
  environment:
    DEB_GET_NO_CONFIRM: "1"
  loop: "{{ dev_deb_get_packages }}"
  loop_control:
    label: "{{ item.name }} (binary: {{ item.binary }})"
```

### Task 3.7 — wezterm

**Files:**
- Create: `ansible/roles/dev-workstation/tasks/30_wezterm.yml`

- [ ] **Step 1: Create file**

```yaml
---
# Wezterm terminal emulator — installed from the upstream Fury apt repo
# rather than deb-get (deb-get does not currently package wezterm).

- name: Add wezterm Fury apt GPG key
  ansible.builtin.shell:
    cmd: |
      curl -fsSL {{ dev_wezterm_apt_key_url }} | gpg --dearmor -o {{ dev_wezterm_apt_key_path }}
    creates: "{{ dev_wezterm_apt_key_path }}"

- name: Add wezterm Fury apt repo
  ansible.builtin.apt_repository:
    repo: "{{ dev_wezterm_apt_repo }}"
    state: present
    filename: wezterm
    update_cache: true

- name: Install wezterm
  ansible.builtin.apt:
    name: wezterm
    state: present
```

### Task 3.8 — Git global config

**Files:**
- Create: `ansible/roles/dev-workstation/tasks/40_git_config.yml`

- [ ] **Step 1: Create file**

```yaml
---
# Git global config — set for ansible_user, NOT root.
# git config --global writes to $HOME/.gitconfig.

- name: Set git user.name
  community.general.git_config:
    scope: global
    name: user.name
    value: "{{ dev_git_user_name }}"
  become: true
  become_user: "{{ ansible_user }}"

- name: Set git user.email
  community.general.git_config:
    scope: global
    name: user.email
    value: "{{ dev_git_user_email }}"
  become: true
  become_user: "{{ ansible_user }}"

- name: Set git core.editor
  community.general.git_config:
    scope: global
    name: core.editor
    value: "{{ dev_git_editor }}"
  become: true
  become_user: "{{ ansible_user }}"

- name: Set git init.defaultBranch
  community.general.git_config:
    scope: global
    name: init.defaultBranch
    value: main
  become: true
  become_user: "{{ ansible_user }}"

- name: Set git pull.rebase
  community.general.git_config:
    scope: global
    name: pull.rebase
    value: "true"
  become: true
  become_user: "{{ ansible_user }}"

- name: Set git commit.gpgsign
  community.general.git_config:
    scope: global
    name: commit.gpgsign
    value: "{{ 'true' if dev_git_commit_gpgsign else 'false' }}"
  become: true
  become_user: "{{ ansible_user }}"
```

---

## Phase 4 — Update inventory and playbook

### Task 4.1 — Move work-laptop into `dev_workstations` group

**Files:**
- Modify: `ansible/inventory.yml`

- [ ] **Step 1: Replace file content**

```yaml
---
# Inventaire des machines monitorées par Beszel + bootstrap k8s-node + dev workstations.
# IPs en clair = LAN privé RFC1918, peu sensible. Pour ajouter une machine :
# 1) ajouter 3 lignes ci-dessous dans le bon groupe, 2) ansible-playbook ... --limit <nouveau-host>

all:
  children:
    # Machines qui hébergent un node Kubernetes — reçoivent common-cli-tools,
    # k8s-node-bootstrap, sealed-secrets-backup, beszel-agent.
    k8s_nodes:
      hosts:
        k8s-node:
          ansible_host: 192.168.88.250
          ansible_connection: local
          ansible_user: moi
          beszel_arch: amd64

    # PC de développement — reçoivent common-cli-tools, dev-workstation, beszel-agent.
    dev_workstations:
      hosts:
        # Linux Mint 22.3 (Ubuntu 24 noble-based) — laptop dev
        work-laptop:
          ansible_host: 192.168.88.211
          ansible_user: moi
          beszel_arch: amd64

  hosts:
    # Machines monitorées uniquement — reçoivent seulement beszel-agent.
    # Décommenter et adapter quand une machine est ajoutée.

    # ha-host:
    #   ansible_host: 192.168.88.200
    #   ansible_user: hass
    #   beszel_arch: amd64

    # pi-salon:
    #   ansible_host: 192.168.88.150
    #   ansible_user: pi
    #   beszel_arch: arm64

  vars:
    ansible_ssh_common_args: '-o StrictHostKeyChecking=no'
```

### Task 4.2 — Rewrite playbook with 3 plays

**Files:**
- Modify: `ansible/playbook.yml`

- [ ] **Step 1: Replace file content**

```yaml
---
# Playbook entry point — 3 plays:
# - k8s_nodes : full bootstrap + backup + monitoring
# - dev_workstations : CLI tools + dev tooling + monitoring
# - others : just monitoring

- name: Bootstrap & monitor k8s-node
  hosts: k8s_nodes
  become: true
  gather_facts: true
  vars_files:
    - group_vars/vault.yml
  pre_tasks:
    - name: Show host info
      ansible.builtin.debug:
        msg: "k8s-node play on {{ inventory_hostname }} ({{ ansible_host }}) — arch={{ beszel_arch }}"
  roles:
    - { role: common-cli-tools, tags: [bootstrap, cli-tools] }
    - { role: k8s-node-bootstrap, tags: [bootstrap] }
    - sealed-secrets-backup
    - beszel-agent

- name: Provision dev workstations
  hosts: dev_workstations
  become: true
  gather_facts: true
  vars_files:
    - group_vars/vault.yml
  pre_tasks:
    - name: Show host info
      ansible.builtin.debug:
        msg: "Dev workstation play on {{ inventory_hostname }} ({{ ansible_host }}) — arch={{ beszel_arch }}"
  roles:
    - { role: common-cli-tools, tags: [dev, cli-tools] }
    - { role: dev-workstation, tags: [dev] }
    - beszel-agent

- name: Deploy Beszel agents on other monitored machines
  hosts: all:!k8s_nodes:!dev_workstations
  become: true
  gather_facts: true
  vars_files:
    - group_vars/vault.yml
  pre_tasks:
    - name: Show host info
      ansible.builtin.debug:
        msg: "Monitor-only play on {{ inventory_hostname }} ({{ ansible_host }}) — arch={{ beszel_arch }}"
  roles:
    - beszel-agent
```

---

## Phase 5 — Validation

### Task 5.1 — Syntax check

- [ ] **Step 1: Run**

```bash
cd ansible/
ansible-playbook --syntax-check playbook.yml --vault-password-file ~/.vault-password.txt
```
Expected: `playbook: playbook.yml`, exit 0.

### Task 5.2 — `--check` on k8s-node (must be near-no-op)

- [ ] **Step 1: Run**

```bash
cd ansible/
ansible-playbook -i inventory.yml playbook.yml \
  --vault-password-file ~/.vault-password.txt \
  --limit k8s-node --ask-become-pass \
  --check --diff
```

Expected: 0 failed, very few changes (the refactor should be a no-op since common-cli-tools installs the same things as the old 10_packages.yml).

### Task 5.3 — `--check` on work-laptop

- [ ] **Step 1: Run**

```bash
cd ansible/
ansible-playbook -i inventory.yml playbook.yml \
  --vault-password-file ~/.vault-password.txt \
  --limit work-laptop --ask-become-pass \
  --check --diff
```

Expected: 0 failed, many `changed` (new role applies all the dev tooling for the first time).

### Task 5.4 — Real run on work-laptop

- [ ] **Step 1: Run**

```bash
cd ansible/
ansible-playbook -i inventory.yml playbook.yml \
  --vault-password-file ~/.vault-password.txt \
  --limit work-laptop --ask-become-pass
```

Expected: `failed=0`, several `changed`.

### Task 5.5 — Smoke tests on work-laptop

- [ ] **Step 1: SSH and check**

```bash
ssh moi@192.168.88.211 'for cmd in jq dust gh code lazygit chezmoi uv ruff wezterm nano; do printf "%-12s " "$cmd"; which "$cmd" || echo MISSING; done'
ssh moi@192.168.88.211 'git config --global --get user.email; git config --global --get user.name; git config --global --get core.editor'
```

Expected: all commands found, git config matching defaults.

### Task 5.6 — Idempotence (2nd run = changed=0)

- [ ] **Step 1: Re-run**

```bash
cd ansible/
ansible-playbook -i inventory.yml playbook.yml \
  --vault-password-file ~/.vault-password.txt \
  --limit work-laptop --ask-become-pass
```

Expected: `changed=0`.

---

## Phase 6 — Doc & commit

### Task 6.1 — Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the Ansible section to mention the 3 roles**

In the section `### Ansible (déploiement multi-machines)`, update the "Rôles disponibles" list to include `common-cli-tools` and `dev-workstation`, and note the new `dev_workstations` group.

### Task 6.2 — Update TODO.md

**Files:**
- Modify: `TODO.md`

- [ ] **Step 1: Add entry under "Récemment terminé"**

```markdown
- [x] **Extension Ansible : dev-workstation + factor common-cli-tools**
  - Nouveau rôle `common-cli-tools` (factor des outils CLI partagés)
  - Nouveau rôle `dev-workstation` (pipx + uv/ruff, VS Code, lazygit, chezmoi, wezterm, git config)
  - Refactor `k8s-node-bootstrap` (suppression tasks/10_packages.yml + templates deb-get, déplacés)
  - Refactor `inventory.yml` (groupe `dev_workstations`) + `playbook.yml` (3 plays)
  - work-laptop (Linux Mint 22.3) ajouté + monitored par Beszel
  - Documentation : spec `2026-05-25-devworkstation-design.md` + plan `2026-05-25-devworkstation.md`
```

### Task 6.3 — Commit & push

- [ ] **Step 1: Stage and commit**

```bash
cd /data/projets/perso/my-kluster
git status --short
git add ansible/ CLAUDE.md TODO.md docs/superpowers/specs/2026-05-25-devworkstation-design.md docs/superpowers/plans/2026-05-25-devworkstation.md
git diff --stat --cached
git commit -m "$(cat <<'EOF'
feat(ansible): add common-cli-tools + dev-workstation roles

Factor shared CLI tooling between k8s-node-bootstrap and the new
dev-workstation role. work-laptop (Linux Mint 22.3) is now provisioned
via dev-workstation: pipx + uv/ruff, VS Code, lazygit, chezmoi, wezterm
(Fury apt repo), and a global git config with nano as editor.

Refactor:
- New role common-cli-tools holds the previous tasks/10_packages.yml
  content from k8s-node-bootstrap plus pipx.
- k8s-node-bootstrap drops the packages section; same effect via the
  playbook's role list now putting common-cli-tools before bootstrap.
- Inventory gains a dev_workstations group; playbook gains a third play
  for those hosts.
EOF
)"
git push
```

---

## Self-Review checklist

- [ ] All file paths exist in the structure section.
- [ ] No placeholders, all code blocks complete.
- [ ] `--check` passes on both k8s-node and work-laptop (Phases 5.2 and 5.3).
- [ ] Real run on work-laptop succeeds (Phase 5.4).
- [ ] All commands found via smoke test (Phase 5.5).
- [ ] Idempotence verified (Phase 5.6).
- [ ] CLAUDE.md mentions the 3 roles and the new group.
