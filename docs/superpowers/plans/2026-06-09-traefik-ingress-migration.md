# Migration ingress-nginx → Traefik (MicroK8s 1.35+)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer le controller `kubernetes/ingress-nginx` (EOL mars 2026, plus de patch CVE) par **Traefik**, fourni nativement par l'addon `ingress` de MicroK8s ≥ 1.35. Migration **phasée in-place**, en gardant **oauth2-proxy** (réintégré via middleware `ForwardAuth`).

**Décisions verrouillées :**
- Auth : **garder oauth2-proxy**, le réintégrer en `ForwardAuth` (pas de changement de provider pendant la migration).
- Bascule : **phasée in-place** (scénario 2). Pas de Traefik parallèle, pas de big-bang.

**Architecture cible :** addon MicroK8s 1.35 → Traefik. Les `ingressClassName` `nginx`/`public`/`traefik` sont des **alias** pointant tous sur Traefik. Les annotations `nginx.ingress.kubernetes.io/*` ne sont **plus interprétées** → chaque comportement (auth, whitelist, timeouts, sticky) est porté par un **Middleware CRD** Traefik (`traefik.io/v1alpha1`) attaché via l'annotation `traefik.ingress.kubernetes.io/router.middlewares`. cert-manager (`letsencrypt-prod`) reste inchangé sauf la classe du solver HTTP-01.

**Tech Stack :** MicroK8s 1.35+ (snap), Traefik v3.x (Helm via addon), cert-manager v1.20, oauth2-proxy 10.1.4, ArgoCD, Sealed Secrets.

**Repo :** `/data/projets/perso/my-kluster`

---

## ⚠️ Contrainte de sécurité structurante

Dès que l'addon bascule sur Traefik, les annotations nginx tombent. **9 hosts perdent leur protection** tant que leur Middleware Traefik n'est pas posé :

- oauth2 (×4) : `dagster`, `kubetail`, `chat`, `dashboard` → exposés sans auth
- whitelist LAN (×5) : `beszel`, `hermes`, `searxng`, `localai`, `chat-lan` → joignables hors LAN

**Règles d'ordre (non négociables) :**
1. Tous les Middlewares (IPAllowList + ForwardAuth) sont écrits et committés **AVANT** l'upgrade (Phase 0). Ils sont inertes tant qu'aucun ingress ne les référence.
2. Après l'upgrade, chaque host sensible est migré **avec son middleware dans le même commit/sync** — jamais d'ingress sensible en ligne sans middleware.
3. Si un host ne peut être sécurisé immédiatement → **retirer son ingress** (offline), pas le laisser ouvert.
4. Ordre de migration : LAN-only (IPAllowList, simple) **avant** oauth2 (ForwardAuth, plus subtil).

---

## Inventaire des ingress actifs (état pré-migration)

| Host | Fichier | À porter en middleware/CRD Traefik |
|---|---|---|
| `argocd.tgu.ovh` | `argocd/argocd-install/values.yaml` | rien (auth ArgoCD propre) — juste className |
| `auth.tgu.ovh` | `argocd/argocd-apps/oauth2-proxy-app.yaml` | rien (c'est l'authN) — juste className |
| `dagster.tgu.ovh` | `argocd/argocd-apps/dagster.yaml` | ForwardAuth |
| `kubetail.tgu.ovh` | `argocd/argocd-apps/kubetail-app.yaml` | ForwardAuth |
| `chat.tgu.ovh` | `argocd/argocd-apps/openwebui-app.yaml` | ForwardAuth + timeouts/body |
| `dashboard.tgu.ovh` | `config/dashboard-ingress.yaml` | ForwardAuth |
| `chat-lan.tgu.ovh` | `config/openwebui-lan-ingress.yaml` | IPAllowList + timeouts/body |
| `beszel.tgu.ovh` | `argocd/argocd-apps/beszel-app.yaml` | IPAllowList + body |
| `hermes.tgu.ovh` | `argocd/argocd-apps/hermes-agent-app.yaml` | IPAllowList + timeouts/body |
| `searxng.tgu.ovh` | `argocd/argocd-apps/searxng-app.yaml` | IPAllowList |
| `localai.tgu.ovh` | `charts/localai/values.yaml` | IPAllowList + timeouts/body |
| `rustfs.tgu.ovh` | `argocd/argocd-apps/rustfs-app.yaml` | sticky session + timeouts |
| `mlflow.tgu.ovh` | `argocd/argocd-apps/mlflow-app.yaml` | rien (juste className) |
| `freshrss.tgu.ovh` | `config/freshrss-ingress.yaml` | nettoyer `nginx.org/*` (inerte) |

