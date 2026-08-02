# Home Assistant Voice — Phase 1 phone-only (procédure complète)

Ce document détaille le déploiement du **pilote vocal maison** (Variante A pure : intent matching, sans LLM dans la boucle voice) en utilisant ton **smartphone via l'app HA Companion** comme seul device de capture audio.

**Objectif** : pouvoir tapper le widget mic sur ton téléphone et dire « allume le salon », « quelle température au bureau », « active scénario nuit » — réponse vocale en ~3 secondes, 100% local, sans cloud.

---

## 🟢 État actuel (déployé le 2026-05-26)

Les 2 services Wyoming sont **déployés** dans le cluster (namespace `voice`), via ArgoCD, exposés en NodePort sur le node k8s.

### Endpoints de disponibilité (à utiliser dans la config HA)

| Service | Image déployée | IP:Port LAN (NodePort) | Port interne | Protocole |
|---|---|---|---|---|
| **Whisper (STT)** | `rhasspy/wyoming-whisper:3.1.0` | **`192.168.88.250:30300`** | 10300 | Wyoming/TCP |
| **Piper (TTS)** | `rhasspy/wyoming-piper:2.2.2` | **`192.168.88.250:30200`** | 10200 | Wyoming/TCP |

> ⚠ **Important** : HA tourne **hors cluster** (HAOS sur `192.168.88.201`). Il doit pointer sur le **NodePort** (`30300`/`30200`), **PAS** sur le port interne (`10300`/`10200`). Le port interne n'existe que dans le cluster.

| Élément | Valeur |
|---|---|
| Node k8s (host des NodePorts) | `192.168.88.250` |
| HAOS (client Wyoming) | `192.168.88.201` |
| Namespace k8s | `voice` |
| AppProject ArgoCD | `infra-project` |
| Manifests | `argocd/argocd-apps/wyoming-{whisper,piper}-app.yaml` |
| Renovate | customManager track les 2 image tags (cf. `renovate.json`) |

### Vérifier que c'est prêt

```bash
# Les 2 NodePorts doivent répondre "succeeded" (le port s'ouvre APRÈS download du modèle)
nc -zv 192.168.88.250 30300   # Whisper
nc -zv 192.168.88.250 30200   # Piper

# État des pods + logs
kubectl -n voice get pod
kubectl -n voice logs deploy/wyoming-whisper --tail=20   # cherche "Ready"
kubectl -n voice logs deploy/wyoming-piper  --tail=20
```

Reste à faire (côté humain) : config HA (§7), une fois les 2 `nc` OK.

---

## 1. Architecture

```
[Smartphone HA Companion]
        │   tap mic → enregistre audio
        ↓   audio bytes (Wyoming protocol)
[Home Assistant (VM/Pi - hors cluster)]
        │
        ├─→ Whisper STT (cluster k8s, NodePort)
        │   192.168.88.250:30300 → "allume le salon"
        │
        ├─→ HA Assist Intent Recognition (built-in, FR)
        │   match pattern → service: light.turn_on, entity_id: light.salon
        │
        ├─→ Exécution action HA
        │   light.turn_on → 💡
        │
        └─→ Piper TTS (cluster k8s, NodePort)
            192.168.88.250:30200 → audio "salon allumé"
                │
                ↓
[Smartphone joue le son]
```

**Latence cible** : 3-5 secondes du tap-to-talk au son de confirmation, dont 1-2s c'est ta voix.

---

## 2. Composants à déployer dans le cluster

| Composant | Image (déployée) | Port interne | NodePort LAN | CPU/GPU | RAM | Disque |
|---|---|---|---|---|---|---|
| `wyoming-whisper` (STT) | `rhasspy/wyoming-whisper:3.1.0` | 10300/TCP | `192.168.88.250:30300` | CPU (Phase 1) | ~2 GB | ~2 GB (modèle) |
| `wyoming-piper` (TTS) | `rhasspy/wyoming-piper:2.2.2` | 10200/TCP | `192.168.88.250:30200` | CPU | ~200 MB | ~100 MB (voix) |

