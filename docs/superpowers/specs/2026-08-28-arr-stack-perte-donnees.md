# Perte des données *arr — une mise à jour automatique, un `prune`, et sept volumes orphelins

Date : 2026-08-28 · Portée : namespace `selfhost`, app ArgoCD `arr-stack`
Statut : **résolu, données intégralement récupérées**

> **En une phrase.** Renovate a auto-mergé une montée de chart qui a fait tomber le
> rendu de 59 à 6 ressources ; ArgoCD, en `prune: true`, a supprimé les PVC ; les
> applications ont redémarré sur des bases vierges pendant que les vraies dormaient
> dans des volumes que la politique `Delete` pouvait effacer à tout instant.

---

## 1. Ce qui s'est passé

`arr-stack` est un **chart parapluie** : quatorze sous-charts `app-template` de
bjw-s, un par application (sonarr, radarr, prowlarr, qbittorrent, seerr, jellyfin,
cleanuparr, et les utilitaires). Renovate suit ce dépôt et auto-mergeait ses montées.

Le bump **v0.53.0 → v0.53.9** fait passer `app-template` de **5.0.1 à 5.1.0** dans
les quatorze dépendances (`Chart.yaml` et `Chart.lock`). Cette version est une
**rupture** pour ce chart : les sous-charts ne rendent plus rien.

Mesuré sur les deux tags, dépendances construites et index Helm à jour :

```
v0.53.0  (app-template 5.0.1)  →  59 ressources
     11 Deployment · 11 Service · 14 ServiceAccount · 8 Ingress
      7 PersistentVolumeClaim · 3 CronJob · 4 ConfigMap · 1 Job

v0.53.9  (app-template 5.1.0)  →   6 ressources
      4 ConfigMap · 1 Job · 1 ServiceAccount
```

ArgoCD a fait exactement ce qu'on lui demande. L'état désiré est tombé à six
ressources ; l'app étant en **`prune: true`**, il a supprimé tout le reste —
Deployments, Ingress, CronJobs, **et les PVC**. Les volumes sont passés en phase
`Released`, avec une `reclaimPolicy: Delete` qui autorisait le provisionneur à les
effacer. Quand la pile est revenue, sept PVC **vides** ont été provisionnés.

### L'écart, mesuré

| Application | Ancien volume | Nouveau volume | Base principale |
|---|---|---|---|
| radarr | 1 482 Mo | 6,5 Mo | 44 142 592 o contre 696 320 o |
| jellyfin | 5 688 Mo | 3 181 Mo | — |
| sonarr | 155 Mo | 4,2 Mo | 19 689 472 o contre 454 656 o |
| prowlarr | 110 Mo | 4,5 Mo | 14 360 576 o contre 241 664 o |
| qbittorrent | 29,4 Mo | 8,3 Mo | — |
| cleanuparr | 15,6 Mo | 2,3 Mo | — |
| seerr | 7,3 Mo | 0,4 Mo | — |

Les anciens volumes avaient été écrits **jusqu'à 09:19**, l'heure exacte où les
nouveaux pods ont démarré.

## 2. Ce n'est pas un bug isolé, c'est un enchaînement

Le bump seul n'aurait rien détruit. **Trois conditions réunies** ont transformé une
régression de rendu en suppression de données :

1. **L'auto-merge sans relecture**, sur un chart parapluie dont le rendu dépend
   d'une dépendance externe versionnée séparément.
2. **`prune: true`**, qui donne à ArgoCD le droit de supprimer ce qu'il ne voit
   plus dans l'état désiré — y compris des PVC.
3. **`reclaimPolicy: Delete`** sur les PV, qui rendait les données effaçables par
   le provisionneur dès la libération des PVC.

Retirer n'importe laquelle des trois aurait suffi à éviter la perte. La troisième
est celle qui a failli être fatale : **c'est un basculement manuel en `Retain`,
fait avant que le provisionneur n'agisse, qui a sauvé les données.** Rien ne
garantissait ce délai.

## 3. Ce qui a permis de récupérer

Le niveau de schéma des bases anciennes s'est révélé **identique** à celui des
bases neuves — vérifié avant toute écriture, dans la table `VersionInfo` :

