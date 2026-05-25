# Ansible Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two Ansible roles to the `my-kluster` repo: `sealed-secrets-backup` (encrypted daily backup of the Sealed Secrets master key to NFS) and `k8s-node-bootstrap` (idempotent OS + MicroK8s + addons setup for the k8s-node machine).

**Architecture:** Two new role directories under `ansible/roles/`, an extended `inventory.yml` with a `k8s_nodes` group, and a 2-play `playbook.yml`. Backup uses `age` for asymmetric encryption + a systemd timer. Bootstrap is decomposed into 6 tagged sub-tasks for partial execution. Failures notify Telegram via direct Bot API call (no `shoutrrr` dependency).

**Tech Stack:** Ansible 2.16+, `community.general` and `ansible.posix` collections (already used in the repo), `age` (apt), `kubectl` (via snap microk8s alias), systemd timers, NFS v3 to NAS 192.168.88.103.

**Spec source:** `docs/superpowers/specs/2026-05-25-ansible-extension-design.md`

---

## File Structure

```
ansible/
├── ansible.cfg                              # unchanged
├── inventory.yml                            # MODIFY — add k8s_nodes group
├── playbook.yml                             # MODIFY — 2 plays
├── group_vars/
│   ├── all.yml                              # MODIFY — add sealed_backup_age_pubkey
│   └── vault.yml                            # MODIFY — add telegram bot+chat
└── roles/
    ├── beszel-agent/                        # unchanged
    │
    ├── sealed-secrets-backup/               # CREATE
    │   ├── defaults/main.yml
    │   ├── handlers/main.yml
    │   ├── tasks/main.yml
    │   └── templates/
    │       ├── backup.sh.j2
    │       ├── sealed-secrets-backup.service.j2
    │       ├── sealed-secrets-backup.timer.j2
    │       └── sealed-secrets-backup-notify.service.j2
    │
    └── k8s-node-bootstrap/                  # CREATE
        ├── defaults/main.yml
        ├── handlers/main.yml
        ├── tasks/
        │   ├── main.yml
        │   ├── 00_preflight.yml
        │   ├── 10_packages.yml
        │   ├── 20_nvidia.yml
        │   ├── 30_filesystem.yml
        │   ├── 40_microk8s.yml
        │   └── 50_gpu_operator.yml
        └── templates/
            ├── sysctl-homelab.conf.j2
            └── limits-homelab.conf.j2
```

CLAUDE.md & TODO.md update lives in the final phase (Task 8.1).

---

## Phase 0 — Human prerequisites (no Ansible)

These steps require the user; no subagent can perform them.

### Task 0.1 — Generate age keypair

- [ ] **Step 1: Install age locally if not already done**

Run:
```bash
sudo apt install age
age --version
```
Expected: `1.x.x`

- [ ] **Step 2: Generate keypair**

Run:
```bash
mkdir -p ~/.config/age
age-keygen -o ~/.config/age/sealed-backup.key
chmod 600 ~/.config/age/sealed-backup.key
```
Expected output ends with `Public key: age1...`

- [ ] **Step 3: Extract pubkey for use in group_vars**

Run:
```bash
grep "public key" ~/.config/age/sealed-backup.key
```
Copy the `age1...` string for use in Task 1.1.

- [ ] **Step 4: Back up the private key to 2 separate locations**

User decides where (password manager, USB stick, second machine). The private key is the only way to decrypt backups. Without it, every encrypted `.yaml.age` file is useless.

### Task 0.2 — Confirm Telegram bot token

- [ ] **Step 1: Confirm the current Telegram bot token used by Beszel**

Beszel was configured with a Telegram Shoutrrr URL. The same token will be reused by the Ansible failure notifier. User retrieves the token from his password manager (NOT from the chat). Chat ID is `843341688`.

---

## Phase 1 — Inventory & playbook refactor

### Task 1.1 — Add k8s_nodes group + age pubkey to group_vars/all.yml

**Files:**
- Modify: `ansible/inventory.yml`
- Modify: `ansible/group_vars/all.yml`

- [ ] **Step 1: Read current inventory.yml**

```bash
cat ansible/inventory.yml
```

- [ ] **Step 2: Rewrite inventory.yml with k8s_nodes group**

Replace the file content with:

```yaml
---
# Inventaire des machines monitorées par Beszel + bootstrap k8s-node.
# IPs en clair = LAN privé RFC1918, peu sensible. Pour ajouter une machine :
# 1) ajouter 3 lignes ci-dessous, 2) ansible-playbook ... --limit <nouveau-host>

all:
  children:
    # Machines qui hébergent un node Kubernetes — reçoivent les 3 rôles
    # (k8s-node-bootstrap, sealed-secrets-backup, beszel-agent).
    k8s_nodes:
      hosts:
        k8s-node:
          ansible_host: 192.168.88.250
          ansible_connection: local
          ansible_user: moi
          beszel_arch: amd64

  hosts:
    # Machines monitorées uniquement (pas k8s) — reçoivent seulement beszel-agent.
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

- [ ] **Step 3: Update group_vars/all.yml**

Append the following lines to `ansible/group_vars/all.yml`:

```yaml