> Note historique : versions initiales du doc (`wyoming-faster-whisper:2.5.0`, `wyoming-piper:1.5.0`) étaient périmées/erronées. Réel déployé : `wyoming-whisper:3.1.0` + `wyoming-piper:2.2.2` (mai 2026).

**Pourquoi CPU pour Whisper en Phase 1** :
- Évite la compétition VRAM avec LocalAI (Qwen 7B + Flux + DeepSeek)
- 2-3s d'audio en français = ~1-2s transcription CPU = acceptable au smartphone
- Pas de cold-start GPU à craindre
- Bascule en GPU possible plus tard (Phase 3) si ESP32 + usage intensif

**Pourquoi Wyoming Protocol (TCP, pas HTTP)** :
- Protocole standard ouvert utilisé par HA Assist
- TCP raw, pas HTTP → pas d'Ingress NGINX nécessaire
- Exposition via `NodePort` Kubernetes (le plus simple sur MicroK8s sans MetalLB)

---

## 3. Pré-requis

- [ ] Home Assistant **2024.11+** (pour HA Assist français mature) ou plus récent
- [ ] HA Companion app installée sur ton smartphone (iOS/Android)
- [ ] HA et le cluster k8s sur le **même LAN** (192.168.88.0/24)
- [x] **IP du node k8s** : `192.168.88.250` (host des NodePorts)
- [x] **IP de HAOS** : `192.168.88.201`
- [ ] Au moins **1-2 entités HA** que tu veux piloter vocalement (light, climate, switch…)

Vérifications rapides :

```bash
# 1. IP du node k8s exposable au LAN
kubectl get nodes -o wide
# Note la colonne EXTERNAL-IP ou INTERNAL-IP

# 2. Que tu as bien des entités HA pilotables
# Va sur ton HA UI → Settings → Devices & services → Entities
# Note quelques entity_id : light.salon, light.bureau, climate.chambre, etc.
```

---

## 4. Préparer le namespace k8s

```bash
# Créer le namespace dédié voice
kubectl create namespace voice

# Ce namespace utilise le project "infra-project" (déjà autorisé pour ns:* dans le cluster)
# Donc rien à modifier côté AppProjects ArgoCD
```

---

## 5. Déploiement Wyoming Whisper (STT)

### 5.1. Application ArgoCD

Créer `argocd/argocd-apps/wyoming-whisper-app.yaml` :

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: wyoming-whisper
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  destination:
    namespace: voice
    server: https://kubernetes.default.svc
  project: infra-project
  source:
    repoURL: https://bjw-s-labs.github.io/helm-charts
    chart: app-template
    targetRevision: 5.0.1
    helm:
      values: |
        controllers:
          whisper:
            type: deployment
            strategy: Recreate
            containers:
              main:
                image:
                  repository: rhasspy/wyoming-whisper
                  tag: "3.1.0"
                  pullPolicy: IfNotPresent
                args:
                  - "--model"
                  - "large-v3-turbo"          # Qualité large, vitesse turbo
                  - "--language"
                  - "fr"                       # Langue par défaut FR
                  - "--uri"
                  - "tcp://0.0.0.0:10300"      # Écoute Wyoming protocol
                  - "--data-dir"
                  - "/data"
                  - "--download-dir"
                  - "/data"
                  - "--device"
                  - "cpu"                      # CPU en Phase 1 (pas de conflit VRAM)
                  - "--beam-size"
                  - "1"                        # Plus rapide, OK pour commandes courtes
                resources:
                  limits:   { cpu: "4",   memory: 4Gi }
                  requests: { cpu: "500m", memory: 2Gi }
        service:
          app:
            controller: whisper
            type: NodePort
            ports:
              wyoming:
                port: 10300
                targetPort: 10300
                nodePort: 30300       # Exposé sur 192.168.88.250:30300
                protocol: TCP
        persistence:
          data:
            type: persistentVolumeClaim
            storageClass: microk8s-hostpath
            accessMode: ReadWriteOnce
            size: 5Gi                 # Cache du modèle (~2 GB téléchargé)
            globalMounts:
              - path: /data
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
    automated:
      selfHeal: true
      prune: true