### Inventaire élargi (snapshot + annotations live 2026-06-10 — ~28 ingress)

Le grep repo ratait les ingress chart-managed. ⚠️ **Correction : ce n'est PAS que du className** — selfhost cache 5 hosts oauth2. Annotations live vérifiées :

| Host (ns) | className | À porter |
|---|---|---|
| cleanuparr, qbittorrent, radarr, seerr, sonarr (`selfhost`) | nginx | **ForwardAuth** (oauth2) → Middleware ajouté en ns `selfhost` |
| jellyfin (`selfhost`) | nginx | `proxy-body-size: 0` → Traefik illimité par défaut, **drop** |
| prowlarr (`selfhost`) | nginx | className seul |
| freshrss (`selfhost`) | public | `nginx.org/*` **inerte** → drop |
| cv, chatbot, dynamic (`cv`) | public | className seul |
| meteo-des-accidents (`accidents`) | nginx | `force-ssl-redirect`+`ssl-redirect` → `redirectScheme` middleware ou redirect entrypoint ; body 50m + timeouts 300s |
| portfolio (`portfolio`) | nginx | `configuration-snippet` WebSocket → **Traefik gère WS nativement, drop snippet** ; `proxy-http-version 1.1` = défaut ; timeouts 3600s → ServersTransport |
| hello (`smoke`) | public | test — **à supprimer si obsolète** |

**Bilan oauth2 global révisé : 9 hosts** (dagster, kubetail, chat, dashboard + cleanuparr, qbittorrent, radarr, seerr, sonarr). Namespaces ForwardAuth : `kube-system`, `dagster`, `openwebui`, **`selfhost`**.

> **Prépa oauth2-proxy validée (2026-06-10) :** config live = `reverse_proxy=true`, `whitelist_domains=*.tgu.ovh`, `cookie_domains=.tgu.ovh` → pattern ForwardAuth rd-less compatible, SSO partagé. P3 dérisqué.

> ⚠️ Points spéciaux à traiter par-host en P2/P4 : `force-ssl-redirect` (accidents — vérifier si l'addon Traefik redirige http→https par défaut, sinon `redirectScheme`), WebSocket portfolio (natif Traefik, juste retirer le snippet). **Impact estimation : +2-3h** → total ~9-11h.

---

## Correspondance des annotations

| nginx | Traefik |
|---|---|
| `auth-url` + `auth-signin` | Middleware `forwardAuth` (`address` → oauth2-proxy `/oauth2/auth`, `authResponseHeaders`, `trustForwardHeader`) |
| `whitelist-source-range` | Middleware `ipAllowList.sourceRange` |
| `proxy-body-size` | Illimité par défaut → souvent **supprimable** ; sinon middleware `buffering.maxRequestBodyBytes` |
| `proxy-read/send-timeout` | `ServersTransport.forwardingTimeouts` (responseHeaderTimeout) ou timeouts d'entrypoint |
| `proxy-connect-timeout` | `ServersTransport.dialTimeout` |
| `affinity: cookie` (rustfs) | annotation **Service** `traefik.ingress.kubernetes.io/service.sticky.cookie: "true"` (+ `.name`) |
| `cert-manager.io/cluster-issuer` | **inchangé** |

**Référencement middleware** (format strict) : `traefik.ingress.kubernetes.io/router.middlewares: <ns>-<name>@kubernetescrd`. Le préfixe `<ns>` est le namespace du Middleware. Cross-namespace nécessite `allowCrossNamespace` côté provider Traefik → **par défaut, définir le Middleware dans le namespace de l'app** qui le consomme.

---

## File Structure

| Path | Statut | Responsabilité |
|---|---|---|
| `config/traefik-middlewares.yaml` | NEW | Middlewares partagés (IPAllowList LAN générique) — namespace `infra` ou dupliqués par ns |
| `config/letsencrypt-issuer.yaml` | MODIFY | Solver HTTP-01 : `ingressClassName: nginx` → `public` |
| `config/dashboard-ingress.yaml` | MODIFY | className + annotation middleware ForwardAuth |
| `config/openwebui-lan-ingress.yaml` | MODIFY | className + middleware IPAllowList |
| `config/freshrss-ingress.yaml` | MODIFY | retirer `nginx.org/*`, className |
| `argocd/argocd-apps/*.yaml` | MODIFY | par host : className + annotation router.middlewares, retrait annotations nginx |
| `charts/localai/values.yaml` | MODIFY | ingress className + middleware |
| `CLAUDE.md` | MODIFY | section Ingress/TLS : nginx → Traefik, pattern middlewares |
| `TODO.md` | MODIFY | tracer la migration |

> Pour les apps gérées par chart (oauth2 ForwardAuth + IPAllowList), un `Middleware` doit exister **dans le namespace de l'app**. Soit ajouté via `extraObjects`/`additionalManifests` du chart, soit dans `config/` (mais `config/` est synché dans ns `infra` → pour les autres ns, déclarer le Middleware dans le manifeste/chart de l'app).

