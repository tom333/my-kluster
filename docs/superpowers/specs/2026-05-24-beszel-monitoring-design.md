# Spec — Monitoring multi-machines avec Beszel + Ansible

**Date** : 2026-05-24
**Auteur** : Thomas Guyader (avec Claude)
**Statut** : design validé, en attente d'implémentation

---

## 1. Objectif

Déployer une solution de **monitoring multi-machines** pour le homelab :
- Tableau de bord centralisé visible en LAN (`beszel.tgu.ovh`)
- Couverture : cluster k8s, VM Home Assistant, Raspberry Pi(s), autres machines Ubuntu (5-10 machines au total)
- Alertes Telegram sur seuils critiques (disque, RAM, CPU, agents down)
- Déploiement des agents 100% automatisé via Ansible (IaC)
- Stack légère : <500 MB RAM total pour hub + agents

## 2. Motivation

**Incident référence du 23 mai 2026** : containerd OOM sur le cluster microk8s, déclenché par sda2 saturé (74% — au-dessus du seuil image-gc 75%) à cause de 247 GB de dossiers `.OLD` oubliés post-migration. Le cluster a été down 2h30 sans alerte préalable.

Un simple alert "disque > 70%" aurait :
1. Notifié 5 jours plus tôt que sda2 montait
2. Déclenché le cleanup au bon moment
3. Évité le crash

→ Le monitoring proactif **multi-machines** devient une priorité opérationnelle.

## 3. Décisions clés et rationale

| Décision | Choix | Pourquoi |
|---|---|---|
| **Solution monitoring** | Beszel | Single binary Go, <50 MB RAM hub + <10 MB par agent. Dashboards + alertes intégrés. Pas de PromQL à apprendre. 12k+ stars GitHub, actif. Alternatives écartées : Prometheus (trop lourd), Netdata (interface trop dense pour le besoin), VictoriaMetrics+Grafana (3-4 composants vs 1). |
| **Déploiement agents** | Ansible | Idempotent, versionné dans Git, agent-less côté cible (juste SSH + Python). Évite le bricolage manuel sur 5-10 machines, scale à plus si besoin. |
| **Conf Ansible repo** | Stratégie B : sous-dossier `ansible/` dans `tom333/my-kluster` public + Ansible Vault pour les secrets | 1 seul repo à maintenir. Inventaire en clair (IPs LAN RFC1918 peu sensibles), secrets (clé SSH privée hub, tokens) chiffrés via Vault. Cohérent avec le pattern Sealed Secrets déjà utilisé pour k8s. |
| **Canal alertes** | Telegram via webhook | 5 min setup. Robuste, gratuit, app sur tous devices. Beszel supporte webhook nativement. Alternatives écartées : WhatsApp (setup 2-3h supplémentaire + risque ban si WAHA self-hosted). |
| **Niveau observabilité** | Dashboards + alertes système | Pas de logs/traces (kubetail déjà installé pour ça). Pas de monitoring k8s-natif (pods, etcd) — couverture du host suffit pour le besoin. Pas de monitoring GPU (DCGM exporter déjà déployé via GPU Operator, peut être visualisé séparément si besoin futur). |

## 4. Architecture

```
                              ┌──────────────────────┐
                              │   Beszel Hub          │
                              │   k8s cluster         │
                              │   beszel.tgu.ovh      │ 🔒 whitelist LAN
                              │   PVC SQLite 1Gi      │
                              └─────────┬────────────┘
                                        │
                                        │ SSH outbound (clé Ed25519)
                                        │ pas de port ouvert côté agents
                                        │
       ┌──────────────────┬─────────────┼─────────────┬──────────────┐
       ↓                  ↓             ↓             ↓              ↓
  [k8s-node]         [ha-host]     [pi-salon]   [ubuntu-bureau]    [...]
  agent systemd      agent         agent        agent              agent
       │                  │             │             │              │
       └──────────────────┴──── métriques ───────────┴──────────────┘
                                        │
                                        │ HTTP POST webhook
                                        ↓
                              Telegram Bot API ──→ chat alertes utilisateur
```

**Flux** :
1. Chaque **agent** lit `/proc`, `/sys`, Docker socket sur sa machine en local. Stateless.
2. Le **hub** SSH vers chaque agent toutes les 30s pour récupérer les métriques. Stocke en SQLite.
3. Le **hub** évalue les seuils → si dépassement, envoie un POST à l'API Telegram → message dans le chat.

## 5. Composants

### 5.1. Hub Beszel (cluster k8s)

