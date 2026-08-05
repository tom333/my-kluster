# Phase 6: Auth Lifecycle & Options - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 06-Auth Lifecycle & Options
**Areas discussed:** Reauth flow (AUTH-05), Reconfigure flow (AUTH-06), OptionsFlow schema & layout (OPT-01..04, COORD-03), Nickname surface (OPT-03)

---

## Reauth flow (AUTH-05)

### Q1 — Quels champs montre le formulaire de reauth ?

| Option | Description | Selected |
|--------|-------------|----------|
| Password-only | Seul `password` est demandé. URL/account_type/username réutilisés depuis entry.data. Interprétation littérale d'AUTH-05 + pattern standard HA. | |
| Password + username | Au cas où le parent change aussi son identifiant Pronote. Plus rare en pratique mais offre une porte de sortie sans recréer l'entry. | ✓ |
| Password + show read-only context | Champ password modifiable + affichage en lecture seule de URL/username. | |

**User's choice:** Password + username
**Notes:** Le choix élargit légèrement la lecture stricte d'AUTH-05 ("password-only") pour offrir une voie de sortie quand l'utilisateur change aussi son identifiant Pronote. Reste sémantiquement "reauth" (pas reconfigure).

### Q2 — Que faire avec entry.data['session'] après reauth réussi ?

| Option | Description | Selected |
|--------|-------------|----------|
| Clear session, force token_login fresh | Vider entry.data['session']. La prochaine setup tombera direct dans le fresh-login branch. Garantie de cohérence. | ✓ |
| Garder l'ancienne session, laisser token_login échouer | Ne pas toucher à entry.data['session']. Au prochain setup, token_login échouera et le fallback fresh-login s'enclenchera. | |

**User's choice:** Clear session
**Notes:** Le pattern actif (token_login fast path + fallback) gère le cas, mais clear explicite garantit la cohérence post-rotation.

### Q3 — Quel device_name lors du reauth ?

| Option | Description | Selected |
|--------|-------------|----------|
| Réutiliser device_name existant `home-assistant-{entry_id[:8]}` | entry_id stable across reauth, contrat AUTH-07. | ✓ |
| Calculer un nouveau device_name si l'utilisateur veut | Champ optionnel pour renommer. Risque: device fantôme dans Pronote. | |

**User's choice:** Réutiliser device_name existant

### Q4 — Comment HA déclenche-t-il le reauth flow ?

| Option | Description | Selected |
|--------|-------------|----------|
| ConfigEntryAuthFailed natif | HA fire le reauth automatiquement. Aucune nouvelle plomberie. | ✓ |
| ConfigEntryAuthFailed + Repair Issue avec bouton 'Reauth' | UX plus visible, mais le Repair Issue est Phase 7 DIAG-03. | |

**User's choice:** ConfigEntryAuthFailed natif (Repair Issue déféré à Phase 7)

---

## Reconfigure flow (AUTH-06)

### Q1 — Quels champs sont éditables dans le reconfigure flow ?

| Option | Description | Selected |
|--------|-------------|----------|
| URL + account_type | Seuls les champs avec un usage réaliste. username/password restent figés. | ✓ |
| URL + account_type + username | Migration vers un autre compte mais même enfant. Floute la frontière reauth/reconfigure. | |
| Tout (URL + account_type + username + password) | Reconfigure = full edit. Mais alors reauth devient redondant. | |

**User's choice:** URL + account_type
**Notes:** Frontière reauth/reconfigure nette pour la review HA quality scale + assertions distinctes dans les tests.

### Q2 — Que faire si la nouvelle URL pointe vers un établissement où child_identifier change ?

| Option | Description | Selected |
|--------|-------------|----------|
| Abort avec erreur claire | async_abort(reason='child_identifier_changed'). Préserve l'unique_id figé (ENT-02) + historique Recorder. | ✓ |
| Permettre, mettre à jour child_identifier + unique_id | Casse l'historique des entités côté HA. | |

**User's choice:** Abort
**Notes:** Anti-pattern explicite : pas de migration auto-magique. Utilisateur invité à supprimer + recréer.

### Q3 — Validation des nouveaux credentials pendant le reconfigure ?

| Option | Description | Selected |
|--------|-------------|----------|
| Re-valider via build_or_resume_client | Avant async_update_entry. Auth fail → erreur dans le form. | ✓ |
| Pas de re-validation | On commit direct, l'utilisateur verra le ConfigEntryAuthFailed et lancera un reauth. | |

**User's choice:** Re-valider

### Q4 — Que faire de entry.data['session'] après reconfigure réussi ?

| Option | Description | Selected |
|--------|-------------|----------|
| Clear session si URL ou account_type a changé | La session pronotepy est liée à l'établissement + au type de compte. | ✓ |
| Toujours clear | Plus simple, même logique que reauth. Coût: un login extra inutile. | |

**User's choice:** Clear si URL ou account_type a changé (conditionnel)

---

## OptionsFlow schema & layout (OPT-01..04, COORD-03)

