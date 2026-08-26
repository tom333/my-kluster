# Panne permanente du plan de contrôle sous dqlite — analyse et options

Date : 2026-08-27 · Cluster : MicroK8s **v1.35.6** (snap 9072), `pc` (control-plane) + `jeux` (worker)

> **À lire en premier si tu reprends ce sujet.** Ce document remplace deux croyances
> fausses qui ont circulé dans ce dépôt : « c'est un rollback de révision dqlite »
> (faux) et « le multinœud exige dqlite » (faux aussi). Les deux sont corrigées ici,
> preuves à l'appui.

---

## 1. En une phrase

Depuis la migration etcd → dqlite du **25 juillet 2026**, le cluster subit une panne
**permanente** — et non des incidents répétés : les caches de veille de l'apiserver
gèlent périodiquement et **ne se réparent jamais seuls**, seul un redémarrage de
kubelite les débloque. C'est un bug amont ouvert, sans correctif annoncé.

## 2. Pourquoi le symptôme trompe

Les **écritures continuent de passer**. `kubectl` répond, les nœuds sont `Ready`, les
pods tournent. Le cluster paraît sain. Mais tout composant qui **lit à travers un
cache** est aveugle :

| Ce qu'on observe | Ce que c'est réellement |
|---|---|
| ArgoCD `sync=Unknown` sur toutes les apps | son cache ne peut plus s'initialiser |
| Pods bloqués en `Terminating` bien au-delà du *grace period*, conteneur toujours `running` | le kubelet ne voit jamais le `deletionTimestamp` |
| CronJobs qui empilent des centaines de pods | le contrôleur de jobs ne voit aucune terminaison |
| « ça remarche après un reboot » | les caches repartent de zéro — jusqu'au prochain décrochage |

⚠️ **Ne pas conclure « bash en PID 1 ignore SIGTERM » devant un pod bloqué en
Terminating.** Cette explication a été avancée à tort dans ce dépôt pour le pod
Hindsight. Vérifier d'abord l'état des caches (§5).

## 3. Le mécanisme, mesuré

### 3.1 Les caches gèlent tous ensemble

`Too large resource version: X, current: Y` : **`Y` est la révision du CACHE**
(`watchCache.resourceVersion`, via `NewTooLargeResourceVersionError`), pas celle du
datastore. Rien ne recule jamais — quelque chose cesse d'être alimenté.

Agrégation du journal de kubelite, une ligne par jour :

```
jour        lignes     demandée min..max        current min..max
août 15     137168   4890034..5118529      4886581..4886666    ← figé
août 16     137098   5118531..5348346      4886581..5310851    ← rattrape (redémarrage)
août 20     128543   6035155..6242629      6034762..6034893    ← figé
août 21      84769   6242629..6380675      6034762..6378693    ← rattrape
août 25     137100   7174970..7438026      7116738..7116760    ← figé
août 26     137126   7438030..7724275      7116738..7116760
août 27      55373   7724282..7838852      7116738..7116760    ← 3 jours
```

**1 192 894 occurrences au total, la première le 3 août à 18:57.** Gel courant démarré
le **24 août à 18:13:06**.

Preuve directe que ce sont bien les caches, et qu'ils gèlent **tous sur la même
valeur** :

```
ressource        quorum(réel)    cache(rv=0)
pods                  7839064        7116738
configmaps            7839072        7116738
secrets               7839085        7116738
services              7839093        7116738
nodes                 7839106        7116738
deployments           7839130        7116738
events                7839094        7839094   ← seul frais
```

`events` est le **témoin** : il ne passe pas par ce chemin, donc il reste sain. Un
point de gel unique et partagé désigne **la boucle d'alimentation unique** qui nourrit
tous les veilleurs, pas un cache défaillant.

### 3.2 Pourquoi ça ne se répare jamais

Côté `snap.microk8s.daemon-k8s-dqlite`, en boucle sur **chaque** préfixe de ressource :

```
error while range on /registry/secrets/ … : rpc error: code = OutOfRange
  desc = etcdserver: mvcc: required revision has been compacted
```

Les caches redemandent la révision où ils se sont arrêtés ; la compaction l'a effacée
entre-temps ; l'apiserver **ne bascule jamais sur une relecture complète** et
redemande éternellement la même révision morte.

### 3.3 D'où vient le décrochage initial

- **~2,7 écritures/s en continu** (231 536 révisions/jour), dominées par les baux de
  leader-election.
- dqlite tourne **en mémoire par défaut** (`--disk-mode` est marqué expérimental) : la
  persistance passe par un **instantané de toute la base, 31 Mo, toutes les ~512
  entrées raft (~2 min)**, soit ~22 Go/jour réécrits, plus la compaction toutes les
  5 min. Chacun prend un verrou.
- D'où `exec (try: 500): database is locked`, **100 à 150 fois par jour**, à cadence
  fixe `:02:08`, `:07:08`, `:12:08`… — **depuis le 25 juillet, jour de la migration**.