# Age recipient public key used by sealed-secrets-backup role.
# Private key is OFF-MACHINE (password manager + USB).
# Generated via: age-keygen -o ~/.config/age/sealed-backup.key
sealed_backup_age_pubkey: "REPLACE_WITH_age1...string_from_task_0.1.step_3"
```

The user replaces the placeholder with the actual pubkey before running the playbook. The role asserts non-empty at preflight.

- [ ] **Step 4: Update vault.yml with telegram secrets**

Run (interactive):
```bash
ansible-vault edit ansible/group_vars/vault.yml --vault-password-file ~/.vault-password.txt
```

Add the following keys to the YAML:

```yaml
vault_telegram_bot_token: "<the bot token>"
vault_telegram_chat_id: "843341688"
```

Save and exit.

- [ ] **Step 5: Verify vault.yml is encrypted at rest**

Run:
```bash
head -1 ansible/group_vars/vault.yml
```
Expected: `$ANSIBLE_VAULT;1.1;AES256`

### Task 1.2 — Refactor playbook.yml for 2 plays

**Files:**
- Modify: `ansible/playbook.yml`

- [ ] **Step 1: Read current playbook.yml**

```bash
cat ansible/playbook.yml
```

- [ ] **Step 2: Rewrite playbook.yml**

Replace the file content with:

```yaml
---
# Playbook entry point.
# - Play 1 : tout sur les machines k8s (bootstrap OS + backups + agent monitoring)
# - Play 2 : juste l'agent Beszel sur les autres machines

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
    - k8s-node-bootstrap
    - sealed-secrets-backup
    - beszel-agent

- name: Deploy Beszel agents on other monitored machines
  hosts: all:!k8s_nodes
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

- [ ] **Step 3: Syntax-check the playbook**

Run:
```bash
cd ansible/
ansible-playbook --syntax-check playbook.yml
```
Expected: `playbook: playbook.yml` (no error).

Note: this will fail if the new roles don't exist yet — only do this step AFTER Phases 3 & 4 are done. For now skip; we'll syntax-check at the start of Phase 5.

---

## Phase 2 — Role: sealed-secrets-backup

### Task 2.1 — Create defaults/main.yml

**Files:**
- Create: `ansible/roles/sealed-secrets-backup/defaults/main.yml`

- [ ] **Step 1: Create file with content**

```yaml
---
# Default variables for sealed-secrets-backup role.
# Overridable via inventory or group_vars.

# Path on the local machine where the NFS share is mounted.
# Must be ensured by k8s-node-bootstrap (or manually mounted) before this role runs.
sealed_backup_nas_path: /mnt/nas/backups/sealed-secrets

# Number of backups to retain (oldest get pruned).
sealed_backup_keep: 30

# Hour of the day (0–23, machine local time) for the timer.
sealed_backup_hour: 3

# age recipient pubkey — OVERRIDE in group_vars/all.yml.
# Empty default triggers preflight assertion failure.
sealed_backup_age_pubkey: ""

# Where the backup script gets installed.
sealed_backup_script_path: /usr/local/bin/sealed-secrets-backup.sh
sealed_backup_service_name: sealed-secrets-backup
```

### Task 2.2 — Create handlers/main.yml

**Files:**
- Create: `ansible/roles/sealed-secrets-backup/handlers/main.yml`

- [ ] **Step 1: Create file with content**

```yaml
---
- name: reload systemd (sealed-secrets-backup)
  ansible.builtin.systemd:
    daemon_reload: true
```

### Task 2.3 — Create templates/backup.sh.j2

**Files:**
- Create: `ansible/roles/sealed-secrets-backup/templates/backup.sh.j2`

- [ ] **Step 1: Create file with content**

```bash
#!/usr/bin/env bash
# Managed by Ansible role sealed-secrets-backup. Do not edit by hand.
#
# Daily encrypted backup of the Bitnami Sealed Secrets master key.
# Uses age for asymmetric encryption — the private key is stored OFF-MACHINE.
# Skips if the master key hasn't changed since last successful backup.

set -euo pipefail

NAS_PATH="{{ sealed_backup_nas_path }}"
AGE_RECIPIENT="{{ sealed_backup_age_pubkey }}"
KEEP={{ sealed_backup_keep }}

mkdir -p "$NAS_PATH"

# Use snap microk8s kubectl since the role runs as root and the host's kubectl
# may not be in PATH for root. microk8s exports a working kubectl.
KUBECTL="microk8s.kubectl"
if ! command -v "$KUBECTL" >/dev/null; then
  KUBECTL="kubectl"
fi

# Export the active master key to a temp file
TMPFILE=$(mktemp /tmp/sealed-backup.XXXXXX.yaml)
trap 'rm -f "$TMPFILE" "${TMPFILE}.age"' EXIT

if ! $KUBECTL get secret -n kube-system \
       -l sealedsecrets.bitnami.com/sealed-secrets-key=active \
       -o yaml > "$TMPFILE"; then
  echo "Failed to fetch sealed-secrets master key via $KUBECTL" >&2
  exit 1
fi

# Verify the file has actual content (the label query can return an empty list).
if [ "$(grep -c '^kind: Secret' "$TMPFILE")" -lt 1 ]; then
  echo "kubectl returned no Secret with active sealed-secrets-key label" >&2
  exit 1
fi

# Compute checksum on the plaintext for dedup
NEW_SHA=$(sha256sum "$TMPFILE" | awk '{print $1}')

# Find last backup's sidecar .sha256 (if any) and compare
LAST=$(ls -1t "$NAS_PATH"/*.yaml.age 2>/dev/null | head -1 || true)
if [ -n "$LAST" ] && [ -f "${LAST%.yaml.age}.sha256" ]; then
  if [ "$NEW_SHA" = "$(cat "${LAST%.yaml.age}.sha256")" ]; then
    logger -t sealed-backup "No change in master key, skipping backup"
    exit 0
  fi
fi

# Encrypt and copy
TS=$(date +%Y-%m-%d_%H%M)
OUT="$NAS_PATH/${TS}.yaml.age"
age -r "$AGE_RECIPIENT" -o "${TMPFILE}.age" "$TMPFILE"
cp "${TMPFILE}.age" "$OUT"
chmod 644 "$OUT"
echo "$NEW_SHA" > "${OUT%.yaml.age}.sha256"

# Rotation : keep $KEEP most recent
ls -1t "$NAS_PATH"/*.yaml.age 2>/dev/null \
  | tail -n +$((KEEP + 1)) \
  | while read -r f; do
      rm -f "$f" "${f%.yaml.age}.sha256"
      logger -t sealed-backup "Pruned old backup: $f"
    done

logger -t sealed-backup "Backup successful: $OUT"
```

