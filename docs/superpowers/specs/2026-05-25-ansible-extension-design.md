# Extension Ansible : sealed-secrets-backup + k8s-node-bootstrap — Design

**Date** : 2026-05-25
**Auteur** : Thomas Guyader (laboitatom@gmail.com)
**Statut** : Approuvé pour implémentation
**Spec parente** : aucune (extension du périmètre Ansible déjà initié par `2026-05-24-beszel-monitoring-design.md`)

---

## 1. Contexte et motivation

Le périmètre Ansible actuel du repo `my-kluster` couvre uniquement le déploiement de l'agent Beszel sur les machines monitorées (rôle `beszel-agent`). Deux besoins sont apparus :

1. **Disaster recovery** — Si la machine k8s-node est perdue (panne disque système, vol, incendie), la clé master Sealed Secrets de Bitnami est perdue, et **tous les secrets chiffrés du repo deviennent indéchiffrables**. Pas de rebuild possible sans cette clé. Le backup manuel actuel (manuel, ad-hoc) est insuffisant : rotation auto tous les 30j → un backup mensuel laisse jusqu'à 30j de SealedSecrets non-déchiffrables après rebuild.

2. **Reproductibilité de la machine** — Le k8s-node a accumulé de la configuration manuelle (snap MicroK8s + addons, drivers NVIDIA, workaround GPU operator, mounts NFS, sysctl). Si on doit rebuilder cette machine, on perdrait des heures à retrouver chaque étape. La doc CLAUDE.md décrit la procédure mais n'est ni exécutable ni testable.

L'extension Ansible adresse ces deux problèmes via deux rôles distincts mais complémentaires.

---

## 2. Objectifs

- **O1** : Automatiser le backup chiffré quotidien de la clé master Sealed Secrets vers le NAS, avec notification en cas d'échec.
- **O2** : Permettre de bootstrapper l'état OS + MicroK8s + addons du k8s-node depuis une install Ubuntu vierge en une seule commande `ansible-playbook`.
- **O3** : Garder la séparation Ansible / GitOps : Ansible gère l'OS et les services système ; ArgoCD gère les workloads k8s.
- **O4** : Tout doit être idempotent (relances sans effet de bord).

## 3. Non-objectifs

- Pas de bootstrap ArgoCD (déjà documenté manuellement dans CLAUDE.md § *Initialisation du cluster*).
- Pas de restore des SealedSecrets de Git → l'app ArgoCD `sealed` s'en charge automatiquement une fois ArgoCD installé.
- Pas de provisioning d'OS (partitionnement, kernel, network) — l'OS Ubuntu doit être installé manuellement avant.
- Pas de SSH hardening / fail2ban / firewall — hors scope (à faire dans un futur rôle dédié si besoin).
- Pas de support multi-node — YAGNI, l'utilisateur n'a qu'une machine k8s.

---

## 4. Architecture

### 4.1 Vue d'ensemble

```
┌──────────────────────────────────────────────────────────────────┐
│                         k8s-node (pc, 192.168.88.250)            │
│                                                                  │
│  ┌─────────────────────────┐    ┌─────────────────────────────┐  │
│  │ k8s-node-bootstrap      │    │ sealed-secrets-backup       │  │
│  │ (one-shot, manuel)      │    │ (cron quotidien, automatic) │  │
│  │                         │    │                             │  │
│  │ • APT packages          │    │ • systemd timer 03h00       │  │
│  │ • NVIDIA drivers + PM   │    │ • kubectl get sealed-secret │  │
│  │ • Mounts NFS            │    │ • Skip si checksum=last     │  │
│  │ • Sysctl + limits       │    │ • age -r <pub> -e -o ...    │  │
│  │ • Snap microk8s + addons│    │ • cp vers /mnt/nas          │  │
│  │ • Workaround gpu-op #430│    │ • rotation 30 derniers      │  │
│  │ • User groupe microk8s  │    │ • erreur → Telegram         │  │
│  └─────────────────────────┘    └─────────────────────────────┘  │
│                                              │                   │
│                                              ▼                   │
└──────────────────────────────────────────────┼───────────────────┘
                                               │ NFS
                                               ▼
                                ┌──────────────────────────────┐
                                │ NAS 192.168.88.103           │
                                │ /Public/backups/             │
                                │   sealed-secrets/            │
                                │     2026-05-25_0300.yaml.age │
                                │     2026-05-24_0300.yaml.age │
                                │     ... (30 derniers)        │
                                └──────────────────────────────┘
```