---

# PHASE 0 — Préparation ✅ FAIT (2026-06-10)

**Objectif :** manifestes Middleware rédigés en **staging non-synché**, backup + snapshot avant upgrade. Aucun impact runtime.

> **Correction vs plan initial :** les CRD `traefik.io/v1alpha1` n'existent pas sur 1.33 → committer les Middleware dans un path synché (config/) ferait **échouer ArgoCD** (`no matches for kind Middleware`, confirmé par dry-run serveur). Donc staging dans `docs/.../traefik-middlewares/` (non watché par ArgoCD), relocalisés en P1 une fois Traefik installé.

## Task 0.1 : Vérifs préalables ✅

- [x] **Step 1: Version MicroK8s** → `v1.33.12` (channel `1.33/stable`). Écart de 2 minors vers 1.35 → double hop requis (cf. P1).
- [x] **Step 2: Backup clé master Sealed Secrets** → `~/sealed-secrets-master-20260610-premigration-traefik.key.backup`.
- [x] **Step 3: Snapshot ingress** → `docs/.../traefik-middlewares/ingress-snapshot-premigration.yaml`.

## Task 0.2 : Middlewares rédigés (staging) ✅

- [x] **Fichier** `docs/superpowers/plans/traefik-middlewares/middlewares.yaml` — 8 Middleware, parse validé :
  - `ipAllowList` (lan-only) ×5 : ns `searxng`, `monitoring`, `hermes`, `localai`, `openwebui`
  - `forwardAuth` (oauth2-forwardauth) ×3 : ns `kube-system` (dashboard+kubetail), `dagster`, `openwebui`
- ForwardAuth : pattern **sans rd par-host** (`authSigninURL: .../oauth2/start` nu, oauth2-proxy `--reverse-proxy` reconstruit la redirection via X-Forwarded-*). À valider sur dashboard en P3.
- IPAllowList : `ipStrategy` à régler en P2 sur searxng (snapshot montre ADDRESS=127.0.0.1 partout → IP cliente réelle à confirmer sous Traefik).

> ⚠️ **Découverte snapshot — scope réel ~28 ingress, pas 14.** Le repo grep ratait les ingress générés par chart. Voir section « Inventaire élargi » ci-dessous.

---

# PHASE 1 — Upgrade MicroK8s → Traefik

**Objectif :** addon Traefik actif, routing de base validé via compat nginx, TLS OK. **Aucune annotation nginx encore migrée** → fenêtre où les 9 hosts sont exposés : minimiser sa durée, idéalement enchaîner Phase 2/3 immédiatement.

## Task 1.1 : Bascule de l'addon