### Task 2.4 — Create templates/sealed-secrets-backup.service.j2

**Files:**
- Create: `ansible/roles/sealed-secrets-backup/templates/sealed-secrets-backup.service.j2`

- [ ] **Step 1: Create file with content**

```ini
[Unit]
Description=Encrypted backup of Sealed Secrets master key (age + NFS)
Documentation=file://{{ sealed_backup_script_path }}
After=network-online.target snap.microk8s.daemon-kubelite.service
Wants=network-online.target
OnFailure={{ sealed_backup_service_name }}-notify.service

[Service]
Type=oneshot
User=root
ExecStart={{ sealed_backup_script_path }}

# Hardening (allow file writes to NAS_PATH but otherwise minimal)
NoNewPrivileges=true
ProtectKernelTunables=true
ProtectControlGroups=true
ProtectKernelModules=true
```

### Task 2.5 — Create templates/sealed-secrets-backup.timer.j2

**Files:**
- Create: `ansible/roles/sealed-secrets-backup/templates/sealed-secrets-backup.timer.j2`

- [ ] **Step 1: Create file with content**

```ini
[Unit]
Description=Daily Sealed Secrets master key backup
Documentation=file://{{ sealed_backup_script_path }}

[Timer]
OnCalendar=*-*-* {{ sealed_backup_hour }}:00:00
RandomizedDelaySec=300
Persistent=true
Unit={{ sealed_backup_service_name }}.service

[Install]
WantedBy=timers.target
```

### Task 2.6 — Create templates/sealed-secrets-backup-notify.service.j2

**Files:**
- Create: `ansible/roles/sealed-secrets-backup/templates/sealed-secrets-backup-notify.service.j2`

- [ ] **Step 1: Create file with content**

```ini
[Unit]
Description=Send Telegram notification on sealed-secrets-backup failure

[Service]
Type=oneshot
ExecStart=/usr/bin/curl -fsS -o /dev/null -X POST \
  https://api.telegram.org/bot{{ vault_telegram_bot_token }}/sendMessage \
  --data-urlencode "chat_id={{ vault_telegram_chat_id }}" \
  --data-urlencode "text=⚠ sealed-secrets-backup failed on {{ ansible_hostname }} ({{ ansible_default_ipv4.address | default('?') }}) — check journalctl -u {{ sealed_backup_service_name }}.service"
```

### Task 2.7 — Create tasks/main.yml

**Files:**
- Create: `ansible/roles/sealed-secrets-backup/tasks/main.yml`

- [ ] **Step 1: Create file with content**

```yaml
---
# sealed-secrets-backup — daily encrypted backup of the Sealed Secrets master key.

- name: Preflight — sealed_backup_age_pubkey must be set
  ansible.builtin.assert:
    that:
      - sealed_backup_age_pubkey is defined
      - sealed_backup_age_pubkey | length > 0
      - sealed_backup_age_pubkey.startswith('age1')
    fail_msg: |
      sealed_backup_age_pubkey must be set in group_vars/all.yml.
      Generate it via:
        age-keygen -o ~/.config/age/sealed-backup.key
        grep "public key" ~/.config/age/sealed-backup.key

- name: Preflight — vault_telegram_bot_token must be set
  ansible.builtin.assert:
    that:
      - vault_telegram_bot_token is defined
      - vault_telegram_bot_token | length > 0
    fail_msg: "vault_telegram_bot_token must be set in vault.yml"

- name: Preflight — NAS mount point exists
  ansible.builtin.stat:
    path: "{{ sealed_backup_nas_path | dirname }}"
  register: nas_dirname_stat

- name: Preflight — NAS parent dir is mounted
  ansible.builtin.assert:
    that:
      - nas_dirname_stat.stat.exists
    fail_msg: |
      Parent of {{ sealed_backup_nas_path }} does not exist.
      Run k8s-node-bootstrap (filesystem tag) first, or mount the NAS manually.

- name: Ensure age is installed
  ansible.builtin.apt:
    name: age
    state: present
    update_cache: false

- name: Ensure backup destination exists
  ansible.builtin.file:
    path: "{{ sealed_backup_nas_path }}"
    state: directory
    mode: '0755'

- name: Install backup script
  ansible.builtin.template:
    src: backup.sh.j2
    dest: "{{ sealed_backup_script_path }}"
    owner: root
    group: root
    mode: '0750'

- name: Install systemd service unit
  ansible.builtin.template:
    src: sealed-secrets-backup.service.j2
    dest: "/etc/systemd/system/{{ sealed_backup_service_name }}.service"
    owner: root
    group: root
    mode: '0644'
  notify: reload systemd (sealed-secrets-backup)

- name: Install systemd timer unit
  ansible.builtin.template:
    src: sealed-secrets-backup.timer.j2
    dest: "/etc/systemd/system/{{ sealed_backup_service_name }}.timer"
    owner: root
    group: root
    mode: '0644'
  notify: reload systemd (sealed-secrets-backup)

- name: Install notify service unit (OnFailure trigger)
  ansible.builtin.template:
    src: sealed-secrets-backup-notify.service.j2
    dest: "/etc/systemd/system/{{ sealed_backup_service_name }}-notify.service"
    owner: root
    group: root
    mode: '0644'
  notify: reload systemd (sealed-secrets-backup)

- name: Flush handlers (so daemon-reload runs before enable/start)
  ansible.builtin.meta: flush_handlers

- name: Enable and start the timer
  ansible.builtin.systemd:
    name: "{{ sealed_backup_service_name }}.timer"
    enabled: true
    state: started
```