Préfixes les plus verrouillés : `leases/kube-system` (1545), `services/endpoints/kube-system`
(695), `leases/gpu-operator-resources` (444), `crd.projectcalico.org/tiers` (404),
`leases/kube-node-lease` (308).

## 4. Chaîne causale

```
migration etcd→dqlite (25/07)
  └─ dqlite en mémoire : instantané 31 Mo / 2 min + compaction / 5 min
      └─ verrou global récurrent  ← amplifié par un retry storm (§6)
          └─ le flux de veille décroche
              └─ à la reprise, la révision de reprise est déjà compactée
                  └─ l'apiserver reboucle au lieu de relire → CACHES GELÉS
                      └─ ArgoCD aveugle · pods Terminating · CronJobs qui s'emballent
```

## 5. Test de diagnostic — 30 secondes

**À faire AVANT tout diagnostic sur ce cluster**, y compris pour un symptôme qui
semble applicatif :

```bash
rv() { kubectl get --raw "$1" | python3 -c 'import json,sys; print(json.load(sys.stdin)["metadata"]["resourceVersion"])'; }
rv "/api/v1/pods?limit=1"                    # lecture à quorum = révision réelle
rv "/api/v1/pods?limit=1&resourceVersion=0"  # servie par le cache
```

Écart de quelques dizaines = sain. Écart de plusieurs centaines de milliers = **caches
gelés**. Comparer avec `events`, qui doit rester frais.

**Déblocage** (palliatif, à rechute) :

```bash
sudo systemctl restart snap.microk8s.daemon-kubelite
```

Redémarre l'apiserver + contrôleurs + scheduler + kubelet, **sans toucher containerd** :
les conteneurs en cours ne bougent pas, coupure d'API ~30-60 s. Préférer à
`microk8s stop && microk8s start`.

## 6. Ce n'est ni une erreur de conf, ni un cas isolé

**Rien à corriger dans la conf.** `k8s-dqlite --help` : ni le seuil d'instantané ni
l'intervalle de compaction ne sont exposés, ils sont en dur.
`--watch-progress-notify-interval` à 1 s au lieu de 5 s a été testé en amont —
« makes NO difference under load ». `ConsistentListFromCache` est **GA-verrouillé
depuis la 1.34** : l'apiserver refuse de démarrer avec le gate à `false`.

Bugs amont, **tous ouverts au 2026-08-27** :

