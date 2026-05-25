# CLAUDE.md — `ansible/`

Guide concis pour agents IA travaillant dans ce dossier. Pour la doc humaine, voir `README.md`.

## Structure

```
ansible/
├── ansible.cfg                  # config Ansible globale (host_key_checking off, etc.)
├── inventory.yml                # 5 groupes : k8s_nodes / dev_workstations / media_pcs / libreelec_hosts / pihole_hosts
├── playbook.yml                 # 5 plays (1 par groupe + 1 catch-all pour Beszel-only)
├── group_vars/
│   ├── all.yml                  # vars non-sensibles globales (refs vault, age pubkey)
│   └── vault.yml                # Ansible Vault — token Telegram, pubkey SSH Beszel hub
└── roles/
    ├── common-cli-tools/        # apt + deb-get + timer hebdo upgrade
    ├── beszel-agent/            # Beszel agent apt-based
    ├── beszel-agent-libreelec/  # Beszel agent LibreELEC (paths /storage/...)
    ├── sealed-secrets-backup/   # backup quotidien age vers NAS
    ├── k8s-node-bootstrap/      # provisioning k8s host (NVIDIA, NFS, MicroK8s, addons)
    ├── dev-workstation/         # pipx + uv/ruff + VS Code + wezterm + lazygit + chezmoi + nerd-fonts + git config
    ├── media-pc/                # Jellyfin client + gamemode + sysctl + xinput autostart
    ├── kodi-backup/             # backup hebdo Kodi userdata vers NAS
    └── pihole-maintenance/      # timer hebdo `pihole -up` + Telegram on failure
```

## Conventions

### Variables
- **Préfixes par rôle** : `beszel_*`, `dev_*`, `media_*`, `cli_*`, `kodi_backup_*`, `pihole_maint_*`.
- **Versions hardcodées en defaults** : suffixe `_version`, format `"X.Y.Z"` sans `v` (cohérent avec les tags Docker/GitHub).
- **Refs vault** : depuis `group_vars/all.yml`, exposer via `{{ vault_xxx }}` (jamais directement).
- **NE PAS dupliquer** des vars entre `group_vars/all.yml` et `defaults/main.yml` d'un rôle — l'override silencieux empêche les bumps du rôle de se propager (incident lors du bump Beszel 0.10→0.18).

### Tags
- `bootstrap` : k8s-node-bootstrap + common-cli-tools (sur k8s_nodes)
- `dev` : dev-workstation + common-cli-tools (sur dev_workstations)
- `media` : media-pc + common-cli-tools (sur media_pcs)
- `cli-tools` : common-cli-tools partout
- Sous-tags rôle-spécifiques : `filesystem`, `microk8s`, `nvidia`, `gpu_operator`, `pipx`, `deb-get-extras`, `chezmoi`, `lazygit`, `git`, `fonts`, `jellyfin`, `gaming`, `xinput`, etc.

### Multi-groupes
Un host peut appartenir à plusieurs groupes. Syntaxe :
```yaml
dev_workstations:
  hosts:
    work-laptop:                # définition canonique
      ansible_host: ...
      ...
media_pcs:
  hosts:
    work-laptop: {}             # ref nue → réutilise les vars de la définition canonique
```

### Idempotence en mode `--check`
- Les tâches `command:` / `shell:` qui font des **reads** (version probes, list installed) doivent avoir `check_mode: false` sinon elles sont skippées → conditions `when:` cassent.
- Les tâches `systemd: enabled: true state: started` plantent en `--check` car le template précédent est simulé (pas écrit) → wrap with `when: not ansible_check_mode`.
- Les tâches `apt: update_cache: true` peuvent fail si l'host a un repo apt cassé (cf. incident `ntop.org` sur work-laptop).

## Gotchas connus