---

## Phase 3 — Role: k8s-node-bootstrap

### Task 3.1 — Create defaults/main.yml

**Files:**
- Create: `ansible/roles/k8s-node-bootstrap/defaults/main.yml`

- [ ] **Step 1: Create file with content**

```yaml
---
# Defaults for k8s-node-bootstrap role.

# MicroK8s
microk8s_channel: "1.31/stable"
microk8s_addons:
  - dns
  - ingress
  - hostpath-storage
  - registry
  - gpu
  - helm3

# NFS
nfs_server_ip: "192.168.88.103"
nfs_export: "/Public"
nfs_local_mount: "/mnt/nas"

# Sysctl
sysctl_max_map_count: 262144
sysctl_inotify_max_user_watches: 524288

# Feature flags
gpu_enabled: true

# Hostname guard (override if you renamed your machine)
k8s_node_expected_hostname: "pc"
```

### Task 3.2 — Create handlers/main.yml

**Files:**
- Create: `ansible/roles/k8s-node-bootstrap/handlers/main.yml`

- [ ] **Step 1: Create file with content**

```yaml
---
- name: reload sysctl
  ansible.builtin.command: sysctl --system
  changed_when: true

- name: reload systemd (k8s-node-bootstrap)
  ansible.builtin.systemd:
    daemon_reload: true
```

### Task 3.3 — Create tasks/main.yml (orchestration)

**Files:**
- Create: `ansible/roles/k8s-node-bootstrap/tasks/main.yml`

- [ ] **Step 1: Create file with content**

```yaml
---
# k8s-node-bootstrap — idempotent OS + MicroK8s setup.
# Decomposed by concern. Use --tags <name> to run partial sections.

- ansible.builtin.import_tasks: 00_preflight.yml
  tags: [bootstrap, preflight]

- ansible.builtin.import_tasks: 10_packages.yml
  tags: [bootstrap, packages]

- ansible.builtin.import_tasks: 20_nvidia.yml
  tags: [bootstrap, nvidia]
  when: gpu_enabled | default(true)

- ansible.builtin.import_tasks: 30_filesystem.yml
  tags: [bootstrap, filesystem]

- ansible.builtin.import_tasks: 40_microk8s.yml
  tags: [bootstrap, microk8s]

- ansible.builtin.import_tasks: 50_gpu_operator.yml
  tags: [bootstrap, gpu_operator]
  when: gpu_enabled | default(true)
```

### Task 3.4 — Create tasks/00_preflight.yml

**Files:**
- Create: `ansible/roles/k8s-node-bootstrap/tasks/00_preflight.yml`

- [ ] **Step 1: Create file with content**

```yaml
---
- name: Preflight — Ubuntu 24+ x86_64
  ansible.builtin.assert:
    that:
      - ansible_distribution == "Ubuntu"
      - ansible_distribution_major_version | int >= 24
      - ansible_architecture == "x86_64"
    fail_msg: "k8s-node-bootstrap requires Ubuntu 24+ x86_64 (got {{ ansible_distribution }} {{ ansible_distribution_version }} {{ ansible_architecture }})"

- name: Preflight — Hostname guard (anti-friendly-fire)
  ansible.builtin.assert:
    that:
      - ansible_hostname == k8s_node_expected_hostname
    fail_msg: |
      Refusing to run on host '{{ ansible_hostname }}' — this role is hardcoded for
      hostname='{{ k8s_node_expected_hostname }}'. If you really want to run elsewhere,
      override via -e 'k8s_node_expected_hostname={{ ansible_hostname }}'.

- name: Preflight — Free disk space on /
  ansible.builtin.command: df -BG --output=avail /
  register: free_root
  changed_when: false

- name: Preflight — Require 20G free
  ansible.builtin.assert:
    that:
      - (free_root.stdout_lines[1] | regex_replace('[^0-9]', '') | int) >= 20
    fail_msg: "Less than 20G free on / — refusing to install."
```

### Task 3.5 — Create tasks/10_packages.yml

**Files:**
- Create: `ansible/roles/k8s-node-bootstrap/tasks/10_packages.yml`