- [ ] **Step 1: Refresh MicroK8s** (single-node → courte coupure ingress)
```bash
sudo snap refresh microk8s --channel=1.35/stable
microk8s status --wait-ready
```
- [ ] **Step 2: Vérifier que l'addon ingress = Traefik**
```bash
microk8s kubectl get pods -A | grep -i traefik
microk8s kubectl get ingressclass
# Attendu : classes public (default), traefik, nginx → toutes Traefik
```

## Task 1.2 : Fixer cert-manager (issue #5351)

- [ ] **Step 1:** `config/letsencrypt-issuer.yaml` → solver `ingressClassName: nginx` → `public`.
- [ ] **Step 2: Commit + sync, vérifier qu'un certificat se renouvelle** (host non-sensible, ex. `mlflow`)
```bash
kubectl describe certificate -A | grep -iE "ready|issuing"
```

## Task 1.3 : Valider routing de base

- [ ] **Step 1:** tester un host **non-protégé** (mlflow / rustfs) : réponse HTTP + cert valide.
```bash
curl -sI https://mlflow.tgu.ovh | head -5
```
→ Si OK : la compat nginx + Traefik route correctement. Passer Phase 2 **sans délai**.

---

# PHASE 2 — Migrer les hosts LAN-only (IPAllowList)

**Objectif :** restaurer la whitelist LAN sur les 5 hosts. Un host par commit, validé avant le suivant.

**Ordre :** `searxng` (le plus simple) → `beszel` → `chat-lan` → `localai` → `hermes` (timeouts longs).

## Task 2.x (répéter par host)