| Attribut | Valeur |
|---|---|
| **Image** | `henrygd/beszel:0.10.0` (pinned, suivi par Renovate) |
| **Chart** | `bjw-s/app-template` 5.0.1 (pattern MLflow) |
| **Namespace** | `monitoring` (nouveau, AppProject `infra-project`) |
| **Resources** | requests 100m CPU / 128 Mi RAM, limits 500m CPU / 512 Mi RAM |
| **PVC** | 1 Gi sur `microk8s-hostpath` (= NVMe via /data/kube) |
| **Service** | ClusterIP port 8090 |
| **Ingress** | `beszel.tgu.ovh`, NGINX, cert-manager letsencrypt-prod, whitelist `192.168.88.0/24,10.1.0.0/16`, **pas d'oauth2-proxy** (Beszel a son propre login via PocketBase) |
| **Secrets** | `beszel-secrets` SealedSecret avec : token Telegram bot, clé SSH privée Hub (pour scrap des agents) |
| **Manifest ArgoCD** | `argocd/argocd-apps/beszel-app.yaml` |

### 5.2. Agents Beszel (sur chaque machine cible)

| Attribut | Valeur |
|---|---|
| **Binaire** | `beszel-agent` v0.10.0 (Go, ARM64 ou amd64 selon arch) |
| **Path install** | `/usr/local/bin/beszel-agent` |
| **User système** | `beszel` (no-login, home `/var/lib/beszel`) |
| **Service** | `beszel-agent.service` (systemd) |
| **Port d'écoute SSH** | 43000 (custom pour pas confliquer avec sshd standard 22) |
| **Authorized key** | clé publique du Hub (push par Ansible) |
| **Auto-restart** | systemd `Restart=always` |
| **Métriques collectées** | CPU (global + par core), RAM, swap, disque (par partition + I/O), réseau (in/out par interface), Docker (status + RAM/CPU par container), température (lm-sensors si dispo), uptime |

### 5.3. Ansible (déploiement)

**Structure dans le repo `my-kluster`** :

```
ansible/
├── ansible.cfg                       # config globale (timeout SSH, host_key_checking off)
├── inventory.yml                     # CLAIR : IPs, hostnames, users SSH
├── playbook.yml                      # entry point
├── group_vars/
│   ├── all.yml                       # CLAIR : version agent, configs non-sensibles
│   └── vault.yml                     # CHIFFRÉ : clé SSH publique hub, password vault
└── roles/
    └── beszel-agent/
        ├── defaults/main.yml         # version, port, paths
        ├── tasks/main.yml            # install + config + start (idempotent)
        ├── handlers/main.yml         # restart service si config change
        └── templates/
            └── beszel-agent.service.j2
```

**Workflow type** :

```bash
# Première install ou ajout de machine
cd ansible/
ansible-playbook -i inventory.yml playbook.yml --vault-password-file ~/.vault-password.txt

# Mise à jour de l'agent sur toutes les machines
# (changer beszel_agent_version dans group_vars/all.yml puis re-run)

# Ajout d'une nouvelle machine
# (ajouter 3 lignes dans inventory.yml, puis :)
ansible-playbook -i inventory.yml playbook.yml --limit nouvelle-machine
```

### 5.4. Telegram Bot

**Setup hors-projet (manuel)** :

1. Sur Telegram : message à `@BotFather` → `/newbot` → suivre les étapes → récupérer le **token** (format `123456:ABC-DEF...`)
2. Trouver son **chat_id** : message à `@userinfobot` → récupérer l'ID numérique
3. Stocker token dans SealedSecret `beszel-secrets`, key `telegram_bot_token`
4. Stocker chat_id en variable d'env du Hub `TELEGRAM_CHAT_ID`