- [ ] **Step 1: Create file with content**

```yaml
---
- name: Install base APT packages
  ansible.builtin.apt:
    name:
      # Required by other roles / k8s
      - jq
      - curl
      - git
      - python3-kubernetes
      - age
      - nfs-common
      - ca-certificates
      - apt-transport-https
      - gnupg
      # User-confort CLI tools
      - htop
      - btop
      - ncdu
      - dust
      - ripgrep
      - fd-find
      - bat
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
```

### Task 3.6 — Create tasks/20_nvidia.yml

**Files:**
- Create: `ansible/roles/k8s-node-bootstrap/tasks/20_nvidia.yml`

- [ ] **Step 1: Create file with content**

```yaml
---
- name: Check for NVIDIA GPU presence
  ansible.builtin.command: lspci
  register: lspci_out
  changed_when: false

- name: Skip NVIDIA section if no GPU detected
  ansible.builtin.meta: end_play
  when: lspci_out.stdout is not search('NVIDIA')

- name: Ensure NVIDIA kernel driver is present (must be installed manually)
  ansible.builtin.command: nvidia-smi
  register: nvidia_smi
  changed_when: false
  failed_when: nvidia_smi.rc != 0

- name: Add NVIDIA Container Toolkit GPG key
  ansible.builtin.shell:
    cmd: |
      curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
        | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    creates: /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

- name: Add NVIDIA Container Toolkit APT repo
  ansible.builtin.apt_repository:
    repo: "deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://nvidia.github.io/libnvidia-container/stable/deb/{{ ansible_architecture | replace('x86_64', 'amd64') }} /"
    state: present
    filename: nvidia-container-toolkit
    update_cache: true

- name: Install nvidia-container-toolkit
  ansible.builtin.apt:
    name: nvidia-container-toolkit
    state: present

- name: Enable nvidia-persistenced (reduce CUDA wake-up latency)
  ansible.builtin.systemd:
    name: nvidia-persistenced
    enabled: true
    state: started
```

### Task 3.7 — Create tasks/30_filesystem.yml + templates

**Files:**
- Create: `ansible/roles/k8s-node-bootstrap/tasks/30_filesystem.yml`
- Create: `ansible/roles/k8s-node-bootstrap/templates/sysctl-homelab.conf.j2`
- Create: `ansible/roles/k8s-node-bootstrap/templates/limits-homelab.conf.j2`

- [ ] **Step 1: Create 30_filesystem.yml**

```yaml
---
- name: Ensure NFS mount directory exists
  ansible.builtin.file:
    path: "{{ nfs_local_mount }}"
    state: directory
    mode: '0755'

- name: Mount NAS NFS share
  ansible.posix.mount:
    src: "{{ nfs_server_ip }}:{{ nfs_export }}"
    path: "{{ nfs_local_mount }}"
    fstype: nfs
    opts: "defaults,_netdev,rsize=1048576,wsize=1048576"
    state: mounted

- name: Configure sysctl for k8s + ML workloads
  ansible.builtin.template:
    src: sysctl-homelab.conf.j2
    dest: /etc/sysctl.d/99-homelab.conf
    owner: root
    group: root
    mode: '0644'
  notify: reload sysctl

- name: Configure ulimits for k8s + ML workloads
  ansible.builtin.template:
    src: limits-homelab.conf.j2
    dest: /etc/security/limits.d/99-homelab.conf
    owner: root
    group: root
    mode: '0644'
```

- [ ] **Step 2: Create sysctl-homelab.conf.j2**

```
# Managed by Ansible role k8s-node-bootstrap. Do not edit by hand.
vm.max_map_count = {{ sysctl_max_map_count }}
fs.inotify.max_user_watches = {{ sysctl_inotify_max_user_watches }}
net.bridge.bridge-nf-call-iptables = 1
net.ipv4.ip_forward = 1
```

- [ ] **Step 3: Create limits-homelab.conf.j2**

```
# Managed by Ansible role k8s-node-bootstrap. Do not edit by hand.
*       soft    nofile  65536
*       hard    nofile  65536
```

### Task 3.8 — Create tasks/40_microk8s.yml

**Files:**
- Create: `ansible/roles/k8s-node-bootstrap/tasks/40_microk8s.yml`

- [ ] **Step 1: Create file with content**

```yaml
---
- name: Install microk8s via snap
  community.general.snap:
    name: microk8s
    classic: true
    channel: "{{ microk8s_channel }}"
    state: present

- name: Add user to microk8s group
  ansible.builtin.user:
    name: "{{ ansible_user }}"
    groups: microk8s
    append: true

- name: Wait for microk8s ready
  ansible.builtin.command: microk8s status --wait-ready --timeout=120
  changed_when: false

- name: Get currently enabled addons
  ansible.builtin.command: microk8s status --format yaml
  register: mk8s_status
  changed_when: false

- name: Enable each microk8s addon if not already enabled
  ansible.builtin.command: "microk8s enable {{ item }}"
  loop: "{{ microk8s_addons }}"
  register: enable_result
  changed_when: "'is already enabled' not in enable_result.stdout"
  failed_when:
    - enable_result.rc != 0
    - "'is already enabled' not in enable_result.stdout"

- name: Ensure ~/.kube directory exists for user
  ansible.builtin.file:
    path: "/home/{{ ansible_user }}/.kube"
    state: directory
    owner: "{{ ansible_user }}"
    group: "{{ ansible_user }}"
    mode: '0700'

- name: Check if kubectl config exists
  ansible.builtin.stat:
    path: "/home/{{ ansible_user }}/.kube/config"
  register: kubeconfig_stat

- name: Export microk8s config to user kubeconfig
  ansible.builtin.shell:
    cmd: |
      microk8s config > /home/{{ ansible_user }}/.kube/config
      chown {{ ansible_user }}:{{ ansible_user }} /home/{{ ansible_user }}/.kube/config
      chmod 600 /home/{{ ansible_user }}/.kube/config
  when: not kubeconfig_stat.stat.exists
```

