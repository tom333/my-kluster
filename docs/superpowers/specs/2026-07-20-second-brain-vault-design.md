# Second-brain — vault markdown git-backed (cadrage)

- **Date** : 2026-07-20
- **Statut** : cadrage validé (décisions actées) — avant implémentation
- **Voir aussi** : txtai déjà déployé (`argocd/argocd-apps/txtai-app.yaml`), mémoire fichier Claude Code actuelle (par-projet, silotée, à migrer).

---

## 1. Problème

- **Silos** : ~19 projets Claude Code + sessions Hermes, chacun sa mémoire locale, aucun lien. Entités transverses (cluster, 3060, Postgres, Traefik…) éclatées.
- **Perte de contexte cross-poste** : mémoire locale à `pc`, non synchronisée. **Usage 50/50 hors-LAN → prérequis dur.**
- **"Où ai-je fait X"** : déjà résolu par **txtai**. ✅
- **Pas de mémoire centrale portable** que Claude lit/écrit. ❌ ← le gap.
- **Volume élevé** (centaines de sessions + crons Hermes) → **la validation manuelle par écriture est exclue**.

## 2. Principes directeurs

1. **Autonomie par défaut** : l'IA écrit sans validation humaine préalable (comme txtai ingère déjà). Pas de gate par écriture.
2. **Zones disjointes** : l'IA n'écrit **que dans ses propres fichiers**, jamais dans les tiens → aucun conflit, aucune revue requise. Elles se **lient** (wikilinks), ne se chevauchent pas.
3. **Append / new-file only** : l'IA **ne supprime ni ne réécrit** jamais un fichier existant. Au pire = du bruit (jamais une perte). 1 fichier par session (nommé par session-id) → quasi pas de conflit git multi-écrivains.
4. **Git = sécurité a posteriori** : tout versionné, `git revert` si dérive. Réversible, auditable — pas de contrôle a priori.
5. **Revue = bulk, périodique, optionnelle** : un digest hebdo (Hermes) ; tu promeus/purges quand tu veux, jamais bloquant.
6. **KISS / pas de graphe-DB au départ** (cf. §7).
7. **OSS / self-host** ; markdown lisible et autonome (grep/éditeur sans outil).

## 3. Architecture (git-backed)

```
Remote : github.com/tom333/brain (PRIVÉ)
   ▲  git pull/push HTTPS — marche PARTOUT (LAN + hors-LAN + offline)
   ├── pc      : clone ~/brain → VRAIS fichiers → Claude-MCP + txtai + grep
   ├── laptop  : clone ~/brain → idem (LAN ou hors-LAN, identique)
   └── SilverBullet (pod) : clone sur PVC + sidecar git-sync (pull/commit/push)
                            → web via ingress PUBLIC + oauth2-proxy  (brain.tgu.ovh)
```

- **Remote** = repo GitHub **privé** `tom333/brain` (zéro infra, hors-LAN natif, auth gh/ssh existante). Migration Forgejo self-host possible plus tard (git remote = 1 commande).
- **Clients** (pc, laptop) : `git clone` → fichiers locaux → **filesystem-MCP** (`@modelcontextprotocol/server-filesystem` sur `~/brain`) + indexeur txtai + grep. Rapide, offline-capable.
- **SilverBullet** : pod, space = clone sur PVC + **sidecar git-sync** (SB = folder pur, pas de git natif → conteneur qui pull/commit/push en boucle). Ingress **public + oauth2-proxy** → web hors-LAN. Push via **deploy-key/PAT GitHub en SealedSecret** (règle kubeseal).
- **Zéro live-sync** assumé : la sync est git (pull au début, push en fin). Cohérent avec le 50/50 hors-LAN où un FS partagé live est impossible.

## 4. Structure du vault (zones disjointes)

```
brain/
  CLAUDE.md            ← schéma + règles + déclare les skills (lu par Claude Code)

  # ── ZONE HUMAINE ── l'IA LIT, n'écrit JAMAIS
  permanent/           tes notes atomiques curées (Zettelkasten)
  entities/            LA note canonique par brique (courte, autoritaire) — à toi
    rtx-3060.md  cluster-microk8s.md  postgres.md  traefik.md  ornith.md
  architecture/        tes MOC : cartes de dépendances (mermaid + [[depends-on]])
    data-stack-map.md

  # ── ZONE IA ── écriture AUTONOME, auto-commit+push, zéro validation
  sessions/            1 fichier/session (Claude + Hermes), résumé auto (nommé session-id)
  observations/        faits/liens extraits par l'IA, EN PARALLÈLE des entities (backlinkés)
    rtx-3060.md        (l'IA accumule ici ; toi tu cures entities/rtx-3060.md quand tu veux)
  .agent/              pages-concepts dérivées, jetables/régénérables
  logs/  inbox/
```