**Webhook URL pour Beszel** (configurée dans l'UI du Hub après déploiement) :
```
https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text={MESSAGE}
```

## 6. Alertes initiales

Configurées dans l'UI du Hub après déploiement Phase 3. **Throttling** : max 1 alerte / 30 min par seuil + machine.

| # | Alerte | Seuil | Cible(s) | Sévérité | Pourquoi |
|---|---|---|---|---|---|
| 1 | Disk usage | >70% | toutes machines | ⚠️ warn | Aurait évité incident 23 mai |
| 2 | Disk usage | >85% | toutes machines | 🚨 critical | Action immédiate requise |
| 3 | RAM usage | >90% sustained 5 min | toutes machines | ⚠️ warn | Détecte memory leaks (LocalAI, Whisper futur) |
| 4 | CPU usage | >90% sustained 10 min | toutes machines | ⚠️ warn | Évite false positives sur builds longs |
| 5 | Agent down | >5 min unreachable | toutes machines | 🚨 critical | Machine offline / crash |
| 6 | Docker container restart loop | >3 restarts / 10 min | machines avec Docker | ⚠️ warn | Typique pour LocalAI ou autres pods k8s |
| 7 | Température | >70°C | Pi seulement | ⚠️ warn | Manque ventilation → throttle |
| 8 | Température | >80°C | Pi seulement | 🚨 critical | Risque dommage hardware |

## 7. Phasage de déploiement

| Phase | Effort | Livrable | Critère de succès |
|---|---|---|---|
| **Phase 1** — Hub k8s + 1 agent manuel | ~1h | Hub déployé sur `beszel.tgu.ovh`. Login admin créé. Agent installé manuellement sur 1 machine (cluster node) pour valider la chaîne. | Dashboard accessible, 1 machine visible avec métriques temps réel. |
| **Phase 2** — Ansible role + déploiement multi | ~2-3h | Rôle `beszel-agent` écrit + inventaire complet + déploiement automatisé sur les 5-10 machines. | `ansible-playbook ... playbook.yml` retourne "ok=N, failed=0". Toutes machines visibles dans le Hub. |
| **Phase 3** — Alertes Telegram | ~30 min | Bot Telegram créé, token dans SealedSecret, webhook configuré dans Hub, 8 seuils activés. | Test manuel : forcer un seuil → message Telegram reçu. |
| **Phase 4** — Tuning (1 semaine après) | ~1h | Ajustement des seuils selon comportement réel observé. Documentation des seuils retenus dans CLAUDE.md. | Aucun false positive en 3 jours, aucun true negative oublié. |

**Total** : ~5-6h sur 1-2 weekends.

## 8. Sécurité

### Modèle de menace

| Vecteur | Risque | Mitigation |
|---|---|---|
| Repo public expose IPs LAN | 🟡 faible | IPs RFC1918 non-routables. Utile uniquement à attaquant déjà sur LAN. Acceptable. |
| Clé SSH privée du Hub leakée | 🔴 critique | Chiffrée dans `ansible/group_vars/vault.yml` via Ansible Vault. Password vault en local seulement (`~/.vault-password.txt` dans `.gitignore`). Côté Hub k8s : dans SealedSecret. |
| Token Telegram leaké | 🟠 moyen | Permet à un attaquant d'envoyer des messages au chat. Pas de prise de contrôle système. Token dans SealedSecret, jamais en clair. |
| Hub compromis → contrôle agents | 🔴 critique | Le user `beszel` sur les machines cibles a `nologin` shell. La clé du Hub ne permet QUE de lire les métriques (pas exec arbitraire). Limite l'exploitation possible. |
| Beszel hub UI exposé internet | 🟡 faible | Whitelist NGINX `192.168.88.0/24,10.1.0.0/16` (LAN only). Pas d'accès externe sans tunneling. |
| Login Beszel weak password | 🟠 moyen | PocketBase exige password strong au signup. À renforcer avec 2FA si Beszel l'ajoute futur. |

### Bonnes pratiques

- **Clé SSH dédiée pour le Hub** : pas la même que celle du user humain. Type Ed25519. Régénérée si compromise.
- **Vault password** : stocké uniquement en local + 1 backup sur clé USB chiffrée hors-cluster. Jamais dans le repo.
- **Sealed Secret** pour token Telegram : clé master sealed-secrets sauvegardée hors-cluster (déjà en place).
- **Rotation** : tous les 6 mois, régénérer la clé SSH Hub + relancer le playbook Ansible.

## 9. Maintenance et runbook

### Monitoring du monitoring

Métriques du Hub lui-même surveillées :
- Sa propre RAM/CPU (visible dans son propre dashboard puisque l'agent peut aussi tourner sur la machine du hub)
- État de la connexion SSH vers chaque agent (alerte "agent down" si timeout)

### Tâches périodiques

| Tâche | Fréquence | Action |
|---|---|---|
| Vérifier dashboards | quotidien (rapide) | Coup d'œil 30s pour anomalies |
| Bumper agent version | tous les 1-2 mois (si nouvelle release) | Modifier `beszel_agent_version` dans `group_vars/all.yml`, re-run playbook |
| Bumper Hub version | tous les 1-2 mois | Renovate ouvre la PR auto si configuré |
| Backup SQLite Hub | hebdomadaire | CronJob k8s (`/data/kube/...beszel.../pb_data.db` → `/media/data/backups/`) |
| Rotation clé SSH Hub | tous les 6 mois | Régénérer, push via Ansible playbook |
| Review seuils alertes | trimestriel | Ajuster si trop/pas assez d'alertes |

### Procédure d'incident type

**Si Hub Beszel down** :
1. `kubectl -n monitoring get pod` → diagnostic
2. Si OOM : check resources Hub (rare avec 512Mi)
3. Si crash : `kubectl logs` → root cause
4. Fallback : tu reçois plus d'alertes Telegram → vérifie manuellement les machines critiques

**Si agent ne remonte plus** :
1. Hub alerte "agent down"
2. SSH manuel sur la machine
3. `systemctl status beszel-agent` → diagnostic
4. Si binaire corrompu : `ansible-playbook ... --limit machine-X` pour réinstaller

## 10. Risques et mitigations

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| Beszel projet abandonné | 🟡 faible | 🟠 moyen | Single binary Go, fork facile si besoin. Maintenu actif 2026, 12k stars. |
| Faux positifs alertes (spam Telegram) | 🟠 moyen | 🟡 faible | Throttling 30 min + tuning Phase 4. |
| Hub DB SQLite corruption | 🟢 très faible | 🟠 moyen | Backup hebdo. PocketBase gère bien SQLite. Reconstruction depuis 0 = 1h. |
| Ansible Vault password perdu | 🟠 moyen | 🔴 critique | Backup password dans password manager (Bitwarden / KeePassXC) + clé USB chiffrée. |
| Drift entre repo et machines réelles | 🟠 moyen | 🟡 faible | Re-run playbook hebdomadaire en CronJob ou tâche manuelle. |
| Bande passante NC saturée par les pulls images | 🟢 faible | 🟡 faible | Image Beszel <50 MB, pull rare. Pas d'impact. |

## 11. Non-objectifs (ce qu'on NE fait PAS)

- ❌ Monitoring k8s-natif (pods, etcd, kube-state-metrics). Si besoin futur, on ajoutera VictoriaMetrics + node_exporter en parallèle.
- ❌ Monitoring GPU NVIDIA. Le DCGM exporter (déjà déployé) reste accessible séparément ou via un Grafana dédié si besoin futur.
- ❌ Monitoring applicatif fin (latences, error rates par endpoint). Pas le bon outil. Si besoin, OpenTelemetry + Tempo plus tard.
- ❌ Logs centralisés. `kubetail` couvre déjà le besoin.
- ❌ Traces distribuées. Pas pertinent pour le homelab.
- ❌ Métriques Home Assistant (capteurs domotiques). HA a son propre monitoring intégré.
- ❌ SLA, alerting on-call rotation, runbook automatisé. Homelab pas un service production.
- ❌ Migration vers solution lourde (Prometheus complet, Mimir, etc.) tant que Beszel suffit.

## 12. Annexe : structure de fichiers attendue après implémentation

```
my-kluster/
├── argocd/argocd-apps/
│   └── beszel-app.yaml                      # NEW : ArgoCD app pour le Hub
├── sealed/
│   └── beszel-secrets.yaml                  # NEW : token Telegram + clé SSH Hub
├── ansible/                                  # NEW : tout le sous-projet Ansible
│   ├── ansible.cfg
│   ├── inventory.yml
│   ├── playbook.yml
│   ├── group_vars/
│   │   ├── all.yml
│   │   └── vault.yml                        # chiffré
│   └── roles/beszel-agent/
│       ├── defaults/main.yml
│       ├── tasks/main.yml
│       ├── handlers/main.yml
│       └── templates/beszel-agent.service.j2
├── CLAUDE.md                                 # MODIF : ajouter la section monitoring
├── TODO.md                                   # MODIF : phase suivante = embeddings ? n8n ?
└── .gitignore                                # MODIF : ajouter `**/.vault-password*`
```

## 13. Critères d'acceptation

L'implémentation est considérée comme **terminée** quand :

- [ ] Hub Beszel accessible sur `beszel.tgu.ovh` (LAN-only)
- [ ] Au moins 5 machines visibles dans le dashboard avec métriques temps réel
- [ ] Les 8 alertes définies en section 6 sont configurées dans le Hub
- [ ] Test manuel : un seuil franchi déclenche bien un message Telegram
- [ ] `ansible-playbook -i inventory.yml playbook.yml` retourne `ok=N, changed=0, failed=0` quand re-run (idempotence)
- [ ] Documentation `CLAUDE.md` mise à jour avec section monitoring
- [ ] Backup SQLite Hub fonctionnel (test de restauration sur poste local)
- [ ] Aucun false positive observé pendant 3 jours consécutifs

## 14. Suivi

Après implémentation, suivre dans `CLAUDE.md` section "Maintenance courante" :
- Date du dernier bump agent / hub
- Liste des machines monitorées (à jour)
- Incidents évités grâce au monitoring (compteur "value")