### Task 3.9 — Create tasks/50_gpu_operator.yml

**Files:**
- Create: `ansible/roles/k8s-node-bootstrap/tasks/50_gpu_operator.yml`

- [ ] **Step 1: Create file with content**

```yaml
---
# Workaround NVIDIA gpu-operator issue #430:
# the validator daemonset re-creates /dev/char/ symlinks that already exist
# in MicroK8s' GPU addon → infinite restart loop.
# Setting DISABLE_DEV_CHAR_SYMLINK_CREATION=true fixes it.

- name: Wait for ClusterPolicy CRD to become available
  ansible.builtin.command: kubectl get clusterpolicy -n gpu-operator-resources
  register: cp_check
  retries: 30
  delay: 10
  until: cp_check.rc == 0
  changed_when: false
  become: false

- name: Get name of ClusterPolicy resource
  ansible.builtin.shell: kubectl get clusterpolicy -n gpu-operator-resources -o name | head -1
  register: cp_name
  changed_when: false
  become: false

- name: Get current value of DISABLE_DEV_CHAR_SYMLINK_CREATION
  ansible.builtin.shell:
    cmd: |
      kubectl get {{ cp_name.stdout }} -n gpu-operator-resources -o json \
        | jq -r '.spec.validator.driver.env[]? | select(.name=="DISABLE_DEV_CHAR_SYMLINK_CREATION") | .value' \
        || echo "absent"
  register: current_val
  changed_when: false
  become: false

- name: Apply DISABLE_DEV_CHAR_SYMLINK_CREATION=true workaround
  when: current_val.stdout != "true"
  become: false
  ansible.builtin.command: >
    kubectl patch {{ cp_name.stdout }}
    -n gpu-operator-resources --type=merge -p
    '{"spec":{"validator":{"driver":{"env":[{"name":"DISABLE_DEV_CHAR_SYMLINK_CREATION","value":"true"}]}}}}'
```

---

## Phase 4 — Validation in --check mode

### Task 4.1 — Syntax-check the playbook

- [ ] **Step 1: From the ansible/ directory**

```bash
cd /data/projets/perso/my-kluster/ansible/
ansible-playbook --syntax-check playbook.yml
```
Expected: `playbook: playbook.yml` and exit 0.

### Task 4.2 — Verify required collections

- [ ] **Step 1: Check community.general snap module**

```bash
ansible-doc community.general.snap | head -5
```
Expected: shows the module description.

- [ ] **Step 2: Check ansible.posix.mount module**

```bash
ansible-doc ansible.posix.mount | head -5
```
Expected: shows the module description.

If either is missing, install:
```bash
ansible-galaxy collection install community.general ansible.posix
```

### Task 4.3 — Dry-run with --check --diff

- [ ] **Step 1: Full dry-run on k8s-node**

```bash
cd /data/projets/perso/my-kluster/ansible/
ansible-playbook -i inventory.yml playbook.yml \
  --vault-password-file ~/.vault-password.txt \
  --limit k8s-node \
  --ask-become-pass \
  --check --diff
```

Expected behavior: Ansible reports many "changed" lines (templates will be created, units installed, etc.) but no error. On the machine that's ALREADY been set up manually, some tasks may legitimately want to change things (e.g., the sysctl template is new). That's expected on first run.

- [ ] **Step 2: Review the --check output**

Read through and look for:
- ❌ Any `FAILED!` line.
- ⚠ Any unexpected "changed" on things like the snap microk8s install (it should be `ok`, not `changed`, on an already-installed system).
- ⚠ The `microk8s enable` loop should be all `ok` (not changed) if addons are already enabled.

If anything blocks, fix the role tasks before proceeding to real execution.

---

## Phase 5 — Real execution (tagged + isolated)

We don't run everything at once. We test piece by piece.

### Task 5.1 — Run the filesystem tag first

This sets up the NFS mount that backups depend on.

- [ ] **Step 1: Run with --tags filesystem only**

```bash
cd /data/projets/perso/my-kluster/ansible/
ansible-playbook -i inventory.yml playbook.yml \
  --vault-password-file ~/.vault-password.txt \
  --limit k8s-node \
  --ask-become-pass \
  --tags filesystem
```

Expected: `PLAY RECAP` shows ok and changed counts; failed=0. NFS is mounted on /mnt/nas.

- [ ] **Step 2: Verify mount**

```bash
mount | grep /mnt/nas
ls /mnt/nas/ | head -5
```
Expected: NFS line is shown, and the NAS root is readable.

### Task 5.2 — Run the sealed-secrets-backup role in isolation

This installs the systemd timer but doesn't trigger an immediate backup.

- [ ] **Step 1: Run with the role's natural tag (we use `--tags sealed-secrets-backup` if added, or run the whole playbook limiting to the role's tasks via task tag)**

