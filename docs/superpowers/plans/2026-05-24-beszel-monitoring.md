# Beszel Monitoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Déployer Beszel (Hub k8s + agents Ansible-déployés) sur 5-10 machines avec alertes Telegram, en suivant le spec `2026-05-24-beszel-monitoring-design.md`.

**Architecture:** Hub Beszel dans namespace `monitoring` du cluster k8s, accessible LAN-only via `beszel.tgu.ovh`. Il se connecte par SSH outbound (clé Ed25519 dédiée) aux agents installés sur chaque machine cible via Ansible (rôle idempotent). Alertes routées vers Telegram via webhook.

**Tech Stack:** Beszel 0.10.0, `bjw-s/app-template` 5.0.1, Ansible 2.16+, Sealed Secrets Bitnami, ArgoCD, Telegram Bot API, SSH Ed25519.

**Repo:** `/home/moi/projets/perso/my-kluster`

---

## File Structure

| Path | Statut | Responsabilité |
|---|---|---|
| `argocd/argocd-apps/beszel-app.yaml` | NEW | Application ArgoCD pour le Hub Beszel |
| `sealed/beszel-secrets.yaml` | NEW | SealedSecret avec token Telegram + clé SSH privée Hub |
| `ansible/ansible.cfg` | NEW | Config Ansible (timeouts, ssh, paths) |
| `ansible/inventory.yml` | NEW | Inventaire machines (clair) |
| `ansible/playbook.yml` | NEW | Entry point Ansible |
| `ansible/group_vars/all.yml` | NEW | Variables globales (clair) |
| `ansible/group_vars/vault.yml` | NEW (chiffré) | Variables sensibles (clé pub Hub) |
| `ansible/roles/beszel-agent/defaults/main.yml` | NEW | Variables par défaut du rôle |
| `ansible/roles/beszel-agent/tasks/main.yml` | NEW | Tâches idempotentes install/config |
| `ansible/roles/beszel-agent/handlers/main.yml` | NEW | Handlers restart |
| `ansible/roles/beszel-agent/templates/beszel-agent.service.j2` | NEW | Template systemd |
| `.gitignore` | MODIFY | Ajouter `**/.vault-password*` |
| `CLAUDE.md` | MODIFY | Ajouter section monitoring (apps + namespace) |
| `TODO.md` | MODIFY | Marquer Beszel comme implémenté |

---

# PHASE 1 — Hub Beszel sur k8s + agent test manuel

**Objectif Phase 1** : Hub accessible à `beszel.tgu.ovh`, 1 agent visible avec métriques temps réel.
**Durée estimée** : 1h.

## Task 1.0 : Pré-requis et clé SSH dédiée Hub

**Files:**
- Create: `~/.ssh/beszel-hub` (clé privée Hub, local seulement, jamais commitée)
- Create: `~/.ssh/beszel-hub.pub` (clé publique Hub)

- [ ] **Step 1: Générer la clé SSH dédiée pour le Hub**

```bash
ssh-keygen -t ed25519 -f ~/.ssh/beszel-hub -N "" -C "beszel-hub@cluster"
ls -la ~/.ssh/beszel-hub*
# Attendu : 2 fichiers, permissions 600 pour la privée, 644 pour la pub
```

- [ ] **Step 2: Vérifier qu'on a kubectl + kubeseal opérationnels**

```bash
kubectl get nodes
kubeseal --version
# Attendu : node Ready, kubeseal version >= 0.24
```

- [ ] **Step 3: Vérifier qu'on a sealed-secrets controller running**

```bash
kubectl -n kube-system get pod -l name=sealed-secrets-controller
# Attendu : 1 pod Running
```

Aucun commit à cette étape.

---

## Task 1.1 : Créer le namespace monitoring

**Files:**
- Create: (rien dans le repo, le namespace sera créé par ArgoCD via `CreateNamespace=true`)

- [ ] **Step 1: Vérifier que le namespace n'existe pas déjà**

```bash
kubectl get namespace monitoring 2>&1
# Attendu : "Error from server (NotFound)"
```

Si présent, vérifier qu'il est vide ou choisir un autre nom.

Pas d'action manuelle ici. Le namespace sera créé automatiquement par ArgoCD à la sync (Task 1.4).

---

## Task 1.2 : Créer le SealedSecret avec token Telegram (placeholder) + clé SSH Hub

**Files:**
- Create: `sealed/beszel-secrets.yaml`

- [ ] **Step 1: Créer le secret en mémoire et le sceller**

```bash
cd ~/projets/perso/my-kluster

kubectl create secret generic beszel-secrets \
  --namespace=monitoring \
  --from-file=ssh-private-key=$HOME/.ssh/beszel-hub \
  --from-file=ssh-public-key=$HOME/.ssh/beszel-hub.pub \
  --from-literal=telegram-bot-token=PLACEHOLDER_WILL_UPDATE_PHASE3 \
  --from-literal=telegram-chat-id=PLACEHOLDER_WILL_UPDATE_PHASE3 \
  --dry-run=client -o yaml \
  | kubeseal --format=yaml > sealed/beszel-secrets.yaml
```

- [ ] **Step 2: Vérifier le fichier produit**

```bash
head -20 sealed/beszel-secrets.yaml
# Attendu : kind: SealedSecret, metadata.name: beszel-secrets, namespace: monitoring,
# encryptedData chiffré
```

- [ ] **Step 3: Commit**

```bash
git add sealed/beszel-secrets.yaml
git commit -m "feat(monitoring): add SealedSecret for Beszel (Telegram placeholder + SSH key)"
```

---

## Task 1.3 : Créer l'Application ArgoCD pour le Hub Beszel

**Files:**
- Create: `argocd/argocd-apps/beszel-app.yaml`

- [ ] **Step 1: Créer le manifest ArgoCD Application**

