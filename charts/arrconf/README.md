# charts/arrconf

Mini-chart custom (D-24, Phase 2 scope) qui déploie le CronJob `arrconf` dans le namespace `selfhost` pour réconcilier la config Sonarr depuis YAML (config-as-code, ADR-1).

> **Scope Phase 2** : Sonarr `download_clients` uniquement (D-25). Phase 3 étendra à indexers / notifications / root_folders / tags / host_config + Radarr + Prowlarr. Phase 4 absorbera ce mini-chart dans l'umbrella `charts/arr-stack/`.

## Two-PR protocol (D-28)

Pour valider sans risque qu'arrconf ne corrompe pas la config Sonarr en production, le déploiement passe par **deux PRs séquentielles** :

| PR | Change | `arrconfDryRun` | Comportement | Critère succès |
|---|---|---|---|---|
| **PR1** | création complète chart + ArgoCD App + Secret | `true` (default) | log les actions sans appeler `POST/PUT/DELETE` | `diff -rq snapshots/before-phase-2-<date>/sonarr/ snapshots/post-phase2-pr1-<date>/sonarr/` = 0 |
| **PR2** | one-line `values.yaml`: `arrconfDryRun: true` → `false` | `false` | apply réel | `sonarr/tag.json` gagne entrée `arrconf-managed`; download_client managé visible dans Sonarr UI |

PR1 doit être mergée et la phase de dry-run validée AVANT d'ouvrir PR2.

## Pre-merge checklist (PR1)

Avant de merger PR1, vérifier dans l'ordre :

1. **Secret bootstrap appliqué manuellement** — ArgoCD ne synchronise pas `secrets/` (exclu du sync) :
   ```bash
   kubectl apply -f my-kluster/secrets/arrconf-secret.yaml
   kubectl get secret arrconf-env -n selfhost   # expect: present
   ```
   Si oublié : Pod CrashLoops sur `SONARR_API_KEY` manquant.

2. **Image GHCR publique et pullable** (Phase 1 HUMAN-UAT #1, ADR-3) :
   ```bash
   docker logout ghcr.io
   docker pull ghcr.io/tom333/arr-stack-arrconf:0.1.2
   ```
   Si fail : toggle visibility dans GitHub package settings (Danger Zone → Public).

3. **Snapshot baseline pré-déploiement existe** (ADR-6) :
   ```bash
   ls /home/moi/projets/perso/arr-stack/snapshots/before-phase-2-2026-05-08/sonarr/downloadclient.json
   ```

## Drift demo runbook (post-PR2)

Pour prouver REQ-drift-detection après merge PR2 :

```bash
# 1. Forensic snapshot AVANT le test (W-01 REQUIRED)
tools/snapshot/snapshot.sh --apps sonarr --output snapshots/drift-test-$(date +%F)/

# 2. Mutation UI hors-Git (port-forward + curl ou UI)
kubectl -n selfhost port-forward svc/sonarr 8989:8989 &
# Modifier name du download_client en UI ou via API

# 3. Forcer un Job arrconf hors-cron pour observer la correction immédiate :
kubectl -n selfhost create job --from=cronjob/arrconf arrconf-drift-demo
kubectl -n selfhost logs job/arrconf-drift-demo > .planning/phases/02-arrconf-cluster-validation/evidence/drift-demo-$(date +%F).log

# 4. Vérifier dispositive value-equality (W-04) :
grep -E '"event":"plan_action".*"action":"update"' .planning/.../drift-demo-*.log
# Le log doit contenir au moins 1 update event indiquant que la mutation UI est revertée.
```

## Operational caveats (Pitfalls)

- **`concurrencyPolicy: Forbid`** ne bloque QUE les Jobs créés par le scheduler (Pitfall 4). Un Job `kubectl create job --from=cronjob/arrconf` est autorisé même si une instance schedulée tourne — utile pour le drift demo, attention en run normal.
- **`selfHeal: true`** dans ArgoCD ⇒ `kubectl edit cronjob arrconf` est revert au prochain sync (Pitfall 8). Pour modifier en prod : passer par PR sur ce chart.
- **`checksum/config` annotation** : largement cosmétique (Pitfall 5). Pour qu'un nouveau ConfigMap force un nouveau Pod hash, il faut hash `subPath` correctement — l'implémentation actuelle re-crée le hash mais Kubernetes ne re-pull pas le ConfigMap dans un volume `subPath` mid-Pod. Pour forcer un redeploy : `kubectl rollout restart cronjob/arrconf` (ou suspendre/réactiver).
- **`tty: true` retiré** (Pitfall 10) : structlog active le rendering JSON quand stdout n'est pas un TTY. Avec `tty: true` les logs étaient en console-friendly format, illisibles par jq. Sans tty:true → JSON propre, parsable.

## Frontière configarr (ADR-5)

Ce chart **ne** réconcilie **pas** :
- `quality_profiles`, `custom_formats`, `quality_definitions`, `media_naming` ← propriété de `charts/configarr/` (ScopeViolationError côté arrconf si config tentait d'écrire ces endpoints)

## Renovate

L'image `ghcr.io/tom333/arr-stack-arrconf` est suivie via l'annotation `# renovate: image=...` dans `values.yaml` (ligne au-dessus de `repository:`, sans ligne vide). Bump auto sur les tags semver `vX.Y.Z` du repo arr-stack.