### Q1 — Quelle surface d'options expose-t-on dans l'OptionsFlow ?

| Option | Description | Selected |
|--------|-------------|----------|
| Minimale stricte = REQUIREMENTS uniquement | 5 clés (refresh_interval, adaptive on/off, afternoon_interval, nickname, school_tz). Les autres clés Phase 5 restent const. | |
| Complète = toutes les clés Phase 5 + nickname + school_tz | 10+ clés. Plus de leviers utilisateur dès v1. | ✓ |

**User's choice:** Complète (10 clés + 1 toggle adaptive_polling_enabled)
**Notes:** Préférence pour exposer tous les leviers dès v1 plutôt que les ajouter en minor releases.

### Q2 — Layout du formulaire OptionsFlow ?

| Option | Description | Selected |
|--------|-------------|----------|
| Single-step | Toutes les clés dans un écran. Plus simple. | |
| Multi-step groupé par concern | Step 1 'Polling', step 2 'Affichage'. Plus chic UX. | ✓ |

**User's choice:** Multi-step
**Notes:** Step 1 = "Polling" (refresh + adaptive toggle + afternoon_* + suspended_cadence + quiet_*) ; Step 2 = "Affichage" (nickname + school_tz).

### Q3 — Defaults dans la voluptuous schema?

| Option | Description | Selected |
|--------|-------------|----------|
| Lus depuis const.py (single source of truth) | Pas de drift UI↔runtime possible. | ✓ |
| Hardcodés dans le schéma config_flow.py | Risque de drift. | |

**User's choice:** const.py via helper `_options_schema_defaults(entry)`

### Q4 — Wiring de reload-on-options-change (OPT-04) ?

| Option | Description | Selected |
|--------|-------------|----------|
| entry.add_update_listener naïf | Reload sur tout changement. Pattern HA standard, ~1s overhead. | ✓ |
| Diff-aware | Reload seulement si certaines clés changent. Plus complexe. | |

**User's choice:** Naïf

---

## Nickname surface (OPT-03)

### Q1 — Qu'est-ce que le nickname change concrètement côté UI ?

| Option | Description | Selected |
|--------|-------------|----------|
| DeviceInfo.name | Propage via has_entity_name=True (ENT-03). Une clef, effet partout. | ✓ |
| Juste l'entity friendly_name (entity registry override) | Plus chirurgical, perd l'effet "device renamed". | |

**User's choice:** DeviceInfo.name

### Q2 — Quand le nickname est None (cas par défaut), quel device.name affiche-t-on ?

| Option | Description | Selected |
|--------|-------------|----------|
| Le real Pronote name `entry.data['child_name']` | Déjà disponible, comportement identique à aujourd'hui. | ✓ |
| Le child_identifier (D-15 Phase 3 ClientInfo.id) | Plus stable mais moins lisible (UUID-like). | |

**User's choice:** entry.data['child_name']

### Q3 — Le nickname affecte-t-il aussi le titre du ConfigEntry (entry.title) ?

| Option | Description | Selected |
|--------|-------------|----------|
| Oui — async_update_entry au reload | Cohérence UI "Devices & Services". | ✓ |
| Non — entry.title reste le real name | Plus simple, mais divergence visuelle. | |

**User's choice:** Oui, mettre à jour entry.title

### Q4 — Validation du nickname (longueur, caractères) ?

| Option | Description | Selected |
|--------|-------------|----------|
| Optionnel + max 40 chars + strip whitespace | Pas de regex, emojis OK, 40 chars suffisants. | ✓ |
| Optionnel + sans limite | Risque de casser le contrat HA state ≤ 255 chars. | |

**User's choice:** Optionnel + max 40 + strip
**Notes:** Empty string post-strip → traité comme None (fallback au real name).

---

## Claude's Discretion

- Ordering des sous-steps Polling dans la voluptuous schema (toutes les clés sont sémantiquement sœurs sous "Polling")
- Tests TZ matrix sur les nouveaux flows (default single-TZ — les flows sont tz-indépendants)
- Rédaction FR des nouvelles clés i18n ajoutées au fur et à mesure ; EN par mirror ; Phase 7 fera la pass exhaustive

## Deferred Ideas

- Repair Issue avec bouton "Reauth" + lien troubleshooting — Phase 7 DIAG-03
- Diagnostics dump avec redact pour les nouvelles clés options — Phase 7 DIAG-01
- Translations exhaustives sur Phases 1-5 — Phase 7 I18N-01/I18N-02
- TZ matrix sur config flows — déféré (flows tz-indépendants)
- Hot-swap school_tz sans reload — retenu mais déféré (optimisation, pas un blocker)
- async_migrate_entry réel v1 → v2 — pas besoin Phase 6 (forward-compatible get-with-default), ajout futur si break-change
- Multi-child "Add another child" shortcut depuis une entry existante — backlog v2 (pattern actuel "re-runner Add Integration" fonctionne, juste moins découvrable)