### 4.2 Organisation Ansible

```
ansible/
├── ansible.cfg
├── inventory.yml                            # Étendu : groupe k8s_nodes
├── playbook.yml                             # Étendu : 2 plays
├── group_vars/
│   ├── all.yml
│   └── vault.yml                            # Étendu : telegram_shoutrrr_url
└── roles/
    ├── beszel-agent/                        # existant — inchangé
    ├── k8s-node-bootstrap/                  # NEW
    │   ├── defaults/main.yml
    │   ├── handlers/main.yml
    │   ├── tasks/
    │   │   ├── main.yml
    │   │   ├── 00_preflight.yml
    │   │   ├── 10_packages.yml
    │   │   ├── 20_nvidia.yml
    │   │   ├── 30_filesystem.yml
    │   │   ├── 40_microk8s.yml
    │   │   └── 50_gpu_operator.yml
    │   └── templates/
    │       ├── sysctl-homelab.conf.j2
    │       ├── limits-homelab.conf.j2
    │       └── nvidia-persistence.service.j2
    └── sealed-secrets-backup/               # NEW
        ├── defaults/main.yml
        ├── handlers/main.yml
        ├── tasks/main.yml
        └── templates/
            ├── backup.sh.j2
            ├── sealed-secrets-backup.service.j2
            └── sealed-secrets-backup.timer.j2
```

### 4.3 Playbook étendu

```yaml
# playbook.yml
---
- name: Bootstrap & monitor k8s-node
  hosts: k8s_nodes
  become: true
  vars_files:
    - group_vars/vault.yml
  pre_tasks:
    - name: Show host info
      ansible.builtin.debug:
        msg: "Running on {{ inventory_hostname }} ({{ ansible_host }}) — arch={{ beszel_arch }}"
  roles:
    - k8s-node-bootstrap
    - sealed-secrets-backup
    - beszel-agent

- name: Deploy Beszel agents on other monitored machines
  hosts: all:!k8s_nodes
  become: true
  vars_files:
    - group_vars/vault.yml
  roles:
    - beszel-agent
```

### 4.4 Inventaire étendu

```yaml
# inventory.yml
---
all:
  children:
    k8s_nodes:
      hosts:
        k8s-node:
          ansible_host: 192.168.88.250
          ansible_connection: local
          ansible_user: moi
          beszel_arch: amd64

  hosts:
    # Futures machines monitorées uniquement (commenté pour l'instant)
    # ha-host:
    #   ansible_host: 192.168.88.200
    #   ansible_user: hass
    #   beszel_arch: amd64

  vars:
    ansible_ssh_common_args: '-o StrictHostKeyChecking=no'
```

---

## 5. Rôle `sealed-secrets-backup`

### 5.1 Spécification fonctionnelle

| Aspect | Choix |
|---|---|
| **Fréquence** | Quotidien à 03h00 (heure locale machine) |
| **Source** | `kubectl get secret -n kube-system -l sealedsecrets.bitnami.com/sealed-secrets-key=active -o yaml` |
| **Déduplication** | SHA256 sur la sortie kubectl, comparé au précédent. Skip si identique. |
| **Chiffrement** | `age` avec recipient unique. Clé privée jamais sur la machine source. |
| **Destination** | NFS mount `/mnt/nas/backups/sealed-secrets/` |
| **Format nom** | `YYYY-MM-DD_HHMM.yaml.age` (ex: `2026-05-25_0300.yaml.age`) |
| **Rétention** | 30 derniers fichiers ; suppression des plus anciens. |
| **Failure mode** | Notification Telegram via webhook Shoutrrr (réutilise la conf Beszel). Exit code ≠ 0 → systemd marque la unit failed → visible dans `systemctl status`. |

### 5.2 Script `backup.sh.j2`

Logique :

