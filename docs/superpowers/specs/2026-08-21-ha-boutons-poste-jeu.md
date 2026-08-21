# Spec — boutons Home Assistant pour le poste de jeu

**Date** : 2026-08-21
**Cible** : Home Assistant (192.168.88.201) → poste de jeu `gaming-pc` (192.168.88.150, nœud k8s `jeux`)
**But** : deux boutons depuis le téléphone — **verrouiller l'écran** et **afficher un message**
(« A TABLE ! ») en grand sur la TV de la salle de jeux.

---

## 1. Ce qui existe déjà, et ce qui reste à faire

Côté poste de jeu, tout est écrit et **testé visuellement** (le bandeau s'affiche par-dessus
un jeu en plein écran) :

| Élément | État |
|---|---|
| `annoncer "<texte>" [durée]` | ✅ fonctionne, dans `~/bin` |
| `verrouiller` | ✅ fonctionne, dans `~/bin` |
| Rôle Ansible (`desktop`) qui les pose dans `/usr/local/bin` | ✅ committé (`dfca0e4f`), **pas encore appliqué** |
| Clé SSH dédiée à Home Assistant | ❌ **à faire** |

⚠️ **Les scripts ne sont aujourd'hui QUE dans `~/bin`**, pas dans `/usr/local/bin`. Or `~/bin`
n'est jamais dans le `PATH` d'une commande SSH non interactive : `ssh jeux annoncer` échoue
avec `command not found`. Deux options :

```bash
# a) tout de suite, une seule commande (nécessite le mot de passe sudo)
ssh -t moi@192.168.88.150 'sudo install -o root -g root -m 755 ~/bin/verrouiller ~/bin/annoncer -t /usr/local/bin/'

# b) ou rejouer le rôle, qui les installe au bon endroit
cd ansible && ansible-playbook -i inventory.yml playbook.yml --limit gaming-pc --tags desktop \
  --vault-password-file ~/.vault-password.txt --ask-become-pass
```

Tant que ce n'est pas fait, **utiliser le chemin complet** dans Home Assistant :
`'~/bin/annoncer'` au lieu de `annoncer`.

> Note : Ansible est actuellement cassé sur le poste de travail (venvs pipx orphelins de
> `python3.13`, retiré par une montée de version). L'option (a) est donc la plus rapide.

---

## 2. Clé SSH dédiée à Home Assistant

**Ne pas réutiliser la clé personnelle `moi@pc`.** Une clé propre à HA permet de la révoquer
sans casser l'accès humain.

