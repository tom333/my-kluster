# Ansible homelab — `my-kluster`

Provisioning Ansible pour les machines du homelab autour du cluster MicroK8s.

## Vue d'ensemble

Inventory découpé en **groupes par usage** :

| Groupe | Hosts | Rôles appliqués |
|---|---|---|
| `k8s_nodes` | `k8s-node` (pc, 192.168.88.250) | `common-cli-tools` + `k8s-node-bootstrap` + `sealed-secrets-backup` + `beszel-agent` |
| `dev_workstations` | `k8s-node`, `work-laptop` (192.168.88.211) | `common-cli-tools` + `dev-workstation` + `beszel-agent` |
| `media_pcs` | `gaming-pc` (192.168.88.199), `work-laptop` | `common-cli-tools` + `media-pc` + `beszel-agent` |
| `libreelec_hosts` | `libreelec-tv` (192.168.88.202) | `beszel-agent-libreelec` + `kodi-backup` |
| `pihole_hosts` | `pihole` (192.168.88.203) | `beszel-agent` + `pihole-maintenance` |
| _(hors groupe)_ | — | `beszel-agent` uniquement (catch-all) |

Un host peut appartenir à plusieurs groupes (cf. `k8s-node` dans `k8s_nodes` + `dev_workstations`).

## Démarrage rapide

```bash
cd ansible/

# Lancer tout sur toutes les machines
ansible-playbook -i inventory.yml playbook.yml \
  --vault-password-file ~/.vault-password.txt \
  --ask-become-pass

# Cibler un seul host
ansible-playbook -i inventory.yml playbook.yml \
  --vault-password-file ~/.vault-password.txt \
  --limit work-laptop --ask-become-pass

# Cibler un sous-ensemble (tags)
ansible-playbook ... --tags bootstrap         # k8s-node-bootstrap uniquement
ansible-playbook ... --tags dev               # dev-workstation uniquement
ansible-playbook ... --tags cli-tools         # common-cli-tools uniquement
ansible-playbook ... --tags fonts             # nerd-fonts uniquement (dev-workstation)
ansible-playbook ... --tags media             # media-pc uniquement
```

## Rôles

| Rôle | Responsabilité |
|---|---|
| `common-cli-tools` | apt + deb-get + outils CLI partagés (jq/htop/btop/ncdu/ripgrep/fd/bat/dust/gh) + timer `deb-get-upgrade` hebdo |
| `beszel-agent` | Install/update agent Beszel (apt-based) |
| `beszel-agent-libreelec` | Idem mais paths LibreELEC (`/storage/.beszel-agent/`, busybox tar) |
| `sealed-secrets-backup` | Backup quotidien chiffré (age) de la master key Sealed Secrets vers NAS + Telegram on failure |
| `k8s-node-bootstrap` | Setup OS k8s-node : NVIDIA toolkit, NFS, sysctl, MicroK8s + addons, workaround gpu-operator #430 |
| `dev-workstation` | Setup poste dev : pipx + uv/ruff (user-scope), VS Code, wezterm, lazygit, chezmoi, git config, Nerd Fonts |
| `media-pc` | Setup PC media : Jellyfin client, gamemode (Feral), sysctl tweaks low-jitter, xinput autostart disable |
| `kodi-backup` | Backup hebdo chiffré (age) de `/storage/.kodi/userdata/` vers NAS |
| `pihole-maintenance` | Timer hebdo `pihole -up` + Telegram on failure (gravity reste gérée par PiHole nativement) |

## Secrets et configuration

- `group_vars/all.yml` : variables non-sensibles partagées (références vault, pubkeys age publiques).
- `group_vars/vault.yml` : secrets chiffrés Ansible Vault (token Telegram, pubkey SSH Beszel hub).
- Le password vault est dans `~/.vault-password.txt` (jamais commité).

Pour éditer le vault :
```bash
ansible-vault edit group_vars/vault.yml --vault-password-file ~/.vault-password.txt
```

## Ajouter une machine

### Machine monitorée seulement (catch-all → `beszel-agent`)
1. Ajouter dans `inventory.yml` sous `hosts:` (hors `children:`).
2. `ansible-playbook ... --limit <nouveau-host> --ask-become-pass`.

### Machine dev-workstation ou media-pc
1. Ajouter dans le groupe correspondant (`dev_workstations:` ou `media_pcs:`).
2. Pour media-pc : éventuellement set per-host `media_xinput_disable_devices` pour devices à désactiver.

### Machine LibreELEC
1. Ajouter dans `libreelec_hosts:` avec `ansible_user: root` + `beszel_le_arch`.
2. SSH key déjà déployée (root@<ip>).

### Machine PiHole
1. Ajouter dans `pihole_hosts:` avec `beszel_arch: arm` (RPi) ou `amd64`.

## Auto-updates

Renovate (cf. `renovate.json` à la racine du repo) track les versions :
- Image Beszel hub (`henrygd/beszel`)
- Versions Beszel agent dans Ansible defaults (apt + libreelec)
- `lazygit`, `chezmoi`, `age` binary versions

→ PRs Renovate auto-mergeables (minor/patch).

## Disaster recovery

### Master key Sealed Secrets
- Backup quotidien chiffré `age` sur `192.168.88.103:/Public/backups/sealed-secrets/`.
- Clé privée `age` correspondante : `~/.config/age/sealed-backup.key` — **à conserver hors-machine** (password manager + clé USB).
- Restore :
  ```bash
  age -d -i ~/.config/age/sealed-backup.key \
    /mnt/nas/backups/sealed-secrets/<latest>.yaml.age | kubectl apply -f -
  ```

### Kodi userdata
- Backup hebdo `age` sur `192.168.88.103:/Public/backups/libreelec/<hostname>/`.
- Même clé privée `age` que pour les Sealed Secrets.

## Voir aussi

- `CLAUDE.md` (ce dossier) — conventions et gotchas pour agents IA.
- Spec / Plan d'origine : `docs/superpowers/specs/2026-05-25-ansible-extension-design.md`, `docs/superpowers/plans/2026-05-25-ansible-extension.md`, `docs/superpowers/specs/2026-05-25-devworkstation-design.md`, `docs/superpowers/plans/2026-05-25-devworkstation.md`.