```bash
#!/usr/bin/env bash
set -euo pipefail

NAS_PATH="{{ sealed_backup_nas_path }}"
AGE_RECIPIENT="{{ sealed_backup_age_pubkey }}"
KEEP={{ sealed_backup_keep }}
SHOUTRRR_URL="{{ vault_telegram_shoutrrr_url }}"

# Export la clé courante
TMPFILE=$(mktemp /tmp/sealed-backup.XXXXXX.yaml)
trap 'rm -f "$TMPFILE" "$TMPFILE".age' EXIT

kubectl get secret -n kube-system \
  -l sealedsecrets.bitnami.com/sealed-secrets-key=active \
  -o yaml > "$TMPFILE"

# Skip si checksum identique au dernier
LAST=$(ls -1t "$NAS_PATH"*.yaml.age 2>/dev/null | head -1 || true)
if [ -n "$LAST" ] && [ -f "$LAST" ]; then
  # On compare le contenu décrypté n'est pas possible (pas la clé privée ici)
  # → on stocke un sidecar sha256 à côté du backup
  LAST_SHA="${LAST%.yaml.age}.sha256"
  if [ -f "$LAST_SHA" ] && [ "$(sha256sum < "$TMPFILE" | cut -d' ' -f1)" = "$(cat "$LAST_SHA")" ]; then
    logger -t sealed-backup "No change in master key, skipping backup"
    exit 0
  fi
fi

# Chiffre et copie
TS=$(date +%Y-%m-%d_%H%M)
OUT="$NAS_PATH/${TS}.yaml.age"
age -r "$AGE_RECIPIENT" -o "$TMPFILE.age" "$TMPFILE"
cp "$TMPFILE.age" "$OUT"
sha256sum < "$TMPFILE" | cut -d' ' -f1 > "${OUT%.yaml.age}.sha256"

# Rotation : garde KEEP derniers
ls -1t "$NAS_PATH"/*.yaml.age 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r f; do
  rm -f "$f" "${f%.yaml.age}.sha256"
done

logger -t sealed-backup "Backup successful: $OUT"
```

Notification en cas d'échec : la unit systemd a `OnFailure=sealed-secrets-backup-notify.service` qui lance un curl vers Shoutrrr (cf. 5.3).

### 5.3 systemd units

**`sealed-secrets-backup.service.j2`** (oneshot) :
```ini
[Unit]
Description=Encrypted backup of Sealed Secrets master key
After=network-online.target {{ nfs_local_mount | replace('/', '-') | regex_replace('^-', '') }}.mount
Wants=network-online.target
OnFailure=sealed-secrets-backup-notify.service

[Service]
Type=oneshot
User=root
ExecStart=/usr/local/bin/sealed-secrets-backup.sh
```

**`sealed-secrets-backup.timer.j2`** :
```ini
[Unit]
Description=Daily Sealed Secrets master key backup

[Timer]
OnCalendar=*-*-* {{ sealed_backup_hour }}:00:00
RandomizedDelaySec=300
Persistent=true

[Install]
WantedBy=timers.target
```

**`sealed-secrets-backup-notify.service.j2`** (one-shot, triggered on failure) :
```ini
[Unit]
Description=Notify Telegram about sealed-secrets-backup failure

[Service]
Type=oneshot
ExecStart=/usr/bin/curl -fsS -X POST \
  -d 'message=⚠ sealed-secrets-backup failed on {{ ansible_hostname }} at %H' \
  '{{ vault_telegram_shoutrrr_failure_webhook_url }}'
```

Note : pour réutiliser le webhook Beszel Shoutrrr (qui est une URL `telegram://...`), on a deux choix :
- (a) installer `shoutrrr` CLI sur la machine et l'utiliser ici : `shoutrrr send -u '$URL' -m '...'`
- (b) utiliser directement l'API Telegram avec token + chat_id (sans dépendance shoutrrr)

**Décision : (b)** — moins de dépendances. La variable vault contiendra séparément le token et le chat_id :
```yaml
# vault.yml
vault_telegram_bot_token: "..."
vault_telegram_chat_id: "843341688"
```

Et le service :
```ini
ExecStart=/usr/bin/curl -fsS -X POST \
  https://api.telegram.org/bot{{ vault_telegram_bot_token }}/sendMessage \
  -d chat_id={{ vault_telegram_chat_id }} \
  -d text=⚠ sealed-secrets-backup failed on {{ ansible_hostname }}
```

### 5.4 Variables (defaults/main.yml)