Sur Home Assistant (add-on Terminal, ou n'importe quel shell y ayant accès) :

```bash
mkdir -p /config/.ssh && chmod 700 /config/.ssh
ssh-keygen -t ed25519 -f /config/.ssh/id_jeux -N "" -C "home-assistant-vers-jeux"
chmod 600 /config/.ssh/id_jeux
cat /config/.ssh/id_jeux.pub
```

Puis autoriser cette clé publique sur le poste de jeu :

```bash
ssh moi@192.168.88.150 'cat >> ~/.ssh/authorized_keys' <<< "<contenu de id_jeux.pub>"
```

Clés déjà autorisées sur `.150`, pour référence (la nouvelle viendra s'ajouter) :

```
moi@pc                            SHA256:T6Mieqorw/2EOAQO5sMek7gsedHTGdKGcJMnFOYOciA
migration-jeux-196-vers-150       SHA256:NIDaiD4BEFyZQtuPZQMZWD9Fxi/ayshmKcw/ccw5w9g
```

**Durcissement conseillé** — restreindre cette clé aux deux seules commandes utiles, pour
qu'une fuite du fichier ne donne pas un shell. Dans `authorized_keys`, préfixer la ligne :

```
restrict,command="/usr/local/bin/ha-commande" ssh-ed25519 AAAA... home-assistant-vers-jeux
```

avec un dispatcher qui n'accepte que ces deux verbes (à écrire si l'on retient cette option) :

```bash
#!/usr/bin/env bash
# /usr/local/bin/ha-commande — n'autorise que verrouiller et annoncer.
set -eu
case "${SSH_ORIGINAL_COMMAND:-}" in
  verrouiller) exec /usr/local/bin/verrouiller ;;
  "annoncer "*) exec /usr/local/bin/annoncer "${SSH_ORIGINAL_COMMAND#annoncer }" ;;
  *) echo "commande non autorisee" >&2; exit 1 ;;
esac
```

C'est optionnel. Sans durcissement, la clé HA donne un shell complet en tant que `moi` sur un
nœud du cluster — à arbitrer selon le niveau d'exposition jugé acceptable.

---

## 3. Configuration Home Assistant

### `configuration.yaml`

```yaml
shell_command:
  jeux_verrouiller: >-
    ssh -i /config/.ssh/id_jeux -o StrictHostKeyChecking=accept-new
    -o ConnectTimeout=5 -o BatchMode=yes
    moi@192.168.88.150 verrouiller

  jeux_a_table: >-
    ssh -i /config/.ssh/id_jeux -o StrictHostKeyChecking=accept-new
    -o ConnectTimeout=5 -o BatchMode=yes
    moi@192.168.88.150 "annoncer 'A TABLE !' 10"

  # Variante paramétrable : le texte et la durée viennent de l'appel.
  jeux_annoncer: >-
    ssh -i /config/.ssh/id_jeux -o StrictHostKeyChecking=accept-new
    -o ConnectTimeout=5 -o BatchMode=yes
    moi@192.168.88.150 "annoncer '{{ texte }}' {{ duree | default(10) }}"
```

`BatchMode=yes` est important : sans lui, une clé refusée fait attendre un mot de passe et la
commande reste bloquée jusqu'au timeout de HA.

### Scripts (pour avoir de vrais boutons)

```yaml
script:
  jeux_a_table:
    alias: "Salle de jeux — A TABLE !"
    icon: mdi:silverware-fork-knife
    sequence:
      - service: shell_command.jeux_a_table
    mode: single

  jeux_verrouiller:
    alias: "Salle de jeux — verrouiller l'écran"
    icon: mdi:lock
    sequence:
      - service: shell_command.jeux_verrouiller
    mode: single

  jeux_prevenir_fin:
    alias: "Salle de jeux — prévenir puis verrouiller"
    icon: mdi:timer-lock
    sequence:
      - service: shell_command.jeux_annoncer
        data:
          texte: "FIN DANS 5 MINUTES"
          duree: 15
      - delay: "00:05:00"
      - service: shell_command.jeux_verrouiller
    mode: single
```

Le troisième est le plus utile à l'usage : il **prévient avant** de couper, ce qui évite
d'interrompre une partie sans sommation.

### Carte de tableau de bord

```yaml
type: horizontal-stack
cards:
  - type: button
    name: A TABLE !
    icon: mdi:silverware-fork-knife
    tap_action: { action: call-service, service: script.jeux_a_table }
  - type: button
    name: Verrouiller
    icon: mdi:lock
    tap_action: { action: call-service, service: script.jeux_verrouiller }
```

---

## 4. Points de vigilance

Ces deux scripts ont demandé du diagnostic ; les contraintes suivantes ne sont pas
optionnelles.

**Environnement graphique.** Les deux commandes relisent `DISPLAY`, `XAUTHORITY`,
`XDG_SESSION_PATH` etc. **sur le processus `openbox`**, parce qu'une session SSH ne les a pas.
Sans `XDG_SESSION_PATH`, `light-locker` meurt sur « Is LightDM running? ». Ne jamais prendre
`pegasus-fe` comme référence : s'il a été relancé hors session, il porte l'environnement du
shell appelant. Cette logique est **interne aux scripts** — rien à faire côté HA.

**Session graphique ouverte requise.** Si personne n'est connecté (LightDM affiche l'écran de
login, `desktop_autologin: false`), il n'y a pas d'`openbox` : les deux commandes sortent en
erreur `session graphique introuvable`. Comportement voulu, mais il faut le prévoir si un
automatisme les appelle sans condition.

**Guillemets.** Le texte passe par deux couches de shell (local puis distant). La forme
`"annoncer 'A TABLE !' 10"` fonctionne ; une apostrophe **dans le texte** (« C'EST L'HEURE »)
casserait le quoting. Si le besoin apparaît, passer par `base64` ou l'API `--stdin`.

**Le message ne bloque rien.** `annoncer` affiche et disparaît, il ne met pas le jeu en pause.
C'est un rappel, pas une interruption.

**Machine allumée en permanence.** Le poste est un worker MicroK8s, il tourne 24/7. La barrière
du démarrage à froid ne joue donc quasiment jamais : le verrou à l'inactivité (900 s) et ces
boutons sont la vraie protection.

---

## 5. Validation

À dérouler dans cet ordre :

1. **Depuis le poste de travail**, sans HA :
   `ssh jeux '~/bin/annoncer "TEST" 3'` → bandeau 3 s.
2. **Depuis HA, à la main** (Terminal add-on), avec la clé HA :
   `ssh -i /config/.ssh/id_jeux -o BatchMode=yes moi@192.168.88.150 "annoncer 'TEST HA' 3"`
   → valide la clé et le réseau HA → poste de jeu.
3. **Outils de développement HA** → Services → `shell_command.jeux_a_table` → Exécuter.
4. **Bouton du tableau de bord**, puis depuis le téléphone.
5. **`verrouiller`** en dernier : vérifier que le mot de passe est demandé et que Pegasus est
   intact derrière.

En cas d'échec silencieux, `shell_command` ne remonte rien d'utile : lire le journal HA
(`Paramètres → Système → Journaux`), et rejouer la commande à l'étape 2 pour voir l'erreur SSH
réelle.

---

## 6. Pistes ultérieures

- **Annonce vocale** plutôt qu'écrite, via le pipeline TTS déjà en place (cf.
  `docs/hermes-voice-hybrid.md`) — le poste a PipeWire et sort le son sur la TV en HDMI.
- **Détection de présence** pour n'annoncer que si quelqu'un joue : un capteur basé sur
  l'existence d'un processus jeu (`pgrep -x retroarch` etc.) exposé en `binary_sensor` par
  commande SSH.
- **Temps de jeu quotidien** : Pegasus tient déjà un `stats.db`, exploitable pour un compteur
  et un verrouillage automatique au-delà d'un quota.