- [ ] **Step 1:** dans l'ingress du host : retirer `nginx.ingress.kubernetes.io/whitelist-source-range`, ajouter
```yaml
annotations:
  traefik.ingress.kubernetes.io/router.middlewares: <ns>-lan-only@kubernetescrd
```
(le Middleware `lan-only` doit exister dans le `<ns>` du host — sinon le créer dans le manifeste/chart de l'app).
- [ ] **Step 2:** porter les timeouts/body si présents (cf. tableau). `proxy-body-size` : tester sans d'abord (Traefik illimité par défaut).
- [ ] **Step 3:** retirer `className: nginx` → laisser défaut `public` ou expliciter `traefik`.
- [ ] **Step 4:** commit + sync ArgoCD, puis **valider la whitelist** :
```bash
# Depuis le LAN : 200 attendu
curl -sI https://<host>.tgu.ovh | head -1
# Depuis hors-LAN (ex. 4G/VPN externe) : 403 attendu
```
> 🔑 Sur le 1er host (searxng), valider le `ipStrategy` : si le 403 ne se déclenche pas / bloque tout, c'est que Traefik voit une IP interne → ajuster `ipAllowList.ipStrategy` dans le Middleware `lan-only`.

---

# PHASE 3 — Migrer les hosts oauth2 (ForwardAuth)

**Objectif :** restaurer l'auth GitHub sur les 4 hosts via oauth2-proxy + ForwardAuth.

**Ordre :** `dashboard` (raw, isolé) → `kubetail` → `dagster` → `chat` (openwebui, + timeouts).

## Task 3.0 : Pré-requis oauth2-proxy

- [ ] **Step 1:** vérifier/activer `--reverse-proxy=true` sur oauth2-proxy (requis pour ForwardAuth derrière Traefik).
- [ ] **Step 2:** valider le flux complet sur `dashboard` (host témoin) AVANT de migrer les 3 autres :
  - non authentifié → redirige vers `auth.tgu.ovh` (login GitHub)
  - après login (tom333/tguyader) → accès OK
  - user hors whitelist → refusé

## Task 3.x (répéter par host)

- [ ] **Step 1:** retirer `auth-url` + `auth-signin`, ajouter `router.middlewares: <ns>-oauth2-forwardauth@kubernetescrd`.
- [ ] **Step 2:** retirer `className: nginx`, porter timeouts (chat).
- [ ] **Step 3:** commit + sync, valider login + refus hors-whitelist.

---

# PHASE 4 — Cas particuliers & nettoyage

- [ ] **Task 4.1 — rustfs sticky session :** remplacer `affinity: cookie` + `session-cookie-*` par l'annotation **Service** `traefik.ingress.kubernetes.io/service.sticky.cookie: "true"` (+ `.name: rustfs`). Porter les timeouts longs (3600s) via ServersTransport si nécessaire. Valider la persistance de session.
- [ ] **Task 4.2 — freshrss :** retirer les `nginx.org/*` (inertes aujourd'hui). Si des timeouts longs sont réellement utiles, les porter en ServersTransport ; sinon supprimer.
- [ ] **Task 4.3 — argocd / auth / mlflow :** vérifier qu'ils routent (className alias). Aucun middleware requis.
- [ ] **Task 4.4 — sweep final :**
```bash
# Plus aucune annotation nginx active ne doit subsister (hors .disable)
grep -rn "nginx.ingress.kubernetes.io\|nginx.org/" --include="*.yaml" . | grep -v disable
kubectl get ingress -A   # tous les hosts présents et Ready
```

---

# PHASE 5 — Décommissionnement & doc

- [ ] **Task 5.1 :** confirmer qu'aucun controller `ingress-nginx` ne tourne (l'addon l'a remplacé). Nettoyer restes éventuels.
- [ ] **Task 5.2 :** `CLAUDE.md` — réécrire la section **Ingress et TLS** : Traefik au lieu de nginx, pattern Middleware (`router.middlewares`), exemples ForwardAuth + IPAllowList. Mettre à jour "Spécificités MicroK8s" (addon ingress = Traefik 1.35+).
- [ ] **Task 5.3 :** `TODO.md` — marquer la migration faite ; noter l'option future Gateway API (`HTTPRoute`) et scale-to-zero Sablier (plugin Traefik) désormais débloqués.

---

## Vérification finale (goal-backward)

- [ ] Aucun host n'a régressé : les 14 ingress répondent, certs valides.
- [ ] Les 5 hosts LAN renvoient 403 hors-LAN.
- [ ] Les 4 hosts oauth2 exigent le login GitHub (tom333/tguyader).
- [ ] `grep` ne trouve plus d'annotation nginx active.
- [ ] cert-manager renouvelle via solver `public`.
- [ ] CLAUDE.md reflète Traefik.

## Risques & points à valider en cours de route

1. **Source IP pour IPAllowList** (Phase 2, host témoin searxng) — le seul vrai inconnu technique. Régler le `ipStrategy` ici conditionne les 5 hosts LAN.
2. **`authSigninURL` dynamique par host** (Phase 3) — valider sur dashboard avant les autres ; fallback = un Middleware ForwardAuth par host avec `rd=` figé.
3. **Cross-namespace middlewares** — défaut interdit ; définir les Middlewares dans le ns de chaque app.
4. **Fenêtre d'exposition Phase 1→3** — enchaîner sans délai ; sur single-node c'est une session de travail continue.

---

# PHASE 6 — Scale-to-zero Sablier

> **✅ 6a (infra) + 6b (pilote mlflow) FAITS le 2026-06-10. Mécanisme prouvé bout-en-bout.** Reste : rollout des autres candidats (6c, un par un).

## État d'exécution
- **6a infra** ✅ : Traefik sous GitOps (`traefik-app.yaml`) → plugin `sablier-traefik-plugin v1.3.0` (`experimental.plugins`) ; serveur Sablier `1.10.1` (`sablier/` + `sablier-app.yaml`, ns kube-system, RBAC scale, Service :10000). Plugin chargé (logs `Plugins loaded [sablier]`).
- **6b pilote mlflow** ✅ : middleware `ia-lab/mlflow-sablier` (`names=deployment_ia-lab_mlflow_1`, dynamic ghost, sessionDuration 10m) + annotation sur l'ingress mlflow. **Testé** : mlflow scalé 0 → requête → page d'attente Sablier + scale 0→1 → sert l'app. Scale-to-zero auto après 10m.

## Recette d'onboarding (par service, un à la fois)
1. Middleware Sablier dans `config/traefik-middlewares.yaml` (ns du service) : `plugin.sablier.names=deployment_<ns>_<deploy>_<replicas>`, `sablierUrl=http://sablier.kube-system:10000`, `sessionDuration`, `dynamic` (UI) ou `blocking` (API).
2. Annotation `traefik.ingress.kubernetes.io/router.middlewares: <ns>-<name>-sablier@kubernetescrd` sur l'ingress (chaîner APRÈS oauth/whitelist si présents).
3. Commit + push, refresh parent `applications` (inline values) + l'app, sync.
4. Valider : `kubectl scale deploy <x> --replicas=0` → requête → page d'attente + réveil.

## Candidats — état rollout (2026-06-10)
- [x] **mlflow** (ia-lab) — pilote, testé ✓
- [x] **openwebui** (StatefulSet) — chaîné après oauth (chat) + whitelist (chat-lan), 30m ✓
- [x] **dagster webserver** (UI) — chaîné après oauth, 15m. Daemon reste up ✓
- [x] **portfolio** (Streamlit public) — testé ✓. Ingress dans repo portfolio (k8s/ingress.yaml, appliqué).
- [x] **accidents** — réveil de GROUPE (accidents-app + accidents-api + streamlit-app), testé ✓. ⚠️ ingress `accidents-ingress` annoté en **kubectl live** (non-ArgoCD) → à reporter dans la source manuelle de cet ingress pour durabilité rebuild.
- [ ] **dagster-user-deployment-accidents** — **SKIPPÉ** : poll gRPC interne du daemon (pas via ingress) → Sablier ne le réveille pas pour le daemon + code-location casse à zéro. Levier alternatif = kube-green (sieste) si on veut récupérer ses 2Gi.
- [ ] **kubetail** — candidat mais footprint ~0 (gain symbolique), non fait.
- [ ] selfhost (arr-stack) — repo externe, non fait.
- **Restent UP** : infra, oauth2-proxy, postgresql/qdrant/rustfs, beszel, hermes, localai, searxng/lightpanda, wyoming (voix, pas Sablier-able → kube-green).

**Durabilité externes** : middlewares portfolio/accidents en GitOps (my-kluster config/). Ingress portfolio = repo portfolio (édité). Ingress accidents = annotation kubectl live (source manuelle à mettre à jour côté user).

> Note exécution P6 : à acter ci-dessous —

**Pré-requis :** Traefik en place (Phases 0-5). Sablier = intégration native Traefik (plugin middleware). Le plugin se charge via la **config statique** de Traefik (`experimental.plugins.sablier`) → à injecter dans les values Helm de l'addon ingress, + déployer le serveur Sablier (Deployment + RBAC pour scaler les Deployments).

**Règle de tri :** Sablier réveille sur **requête HTTP via Traefik**. Candidat = service avec ingress HTTP **déclenché par un humain**. Background/event-driven/monitoring/DB partagée → restent up.

## Classification (décisions verrouillées)

### Restent UP en permanence

| Catégorie | Services | Raison |
|---|---|---|
| Control plane / infra | argocd, cert-manager, sealed-secrets, config, Traefik | jamais à éteindre |
| Auth | **oauth2-proxy** | backend ForwardAuth — son sommeil casse l'auth des 4 hosts protégés |
| Backends stateful | postgresql, qdrant, rustfs | DB/stockage partagés — sommeil casse les dépendants |
| Monitoring | **beszel** | doit collecter + alerter H24 |
| Event-driven / background | **hermes-agent** (bot Telegram toujours-actif), wyoming-piper, wyoming-whisper (voix HA, TCP interne) | non réveillables par requête HTTP ingress |
| GPU / IA | **localai** (usage courant) | reste up ; cold-start modèle trop pénalisant pour l'usage |
| Consommés par services up | searxng, browserless/lightpanda | dépendances de hermes (up) ; lightpanda = CDP interne sans ingress, non réveillable |
| Downloads / automation média | **qbittorrent** (torrents actifs), **arrconf** (automation *arr en fond) | jobs/transferts continus, sommeil = casse |

### Candidats scale-to-zero (Sablier)

**Le périmètre est large** — au-delà du noyau d'UI, des namespaces entiers sont éligibles :

| Périmètre | Candidats | Exclusions (restent up) |
|---|---|---|
| Noyau UI | mlflow ★, kubetail ★, openwebui ★, cv (borderline, site public) | — |
| `selfhost` | **tout** (freshrss, UIs *arr type sonarr/radarr/prowlarr…) | **qbittorrent**, **arrconf** |
| `accidents` | **tout** | — |
| `dagster` | **tout** (webserver/UI, user-code) | ⚠️ vérifier le **daemon** par-service : s'il porte des schedules actifs, il reste up ; sinon candidat |
| … | autres namespaces à énumérer à l'exécution | — |

**★ RÈGLE D'ONBOARDING — un service à la fois.** Chaque service est traité **individuellement** : son propre middleware Sablier + sa propre validation (réveil OK, page d'attente OK, re-scale-to-zero OK) avant de passer au suivant. **Jamais de bascule en masse** par namespace — le tag « namespace entier » ci-dessus décrit l'éligibilité, pas un toggle groupé.

**Conséquence des décisions hermes-up + localai-up :** plus aucune chaîne de dépendance à réveiller en groupe. Les candidats sont tous **standalone** → config Sablier simplifiée (1 middleware par host candidat, pas de groupes).

**Première tâche Phase 6 (à l'exécution) :** énumérer service par service les namespaces `selfhost` / `accidents` / `dagster` / … → produire la liste nominative des Deployments à onboarder (avec leur ingress), puis les traiter un par un.

**Gisement réel :** localai (gros poste GPU/requests) reste up par choix → mais avec un périmètre candidat aussi large (selfhost + accidents + dagster + UIs), le gain CPU-request cumulé devient **significatif**, pas juste les 3-4 UI légères du noyau. À chiffrer une fois la liste nominative établie.

---

# JOURNAL D'EXÉCUTION — P1 réalisé le 2026-06-10

**Statut : ✅ MIGRATION COMPLÈTE (2026-06-10).** Traefik en place, sécurité durable (GitOps), oauth login-redirect OK, argocd OK, cleanups faits. Smoke test 21 hosts : tous OK (oauth→302 login, whitelist→200, public→200). WAN réouvrable. Reste seulement du bruit inerte non-bloquant (cf. bas).

## Déroulé réel (déviations vs plan)

1. **Upgrade snap** 1.33→1.34→1.35 : OK, sans coupure (workloads survivent au restart control-plane).
2. **Bascule addon = piège** : `microk8s enable ingress` a redéployé **nginx** 2× car la copie persistante des addons (`/var/snap/microk8s/common/addons/core/`) était **stale**. Fix : `sudo microk8s addons repo update core` (resync depuis le snap), PUIS disable/enable.
3. **Wrapper enable no-op** ("already enabled") après update repo → installé Traefik **directement via helm** (`microk8s helm3 upgrade --install traefik traefik/traefik --version 37.4.0 -n ingress --values /var/snap/.../ingress/values.yaml`). A fallu **supprimer les IngressClass `public`/`nginx` orphelines** (controller nginx) pour que Helm crée les siennes.
4. **Découverte values.yaml addon** : active **2 providers** (`kubernetesIngress` + `kubernetesIngressNginx` compat). Le compat ne porte PAS l'auth → bypass. **Désactivé** `kubernetesIngressNginx` via `helm upgrade --reuse-values --set providers.kubernetesIngressNginx.enabled=false`.
5. **Deadlock DaemonSet** : Traefik DS = `maxSurge=1, maxUnavailable=0` + hostPort 80/443 → le nouveau pod reste Pending (port pris), l'ancien ne meurt pas. **Toutes les modifs de config statique restaient inappliquées.** Résolu en `kubectl delete pod` de l'ancien (blip, WAN bloqué).
6. **`authSigninURL` n'existe pas** dans le CRD Traefik OSS v3.6 (Hub-only) → retiré. ForwardAuth = **401 si non-auth** (sécurisé) mais **pas de redirect login** (dette).
7. **Sécu re-appliquée** : 9 Middleware (5 ipAllowList + 4 forwardAuth) dans `config/traefik-middlewares.yaml` + annotations `router.middlewares` portées dans chaque app/chart. Vérifié : oauth=401, whitelist=200(LAN).
8. **Bonus** : `chat-lan` réparé (service `open-webui`→`openwebui-open-webui`, 503→200).
9. **arr-stack** (repo externe) : 5 hosts oauth migrés en cherry-pick sur v0.22.0 → **tag v0.22.1**, bump `targetRevision`. Durable.

## Config NON-GitOps (fragile — à réappliquer si l'addon ingress est ré-enable)
- `providers.kubernetesIngressNginx.enabled=false` (sinon routers dupliqués non-protégés)
- DS `updateStrategy` deadlock hostPort : prochain upgrade Traefik nécessitera `kubectl delete pod` manuel, ou passer `maxSurge=0/maxUnavailable=1`.
- Ces overrides vivent sur le release Helm `traefik` (ns ingress), pas dans Git.

## Commits my-kluster
`f91b54eb` plan+middlewares staging · `22931e82` prépas · `ab8c7202` solver cert-manager public · `551cfd4b` wave1 (middlewares config + dashboard/chat-lan) · `f9a05d8f` wave2 (6 apps) · `1b9112d0` localai · `83851d23`+`63842459` argocd serversscheme (h2c→http, **ne fixe pas**) · `cfb8136c` bump arr-stack v0.22.1. arr-stack repo : tag **v0.22.1**.

## FOLLOW-UPS ouverts
1. ~~**argocd 502**~~ **RÉSOLU (2026-06-10)** — Root cause (via api Traefik `/api/http/services`) : le service résolvait `https://POD:8080` car l'ingress ciblait le port service nommé `https` (443) → Traefik faisait du TLS sur le backend cleartext (`--insecure` sur 8080) → 502. L'annotation `serversscheme: http` n'est PAS honorée (l'heuristique port-name gagne). Fix : `configs.params."server.insecure": true` (le chart pilote le port backend sur ce param via ternary http:https dans `templates/argocd-server/ingress.yaml`) → ingress port 80 → 200. Retiré `extraArgs --insecure` + l'annotation serversscheme inutile. Commit `b7738ec3`.
2. ~~**Login redirect oauth**~~ **RÉSOLU (2026-06-10, commit 7fee6bf5)** — Pattern doc oauth2-proxy "ForwardAuth with static upstreams" : `address` ForwardAuth = **racine du service** oauth2-proxy (`http://oauth2-proxy.kube-system.svc.cluster.local/`, pas `/oauth2/auth`) + `upstreams=static://202` + **`skip_provider_button=true`** → authentifié=202, non-auth navigateur=302 vers GitHub. Pas besoin de la middleware `errors` (qui ne catche PAS le 401 d'un middleware frère sur Traefik v3.6, testé) ni de cross-namespace. Vérifié : chat/kubetail/dagster/sonarr/qbittorrent → 302 github avec `rd` = host d'origine. *(À confirmer par un vrai login navigateur que l'accès authentifié=202 passe.)*
3. ~~**freshrss 404**~~ **RÉSOLU** : `config/freshrss-ingress.yaml` était un ingress orphelin (app `.old`, aucun service) → supprimé (commit e4210248).
4. ~~**Cleanups non-sécu**~~ **FAIT** : rustfs timeouts nginx retirés (commit 2e967f67) ; sticky/body-size restants = générés par le chart rustfs, **inertes sous Traefik**, non nettoyés (faible valeur, 1 replica). mlflow/cv/portfolio/meteo = 200 sans action (className alias OK). dashboard backend HTTPS = N/A (addon dashboard désactivé). **À surveiller** : accidents/portfolio (repos externes) avaient `force-ssl-redirect`/WebSnippet nginx — inertes sous Traefik ; WS marche nativement, mais pas de redirect http→https auto (accès https OK).
5. **WAN** : sécurité restaurée (oauth=401, whitelist OK) → réouverture possible côté sécu, MAIS fixer le **login redirect** (#2) d'abord pour l'usage navigateur des hosts publics oauth. argocd restera 502 jusqu'à #1.

## Doc CLAUDE.md à mettre à jour (post-stabilisation)
Section "Ingress et TLS" + "Spécificités MicroK8s" : nginx→Traefik, pattern Middleware, addon 1.35, config non-GitOps.