### Beszel
- **Mode SSH** (k8s-node, work-laptop, libreelec, pihole, gaming-pc, qnap) : le hub initie la connexion vers l'agent. Le rôle config la pubkey hub dans `KEY=` env var de l'agent. Port agent par défaut 43000.
- **Mode Token** (home-assistant via add-on HAOS) : l'agent initie la connexion WebSocket vers le hub. Disponible depuis Beszel 0.18.x. Géré par l'add-on `vineetchoudhary/home-assistant-beszel-agent`.
- L'agent vanilla (rôle `beszel-agent`) marche sur Debian/Ubuntu/Raspbian. Pour LibreELEC, utiliser `beszel-agent-libreelec` (busybox tar, paths `/storage/...`).

### ArgoCD ↔ Ansible
Ces 2 systèmes sont **disjoints** :
- ArgoCD gère ce qui tourne **dans** le cluster k8s.
- Ansible gère ce qui tourne **sur les hosts** (OS, services systemd, packages apt).
- L'OS du k8s-node est géré par Ansible (`k8s-node-bootstrap`). Les workloads k8s par ArgoCD.

### ArgoCD app-of-apps overwrite
Modifier un manifest ArgoCD via `kubectl patch` est **inefficace** : l'app `applications` parente le réécrit dès son prochain reconcile. Toujours modifier le **fichier Git** + commit + push.

### LibreELEC
- Filesystem read-only sauf `/storage/`.
- Pas d'apt — binaries en téléchargement direct (tar.gz GitHub).
- Systemd unit files vont dans `/storage/.config/system.d/` (LibreELEC convention), pas `/etc/systemd/system/`.
- Pas de `become:` — root est le user SSH par défaut.

### Linux Mint
- `ansible_distribution == "Linux Mint"` (avec espace). Si tu match `"Linuxmint"` sans espace, ça ne match pas.
- Snap est désactivé par défaut → préférer apt / deb-get / binary GitHub releases (`chezmoi` et `lazygit` y sont via binary tarball, pas snap).
- Mint 22.3 = base Ubuntu 24.04 jammy/noble → la plupart des paquets apt marchent.

### Bodhi 7
- Reporte `ansible_distribution == "Ubuntu"` (pas "Bodhi"). Donc `media_pc_allowed_distros: ["Ubuntu", "Linux Mint"]` couvre Bodhi automatiquement.

### PiHole (Raspbian)
- ARM 32-bit : `beszel_arch: arm` (pas `arm64`, pas `armv7`).
- `pihole` binary est dans `/usr/local/bin/pihole`.

### QNAP NAS
- **Pas géré par Ansible** — c'est une appliance avec QTS. Beszel agent y tourne en Docker (Container Station), géré manuellement via la UI QNAP.

## Workflows usuels

### Bumper une version d'agent / outil
1. Modifier `defaults/main.yml` du rôle concerné (ex: `beszel_agent_version`).
2. Commit + push.
3. Re-run le playbook sur les hosts concernés.

### Ajouter un secret au vault
```bash
ansible-vault edit group_vars/vault.yml --vault-password-file ~/.vault-password.txt
```
Y ajouter `vault_xxx: "..."` puis référencer depuis un rôle ou `group_vars/all.yml` via `{{ vault_xxx }}`.

### Renovate auto-updates
Les `customManagers` dans `renovate.json` (à la racine du repo) trackent les versions :
- Image Beszel hub (`henrygd/beszel`)
- Beszel agent versions (Ansible defaults)
- `lazygit`, `chezmoi`, `age` binary versions

PRs créées par Renovate, auto-merge minor/patch.

## Ce qu'il NE faut PAS faire

- ❌ Dupliquer `beszel_*` vars entre `group_vars/all.yml` et `defaults/main.yml` du rôle (override silencieux bloque les bumps).
- ❌ `kubectl patch` sur les Applications ArgoCD enfants d'une app-of-apps (l'app parente réécrit).
- ❌ `update_cache: true` sans tolérance si l'host peut avoir un repo apt cassé (mieux : une task `apt update` avec `failed_when: false` séparée).
- ❌ Forcer `dev_workstation_allowed_distros: ["Linuxmint"]` sans espace.
- ❌ Modifier `/etc/systemd/system/` sur LibreELEC (read-only) — toujours utiliser `/storage/.config/system.d/`.
- ❌ `ansible.builtin.unarchive` sur LibreELEC (rejette busybox tar) — préférer `command tar xzf`.