**Conventions** : `[[wikilinks]]` (backlinks = graphe transverse gratuit) · frontmatter obligatoire (`title, tags, type, zone: human|ai, created, updated`) · kebab-case · l'IA écrit `zone: ai`, ne touche jamais `zone: human`.

## 5. La glue

- **`brain/CLAUDE.md`** : règles + skills.
- **Skill `/recall <sujet>`** : `git pull` → lit `entities/` + `observations/` + `architecture/` + logs récents pertinents (+ option recherche txtai).
- **Skill `/save`** : écrit dans la **zone IA** (résumé de session + observations + nouveaux liens) → **`git add` + commit + push AUTONOME** (pas de gate). 1 fichier session par session-id (anti-conflit).
- **Projets** : les `CLAUDE.md` des repos **référencent** le vault (`@~/brain/…`) au lieu de dupliquer.

## 6. Relation avec la mémoire Claude Code actuelle

- Mémoire par-projet (`~/.claude/projects/<proj>/memory/`) → migrée vers `brain/permanent/` + `brain/entities/` (zone humaine) au fil de l'eau.
- Filesystem-MCP donne l'accès **cross-projet** (indépendant du cwd) : une session cluster lit la veille, etc.
- txtai indexe `~/brain` (après `git pull`) → recherche unifiée sessions + vault.

## 7. Hors scope + conditions de bascule

**PAS au départ** :
- **Graphe-DB** (Cognee/Graphiti) : transverse = backlinks, dépendances = MOC curé, recherche = txtai. Bascule seulement si multi-hop récurrent non résolu ET extraction validée propre. **Pilote, ne fonde pas.**
- **IA qui édite la zone humaine** : jamais. L'IA propose au plus via `observations/` ; la promotion vers `entities/`/`permanent/` est humaine (ou via digest).
- **Lint qui mute** : le digest **signale** (contradictions/orphelins), ne corrige pas.

## 8. Décisions actées

| Point | Décision |
|---|---|
| Stockage | **Git-backed**, remote **GitHub privé `tom333/brain`** (Forgejo self-host = évolution) |
| Interface humaine | **SilverBullet** (pod + sidecar git-sync, ingress public + oauth2) |
| Accès Claude | filesystem-MCP officiel sur clone local `~/brain` |
| Modèle d'écriture | **autonome, zones disjointes, append-only, git-réversible** (pas de veto par écriture) |
| Revue | **digest hebdo Hermes** (bulk, optionnel) |
| Migration silos | **au fil de l'eau** (un projet migré à sa prochaine session) |

## 9. Phasage

- **P0 — socle** : créer repo privé `tom333/brain` + structure + `CLAUDE.md` + cloner sur pc + brancher **filesystem-MCP** sur Claude Code. → mémoire centrale lisible/écrivable, autonome.
- **P1 — glue** : skills `/recall` + `/save` (avec git pull/commit/push auto). → continuité cross-session/poste, le plus fort levier.
- **P2 — recherche** : indexeur txtai ajoute `~/brain` (pull puis index). → recherche unifiée.
- **P3 — web** : SilverBullet + sidecar git-sync + ingress public/oauth (deploy-key SealedSecret). → accès web hors-LAN + graphe de liens.
- **P4 — entités & MOC** : peupler `entities/` + `architecture/data-stack-map.md` en migrant les silos.
- **P5 — digest** : cron Hermes hebdo (nouvelles observations + contradictions + orphelins → Telegram).
- **P6 (conditionnel)** : graphe-DB si §7 déclenché.

## Notes d'implémentation

- **Clients** : clone sur les 2 postes (pc + laptop) via ansible (rôle `dev-workstation`), auth clé `tom333`.
- **Anti-conflit** : privilégier new-file (session-id, entity-name) ; les rares merges = git gère (markdown line-based).
- **Secret push SB** : deploy-key GitHub write sur `tom333/brain` → SealedSecret ns du pod SilverBullet.