```
sonarr 217 = 217 · radarr 242 = 242 · prowlarr 44 = 44
```

Aucune rétrogradation, donc aucun risque du type `SQLite Error: no such column`
qui avait déjà cassé cleanuparr lors d'un précédent retour arrière. Cette
vérification conditionnait la restauration : sans elle, rendre une base migrée à
une application plus ancienne l'aurait corrompue.

Résultat : **7 volumes sur 7 restaurés**, aux tailles exactes d'origine. Les
anciens volumes restent en `Retain`, intacts, et les volumes vierges sont
sauvegardés dans `~/restore-backup-20260828-143206`.

## 4. Les pièges rencontrés pendant la réparation

Ils valent d'être consignés : chacun a coûté une itération, et tous se
reproduiront.

**Suspendre ArgoCD sur l'app enfant ne tient pas.** L'objet `Application` de
`arr-stack` est lui-même géré par l'app-of-apps `applications`, qui le réécrit
depuis Git en quelques minutes et rétablit `selfHeal`. Les pods étaient donc
relancés en boucle. L'app-of-apps, elle, porte `managed-by=Helm` **sans
tracking-id ArgoCD** — personne ne la réconcilie, donc la patcher tient.
**Il faut suspendre les deux niveaux.**

**Un script de données doit se remettre d'aplomb sur TOUTE sortie.** Le premier
`trap` ne couvrait que `INT`/`TERM`. Un échec anodin sous `set -e` — un `mkdir`
refusé — a laissé sept déploiements à zéro et la synchro suspendue : la pile
arrêtée. Un `trap EXIT` relève désormais les déploiements et rétablit ArgoCD quelle
que soit la cause de la sortie.

**Ne jamais copier si l'arrêt n'est pas confirmé.** La première version poursuivait
la copie après cinq minutes d'attente même si des pods tournaient encore —
garantissant des bases SQLite incohérentes. Elle abandonne maintenant explicitement.

**Droits :** `/data/kube` appartient à root en `drwxr-xr-x` ; seuls les répertoires
de volumes qu'il contient sont en `drwxrwxrwx`. Et les répertoires de `seerr` sont
`root:root` — poser une date sur un répertoire exige d'en être propriétaire, d'où
un `rsync` qui échoue **seul**, après avoir tout copié. `--omit-dir-times` règle
le cas ; les applications ne dépendent pas de l'horodatage des dossiers.

**Un outil a menti.** `diff` passé par le proxy rtk a répondu « fichiers
identiques » sur deux `Chart.yaml` qui différaient bel et bien. Sans un second
passage par `/usr/bin/diff`, la cause aurait été manquée. Recouper avec le binaire
direct dès qu'une comparaison décide d'un diagnostic.

**Et une fausse alerte, la mienne.** J'ai annoncé une pile « entièrement supprimée »
sur la foi d'une lecture `kubectl` partielle. Elle avait en réalité été **recréée à
neuf** — ce qui est différent, et moins grave. Recouper avant d'alarmer.

## 5. Ce qui est en place

- `arr-stack` **épinglé en v0.53.0**, avec le mode opératoire de vérification en
  commentaire : `helm dependency build` puis `helm template`, et comparer le nombre
  de ressources rendues.
- **Règle Renovate `automerge: false`** sur ce dépôt (`renovate.json`).
- `scripts/restore-arr-volumes.sh`, réutilisable, avec ses garde-fous.
- Les 7 PV concernés sont en **`Retain`**.

## 6. Ce qui reste ouvert

- [ ] **Les autres volumes du cluster sont toujours en `reclaimPolicy: Delete`.**
      La même séquence sur une autre application produirait la même perte, sans le
      sursis. À arbitrer : passer en `Retain` les volumes portant un état
      irremplaçable (bases, configurations), au prix d'un nettoyage manuel des
      volumes libérés.
- [ ] **Auditer les autres apps en `prune: true`** dont la source est un chart
      externe versionné indépendamment — ce sont celles qui exposent le même
      enchaînement.
- [ ] Décider du sort des 7 anciens volumes et de `~/restore-backup-20260828-143206`
      une fois la restauration validée dans les interfaces.
- [ ] Remonter à l'amont `tom333/arr-stack` que v0.53.9 casse le rendu.