```yaml
# argocd/argocd-apps/beszel-app.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: beszel
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  destination:
    namespace: monitoring
    server: https://kubernetes.default.svc
  project: infra-project
  source:
    repoURL: https://bjw-s-labs.github.io/helm-charts
    chart: app-template
    targetRevision: 5.0.1
    helm:
      values: |
        controllers:
          beszel:
            type: deployment
            strategy: Recreate
            containers:
              main:
                image:
                  repository: henrygd/beszel
                  tag: "0.10.0"
                  pullPolicy: IfNotPresent
                env:
                  PORT: "8090"
                  HUB_URL: "https://beszel.tgu.ovh"
                envFrom:
                  - secretRef:
                      name: beszel-secrets
                resources:
                  limits:   { cpu: "500m", memory: 512Mi }
                  requests: { cpu: "100m", memory: 128Mi }
        service:
          app:
            controller: beszel
            ports:
              http:
                port: 8090
        ingress:
          app:
            className: nginx
            annotations:
              cert-manager.io/cluster-issuer: "letsencrypt-prod"
              nginx.ingress.kubernetes.io/whitelist-source-range: "192.168.88.0/24,10.1.0.0/16"
              nginx.ingress.kubernetes.io/proxy-body-size: "10m"
            hosts:
              - host: beszel.tgu.ovh
                paths:
                  - path: /
                    pathType: Prefix
                    service:
                      identifier: app
                      port: http
            tls:
              - secretName: beszel-tls
                hosts:
                  - beszel.tgu.ovh
        persistence:
          data:
            type: persistentVolumeClaim
            storageClass: microk8s-hostpath
            accessMode: ReadWriteOnce
            size: 1Gi
            globalMounts:
              - path: /beszel_data
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
    automated:
      selfHeal: true
      prune: true
```

- [ ] **Step 2: Vérifier que le YAML est valide**

```bash
python3 -c "import yaml; yaml.safe_load(open('argocd/argocd-apps/beszel-app.yaml'))"
# Attendu : aucune sortie (= YAML valide)
```

- [ ] **Step 3: Commit + push**

```bash
git add argocd/argocd-apps/beszel-app.yaml
git commit -m "feat(monitoring): add Beszel Hub Application via app-template 5.0.1"
git push
```

---

## Task 1.4 : Sync ArgoCD + vérifier le Hub UP

- [ ] **Step 1: Forcer la sync ArgoCD (ou attendre auto)**

```bash
kubectl -n argocd patch app beszel --type merge -p '{"operation":{"sync":{}}}'
```

- [ ] **Step 2: Attendre que le pod soit Ready**

```bash
kubectl -n monitoring wait --for=condition=Ready pod -l app.kubernetes.io/name=app-template --timeout=5m
```

Expected: `pod/<name> condition met` en quelques minutes (pull image ~50 MB, démarrage <30s).

- [ ] **Step 3: Vérifier l'ingress + le certificat TLS**

```bash
kubectl -n monitoring get ingress
kubectl -n monitoring get certificate beszel-tls
# Attendu : cert READY=True après ~1-2 min (challenge Let's Encrypt)
```

- [ ] **Step 4: Tester l'accès web depuis le LAN**

Depuis ton poste de dev (sur 192.168.88.0/24) :
```bash
curl -I https://beszel.tgu.ovh
# Attendu : HTTP/2 200 (ou 401 si pas auth) — pas 403 (whitelist OK)
```

Ouvre `https://beszel.tgu.ovh` dans ton navigateur.

- [ ] **Step 5: Créer le compte admin Beszel via l'UI**

Premier accès → page de setup PocketBase → créer ton compte admin (email + password fort).
Stocker le password dans ton password manager.

Pas de commit à cette étape (juste validation manuelle).

**🛑 CHECKPOINT 1.4** : Hub accessible, login admin créé. Si problème ingress/TLS, debug avant de continuer.

---

## Task 1.5 : Installer manuellement le binaire agent Beszel sur le node k8s

**Files:** (sur la machine k8s-node, pas dans le repo)
- Create: `/usr/local/bin/beszel-agent`
- Create: `/etc/systemd/system/beszel-agent.service`
- Create: `/var/lib/beszel/` (home du user système)

- [ ] **Step 1: Sur le poste de dev, récupérer la clé publique du hub**

```bash
cat ~/.ssh/beszel-hub.pub
# Copier le contenu (commence par "ssh-ed25519 AAAA...")
```

- [ ] **Step 2: Sur le node k8s (192.168.88.250), créer le user système beszel**

```bash
sudo useradd --system --shell /usr/sbin/nologin --home /var/lib/beszel --create-home beszel
sudo mkdir -p /var/lib/beszel/.ssh
sudo chmod 700 /var/lib/beszel/.ssh
```

- [ ] **Step 3: Ajouter la clé publique du Hub aux authorized_keys**

```bash
echo "<CONTENU DE beszel-hub.pub>" | sudo tee /var/lib/beszel/.ssh/authorized_keys
sudo chmod 600 /var/lib/beszel/.ssh/authorized_keys
sudo chown -R beszel:beszel /var/lib/beszel/.ssh
```

- [ ] **Step 4: Télécharger le binaire beszel-agent v0.10.0 (x86_64)**

```bash
cd /tmp
wget https://github.com/henrygd/beszel/releases/download/v0.10.0/beszel-agent_linux_amd64.tar.gz
tar -xzf beszel-agent_linux_amd64.tar.gz
sudo install -o root -g root -m 0755 beszel-agent /usr/local/bin/beszel-agent
/usr/local/bin/beszel-agent -v
# Attendu : "beszel-agent v0.10.0"
```

- [ ] **Step 5: Créer le service systemd**

```bash
sudo tee /etc/systemd/system/beszel-agent.service > /dev/null << 'EOF'
[Unit]
Description=Beszel Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=beszel
Group=beszel
Environment="PORT=43000"
Environment="KEY=$(cat /var/lib/beszel/.ssh/authorized_keys)"
ExecStart=/usr/local/bin/beszel-agent
Restart=always
RestartSec=10
LimitNOFILE=4096

# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=read-only

[Install]
WantedBy=multi-user.target
EOF
```