| Issue | Contenu |
|---|---|
| [microk8s#5153](https://github.com/canonical/microk8s/issues/5153) | `database is locked` 500 sur update de lease. Régression 1.32+ (absente en 1.29). Cause : `updateSQL` réessaie jusqu'à 500 fois → **1 update de lease = 327 INSERT en 1 s**. Reproduit 1.32 → 1.36.2, mono-nœud ET HA, jusque dans la CI Canonical. |
| [microk8s#5568](https://github.com/canonical/microk8s/issues/5568) | Les correctifs amont de kine sur la *watch progress notification* (`k3s-io/kine#568`, `#602`, `#615`) **n'ont jamais été portés** dans k8s-dqlite (code inchangé v1.7.0 → master). Cf. `k3s-io/k3s#13305` : « a spurious progress response **desyncs the watch stream until an apiserver restart** ». Note aussi que `events` reste sain — notre témoin. |
| [microk8s#3064](https://github.com/canonical/microk8s/issues/3064) | Ouvert depuis 2022 : dqlite écrit énormément sur disque. |
| [microk8s#5524](https://github.com/canonical/microk8s/issues/5524) | k8s-dqlite échoue silencieusement, sans chemin de reprise. |

Un rapporteur de #5153 décrit **exactement** notre installation : *« 70+ ArgoCD
applications continuously reconciling […] ArgoCD UI goes stale, new pods fail to start
[…] a rolling reboot reliably clears it […] the problem returns within roughly a week »*,
avec un fsync mesuré à 0,9 ms sur SSD — **ce n'est pas un problème de disque lent**.
Sa question de juillet 2026, *« is moving to etcd the recommended path? »*, est
**restée sans réponse** ; les derniers commentaires (5 et 11 août 2026) sont « any
news on when there will be a fix? », sans réponse non plus.

## 7. Prémisse fausse corrigée : multinœud ≠ dqlite

La migration de juillet reposait sur cette conclusion, **fausse** :

> ~~« Le multinode exige dqlite. Seule voie = `microk8s enable ha-cluster` »~~

Vérifié dans le code livré en 1.35.6 (pas déduit d'un symptôme) :

- `microk8s-cluster-agent/pkg/api/v1/join.go` sert le chemin **etcd** et refuse si
  dqlite est actif — l'inverse exact de la v2 :
  ```go
  // v1 : chemin etcd
  if a.Snap.HasDqliteLock() { return nil, fmt.Errorf("...This is an HA MicroK8s cluster.\nPlease retry after enabling HA on this joining node...") }
  // v2 : chemin dqlite
  if !a.Snap.HasDqliteLock() { return nil, http.StatusNotImplemented, fmt.Errorf("...This is not an HA MicroK8s cluster") }
  ```
- `scripts/wrappers/join.py` embarque `join_etcd()` **et** `join_dqlite()`, et arbitre
  ainsi :
  ```python
  if is_node_running_dqlite():
      join_dqlite(connection_parts, verify, worker)
  else:
      join_etcd(connection_parts, verify)
  ```
  → le choix se fait sur l'état du **nœud qui rejoint**, pas du master.

Le 501 de juillet ne disait donc pas « etcd interdit le multinœud » mais **« les deux
nœuds ne sont pas dans le même mode »** : `jeux`, fraîchement installé, était sur
dqlite (défaut depuis 1.19). **`microk8s disable ha-cluster` sur `jeux` aurait suffi.**

**Réserves réelles du chemin etcd** (à connaître avant de le choisir) :
- `join_etcd()` appelle `update_flannel(...)` → **flannel câblé en dur**, donc
  etcd + flannel, pas etcd + calico ;
- il n'accepte pas `--worker` (`join_etcd(connection_parts, verify)`) ;
- la doc officielle de clustering **ne documente plus ce chemin** (héritage d'avant
  1.19, conservé pour compatibilité) — livré mais moins éprouvé.

## 8. Options, chiffrées

Un migrateur bidirectionnel est livré : `k8s-dqlite migrator --mode
[backup-etcd|restore-etcd|backup-dqlite|restore-dqlite]`. Donc `backup-dqlite` puis
`restore-etcd` — pas de reconstruction.

⚠️ `scripts/revert-dqlite-to-etcd.sh` **n'est pas l'outil pour ça aujourd'hui** : il
restaure les fichiers etcd d'avant le 25 juillet, soit un datastore vieux d'un mois.
C'était un filet pour un revert le jour même.

| Option | Effet | Prix |
|---|---|---|
| **Garder dqlite + garde-fou** | Gels ramenés de 3 jours à ~1 min | Le bug reste ; garde-fou à écrire |
| **etcd + flannel, 2 nœuds** | Supprime la classe d'incident **et** garde `jeux` | Flannel au lieu de calico ; chemin non documenté ; migration à mener |
| **etcd mono-nœud** | Le plus simple | Inutilement coûteux : le multinœud tient sans dqlite (§7) |

**Coût de perdre calico, mesuré :** 7 `NetworkPolicies`, **toutes issues du chart
ArgoCD**, **0** policy Calico native. Rien d'écrit à la main — mais ces 7 cesseraient
d'être appliquées, sur un composant qui détient les droits d'administration du cluster.
En sens inverse, `crd.projectcalico.org/tiers` figure parmi les préfixes les plus
verrouillés : retirer calico réduirait aussi le volume d'écriture.

**Charge réelle portée par `jeux`** (à re-mesurer, elle conditionne l'arbitrage) : au
2026-08-27, trois composants ArgoCD (`applicationset-controller`, `redis`, `server`) et
`crowdsec-agent`. Aucun n'y est épinglé par nécessité. `localai-jeux` (embeddings
Qwen3-0.6B sur GTX 1050 Ti) a été réactivé le 2026-08-27 pour OpenViking — et pourrait
tourner hors k8s, en conteneur exposé sur le LAN, si `jeux` quittait le cluster.

**Garde-fou recommandé dans tous les cas** (non écrit à ce jour) : comparer
périodiquement les deux révisions du §5 ; au-delà d'un écart durable, redémarrer
kubelite et notifier. Utile même après migration, pour savoir qu'un cache décroche.

## 9. Piège de nettoyage — à ne pas refaire

Après un gel, les CronJobs ont empilé des pods (mesuré : **483 pods** et 67 jobs pour
`crowdsec-machines-prune`, cadence `*/30`, sur 2 j 16 h ; **500 pods `Pending` au
total**, saturant le scheduler au point d'empêcher le placement du contrôleur ArgoCD).

**Ordre de suppression important.** Supprimer les `Job` **d'abord** laisse leurs pods
orphelins avec le finaliseur `batch.kubernetes.io/job-tracking`, que plus personne ne
retire — ils restent `Terminating` indéfiniment. Il faut alors le retirer à la main :

```bash
kubectl get pods -n <ns> -o name | grep <prefixe> \
  | xargs -r -P 10 -I{} kubectl patch {} -n <ns> --type=merge \
      -p '{"metadata":{"finalizers":null}}'
```

Supprimer les **pods** avant les jobs évite le piège.

## 10. Reste à faire

- [ ] Trancher entre les trois options du §8.
- [ ] Écrire le garde-fou de détection (§8).
- [ ] Réduire le churn d'écriture : le GPU operator génère 444 verrous pour un unique
      consommateur GPU ; `crd.projectcalico.org/tiers` en génère 404.
- [ ] Vérifier le déploiement de `localai-jeux` (réactivée en `e8fdf9bb`, jamais
      synchronisée : ArgoCD était aveugle) puis reprendre l'évaluation d'OpenViking.