```yaml
---
sealed_backup_nas_path: /mnt/nas/backups/sealed-secrets
sealed_backup_keep: 30
sealed_backup_hour: 3
sealed_backup_age_pubkey: ""   # OVERRIDE OBLIGATOIRE via inventory/group_vars
sealed_backup_script_path: /usr/local/bin/sealed-secrets-backup.sh
sealed_backup_service_name: sealed-secrets-backup
```

`sealed_backup_age_pubkey` doit être set en var globale (group_vars/all.yml) ou par-host. Pas de défaut → si vide, le rôle fail au preflight assertion.

### 5.5 Actions humaines requises

Avant d'exécuter le rôle pour la première fois :

1. **Installer `age`** (si pas déjà fait par `k8s-node-bootstrap`) : `sudo apt install age`.
2. **Générer la paire age** :
   ```bash
   mkdir -p ~/.config/age
   age-keygen -o ~/.config/age/sealed-backup.key
   chmod 600 ~/.config/age/sealed-backup.key
   ```
3. **Extraire la pubkey** et la mettre dans `group_vars/all.yml` :
   ```bash
   grep "public key" ~/.config/age/sealed-backup.key
   # → # public key: age1...
   ```
   Ajouter à `group_vars/all.yml` :
   ```yaml
   sealed_backup_age_pubkey: "age1abc...xyz"
   ```
4. **Backup la clé privée hors-machine** :
   - Copier `~/.config/age/sealed-backup.key` vers : password manager (encrypted), clé USB chiffrée, ou autre device hors-cluster.
   - **Sans cette clé privée, les backups sont inutilisables.**