```

**Note sur le premier démarrage** : le container va télécharger Whisper Large-v3-Turbo depuis HuggingFace au premier boot (~1.5 GB). À ta bande passante (~5 Mbps), compte **40-50 minutes** de download initial. Ensuite c'est cached dans le PVC.

### 5.2. Push + sync

```bash
git add argocd/argocd-apps/wyoming-whisper-app.yaml
git commit -m "feat(voice): add wyoming-whisper STT (CPU, FR, large-v3-turbo)"
git push

# Attendre la sync ArgoCD ou forcer
kubectl -n argocd patch app wyoming-whisper --type merge -p '{"operation":{"sync":{}}}'

# Surveiller le download du modèle (premier boot)
kubectl -n voice logs deploy/wyoming-whisper -f
# Tu dois voir des logs "Downloading model..." puis "Loading..."
# Quand tu vois "Ready" ou similar, c'est OK
```

### 5.3. Test de connectivité STT

```bash
# Le service NodePort doit être accessible depuis le LAN
nc -zv 192.168.88.250 30300
# Doit afficher "Connection to ... 30300 port [tcp/*] succeeded!"

# Test d'un round-trip Wyoming (optionnel, nécessite python wyoming)
pip install wyoming
python -c "
import asyncio
from wyoming.client import AsyncTcpClient
async def main():
    async with AsyncTcpClient('192.168.88.250', 30300) as client:
        print('Connected to Whisper')
asyncio.run(main())
"
```

---

## 6. Déploiement Wyoming Piper (TTS)

### 6.1. Application ArgoCD

Créer `argocd/argocd-apps/wyoming-piper-app.yaml` :

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: wyoming-piper
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  destination:
    namespace: voice
    server: https://kubernetes.default.svc
  project: infra-project
  source:
    repoURL: https://bjw-s-labs.github.io/helm-charts
    chart: app-template
    targetRevision: 5.0.1
    helm:
      values: |
        controllers:
          piper:
            type: deployment
            strategy: Recreate
            containers:
              main:
                image:
                  repository: rhasspy/wyoming-piper
                  tag: "2.2.2"
                  pullPolicy: IfNotPresent
                args:
                  - "--voice"
                  - "fr_FR-siwis-medium"       # Voix féminine FR claire
                  - "--uri"
                  - "tcp://0.0.0.0:10200"      # Wyoming protocol port
                  - "--data-dir"
                  - "/data"
                  - "--download-dir"
                  - "/data"
                resources:
                  limits:   { cpu: "2",   memory: 1Gi }
                  requests: { cpu: "200m", memory: 256Mi }
        service:
          app:
            controller: piper
            type: NodePort
            ports:
              wyoming:
                port: 10200
                targetPort: 10200
                nodePort: 30200       # Exposé sur 192.168.88.250:30200
                protocol: TCP
        persistence:
          data:
            type: persistentVolumeClaim
            storageClass: microk8s-hostpath
            accessMode: ReadWriteOnce
            size: 1Gi                 # Voix Piper FR ~100 MB
            globalMounts:
              - path: /data
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
    automated:
      selfHeal: true
      prune: true
```

**Premier démarrage** : ~100 MB de voix à télécharger. **2-3 minutes** à ta bande passante.

### 6.2. Push + sync

```bash
git add argocd/argocd-apps/wyoming-piper-app.yaml
git commit -m "feat(voice): add wyoming-piper TTS (FR siwis voice)"
git push

kubectl -n argocd patch app wyoming-piper --type merge -p '{"operation":{"sync":{}}}'

kubectl -n voice logs deploy/wyoming-piper -f
# Voir "Voice 'fr_FR-siwis-medium' loaded" puis "Ready"
```