Note: the role doesn't have explicit tags. To run only this role, use a temporary `--start-at-task`. Simpler: just run everything and check.

```bash
cd /data/projets/perso/my-kluster/ansible/
ansible-playbook -i inventory.yml playbook.yml \
  --vault-password-file ~/.vault-password.txt \
  --limit k8s-node \
  --ask-become-pass \
  --skip-tags bootstrap
```

`--skip-tags bootstrap` skips the k8s-node-bootstrap role (all its tasks are tagged `bootstrap`). The sealed-secrets-backup and beszel-agent roles have no `bootstrap` tag so they run.

Expected: changed lines for the new service / timer / script. Failed=0.

- [ ] **Step 2: Trigger a manual backup**

```bash
sudo systemctl start sealed-secrets-backup.service
sudo systemctl status sealed-secrets-backup.service
```
Expected: status `succeeded` (one-shot finished cleanly).

- [ ] **Step 3: Verify backup file on NAS**

```bash
ls -la /mnt/nas/backups/sealed-secrets/
```
Expected: at least one `YYYY-MM-DD_HHMM.yaml.age` + matching `.sha256`.

- [ ] **Step 4: Try decrypting (proves the keypair works end-to-end)**

```bash
LATEST=$(ls -1t /mnt/nas/backups/sealed-secrets/*.yaml.age | head -1)
age -d -i ~/.config/age/sealed-backup.key "$LATEST" | head -20
```
Expected: a valid YAML starting with `apiVersion:`, `kind: List` or `kind: Secret`, etc.

- [ ] **Step 5: Verify timer scheduling**

```bash
systemctl list-timers sealed-secrets-backup.timer
```
Expected: next trigger at 03h00 ± 5 min.

### Task 5.3 — Run the k8s-node-bootstrap role (idempotent check first)

The machine is already configured manually — this run should be mostly `ok`, with `changed` only on templates/scripts the role introduces (sysctl-homelab.conf, limits-homelab.conf, etc.).

- [ ] **Step 1: Run with --check first**

```bash
cd /data/projets/perso/my-kluster/ansible/
ansible-playbook -i inventory.yml playbook.yml \
  --vault-password-file ~/.vault-password.txt \
  --limit k8s-node \
  --ask-become-pass \
  --tags bootstrap \
  --check --diff
```

- [ ] **Step 2: Review the diff**

Expected `changed`:
- `/etc/sysctl.d/99-homelab.conf` (new file)
- `/etc/security/limits.d/99-homelab.conf` (new file)
- Maybe a few APT packages if `btop`/`dust`/`ripgrep`/`fd-find`/`bat` aren't installed

Expected `ok` (already configured):
- `microk8s` snap (already installed)
- Each addon `enable` (already enabled — must show as `ok`)
- NFS mount (already mounted)

If diff reveals unexpected destructive changes (e.g., trying to recreate kubeconfig that already exists, or trying to remove existing sysctl settings), STOP and fix the role.

- [ ] **Step 3: Apply for real if --check looked clean**

```bash
cd /data/projets/perso/my-kluster/ansible/
ansible-playbook -i inventory.yml playbook.yml \
  --vault-password-file ~/.vault-password.txt \
  --limit k8s-node \
  --ask-become-pass \
  --tags bootstrap
```

- [ ] **Step 4: Verify sysctl is loaded**

```bash
sysctl vm.max_map_count fs.inotify.max_user_watches net.bridge.bridge-nf-call-iptables
```
Expected: shows the values from the role.

### Task 5.4 — Run the full playbook to verify global idempotence

- [ ] **Step 1: Full run**

```bash
cd /data/projets/perso/my-kluster/ansible/
ansible-playbook -i inventory.yml playbook.yml \
  --vault-password-file ~/.vault-password.txt \
  --limit k8s-node \
  --ask-become-pass
```

Expected: many `ok`, few or zero `changed`, failed=0, unreachable=0.

- [ ] **Step 2: Re-run immediately — should be 100% ok=N, changed=0**

```bash
ansible-playbook -i inventory.yml playbook.yml \
  --vault-password-file ~/.vault-password.txt \
  --limit k8s-node \
  --ask-become-pass
```
Expected `changed=0`. If anything still reports changed on the 2nd run, that task is not idempotent — fix it.

---

## Phase 6 — Documentation update

### Task 6.1 — Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Find the existing Ansible section**

```bash
grep -n "Ansible (déploiement multi-machines)" CLAUDE.md
```
Expected: a single match.

- [ ] **Step 2: Replace that section**

Find the section starting with `### Ansible (déploiement multi-machines)` (added during the Beszel work). Replace its body with:

```markdown
### Ansible (déploiement multi-machines)

- Dossier : `ansible/` du repo.
- Inventaire : `ansible/inventory.yml`. Groupe `k8s_nodes` (juste `k8s-node` aujourd'hui) reçoit le pack complet bootstrap+backup+monitoring. Les autres machines ne reçoivent que `beszel-agent`.
- Secrets chiffrés via Ansible Vault dans `ansible/group_vars/vault.yml` (password local en `~/.vault-password.txt`, jamais commité).
- Variables non-sensibles dans `ansible/group_vars/all.yml` (dont la pubkey `age` `sealed_backup_age_pubkey`).
- Commande pleine : `cd ansible/ && ansible-playbook -i inventory.yml playbook.yml --vault-password-file ~/.vault-password.txt --ask-become-pass`.
- Exécution partielle via tags : `--tags bootstrap` (k8s-node-bootstrap), `--tags filesystem` ou `--tags microk8s` (sous-étapes), `--skip-tags bootstrap` (juste backup + beszel).
- Ajout machine monitorée : éditer `inventory.yml` (hors `k8s_nodes`), runner avec `--limit <nouveau-host>`.

Rôles disponibles :
- `beszel-agent` : install/update agent Beszel.
- `sealed-secrets-backup` : backup quotidien chiffré (age) de la clé master Sealed Secrets vers NAS, notification Telegram en cas d'échec.
- `k8s-node-bootstrap` : install OS + drivers NVIDIA toolkit + mount NFS + sysctl + MicroK8s + addons + workaround gpu-operator #430. Idempotent. Garde-fou hostname.

**Disaster recovery — clé master Sealed Secrets** :
Les backups sont sur `192.168.88.103:/Public/backups/sealed-secrets/` (chiffrés `.yaml.age`). La clé privée `age` correspondante (`~/.config/age/sealed-backup.key`) est **CRITIQUE** : sans elle les backups sont inutilisables. À conserver hors-machine (password manager + clé USB).

Procédure de restore (machine fraîchement bootstrappée) :
```bash
age -d -i ~/.config/age/sealed-backup.key \
  /mnt/nas/backups/sealed-secrets/<latest>.yaml.age | kubectl apply -f -
```
```

- [ ] **Step 3: Verify the section is well-placed and not duplicated**

```bash
grep -c "### Ansible (déploiement multi-machines)" CLAUDE.md
```
Expected: `1`.

### Task 6.2 — Update TODO.md

**Files:**
- Modify: `TODO.md`

- [ ] **Step 1: Add entry to "Récemment terminé"**

Insert at the top of the `## ✅ Récemment terminé (mai 2026)` section (after the Beszel entry):

```markdown

- [x] **Extension Ansible : disaster recovery + bootstrap**
  - Rôle `sealed-secrets-backup` : backup quotidien chiffré (`age`) de la clé master Sealed Secrets vers NAS, alerte Telegram on failure
  - Rôle `k8s-node-bootstrap` : install OS + drivers NVIDIA toolkit + mounts NFS + sysctl + MicroK8s + addons + workaround gpu-operator NVIDIA #430, idempotent, garde-fou hostname
  - Refactor `inventory.yml` (groupe `k8s_nodes`) + `playbook.yml` (2 plays)
  - Documentation : spec `2026-05-25-ansible-extension-design.md` + plan `2026-05-25-ansible-extension.md`
```

---

## Phase 7 — Commit & push

### Task 7.1 — Stage and commit

- [ ] **Step 1: Review git status**

```bash
git status --short
```
Expected files modified/created :
- `ansible/inventory.yml` (modified)
- `ansible/playbook.yml` (modified)
- `ansible/group_vars/all.yml` (modified)
- `ansible/group_vars/vault.yml` (modified — but still encrypted at rest)
- `ansible/roles/sealed-secrets-backup/` (new dir, ~7 files)
- `ansible/roles/k8s-node-bootstrap/` (new dir, ~12 files)
- `CLAUDE.md` (modified)
- `TODO.md` (modified)
- `docs/superpowers/specs/2026-05-25-ansible-extension-design.md` (new)
- `docs/superpowers/plans/2026-05-25-ansible-extension.md` (new)

- [ ] **Step 2: Verify vault.yml is encrypted**

```bash
head -1 ansible/group_vars/vault.yml
```
Expected: `$ANSIBLE_VAULT;1.1;AES256` — if it's not, ABORT and re-encrypt before committing.

- [ ] **Step 3: Verify pre-commit hooks pass on a dry run**

```bash
pre-commit run --files ansible/group_vars/vault.yml ansible/group_vars/all.yml
```
Expected: gitleaks passes (vault is encrypted, all.yml has only a non-sensitive age pubkey).

- [ ] **Step 4: Stage & commit**

```bash
git add ansible/ CLAUDE.md TODO.md docs/superpowers/
git commit -m "$(cat <<'EOF'
feat(ansible): add sealed-secrets-backup + k8s-node-bootstrap roles

- sealed-secrets-backup: daily age-encrypted backup of Bitnami Sealed
  Secrets master key to NFS, with Telegram failure notifications via
  systemd OnFailure.
- k8s-node-bootstrap: idempotent OS + NVIDIA toolkit + NFS + sysctl +
  MicroK8s + addons + gpu-operator workaround setup, decomposed into
  6 tagged sub-tasks. Hostname guard prevents accidental runs.
- Inventory refactor: k8s_nodes group separates bootstrap-targets from
  monitor-only machines.
EOF
)"
```

- [ ] **Step 5: Push**

```bash
git push
```

---

## Self-Review checklist

- [ ] All file paths exist in the structure section.
- [ ] Every task has full code snippets (no TBD, no "similar to N").
- [ ] Idempotence verified at Task 5.4 (full re-run shows `changed=0`).
- [ ] Vault stays encrypted at commit time.
- [ ] Hostname guard is overridable (cf. `-e k8s_node_expected_hostname=...`).
- [ ] Backup encryption works end-to-end (Task 5.2 step 4 decryption test).
- [ ] Failure notification path exists (Task 2.6 + service `OnFailure=`).