5. **Configurer Telegram dans vault.yml** (le bot et chat_id sont déjà ceux configurés pour Beszel, mais ils n'étaient pas accessibles à Ansible) :
   ```bash
   ansible-vault edit ansible/group_vars/vault.yml --vault-password-file ~/.vault-password.txt
   # Ajouter :
   #   vault_telegram_bot_token: "<token>"
   #   vault_telegram_chat_id: "843341688"
   ```

### 5.6 Procédure de restore (en cas de sinistre)

1. Récupérer un fichier `YYYY-MM-DD_HHMM.yaml.age` depuis le NAS (ou réplique externe).
2. Récupérer la clé privée `sealed-backup.key` depuis le coffre hors-machine.
3. Sur la nouvelle machine k8s-node fraîchement bootstrappée :
   ```bash
   age -d -i sealed-backup.key 2026-05-25_0300.yaml.age > master-key.yaml
   kubectl apply -f master-key.yaml
   # Le controller sealed-secrets-controller va redémarrer et utiliser cette clé pour déchiffrer.
   ```
4. Continuer le bootstrap ArgoCD normal (cf. CLAUDE.md §Initialisation).

---

## 6. Rôle `k8s-node-bootstrap`

### 6.1 Vue d'ensemble

Un rôle décomposé en **6 task files** orchestrés par `tasks/main.yml`. Chaque sous-fichier a un tag pour exécution partielle.

```yaml
# tasks/main.yml
---
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

### 6.2 `00_preflight.yml` — Garde-fous

```yaml
- name: Preflight — OS check
  ansible.builtin.assert:
    that:
      - ansible_distribution == "Ubuntu"
      - ansible_distribution_major_version | int >= 24
      - ansible_architecture == "x86_64"
    fail_msg: "k8s-node-bootstrap requires Ubuntu 24+ x86_64"

- name: Preflight — Hostname guard (anti-friendly-fire)
  ansible.builtin.assert:
    that:
      - ansible_hostname == "pc"
    fail_msg: |
      Refusing to run on host '{{ ansible_hostname }}' — this role is hardcoded for
      the k8s-node machine (hostname=pc). If you really want to run elsewhere,
      override via -e "k8s_node_expected_hostname=<your-host>".

- name: Preflight — Disk space on /
  ansible.builtin.shell: df -BG / | awk 'NR==2 {gsub("G",""); print $4}'
  register: free_gb
  changed_when: false

- name: Preflight — Require 20G free
  ansible.builtin.assert:
    that:
      - free_gb.stdout | int >= 20
    fail_msg: "Less than 20G free on / — refusing to install."
```

### 6.3 `10_packages.yml` — APT packages

```yaml
- name: Install base APT packages
  ansible.builtin.apt:
    name:
      # Outils requis par les autres rôles / k8s
      - jq
      - curl
      - git
      - python3-kubernetes      # modules Ansible k8s
      - age                     # backup chiffrement
      - nfs-common              # mount NFS
      - ca-certificates
      - apt-transport-https
      - gnupg

      # Outils de confort (CLI usuels) — explicitement demandés par l'utilisateur
      - htop
      - btop
      - ncdu
      - dust
      - ripgrep
      - fd-find
      - bat
    state: present
    update_cache: yes
    cache_valid_time: 3600
```

Note : `fd-find` s'appelle `fd-find` sous Debian/Ubuntu mais le binaire se nomme `fdfind`. De même `bat` est exposé en `batcat`. Un symlink `/usr/local/bin/fd → /usr/bin/fdfind` et `/usr/local/bin/bat → /usr/bin/batcat` peut être créé en post-task si l'utilisateur préfère les noms upstream.

### 6.4 `20_nvidia.yml` — Drivers NVIDIA + persistence mode

```yaml
- name: Check if NVIDIA GPU is present
  ansible.builtin.shell: lspci | grep -i nvidia | wc -l
  register: nvidia_count
  changed_when: false

- name: Skip NVIDIA setup if no GPU
  ansible.builtin.meta: end_play
  when: nvidia_count.stdout | int == 0

- name: Add NVIDIA Container Toolkit repo key
  ansible.builtin.shell: |
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
      | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  args:
    creates: /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

- name: Add NVIDIA Container Toolkit repo
  ansible.builtin.apt_repository:
    repo: "deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://nvidia.github.io/libnvidia-container/stable/deb/$(ARCH) /"
    state: present
    filename: nvidia-container-toolkit

- name: Install nvidia-container-toolkit
  ansible.builtin.apt:
    name: nvidia-container-toolkit
    state: present
    update_cache: yes

- name: Enable nvidia-persistenced (avoid CUDA wakeup latency)
  ansible.builtin.systemd:
    name: nvidia-persistenced
    enabled: yes
    state: started
```

**Note importante** : ce rôle suppose que les drivers NVIDIA eux-mêmes (`nvidia-driver-XXX`) sont déjà installés. La gestion des drivers kernel est délicate (DKMS, secure boot, etc.) et hors scope d'Ansible. L'utilisateur doit installer les drivers via `ubuntu-drivers autoinstall` ou la procédure Ubuntu standard AVANT d'exécuter ce rôle.

### 6.5 `30_filesystem.yml` — NFS + sysctl + limits

```yaml
- name: Ensure NFS mount point exists
  ansible.builtin.file:
    path: "{{ nfs_local_mount }}"
    state: directory
    mode: '0755'

- name: Mount NFS share
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
    mode: '0644'
  notify: reload sysctl

- name: Configure ulimits
  ansible.builtin.template:
    src: limits-homelab.conf.j2
    dest: /etc/security/limits.d/99-homelab.conf
    mode: '0644'
```

**`sysctl-homelab.conf.j2`** :
```
vm.max_map_count = {{ sysctl_max_map_count }}
fs.inotify.max_user_watches = {{ sysctl_inotify_max_user_watches }}
net.bridge.bridge-nf-call-iptables = 1
net.ipv4.ip_forward = 1
```

**`limits-homelab.conf.j2`** :
```
*       soft    nofile  65536
*       hard    nofile  65536
```

### 6.6 `40_microk8s.yml` — Install + addons

```yaml
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
    append: yes

- name: Wait for microk8s ready
  ansible.builtin.command: microk8s status --wait-ready --timeout=120
  changed_when: false

- name: Enable microk8s addons
  ansible.builtin.command: "microk8s enable {{ item }}"
  loop: "{{ microk8s_addons }}"
  register: enable_result
  changed_when: "'is already enabled' not in enable_result.stdout"

- name: Generate kubectl config in user home
  ansible.builtin.shell: |
    mkdir -p /home/{{ ansible_user }}/.kube
    microk8s config > /home/{{ ansible_user }}/.kube/config
    chown -R {{ ansible_user }}:{{ ansible_user }} /home/{{ ansible_user }}/.kube
    chmod 600 /home/{{ ansible_user }}/.kube/config
  args:
    creates: /home/{{ ansible_user }}/.kube/config
```

### 6.7 `50_gpu_operator.yml` — Workaround NVIDIA #430

```yaml
- name: Wait for ClusterPolicy CRD to be available
  ansible.builtin.command: kubectl get clusterpolicy -n gpu-operator-resources
  register: cp_check
  retries: 30
  delay: 10
  until: cp_check.rc == 0
  changed_when: false
  become: false

- name: Get current value of DISABLE_DEV_CHAR_SYMLINK_CREATION
  ansible.builtin.shell: |
    kubectl get clusterpolicy -n gpu-operator-resources -o json \
      | jq -r '.items[0].spec.validator.driver.env[]? | select(.name=="DISABLE_DEV_CHAR_SYMLINK_CREATION") | .value'
  register: current_val
  changed_when: false
  become: false

- name: Apply workaround DISABLE_DEV_CHAR_SYMLINK_CREATION=true
  when: current_val.stdout != "true"
  ansible.builtin.command: >
    kubectl patch clusterpolicy
    $(kubectl get clusterpolicy -n gpu-operator-resources -o name | head -1)
    -n gpu-operator-resources --type=merge -p
    '{"spec":{"validator":{"driver":{"env":[{"name":"DISABLE_DEV_CHAR_SYMLINK_CREATION","value":"true"}]}}}}'
  become: false
```

### 6.8 Variables (defaults/main.yml)

```yaml
---
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
```

### 6.9 Actions humaines requises

Avant d'exécuter le rôle :

1. Installer Ubuntu 24+ x86_64 avec hostname `pc`.
2. Installer les drivers NVIDIA : `sudo ubuntu-drivers autoinstall && reboot`.
3. Vérifier `nvidia-smi` retourne une RTX 3060 (ou GPU NVIDIA équivalent).
4. Vérifier que le NAS 192.168.88.103 est joignable et exporte `/Public` via NFS.
5. Cloner le repo `my-kluster`, installer Ansible.

Après exécution :

1. **`sudo reboot`** (le groupe `microk8s` ne prend effet qu'après reconnexion + utilisateur courant doit avoir microk8s dans ses groupes).
2. Suivre la procédure CLAUDE.md §Initialisation pour bootstrap ArgoCD :
   - Restore Sealed Secrets master key (depuis backup chiffré age — cf. §5.6).
   - `helm install argocd argocd/argocd-install/ --namespace argocd --create-namespace`
   - `helm install argocd-apps argocd/argocd-install-apps/ --namespace argocd`
3. Attendre quelques minutes qu'ArgoCD synchronise toutes les apps.

---

## 7. Sécurité

### 7.1 Surface d'attaque

| Élément | Risque | Mitigation |
|---|---|---|
| Clé privée age | Quiconque l'a peut déchiffrer tous les backups Sealed Secrets | Stockée hors-machine (password manager / clé USB). Pas dans le repo. |
| Clé publique age | Aucun, c'est publique par définition | Committée dans `group_vars/all.yml` |
| Backup .age sur NAS | Volume du NAS compromis → backups exposés, mais chiffrés | Chiffrement age impossible à casser sans la privée |
| Vault Ansible | Si vault password leaké → secrets décryptables (tokens Telegram, etc.) | `~/.vault-password.txt` jamais committé (`.gitignore` couvre `**/.vault-password*`) |
| Token Telegram bot | Si compromis, qqn peut envoyer des messages au chat | Stocké dans vault.yml. Rotation manuelle si fuite. |
| Mount NFS sans auth | Anyone on the LAN can read | NAS sur LAN privé. Pas exposé internet. Limite acceptable. |

### 7.2 Chaîne de récupération en cas de sinistre

Pour reconstituer le cluster depuis zéro :

| # | Élément perdu | Récupérable si... |
|---|---|---|
| 1 | Machine k8s-node entière | OS install Ubuntu fresh + `ansible-playbook` |
| 2 | Clé master Sealed Secrets | Backup `.age` sur NAS + clé privée hors-machine |
| 3 | NAS | Backup NAS hors-site (RAID + snapshot offsite — non couvert par ce design) |
| 4 | Clé privée age | **PERTE FATALE des backups Sealed Secrets**. Donc cette clé doit être backupée à plusieurs endroits. |

→ **Single point of failure** restant : la clé privée age. **Recommandation** : la copier dans **au moins 2 endroits physiquement séparés** (password manager cloud + clé USB hors-bureau).

---

## 8. Tests d'acceptation

### 8.1 `sealed-secrets-backup`

- [ ] Première exécution : un fichier `.yaml.age` est créé dans `/mnt/nas/backups/sealed-secrets/`.
- [ ] Décryption : `age -d -i ~/.config/age/sealed-backup.key <file>.yaml.age` retourne un YAML K8s valide.
- [ ] Deuxième exécution la même journée (manuelle) : skip avec log `No change in master key`.
- [ ] Forcer une rotation de la clé master (cf. doc Bitnami) → la prochaine exécution crée un nouveau fichier.
- [ ] Simuler un échec (renommer kubectl temporairement) → notification Telegram reçue.
- [ ] Après 31 backups simulés, le plus ancien est supprimé.
- [ ] `systemctl list-timers sealed-secrets-backup.timer` montre la prochaine exécution à 03h00.

### 8.2 `k8s-node-bootstrap`

- [ ] `ansible-playbook ... --check --diff` ne montre aucun changement (idempotence sur machine déjà setup).
- [ ] Tags fonctionnent : `--tags packages` n'exécute que la section packages.
- [ ] Sur une VM fresh Ubuntu 24, le rôle bootstrappe MicroK8s correctement (test à faire en VM).
- [ ] Preflight bloque sur Ubuntu 22 ou hostname != "pc" ou disk < 20G.

---

## 9. Plan de phasage

| Phase | Étape | Acteur | Durée |
|---|---|---|---|
| **1** | Génération paire age + backup hors-machine | Humain | 15 min |
| **2** | Mise à jour vault.yml (Telegram token + chat_id) | Humain | 5 min |
| **3** | Écriture du rôle `sealed-secrets-backup` (script, units, defaults) | Subagent | 1h |
| **4** | Refactor playbook.yml + inventory pour groupe `k8s_nodes` | Subagent | 30 min |
| **5** | Test `sealed-secrets-backup` en isolé : `ansible-playbook ... --tags sealed-backup --check --diff` puis exécution réelle, vérifier le premier backup | Humain + assistant | 30 min |
| **6** | Écriture du rôle `k8s-node-bootstrap` (6 sous-tâches, templates, handlers) | Subagent | 2h |
| **7** | Test `k8s-node-bootstrap` en `--check --diff` sur la machine actuelle (devrait être idempotent — la machine est déjà configurée à la main) | Humain | 1h |
| **8** | Code review final + commit + push | Humain + assistant | 30 min |

Total estimé : ~6 heures, dont ~50% subagents.

---

## 10. Limites / TODO post-implémentation

- Pas de test en VM fresh du rôle `k8s-node-bootstrap` (faisable mais coût/temps).
- Pas de backup offsite du NAS lui-même.
- Pas de chiffrement de la connexion NFS (NFSv4 + Kerberos ou NFSv4 + sec=krb5 → trop complexe pour le bénéfice ici).
- Le bot Telegram est partagé entre Beszel et les notifications Ansible — si on veut séparer (filtrage de chat différent), créer un 2e bot.
- Le rôle ne tag pas explicitement les machines réellement supportées au-delà du preflight hostname — si un jour on a 2 k8s-nodes, refactor en mode `k8s_nodes` group + `inventory_hostname in ['pc', ...]`.

---

## 11. Récapitulatif des actions humaines

À faire avant le premier `ansible-playbook` :

1. ✅ **Générer paire age** :
   ```bash
   mkdir -p ~/.config/age
   age-keygen -o ~/.config/age/sealed-backup.key
   chmod 600 ~/.config/age/sealed-backup.key
   ```

2. ✅ **Backup la clé privée age en 2 endroits hors-machine** (password manager + clé USB).

3. ✅ **Ajouter la pubkey age à `group_vars/all.yml`** :
   ```yaml
   sealed_backup_age_pubkey: "age1abc...xyz"
   ```

4. ✅ **Étendre `vault.yml`** :
   ```yaml
   vault_telegram_bot_token: "<nouveau token>"
   vault_telegram_chat_id: "843341688"
   ```

5. ✅ **Installer `age`** sur le k8s-node (`sudo apt install age`) AVANT le premier run du rôle backup (sinon il faut le faire via le rôle bootstrap d'abord).