### 6.3. Vérification

```bash
# Les 2 services exposés
kubectl -n voice get svc
# wyoming-whisper-app  NodePort  ClusterIP   10.x.x.x  10300:30300/TCP
# wyoming-piper-app    NodePort  ClusterIP   10.x.x.x  10200:30200/TCP

# Test connectivité depuis ton poste de dev
nc -zv 192.168.88.250 30300   # whisper
nc -zv 192.168.88.250 30200   # piper
```

---

## 7. Configuration Home Assistant (sur la VM/Pi)

### 7.1. Ajouter l'intégration Wyoming Protocol

Depuis l'UI HA :

1. **Settings** → **Devices & services** → **Add Integration**
2. Chercher **« Wyoming Protocol »**
3. Cliquer → entrer :
   - **Host** : `192.168.88.250` (IP du node k8s)
   - **Port** : `30300` (Whisper — **NodePort**, pas 10300 !)
4. Cliquer Submit → HA détecte automatiquement « whisper »

Répéter pour Piper :
1. Add Integration → Wyoming Protocol
2. Host : `192.168.88.250`, Port : `30200` (**NodePort**, pas 10200 !)
3. HA détecte « piper »

> ⚠ HA est hors cluster → il atteint les services via le **NodePort** (`30300`/`30200`), pas le port interne Wyoming (`10300`/`10200`). Le port interne n'est joignable que depuis l'intérieur du cluster.

### 7.2. Créer le pipeline Assist