- [ ] **Step 6: Activer et démarrer le service**

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now beszel-agent
sudo systemctl status beszel-agent --no-pager
# Attendu : Active: active (running)
```

- [ ] **Step 7: Vérifier que l'agent écoute bien sur le port 43000**

```bash
sudo ss -tlnp | grep 43000
# Attendu : LISTEN 0 ... 0.0.0.0:43000 ... beszel-agent
```

Pas de commit à cette étape (config sur la machine, pas dans le repo).

---

## Task 1.6 : Connecter l'agent au Hub via l'UI

- [ ] **Step 1: Ouvrir `https://beszel.tgu.ovh` et login**

- [ ] **Step 2: Cliquer "Add System"**

Remplir :
- **Name** : `k8s-node`
- **Host or IP** : `192.168.88.250`
- **Port** : `43000`
- Cliquer "Save"

- [ ] **Step 3: Vérifier que l'agent répond et envoie les métriques**

Après ~30s, le system doit passer en statut "Up" (vert). Cliquer dessus → vérifier que CPU/RAM/Disk/Network apparaissent et bougent.

- [ ] **Step 4: Capturer le résultat dans un commit du repo (snapshot du chemin parcouru)**

Aucun changement de fichier, mais on documente :

```bash
git commit --allow-empty -m "feat(monitoring): Phase 1 complete — Hub up at beszel.tgu.ovh, 1 agent (k8s-node) connected and reporting"
git push
```

**🛑 CHECKPOINT FIN DE PHASE 1** :
- Hub accessible, sécurisé (LAN whitelist + cert TLS)
- 1 agent visible avec métriques temps réel
- Pas encore d'alertes ni d'automation (à venir)

Si problème, debug puis valider avant de passer à Phase 2.

---

# PHASE 2 — Ansible role + déploiement multi-machines

**Objectif Phase 2** : Toutes les machines (5-10) ont leur agent Beszel installé via Ansible, et sont visibles dans le Hub.
**Durée estimée** : 2-3h.
**Pré-requis** : Phase 1 complète.

## Task 2.1 : Setup du dossier ansible/ et de la config

**Files:**
- Create: `ansible/ansible.cfg`
- Create: `ansible/.gitignore`
- Modify: `.gitignore` (à la racine)

