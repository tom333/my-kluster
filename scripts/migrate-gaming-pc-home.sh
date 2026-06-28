#!/usr/bin/env bash
#
# migrate-gaming-pc-home.sh
#
# Restaure les données utilisateur du gaming-pc depuis l'ancienne install Bodhi
# (partition sda2) vers la nouvelle install Ubuntu Server 24.04 (sda3).
#
# À LANCER SUR LE NOUVEAU SYSTÈME, en tant que `moi`, APRÈS :
#   1. fresh install Ubuntu Server 24.04 sur sda3 (user=moi, hostname=jeux, SSH on)
#   2. provisioning Ansible (ansible-playbook --limit gaming-pc --tags desktop,games,media)
#
# Bodhi (sda2) est monté en LECTURE SEULE -> aucun risque pour l'ancien système.
# Les chemins/UID étant identiques (user moi = uid 1000), la ludothèque Lutris
# (pga.db) et les prefixes Wine remarchent tels quels.
#
# Usage : ./migrate-gaming-pc-home.sh [/dev/sdaX]   (défaut: /dev/sda2 = Bodhi)

set -euo pipefail

SRC_DEV="${1:-/dev/sda2}"
MNT="/mnt/bodhi"
USER_NAME="moi"
SRC_HOME="$MNT/home/$USER_NAME"
DST_HOME="$HOME"

[ "$(id -un)" = "$USER_NAME" ] || { echo "ERREUR: lance ce script en tant que '$USER_NAME'."; exit 1; }
[ "$DST_HOME" = "/home/$USER_NAME" ] || { echo "ERREUR: HOME inattendu ($DST_HOME)."; exit 1; }

echo ">>> Montage $SRC_DEV (read-only) sur $MNT"
sudo mkdir -p "$MNT"
mountpoint -q "$MNT" || sudo mount -o ro "$SRC_DEV" "$MNT"

# Garde-fou : c'est bien l'ancien home avec la ludothèque ?
if [ ! -d "$SRC_HOME/.config/lutris" ]; then
  echo "ERREUR: pas de ~/.config/lutris dans $SRC_HOME — mauvaise partition ($SRC_DEV) ?"
  sudo umount "$MNT"; exit 1
fi

# Dossiers à restaurer (données irremplaçables + runners référencés par Lutris).
DIRS=(
  Applications                       # AppImages/jars (Prism, ES-DE, RetroArch, Dusklight, OpenRA, jre25, Xonotic...) — référencés par pga.db
  jeux                               # Tomb Raider (jeu + prefix Wine), ROMs rétro
  retro                              # ROMs ES-DE
  .minecraft                         # données launcher officiel + 32 mondes
  .local/share/PrismLauncher         # instance Prism "SachNC" + mondes
  .config/lutris                     # config jeux (yml) + system.yml (gamemode)
  .local/share/lutris                # pga.db (ludothèque) + jaquettes + runners/wine (wine-ge)
  .config/retroarch                  # cœurs + configs + SAVES/STATES émulateurs
  ES-DE                              # config ES-DE + médias scrapés
  .local/share/flatpak               # apps flatpak user (OpenSurge, Scratch) + runtimes
  .var/app                           # données des apps flatpak
)

# Optionnel (gros, re-téléchargeable) : décommenter pour rapatrier la lib Steam.
# DIRS+=( .steam .local/share/Steam )

for d in "${DIRS[@]}"; do
  if [ -e "$SRC_HOME/$d" ]; then
    echo ">>> Restore $d"
    mkdir -p "$DST_HOME/$(dirname "$d")"
    rsync -aH --info=progress2 "$SRC_HOME/$d/" "$DST_HOME/$d/"
    sudo chown -R "$USER_NAME:$USER_NAME" "$DST_HOME/$d"
  else
    echo ">>> (absent sur Bodhi, skip) $d"
  fi
done

echo ">>> Démontage $MNT"
sudo umount "$MNT"

cat <<EOF

=== Terminé ===
- Relance Lutris -> la ludothèque (24 jeux + jaquettes) doit être là.
- Vérifie : un monde Minecraft (Prism instance SachNC), un état RetroArch, Tomb Raider.
- Steam non rapatrié par défaut (re-télécharge, ou décommente la ligne DIRS+=).
- Quand tout est validé, tu peux récupérer sda2 (ancien Bodhi) comme espace libre.
EOF
