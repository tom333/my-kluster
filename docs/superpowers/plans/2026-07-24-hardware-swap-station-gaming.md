# Plan — Swap matériel : R5 5500 → station, i5-9400F → PC jeu

Date : 2026-07-24

## Principe
Le **CPU fort va à la machine la plus chargée**. La station `pc` (cluster + fabrique IA
+ dev) est **CPU-saturée** (i5-9400F 6c/**6t**, load 5.5) et **RAM-tendue** (62 Go, swap plein).
- **Station `pc`** ← reçoit **B550M-K + R5 5500 (6c/12t Zen3)** + **PSU 750W** ; garde RAM/disques/3060.
- **PC jeu `jeux`** ← reçoit l'**ancienne CM LGA1151 + i5-9400F** + VS450 + la RAM/SSD/1050 Ti de l'achat AM4.
Les **2 goulots** traités : CPU par le swap (6t→12t), RAM par l'**offload** de pods vers le worker (i5).

## Config cible
| | CPU | CM | RAM | GPU | PSU | Disques |
|---|---|---|---|---|---|---|
| **Station `pc`** (Ubuntu 26.04) | R5 5500 12t | B550M-K (AM4) | 62 Go 2×32 (déplacée) | RTX 3060 | **750W** | SSD SATA (/,OS) + NVMe (LABEL kube-data,/data) + HDD SATA (/media/data) |
| **PC jeu `jeux`** (Ubuntu 24.04) | i5-9400F 6t | ancienne CM LGA1151 | 16 Go (achat AM4) | 1050 Ti | VS450 | SSD + 2 To SATA (achat AM4) |

## Faits clés (station)
- Ubuntu **26.04** (AMD/3060 OK, driver courant). fstab `/` + `/data`(LABEL) + `/media/data`(UUID ✅ corrigé). Réseau **NetworkManager**, IP **192.168.88.250**, NIC `enp3s0`. Master control-plane MicroK8s. Data des pods (hostpath) sur les disques → **suit la station**.

---

## Phase 0 — Pré-vol (AVANT d'ouvrir la station)
- [x] Backup **clé Sealed Secrets** rafraîchi (fait).
- [x] fstab `/media/data` en **UUID** (fait).
- [ ] **Burn-in B550M-K + 5500** : boot USB jetable → **memtest86** (2×32 en DOCP) + `stress-ng --cpu $(nproc) --timeout 1h`. CM/RAM instable sous charge = corruption cluster. **Ne pas mettre les disques prod avant OK.**
- [ ] **Noter la MAC** de la NIC B550M-K (pendant le burn-in : `ip link`).
- [ ] **Plan réseau `.250`** : déterminer si `.250` = statique NM ou **réservation DHCP MikroTik (par MAC)**.
  - statique NM → recréer le profil sur la nouvelle NIC (IP .250/24, GW 192.168.88.1, DNS, **ipv6 disabled** = re-appliquer le fix kicker).
  - réservation MikroTik → **mettre à jour la réservation vers la nouvelle MAC**.
- [ ] **Clé live Ubuntu** prête (réparation GRUB/EFI).
- [ ] **Retrouver le disque du laptop Bodhi mort** (ludothèque Lutris + 32 mondes Minecraft + ROMs) → adaptateur USB pour le brancher au PC jeu au moment de la restauration (cf. `migrate-gaming-pc-home.sh`, source = ce disque, pas sda2).

## Phase 1 — Fenêtre de coupure
Down pendant le swap : **cluster + média (jellyfin/*arr) + fabrique IA + dev**. Restent up : **Home Assistant** (hors cluster, .201), NAS, routeur, LibreELEC, PiHole. Prévoir 2-4 h.

## Phase 2 — Swap physique (ordre)
1. **Shutdown propre** de la station.
2. Démonter de la station : i5 + son cooler + CM LGA1151 + PSU actuelle → **mis de côté INTACTS** (PC jeu + rollback).
3. **Garder** : les 3 disques, les 2×32 RAM, la 3060.
4. Monter dans le boîtier station : **B550M-K + 5500** (déjà burn-in) + **750W** + RAM 2×32 en **A2/B2** + les 3 disques + 3060 (PCIe x16).
5. **Ne PAS** encore assembler le PC jeu (rollback possible tant que la station n'est pas validée).

## Phase 3 — 1er boot station + fixups
1. **Boot** : menu UEFI one-shot → disque Ubuntu (EFI sda). Si pas d'entrée boot → **live-USB → chroot → `grub-install` + `update-grub` + `efibootmgr`**.
2. **BIOS** : DOCP (RAM), Resizable BAR (3060), SVM, **Secure Boot OFF** (dkms nvidia), UEFI.
3. **Réseau** : nouvelle NIC → poser **.250** (NM) + **ipv6 disabled** (fix kicker). Vérifier `.250` + internet + `/mnt/nas`.
4. **Montages** : `findmnt --verify` ; `/data` (LABEL), `/media/data` (UUID), `/mnt/nas` OK.
5. **nvidia 3060** : `nvidia-smi` (dkms rebuild auto si kernel/HW changé). gpu-operator re-valide (garder l'œil sur GPU-unhealthy → force-delete pods GPU coincés si besoin).
6. **MicroK8s** : `microk8s status` → cluster revient ; `kubectl get nodes/pods -A` ; addon GPU healthy ; LocalAI sert.

## Phase 4 — Validation (GATE avant de cannibaliser l'i5)
✅ Station stable + `.250` + **tous pods Running** + 3060 utilisable (LocalAI) + dev OK + `load` en baisse nette. **Tant que non-vert → NE PAS** toucher l'i5/ancienne CM (rollback = remettre les disques dessus).

## Phase 5 — Build + provision PC jeu (`jeux`)
1. Assembler : CM LGA1151 + i5 + cooler (**re-pâte**) + 16 Go + 1050 Ti + SSD + 2 To + VS450.
2. Install **Ubuntu Server 24.04** (user **moi**, hostname **jeux**, SSH).
3. **Re-plan host_vars Intel** (cf. Phase 7).
4. `ansible-playbook -i inventory.yml playbook.yml --limit gaming-pc -e ansible_host=<ip> --vault-password-file … --ask-become-pass` → desktop (Pegasus) + gaming + worker.
5. Reboot. Join worker auto (token délégué au master).
6. **Restore data** : brancher le disque Bodhi (USB) → adapter `migrate-gaming-pc-home.sh` (source = disque laptop) → ludothèque/mondes/ROMs.
7. Steam ROM Manager (art rétro Pegasus). Cleanup ES-DE.

## Phase 6 — Offload pods
Cf. `2026-07-07-k8s-secondary-node-x299.md` (renommé AM4 → maintenant l'i5). Worker = i5 6t + 16 Go (extensible). CPU moins urgent (station 12t) ; **RAM offload = le vrai gain restant** (vider le swap station). 4 vagues, co-loc 1 GbE, hostpath = rsync+pin.

## Phase 7 — Re-plan Ansible Intel↔AMD (host_vars/gaming-pc.yml)
Le PC jeu **redevient Intel** (i5-9400F, intel_pstate) :
- **retirer** `desktop_cpu_epp` + remettre `desktop_force_cpu_governor: true` (ou défaut) — l'amd_pstate ne s'applique plus.
- `desktop_nvidia_driver: nvidia-driver-580` **inchangé** (1050 Ti = Pascal).
- reste inchangé : `desktop_frontend: pegasus`, `desktop_autologin: false`, `desktop_purge_snapd: false` (worker), `k8s_node_role: worker`, `k8s_node_expected_hostname: jeux`, GL i386 580.
- **Station (AMD Zen3)** : tuning amd_pstate côté master (hors desktop role) — optionnel, amd_pstate=active par défaut suffit.

## Rollback
Tant que Phase 4 pas verte : remettre les 3 disques + RAM + 3060 sur **l'ancienne CM LGA1151 + i5** (conservée intacte) + ancienne PSU → retour à l'état d'origine. Aucune donnée détruite (disques jamais formatés).

## Points ouverts
- Disque du laptop Bodhi mort **récupérable** ? (sinon ludothèque/mondes à reconstruire).
- `.250` = NM statique ou réservation DHCP MikroTik ? (détermine le fix réseau).
- Boîtier PC jeu accepte la CM LGA1151 (form factor) ?