- [ ] **Step 1: Créer le dossier ansible/**

```bash
cd ~/projets/perso/my-kluster
mkdir -p ansible/{group_vars,roles/beszel-agent/{defaults,tasks,handlers,templates}}
```

- [ ] **Step 2: Créer `ansible/ansible.cfg`**

```ini
# ansible/ansible.cfg
[defaults]
inventory = inventory.yml
roles_path = roles
host_key_checking = False
retry_files_enabled = False
forks = 10
timeout = 30
stdout_callback = yaml
deprecation_warnings = False
interpreter_python = auto_silent

[ssh_connection]
ssh_args = -o ControlMaster=auto -o ControlPersist=60s -o ServerAliveInterval=15
pipelining = True
```

- [ ] **Step 3: Mettre à jour le `.gitignore` racine pour éviter les leaks**

```bash
cat >> .gitignore << 'EOF'

# Ansible — vault password files (jamais commiter)
**/.vault-password*
**/*.vault-password
ansible/*.retry
EOF
```

- [ ] **Step 4: Commit**

```bash
git add ansible/ansible.cfg .gitignore
git commit -m "feat(ansible): scaffold ansible/ + gitignore vault passwords"
```

---

## Task 2.2 : Setup Ansible Vault et group_vars

**Files:**
- Create: `~/.vault-password.txt` (en local, jamais commit)
- Create: `ansible/group_vars/vault.yml` (chiffré)
- Create: `ansible/group_vars/all.yml` (clair)

- [ ] **Step 1: Créer un mot de passe vault fort + le stocker en local**

```bash
openssl rand -base64 32 > ~/.vault-password.txt
chmod 600 ~/.vault-password.txt
# IMPORTANT : copier ce password dans ton password manager (Bitwarden/KeePass) IMMÉDIATEMENT
# Si perdu, tu ne peux plus déchiffrer le vault
cat ~/.vault-password.txt
```

- [ ] **Step 2: Créer le `group_vars/vault.yml` chiffré avec la clé publique du Hub**

```bash
cd ~/projets/perso/my-kluster/ansible

# Récupérer le contenu de la clé publique du Hub
HUB_PUBKEY=$(cat ~/.ssh/beszel-hub.pub)

# Créer le fichier en clair temporaire
cat > /tmp/vault.yml.tmp << EOF
---
# Variables sensibles, chiffrées via ansible-vault.
# Pour éditer : ansible-vault edit group_vars/vault.yml
vault_beszel_hub_ssh_pubkey: "$HUB_PUBKEY"
EOF

# Chiffrer
ansible-vault encrypt /tmp/vault.yml.tmp \
  --vault-password-file ~/.vault-password.txt \
  --output group_vars/vault.yml
/bin/rm /tmp/vault.yml.tmp
```

- [ ] **Step 3: Vérifier que vault.yml est bien chiffré**

```bash
head -3 ansible/group_vars/vault.yml
# Attendu : "$ANSIBLE_VAULT;1.1;AES256\n<binary chiffré>"
```

- [ ] **Step 4: Créer `ansible/group_vars/all.yml` (variables non-sensibles)**

```yaml
# ansible/group_vars/all.yml
---
# Variables globales partagées par toutes les machines du playbook.
# Pas de secrets ici (cf. vault.yml pour les sensibles).

beszel_agent_version: "0.10.0"
beszel_agent_port: 43000
beszel_agent_user: beszel
beszel_agent_home: /var/lib/beszel

# Référence le secret chiffré dans vault.yml
beszel_hub_ssh_pubkey: "{{ vault_beszel_hub_ssh_pubkey }}"
```

- [ ] **Step 5: Tester le déchiffrement**

```bash
ansible-vault view group_vars/vault.yml --vault-password-file ~/.vault-password.txt
# Attendu : affiche le contenu en clair (la ligne vault_beszel_hub_ssh_pubkey: "ssh-ed25519...")
```

- [ ] **Step 6: Commit**

```bash
cd ~/projets/perso/my-kluster
git add ansible/group_vars/
git commit -m "feat(ansible): add group_vars (all.yml clear, vault.yml encrypted)"
```

---

## Task 2.3 : Créer l'inventaire des machines

**Files:**
- Create: `ansible/inventory.yml`

- [ ] **Step 1: Identifier toutes les machines à monitorer**

Lister tes machines (à remplir avec les vraies valeurs avant l'étape 2) :
- `k8s-node` : 192.168.88.250 — user `moi`
- `ha-host` : IP à confirmer — user à confirmer
- `pi-XYZ` : IP à confirmer — user `pi` ou `ubuntu`
- `ubuntu-bureau` : IP à confirmer — user `moi`
- etc.

- [ ] **Step 2: Créer `ansible/inventory.yml`**

⚠️ **REMPLACER les IPs/users par les vraies valeurs avant de commit.**

```yaml
# ansible/inventory.yml
---
# Inventaire des machines monitorées par Beszel.
# IPs en clair = LAN privé RFC1918, peu sensible. Pour ajouter une machine :
# 1) ajouter 3 lignes ci-dessous, 2) ansible-playbook ... --limit <nouveau-host>

all:
  hosts:
    # Cluster k8s MicroK8s (Ubuntu, x86_64)
    k8s-node:
      ansible_host: 192.168.88.250
      ansible_user: moi
      beszel_arch: amd64

    # Home Assistant — REMPLACER IP + user selon ton install
    # ha-host:
    #   ansible_host: 192.168.88.200
    #   ansible_user: hass
    #   beszel_arch: amd64

    # Raspberry Pi — REMPLACER
    # pi-salon:
    #   ansible_host: 192.168.88.150
    #   ansible_user: pi
    #   beszel_arch: arm64

    # Ubuntu bureau — REMPLACER
    # ubuntu-bureau:
    #   ansible_host: 192.168.88.151
    #   ansible_user: moi
    #   beszel_arch: amd64

  vars:
    # Toutes les machines partagent ces vars (override possible par-host)
    ansible_ssh_common_args: '-o StrictHostKeyChecking=no'
```

- [ ] **Step 3: Tester la connectivité SSH vers k8s-node (déjà accessible)**

```bash
cd ~/projets/perso/my-kluster/ansible
ansible -i inventory.yml k8s-node -m ping
# Attendu : k8s-node | SUCCESS => { "ping": "pong" }
```

- [ ] **Step 4: Commit (avec inventaire k8s-node uniquement pour démarrer)**

```bash
git add ansible/inventory.yml
git commit -m "feat(ansible): add inventory.yml (k8s-node first, others to add iteratively)"
```

---

## Task 2.4 : Écrire le rôle `beszel-agent` — defaults

**Files:**
- Create: `ansible/roles/beszel-agent/defaults/main.yml`

- [ ] **Step 1: Créer le fichier defaults**

```yaml
# ansible/roles/beszel-agent/defaults/main.yml
---
# Valeurs par défaut du rôle beszel-agent.
# Overrides possible via inventory ou group_vars.

beszel_agent_version: "0.10.0"
beszel_agent_port: 43000
beszel_agent_user: beszel
beszel_agent_group: beszel
beszel_agent_home: /var/lib/beszel
beszel_agent_binary_path: /usr/local/bin/beszel-agent
beszel_agent_service_name: beszel-agent

# Architecture : "amd64" ou "arm64" (à set par host dans inventory)
beszel_arch: amd64

# Clé publique du Hub (override via group_vars/vault.yml)
beszel_hub_ssh_pubkey: ""
```

- [ ] **Step 2: Commit**

```bash
git add ansible/roles/beszel-agent/defaults/main.yml
git commit -m "feat(ansible): beszel-agent role defaults"
```

---

## Task 2.5 : Écrire le rôle — tasks (le cœur de l'install)

**Files:**
- Create: `ansible/roles/beszel-agent/tasks/main.yml`

- [ ] **Step 1: Créer le fichier tasks**

```yaml
# ansible/roles/beszel-agent/tasks/main.yml
---
- name: Validate beszel_hub_ssh_pubkey is set
  ansible.builtin.assert:
    that:
      - beszel_hub_ssh_pubkey is defined
      - beszel_hub_ssh_pubkey | length > 0
    fail_msg: "beszel_hub_ssh_pubkey must be set (via group_vars/vault.yml)"

- name: Create beszel system group
  ansible.builtin.group:
    name: "{{ beszel_agent_group }}"
    system: true
    state: present

- name: Create beszel system user
  ansible.builtin.user:
    name: "{{ beszel_agent_user }}"
    group: "{{ beszel_agent_group }}"
    system: true
    shell: /usr/sbin/nologin
    home: "{{ beszel_agent_home }}"
    create_home: true
    state: present

- name: Ensure .ssh directory exists
  ansible.builtin.file:
    path: "{{ beszel_agent_home }}/.ssh"
    state: directory
    owner: "{{ beszel_agent_user }}"
    group: "{{ beszel_agent_group }}"
    mode: '0700'

- name: Add Hub SSH public key to authorized_keys
  ansible.posix.authorized_key:
    user: "{{ beszel_agent_user }}"
    state: present
    key: "{{ beszel_hub_ssh_pubkey }}"
    exclusive: true

- name: Check if beszel-agent binary already at correct version
  ansible.builtin.command: "{{ beszel_agent_binary_path }} -v"
  register: beszel_current_version
  changed_when: false
  failed_when: false

- name: Download and install beszel-agent binary
  when: beszel_current_version.rc != 0 or beszel_agent_version not in (beszel_current_version.stdout | default(''))
  block:
    - name: Download beszel-agent tarball
      ansible.builtin.get_url:
        url: "https://github.com/henrygd/beszel/releases/download/v{{ beszel_agent_version }}/beszel-agent_linux_{{ beszel_arch }}.tar.gz"
        dest: "/tmp/beszel-agent-{{ beszel_agent_version }}.tar.gz"
        mode: '0644'
        force: true

    - name: Extract beszel-agent binary
      ansible.builtin.unarchive:
        src: "/tmp/beszel-agent-{{ beszel_agent_version }}.tar.gz"
        dest: /tmp/
        remote_src: true

    - name: Install beszel-agent binary
      ansible.builtin.copy:
        src: /tmp/beszel-agent
        dest: "{{ beszel_agent_binary_path }}"
        remote_src: true
        owner: root
        group: root
        mode: '0755'
      notify: restart beszel-agent

    - name: Cleanup tarball
      ansible.builtin.file:
        path: "/tmp/beszel-agent-{{ beszel_agent_version }}.tar.gz"
        state: absent

    - name: Cleanup extracted binary in /tmp
      ansible.builtin.file:
        path: /tmp/beszel-agent
        state: absent

- name: Install beszel-agent systemd service unit
  ansible.builtin.template:
    src: beszel-agent.service.j2
    dest: "/etc/systemd/system/{{ beszel_agent_service_name }}.service"
    owner: root
    group: root
    mode: '0644'
  notify:
    - reload systemd
    - restart beszel-agent

- name: Enable and start beszel-agent service
  ansible.builtin.systemd:
    name: "{{ beszel_agent_service_name }}"
    enabled: true
    state: started
    daemon_reload: true

- name: Wait for beszel-agent to listen on configured port
  ansible.builtin.wait_for:
    port: "{{ beszel_agent_port }}"
    host: 127.0.0.1
    timeout: 30
```

- [ ] **Step 2: Commit**

```bash
git add ansible/roles/beszel-agent/tasks/main.yml
git commit -m "feat(ansible): beszel-agent role tasks (idempotent install + systemd)"
```

---

## Task 2.6 : Écrire le rôle — handlers + template

**Files:**
- Create: `ansible/roles/beszel-agent/handlers/main.yml`
- Create: `ansible/roles/beszel-agent/templates/beszel-agent.service.j2`

- [ ] **Step 1: Créer le fichier handlers**

```yaml
# ansible/roles/beszel-agent/handlers/main.yml
---
- name: reload systemd
  ansible.builtin.systemd:
    daemon_reload: true

- name: restart beszel-agent
  ansible.builtin.systemd:
    name: "{{ beszel_agent_service_name }}"
    state: restarted
```

- [ ] **Step 2: Créer le template systemd**

```jinja2
# ansible/roles/beszel-agent/templates/beszel-agent.service.j2
[Unit]
Description=Beszel Agent ({{ beszel_agent_version }})
Documentation=https://github.com/henrygd/beszel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={{ beszel_agent_user }}
Group={{ beszel_agent_group }}
Environment="PORT={{ beszel_agent_port }}"
Environment="KEY={{ beszel_hub_ssh_pubkey }}"
ExecStart={{ beszel_agent_binary_path }}
Restart=always
RestartSec=10
LimitNOFILE=4096

# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=read-only
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 3: Commit**

```bash
git add ansible/roles/beszel-agent/handlers/main.yml \
        ansible/roles/beszel-agent/templates/beszel-agent.service.j2
git commit -m "feat(ansible): beszel-agent role handlers + systemd template"
```

---

## Task 2.7 : Écrire le playbook entry point

**Files:**
- Create: `ansible/playbook.yml`

- [ ] **Step 1: Créer le playbook**

```yaml
# ansible/playbook.yml
---
- name: Deploy Beszel agents on all monitored machines
  hosts: all
  become: true
  gather_facts: true

  pre_tasks:
    - name: Ensure required python collections are installed (posix.authorized_key)
      ansible.builtin.debug:
        msg: "Running on {{ inventory_hostname }} ({{ ansible_host }}) — arch={{ beszel_arch }}"

  vars_files:
    - group_vars/vault.yml

  roles:
    - beszel-agent
```

- [ ] **Step 2: Vérifier les collections Ansible requises**

```bash
cd ~/projets/perso/my-kluster/ansible
ansible-galaxy collection list ansible.posix 2>&1 | head -5
# Si vide : pip install ansible OU ansible-galaxy collection install ansible.posix
ansible-galaxy collection install ansible.posix
```

- [ ] **Step 3: Commit**

```bash
git add ansible/playbook.yml
git commit -m "feat(ansible): playbook entry point deploying beszel-agent role"
```

---

## Task 2.8 : Dry-run du playbook sur k8s-node (--check)

- [ ] **Step 1: Lancer en mode check (rien n'est modifié)**

```bash
cd ~/projets/perso/my-kluster/ansible
ansible-playbook -i inventory.yml playbook.yml \
  --vault-password-file ~/.vault-password.txt \
  --check --diff \
  --limit k8s-node
```

Expected output :
- `PLAY [Deploy Beszel agents...]` puis tâches `ok=N changed=N`
- Comme l'agent k8s-node est déjà installé manuellement (Task 1.5), beaucoup de `ok`, peut-être quelques `changed` (notamment template service unit si différent)

- [ ] **Step 2: Analyser le diff**

Si Ansible voit des `changed` sur des choses qui ne devraient pas changer (genre re-télécharger le binaire alors qu'il est déjà en v0.10.0), debug le rôle. La task `Check if beszel-agent binary already at correct version` doit short-circuiter le block download.

Si tout est `ok` ou les changes sont attendus (genre template service unit nouvellement formaté), c'est OK.

Pas de commit.

---

## Task 2.9 : Real run du playbook sur k8s-node

- [ ] **Step 1: Lancer le playbook pour de vrai (idempotent)**

```bash
ansible-playbook -i inventory.yml playbook.yml \
  --vault-password-file ~/.vault-password.txt \
  --limit k8s-node
```

Expected : `ok=N, changed=0` (ou très peu) si l'install manuelle Phase 1 a fait la même config que le rôle. Si beaucoup de `changed`, c'est que le rôle redéploie proprement → OK.

- [ ] **Step 2: Vérifier que l'agent est toujours running après le re-deploy**

```bash
ssh moi@192.168.88.250 'sudo systemctl status beszel-agent --no-pager | head -8'
# Attendu : Active: active (running)
```

- [ ] **Step 3: Vérifier le dashboard Hub**

Ouvre `https://beszel.tgu.ovh` → `k8s-node` doit toujours être Up.

- [ ] **Step 4: Re-run idempotence test (sans modifier rien)**

```bash
ansible-playbook -i inventory.yml playbook.yml \
  --vault-password-file ~/.vault-password.txt \
  --limit k8s-node
```

Expected : **`ok=N, changed=0`**. Si `changed > 0`, le rôle n'est pas idempotent → bug à fixer.

- [ ] **Step 5: Commit (empty, doc le checkpoint)**

```bash
cd ~/projets/perso/my-kluster
git commit --allow-empty -m "test(ansible): k8s-node playbook run idempotent (ok=N, changed=0)"
git push
```

**🛑 CHECKPOINT 2.9** : Si idempotence OK, on est prêt à étendre aux autres machines. Sinon, debug.

---

## Task 2.10 : Étendre l'inventaire et déployer sur les autres machines

- [ ] **Step 1: Ajouter une 2e machine dans `inventory.yml`**

Choisir une machine non-cluster (par exemple `ha-host` ou un Pi).
Vérifier que tu peux y SSH manuellement d'abord :

```bash
ssh <user>@<IP> 'whoami && uname -m'
# whoami doit retourner le user attendu, uname -m doit donner x86_64 ou aarch64
```

Éditer `ansible/inventory.yml` :
```yaml
# Décommenter et adapter avec les vraies valeurs
ha-host:
  ansible_host: 192.168.88.XXX
  ansible_user: USER
  beszel_arch: amd64   # ou arm64 si Pi
```

- [ ] **Step 2: Tester la connectivité Ansible**

```bash
cd ~/projets/perso/my-kluster/ansible
ansible -i inventory.yml ha-host -m ping
# Attendu : ha-host | SUCCESS => { "ping": "pong" }
```

Si fail : vérifier SSH key (le user doit pouvoir SSH sans mot de passe — sinon ajouter ta clé publique manuellement avec `ssh-copy-id`).

- [ ] **Step 3: Dry-run sur cette machine**

```bash
ansible-playbook -i inventory.yml playbook.yml \
  --vault-password-file ~/.vault-password.txt \
  --check --diff \
  --limit ha-host
```

Examiner les `changed` annoncés. Tout doit être logique (user créé, binaire installé, service créé).

- [ ] **Step 4: Real run**

```bash
ansible-playbook -i inventory.yml playbook.yml \
  --vault-password-file ~/.vault-password.txt \
  --limit ha-host
```

- [ ] **Step 5: Ajouter la machine dans le Hub UI**

`https://beszel.tgu.ovh` → "Add System" → renseigner Name, IP de la machine, port `43000` → Save.

Vérifier que la machine apparaît Up dans le dashboard.

- [ ] **Step 6: Répéter Steps 1-5 pour chaque autre machine**

Pour chaque machine restante (Pi, autres Ubuntu) :
- Ajouter dans inventory.yml
- ansible -m ping (vérif)
- ansible-playbook --check --limit (dry-run)
- ansible-playbook --limit (real run)
- Add System dans Hub UI

- [ ] **Step 7: Commit l'inventaire final**

```bash
cd ~/projets/perso/my-kluster
git add ansible/inventory.yml
git commit -m "feat(ansible): extend inventory with all monitored machines (N hosts)"
git push
```

**🛑 CHECKPOINT FIN DE PHASE 2** :
- Tous les hosts listés dans `inventory.yml` sont visibles dans le Hub avec métriques temps réel
- Re-run `ansible-playbook` sur l'ensemble → `ok=N, changed=0` (idempotent)
- Documentation utilisateur à jour

---

# PHASE 3 — Alertes Telegram

**Objectif Phase 3** : Bot Telegram créé, webhook configuré, 8 seuils actifs, test passé.
**Durée estimée** : 30 min.
**Pré-requis** : Phase 2 complète.

## Task 3.1 : Créer le bot Telegram

**Files:** (rien dans le repo, juste config externe)

- [ ] **Step 1: Sur Telegram, ouvrir une conversation avec `@BotFather`**

- [ ] **Step 2: Créer un nouveau bot**

```
Toi: /newbot
BotFather: Alright, a new bot...
Toi: Beszel Homelab Alerts
BotFather: Good. Now let's choose a username...
Toi: beszel_homelab_alerts_bot (doit finir par _bot et être unique)
BotFather: Done! Congratulations. Use this token to access the HTTP API: <TOKEN>
```

**Garder le TOKEN précieusement** (format `123456789:ABC-DEF...`).

- [ ] **Step 3: Récupérer ton chat_id**

Ouvrir une conv avec `@userinfobot` et envoyer `/start`. Il te renvoie ton ID numérique (genre `123456789`).

- [ ] **Step 4: Envoyer un message au bot pour qu'il puisse t'écrire**

Cherche `@beszel_homelab_alerts_bot` (ton bot) dans Telegram, ouvre la conv, envoie `/start`.
Sans ça, le bot ne peut pas envoyer de message.

- [ ] **Step 5: Test manuel du token + chat_id**

```bash
TOKEN="<ton-token>"
CHAT_ID="<ton-chat-id>"
curl -s "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -d "chat_id=${CHAT_ID}" \
  -d "text=Test depuis terminal - setup Beszel"
# Attendu : {"ok":true,...} ET tu reçois le message dans Telegram
```

Si pas de message reçu : vérifier que tu as bien fait Step 4 (envoyer /start au bot).

---

## Task 3.2 : Update le SealedSecret avec les vraies valeurs Telegram

**Files:**
- Modify: `sealed/beszel-secrets.yaml`

- [ ] **Step 1: Re-générer le SealedSecret avec vrais Telegram + même SSH key**

```bash
cd ~/projets/perso/my-kluster

TELEGRAM_TOKEN="<token-recupere-task-3.1>"
TELEGRAM_CHAT_ID="<chat-id-recupere-task-3.1>"

kubectl create secret generic beszel-secrets \
  --namespace=monitoring \
  --from-file=ssh-private-key=$HOME/.ssh/beszel-hub \
  --from-file=ssh-public-key=$HOME/.ssh/beszel-hub.pub \
  --from-literal=telegram-bot-token="$TELEGRAM_TOKEN" \
  --from-literal=telegram-chat-id="$TELEGRAM_CHAT_ID" \
  --dry-run=client -o yaml \
  | kubeseal --format=yaml > sealed/beszel-secrets.yaml
```

- [ ] **Step 2: Vérifier le diff (rien en clair ne doit avoir fuité)**

```bash
git diff sealed/beszel-secrets.yaml | head -30
# Les champs encryptedData ont changé (normal, chiffré différemment à chaque fois)
# Aucune valeur en clair visible — c'est le but
```

- [ ] **Step 3: Commit + push**

```bash
git add sealed/beszel-secrets.yaml
git commit -m "feat(monitoring): inject real Telegram bot token + chat_id into beszel-secrets"
git push
```

- [ ] **Step 4: ArgoCD sync + restart pod pour récupérer les nouveaux env**

```bash
kubectl -n argocd patch app beszel --type merge -p '{"operation":{"sync":{}}}'
sleep 30
kubectl -n monitoring rollout restart deploy -l app.kubernetes.io/name=app-template
kubectl -n monitoring wait --for=condition=Ready pod -l app.kubernetes.io/name=app-template --timeout=3m
```

---

## Task 3.3 : Configurer le webhook Telegram dans l'UI Beszel

**Note** : Beszel UI v0.10.0 supporte les "Notification Channels". La config se fait dans l'UI, pas en YAML.

- [ ] **Step 1: Aller dans `https://beszel.tgu.ovh` → Settings → Notifications**

- [ ] **Step 2: Add Notification Channel**

Choisir "Webhook" (ou "Telegram" si disponible directement).

Si Webhook générique :
- **Name** : `Telegram`
- **URL** : `https://api.telegram.org/bot{token}/sendMessage`
- **Method** : POST
- **Payload template** (JSON) :
```json
{
  "chat_id": "{chat_id}",
  "text": "🚨 *{alert_name}*\n\nSystem: `{system_name}`\nValue: {value}\nThreshold: {threshold}\n\nTime: {timestamp}",
  "parse_mode": "Markdown"
}
```

Remplacer `{token}` et `{chat_id}` par les valeurs réelles (depuis les env vars du container = SealedSecret).

⚠️ **NOTE** : si Beszel ne peut pas templater le token depuis env, il faudra hardcoder dans l'URL — moins propre mais fonctionnel. Limite connue. Alternative : créer un petit relais HTTP dans le cluster qui lit les env et forwarde vers Telegram. Hors scope phase 3 — à voir si besoin.

- [ ] **Step 3: Test du channel**

Bouton "Test" dans l'UI → tu dois recevoir un message Telegram.

Si fail : vérifier l'URL, le token, et que le bot a bien été contacté en premier (cf. Task 3.1 Step 4).

---

## Task 3.4 : Configurer les 8 seuils d'alerte

**Note** : pour CHAQUE alerte définie dans le spec §6, créer une alerte dans Beszel UI.

- [ ] **Step 1: Aller dans Settings → Alerts (ou par-système)**

- [ ] **Step 2: Pour chaque alerte ci-dessous, créer une nouvelle alerte**

| # | Trigger | Threshold | Duration | Sévérité | Channel |
|---|---|---|---|---|---|
| 1 | Disk usage | > 70% | 5 min | warn | Telegram |
| 2 | Disk usage | > 85% | 1 min | critical | Telegram |
| 3 | RAM usage | > 90% | 5 min | warn | Telegram |
| 4 | CPU usage | > 90% | 10 min | warn | Telegram |
| 5 | Status | offline | 5 min | critical | Telegram |
| 6 | Docker restart count | > 3 in 10min | — | warn | Telegram |
| 7 | Temperature | > 70°C | 5 min | warn (Pi only) | Telegram |
| 8 | Temperature | > 80°C | 1 min | critical (Pi only) | Telegram |

Pour les alertes Pi-only (7, 8) : appliquer uniquement aux systems taggés "pi" (ou désactiver pour les non-Pi).

- [ ] **Step 3: Activer le throttling**

Pour chaque alerte, fixer un "minimum interval between notifications" à 30 minutes (évite spam).

- [ ] **Step 4: Test manuel d'une alerte (disk 70%)**

Sur une machine de test (idéalement la moins critique, ex un Pi), monter artificiellement l'usage disque :

```bash
ssh user@pi-test
# Créer un gros fichier dummy (~5 GB sur un disque 8 GB → ~62%)
sudo fallocate -l 5G /tmp/dummy
df -h /
```

Attendre 5-6 min, le seuil 70% doit se déclencher → message Telegram.

Cleanup :
```bash
sudo /bin/rm /tmp/dummy
df -h /
```

Si pas de message : check les logs du Hub :
```bash
kubectl -n monitoring logs deploy -l app.kubernetes.io/name=app-template --tail=50
```

---

## Task 3.5 : Documentation — mise à jour CLAUDE.md et TODO.md

**Files:**
- Modify: `CLAUDE.md`
- Modify: `TODO.md`

- [ ] **Step 1: Ajouter une section dans CLAUDE.md sous "Applications actives"**

Insérer la section suivante avant "Self-hosted" :

```markdown
### Monitoring (namespace `monitoring`)

| Application | Namespace    | Source                            | Version | Notes                                                                  |
|-------------|--------------|-----------------------------------|---------|------------------------------------------------------------------------|
| `beszel`    | `monitoring` | bjw-s-labs.github.io/helm-charts  | 5.0.1   | Hub Beszel (henrygd/beszel 0.10.0). Ingress LAN-only `beszel.tgu.ovh`. Alertes Telegram. |

Agents déployés via Ansible (`ansible/` du repo) sur toutes les machines monitorées.
Documentation déploiement : `docs/superpowers/specs/2026-05-24-beszel-monitoring-design.md`.
```

- [ ] **Step 2: Ajouter dans CLAUDE.md section "Spécificités MicroK8s" ou nouvelle section Ansible**

```markdown
### Ansible (déploiement multi-machines)

- Dossier : `ansible/` du repo.
- Inventaire en clair dans `ansible/inventory.yml` (IPs LAN RFC1918).
- Secrets chiffrés via Ansible Vault dans `ansible/group_vars/vault.yml` (password local en `~/.vault-password.txt`, jamais commité).
- Commande pleine : `cd ansible/ && ansible-playbook -i inventory.yml playbook.yml --vault-password-file ~/.vault-password.txt`.
- Ajout machine : éditer `inventory.yml`, runner avec `--limit <nouveau-host>`.
- Rôle disponible : `beszel-agent` (install/update agent Beszel).
```

- [ ] **Step 3: Mettre à jour TODO.md**

Ajouter dans "Récemment terminé" :

```markdown
- [x] **Monitoring multi-machines Beszel + Ansible**
  - Hub Beszel sur cluster k8s (namespace `monitoring`), ingress LAN-only `beszel.tgu.ovh`
  - Agents déployés via Ansible sur N machines (cf. `ansible/inventory.yml`)
  - 8 alertes Telegram configurées (disque, RAM, CPU, agent down, Docker, température)
  - Documentation : spec `2026-05-24-beszel-monitoring-design.md` + plan `2026-05-24-beszel-monitoring.md`
```

- [ ] **Step 4: Commit + push**

```bash
git add CLAUDE.md TODO.md
git commit -m "docs: add monitoring section (Beszel + Ansible) to CLAUDE.md and TODO.md"
git push
```

**🛑 CHECKPOINT FIN DE PHASE 3** :
- Bot Telegram fonctionnel (test manuel OK)
- 8 alertes configurées
- Documentation à jour
- Cluster monitoré 24/7

---

# PHASE 4 — Tuning des seuils (différé +7 jours)

**Objectif Phase 4** : Ajuster les seuils selon le comportement réel observé.
**Durée estimée** : 1h.
**Pré-requis** : Phase 3 complète + 7 jours d'observation.

## Task 4.1 : Review des notifications reçues

- [ ] **Step 1: Compter les notifications reçues sur 7 jours**

Dans Telegram, scroller dans la conv du bot et compter :
- Combien de notifications par alerte ?
- Lesquelles sont des vrais positifs (vrais incidents) ?
- Lesquelles sont des faux positifs (bruit) ?

- [ ] **Step 2: Identifier les seuils à ajuster**

Règles de tuning :
- Si une alerte se déclenche >10 fois sans intervention → seuil trop bas, monter
- Si un incident est arrivé sans alerte → seuil trop haut, baisser ou ajouter alerte manquante
- Si beaucoup de "noise" sur un seuil court → augmenter la durée

- [ ] **Step 3: Documenter les observations dans `docs/superpowers/specs/2026-05-24-beszel-monitoring-design.md`**

Ajouter une section "Phase 4 — Tuning observations (date)" dans le spec.

---

## Task 4.2 : Appliquer les ajustements dans le Hub UI

- [ ] **Step 1: Modifier les seuils dans Beszel UI**

Settings → Alerts → édition de chaque alerte concernée.

- [ ] **Step 2: Observer 3 jours sans changement**

Vérifier qu'on tend vers 0 faux positifs et qu'on capte les vrais.

---

## Task 4.3 : Commit empty pour marquer la fin de Phase 4

```bash
git commit --allow-empty -m "chore(monitoring): Phase 4 tuning complete — N alerts adjusted after 7d observation"
git push
```

**🛑 CHECKPOINT FIN DE PHASE 4** :
- Aucun false positive observé pendant 3 jours
- Aucun true negative oublié
- Documentation tuning ajoutée au spec

---

# Annexe A — Rollback procedures

## Rollback complet (revenir à l'état pré-Beszel)

```bash
# Désinstaller le Hub k8s (côté ArgoCD)
kubectl -n argocd delete app beszel

# Le namespace monitoring + PVC seront pruned
kubectl get namespace monitoring 2>&1 | head -3   # doit retourner NotFound

# Supprimer les agents sur toutes les machines (via Ansible playbook reverse)
# Pas inclus dans ce plan — manuel :
for host in $(yq '.all.hosts | keys | .[]' ansible/inventory.yml); do
  ssh user@$host 'sudo systemctl stop beszel-agent && sudo systemctl disable beszel-agent && sudo /bin/rm /etc/systemd/system/beszel-agent.service /usr/local/bin/beszel-agent && sudo userdel beszel'
done

# Supprimer les fichiers du repo
git rm -r ansible/ argocd/argocd-apps/beszel-app.yaml sealed/beszel-secrets.yaml
git commit -m "revert: remove Beszel monitoring stack"
git push
```

## Rollback partiel (juste désactiver les alertes)

Dans Beszel UI → Settings → Alerts → "Pause All".

---

# Annexe B — Troubleshooting

## Hub down

```bash
kubectl -n monitoring get pod -l app.kubernetes.io/name=app-template
kubectl -n monitoring logs deploy -l app.kubernetes.io/name=app-template --tail=50
kubectl -n monitoring describe pod -l app.kubernetes.io/name=app-template
```

## Agent injoignable depuis le Hub

```bash
# Sur la machine cible
sudo systemctl status beszel-agent
sudo ss -tlnp | grep 43000   # port doit écouter

# Test SSH manuel depuis le Hub
kubectl -n monitoring exec deploy/beszel -- ssh -i /beszel_data/keys/ssh-private-key beszel@<IP-agent> -p 43000
```

## Ansible playbook fail

```bash
# Re-run en mode verbose
ansible-playbook ... -vvv --limit <host-en-cause>

# Test connectivité brute
ansible -i inventory.yml <host> -m setup --vault-password-file ...
```

## Telegram pas de messages

```bash
# Test direct API
curl -s "https://api.telegram.org/bot${TOKEN}/getMe"
# Doit retourner {"ok":true,"result":{...}}

# Test sendMessage
curl -s "https://api.telegram.org/bot${TOKEN}/sendMessage" -d "chat_id=${CHAT_ID}" -d "text=test"
```
