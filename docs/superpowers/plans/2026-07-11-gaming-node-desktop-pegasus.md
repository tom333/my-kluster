# Plan — Rôle desktop pour le nœud AM4 (worker k8s + frontend Pegasus)

Date : 2026-07-11

## Contexte
Le nouveau nœud AM4 (Gigabyte B550M K + Ryzen 5 5500 6c/12t + **1050 Ti Pascal** + SSD +
2 To SATA, 16→32 Go, 24/7) remplace le laptop de jeu mort ET sert de **worker MicroK8s**
(cf. `2026-07-07-k8s-secondary-node-x299.md`, cible matérielle re-ciblée AM4).

Les rôles `desktop`/`gaming`/`media-pc` avaient été tunés pour le **laptop mort**
(Kepler 920M/nvidia-470, autologin kid, tint2, hack BT rtl8723, purge snapd). Ce nœud
a des besoins **différents** :
- **Frontend "à la Batocera"** = **Pegasus** (UI canapé unique : jeux PC + rétro + Brave + Jellyfin), remplace ES-DE.
- **Protégé par mot de passe** → **login LightDM** (PAS autologin).
- **Worker k8s** → **snapd conservé** (MicroK8s = snap), nvidia **580** (Pascal legacy, branche maintenue).

## Décisions
- **Pegasus en NATIF** (AppImage/tarball GitHub `mmatyas/pegasus-frontend`), **pas Flatpak** :
  le sandbox flatpak ne lance pas proprement les binaires hôte (Lutris/RetroArch/Brave).
- **RetroArch + cœurs conservés** (Pegasus = lanceur, n'émule pas). **ES-DE retiré**.
- Art rétro = passe **Steam ROM Manager** (gère Pegasus + Steam) hors-Ansible, une fois.
- Valeurs spécifiques machine → **`host_vars/gaming-pc.yml`** ; defaults de rôle restent génériques.

## Changements rôle `desktop`

### Nouveaux toggles (defaults, génériques)
| Var | Défaut | Effet |
|---|---|---|
| `desktop_frontend` | `tint2` | `tint2` \| `pegasus` (shell de session) |
| `desktop_autologin` | `false` | false = **login mot de passe** ; true = autologin |
| `desktop_screenlock` | `false` | light-locker à l'idle |

### Tâches
- **`40_lightdm_autologin.yml`** → autologin **conditionnel** (`when: desktop_autologin`).
  Si false : greeter login normal + session par défaut = openbox (le frontend est lancé par l'autostart openbox).
- **`50_session.yml`** → `openbox-autostart.j2` **conditionnel** : lance **Pegasus** si
  `desktop_frontend == pegasus`, sinon **tint2**. `tint2rc` écrit seulement si tint2.
  + light-locker si `desktop_screenlock`.
- **`55_pegasus.yml`** (nouveau, `when: desktop_frontend == 'pegasus'`) :
  - télécharge + installe Pegasus natif dans `~/Applications/pegasus`.
  - config de base `~/.config/pegasus-frontend/` : providers Lutris + Steam activés (import auto),
    collection "Applications" (Brave + Jellyfin Media Player).
  - (retro + art = Steam ROM Manager en suivi manuel.)
- **`60_optimisations.yml`** : `desktop_purge_snapd` **false** sur ce nœud (override host_vars) —
  MicroK8s dépend de snapd. Reste (cloud-init/oomd/zram/grub mitigations) inchangé.

### Inchangé
`10_packages` (Xorg/Openbox/PipeWire/bluez/flatpak), `20_nvidia` (driver via var), `30_brave`.

## Changements `host_vars/gaming-pc.yml` (nouveau)
```yaml
desktop_frontend: pegasus
desktop_autologin: false
desktop_screenlock: true
desktop_nvidia_driver: nvidia-driver-580     # Pascal 1050 Ti (branche legacy maintenue)
desktop_hold_hwe_kernel: false               # pas de contrainte 470
desktop_purge_snapd: false                   # microk8s = snap
gaming_blacklist_rtl8723_wifi: false         # autre carte que le laptop
gaming_btusb_disable_autosuspend: false
gaming_nvidia_gl_i386_package: "libnvidia-gl-580:i386"
media_xinput_disable_devices: []             # pas de touchpad
```

## Rôle `gaming` / `media-pc`
Aucun code — pilotés par les host_vars ci-dessus. `50_bluetooth_fix` devient no-op (toggles false),
`30_disable_input` skip (liste vide). Lutris/jeux apt/Steam/Jellyfin/gamemode conservés.

## Dépendance séparée : `k8s-node-bootstrap` variante worker
Join worker (pas de control-plane) + **nvidia-container-toolkit** (passthrough 1050 Ti → NVENC
jellyfin) + label `workload=offload`. = Phase 0 du plan k8s. Traité à part.

## Cleanup au déploiement
- Retirer l'entrée Lutris `es-de` (pga.db) + `~/Applications/esde`. RetroArch + cœurs gardés.

## Ordre
1. Rôle `desktop` : toggles + 40 conditionnel + 55_pegasus + 50 conditionnel. ← **ce commit**
2. `host_vars/gaming-pc.yml`.
3. Cleanup ES-DE (déploiement).
4. `k8s-node-bootstrap` worker + NVENC (plan séparé).