1. **Settings** → **Voice assistants** → cliquer **Add assistant**
2. Configurer :
   - **Name** : `Domicile` (ou ce que tu veux)
   - **Language** : `Français`
   - **Conversation agent** : `Home Assistant` (= intent recognition built-in, **PAS** d'agent LLM externe en Phase 1)
   - **Speech-to-text** : `faster-whisper` (la nouvelle intégration)
   - **Text-to-speech** : `piper`
   - **TTS voice** : `fr_FR-siwis-medium`
3. **Save**

### 7.3. Définir cet assistant comme défaut

- Dans la liste, clic sur **⭐ Set as preferred** sur l'assistant `Domicile`.

### 7.4. Activer l'accès via HA Companion (smartphone)

Côté smartphone, dans **HA Companion app** :

1. **Settings** → **Companion app** → **Voice assistant**
2. Sélectionner l'assistant `Domicile`
3. Optionnel : activer **« Show on Wear OS »** ou widget rapide selon ton OS

---

## 8. Premières commandes (test)

Sur smartphone, tap l'icône **micro** dans l'app HA (en haut à droite, ou via widget) :

### Commandes built-in (fonctionnent direct, FR natif depuis 2024.11) :

```
Allume le salon
Éteins toutes les lumières
Quelle est la température dans le bureau ?
Ferme les volets de la chambre
Active la scène cinéma
Quelle est l'heure ?                   ← built-in
Quel temps fait-il ?                   ← built-in (si tu as une intégration météo)
```

### Pour piloter une entité, il faut qu'elle soit **exposée à Assist** :

1. HA UI → **Settings** → **Voice assistants** → ton assistant → onglet **Expose**
2. Cocher toutes les entités que tu veux pilotables (lights, climate, switch, scene)
3. Donner des **alias** aux entités si leur nom système est moche (`light.salon_principal_dimmer` → alias `salon`)

---

## 9. Étendre avec des intentions custom (sentences)

Si une formulation n'est pas reconnue (genre « plus chaud ici » à la place de « augmente la température »), tu peux **ajouter tes propres patterns** :

Créer `/config/custom_sentences/fr/maison.yaml` côté HA (via Studio Code Server addon ou SSH) :

```yaml
language: fr
intents:
  HassLightTurnOn:
    data:
      - sentences:
          - "fais (de la|un peu de) lumière dans (le|la) {area}"
          - "j'ai besoin de lumière dans (le|la) {area}"
          - "il fait sombre dans (le|la) {area}"

  HassClimateSetTemperature:
    data:
      - sentences:
          - "j'ai froid"
          - "il fait froid"
        slots:
          temperature: 21
          climate: "climate.chambre"
      - sentences:
          - "il fait trop chaud"
        slots:
          temperature: 19
          climate: "climate.chambre"
```

Redémarrer Assist (Developer tools → Reload → "Assist Pipeline") pour prendre en compte.

---

## 10. Troubleshooting fréquent

### Whisper ne transcrit pas / mauvaise transcription

```bash
# Voir les logs en temps réel
kubectl -n voice logs deploy/wyoming-whisper -f --tail=30
```

Causes courantes :
- **Modèle pas encore téléchargé** (au premier boot, attendre ~50 min de download)
- **Audio trop court** (Whisper réclame >0.5s d'audio) → parle plus longtemps
- **Mauvais accent / bruit ambiant** → essayer `--beam-size 5` (plus précis mais 2x plus lent)

### Piper ne sort pas de son sur le smartphone

- **Volume média** du téléphone (pas le volume de sonnerie)
- Tester en direct dans HA UI : **Developer tools** → **Services** → `tts.speak` → choisir piper → texte de test
- Vérifier que la voix `fr_FR-siwis-medium` est bien dans `/data` du pod : `kubectl -n voice exec deploy/wyoming-piper -- ls /data`

### HA Assist répond « Désolé je ne comprends pas »

- L'entité n'est pas exposée à Assist (cf. §8 — onglet Expose)
- Pattern non reconnu (cf. §9 — ajouter custom_sentences)
- Whisper a mal transcrit → vérifier le **debug log Assist** : HA UI → Settings → System → Logs → filtrer « assist »

### Latence trop élevée (>5s sur un simple « allume le salon »)

- Whisper CPU sur Large-v3-turbo : si lent, basculer sur **`small`** dans `--model` (`small` = 244M, ~500 ms transcription)
- Network : ping de HA vers le node k8s. Si >50ms, vérifier wifi vs ethernet
- Si le pod whisper a du `iowait` élevé, vérifier où vit son PVC (devrait être sur NVMe maintenant après migration)

---

## 11. Phase 2 (preview) — Activer le fallback LLM

Une fois la Phase 1 stabilisée et que tu as identifié les commandes qui ne sont pas reconnues, tu peux activer **Qwen 7B comme fallback agent** :

1. HA UI → **Settings** → **Devices & services** → **Add Integration** → **OpenAI Conversation** (compatible LocalAI)
2. Configurer :
   - **API Key** : ton token LocalAI (`H/Kk5SCTCa0wPH+y3X8Cktuvgv3uLNaTFQGwTy+M7eE=`)
   - **API URL** : `http://192.168.88.250:30180/v1` (à mettre en place — il faut NodePort sur LocalAI ou via ingress LAN qu'on a déjà)
   - **Model** : `qwen2.5-7b-instruct`
3. Activer **Control Home Assistant** dans les options de l'intégration
4. Dans le pipeline Assist (cf. §7.2), changer **Conversation agent** → **Fallback** → sélectionner cet agent OpenAI Conversation

Effet : commande non matchée par intent natif → bascule sur Qwen 7B avec function calling sur les entités exposées.

**Surveiller** : latence devient ~3-5s pour ces fallbacks (au lieu de <1s pour intent natif).

---

## 12. Phase 3 (preview) — Investir en ESP32 voice satellite

Si après 2-3 semaines tu utilises vraiment le voice :

- **M5Stack ATOM Echo** (~25€) — petit, USB, format clé
- **ESP32-S3-Box-3** (~55€) — meilleure qualité audio, écran
- **HA Voice PE** (~60€) — device officiel HA, le plus intégré

Flash ESPHome (assistant intégré dans HA UI → Devices & services → ESPHome), pointer sur les services Wyoming du cluster (`192.168.88.250:30300` et `:30200`), wake word « Hey Computer » ou « OK Nabu ».

→ Tu peux désormais parler sans toucher le téléphone, plusieurs zones possibles.

---

## 13. Commandes utiles post-déploiement

```bash
# Watch sync ArgoCD des 2 nouvelles apps
kubectl -n argocd get app -l name=wyoming-whisper -w
kubectl -n argocd get app -l name=wyoming-piper -w

# Logs en live
kubectl -n voice logs deploy/wyoming-whisper -f
kubectl -n voice logs deploy/wyoming-piper -f

# Tester l'accessibilité depuis le LAN
nc -zv 192.168.88.250 30300   # Whisper
nc -zv 192.168.88.250 30200   # Piper

# Liste des modèles téléchargés côté pod
kubectl -n voice exec deploy/wyoming-whisper -- ls -lh /data
kubectl -n voice exec deploy/wyoming-piper -- ls -lh /data

# Voir l'utilisation CPU/RAM des 2 services
kubectl -n voice top pod
```

---

## 14. Mise à jour CLAUDE.md à prévoir

Quand la Phase 1 sera validée, ajouter à `CLAUDE.md` dans la section "Applications actives" :

```markdown
### Voice (namespace `voice`)

| Application       | Namespace | Source                          | Version | Notes                                          |
|-------------------|-----------|---------------------------------|---------|------------------------------------------------|
| `wyoming-whisper` | `voice`   | bjw-s-labs.github.io/helm-charts | 5.0.1   | STT, Whisper Large-v3-Turbo CPU, FR, port 30300|
| `wyoming-piper`   | `voice`   | bjw-s-labs.github.io/helm-charts | 5.0.1   | TTS, voix `fr_FR-siwis-medium`, port 30200     |
```

---

## 15. Architecture finale après Phase 1

```
Smartphone (HA Companion) ─wifi─→ HA (VM/Pi) ─LAN→ Cluster k8s
                                       │              │
                                       │              ├─ wyoming-whisper:30300 (STT, CPU)
                                       │              └─ wyoming-piper:30200 (TTS, CPU)
                                       │
                                       └─ Assist Intent (built-in FR) → light.turn_on, etc.
```

**Ressources mobilisées** côté cluster :
- Whisper : ~2 GB RAM, ~10% CPU sustained pendant les transcriptions
- Piper : ~200 MB RAM, ~5% CPU pendant les générations TTS
- 0 VRAM (CPU only en Phase 1) → ne touche pas à LocalAI/Qwen/Flux

**Pas de modification** des charts existants (LocalAI, OpenWebUI, etc.). Tout est additif.

---

## 16. TL;DR commandes (référence rapide)

```bash
# Setup
kubectl create namespace voice
# Créer les 2 fichiers argocd/argocd-apps/wyoming-{whisper,piper}-app.yaml
git add argocd/argocd-apps/wyoming-*.yaml
git commit -m "feat(voice): add Whisper STT + Piper TTS for HA Assist"
git push

# Attendre sync ArgoCD (auto) + download des modèles (~50 min total à 5 Mbps)
kubectl -n voice get pod -w
kubectl -n voice logs deploy/wyoming-whisper -f

# Config HA (HAOS sur 192.168.88.201, hors cluster → utilise les NodePorts)
# UI : Settings → Devices → Wyoming Protocol → 192.168.88.250:30300  (Whisper)
# UI : Settings → Devices → Wyoming Protocol → 192.168.88.250:30200  (Piper)
# UI : Settings → Voice assistants → Add → STT: whisper, TTS: piper, Agent: HA, Voice: fr_FR-siwis-medium

# Test sur smartphone HA Companion : tap mic → "allume le salon"
```
