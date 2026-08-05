# Requirements: HA-Pronote

**Defined:** 2026-05-03
**Core Value:** L'utilisateur reçoit une notification fiable et exploitable dès qu'un cours est annulé ou modifié pour le jour même ou le lendemain.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Authentification & Configuration

- [ ] **AUTH-01**: L'utilisateur peut configurer un compte Pronote via Config Flow UI HA (URL + type compte parent/eleve + username + password)
- [ ] **AUTH-02**: Le système valide les credentials contre Pronote au moment de la configuration (no entry created if auth fails)
- [ ] **AUTH-03**: L'utilisateur peut configurer plusieurs enfants — un `ConfigEntry` HA par enfant
- [ ] **AUTH-04**: Le système persiste la session via `client.export_credentials()` et la rejoue au démarrage HA (un seul login par lifetime de l'install)
- [ ] **AUTH-05**: L'utilisateur peut se réauthentifier après changement de mot de passe via reauth flow (`async_step_reauth`, password-only)
- [ ] **AUTH-06**: L'utilisateur peut modifier URL/type de compte via reconfigure flow (`async_step_reconfigure`) sans perdre l'historique des entités
- [ ] **AUTH-07**: Le système utilise un `device_name` stable (`home-assistant-{entry_id[:8]}`) reconnaissable dans l'app Pronote pour révocation manuelle

### Coordinator & Polling

- [ ] **COORD-01**: Le système utilise HA `DataUpdateCoordinator` avec le pattern `runtime_data` (aucun usage du legacy `hass.data[DOMAIN]`)
- [ ] **COORD-02**: Tous les appels `pronotepy` sont wrappés dans `hass.async_add_executor_job` (zéro blocking call dans l'event loop)
- [ ] **COORD-03**: L'intervalle de polling est configurable via Options Flow (défaut 30 min, choix 15/30/60)
- [ ] **COORD-04**: Le polling adaptatif applique un intervalle plus court (défaut 15 min) pendant la fenêtre J+1 (défaut 17h–20h, school timezone)
- [ ] **COORD-05**: Le polling est suspendu les week-ends et pendant les vacances scolaires NC (no requests, no events)
- [ ] **COORD-06**: Aucun event n'est émis pendant les heures silencieuses (22h–6h, school timezone)
- [ ] **COORD-07**: Un circuit breaker déclenche un backoff exponentiel jusqu'à 24h sur échecs d'auth consécutifs
- [ ] **COORD-08**: Le système détecte le message littéral `Your IP address is suspended` et applique long backoff + persistent HA notification
- [ ] **COORD-09**: L'intervalle de polling intègre un jitter ±30s pour éviter les requêtes synchronisées

### Sensor — Emploi du temps

- [ ] **TIME-01**: Un sensor "Emploi du temps" par enfant — state = nombre de cours du jour OU timestamp du prochain cours
- [ ] **TIME-02**: Le sensor expose les attributs J et J+1 (matière, prof, salle, heure début/fin, statut [maintenu/annulé/modifié])
- [ ] **TIME-03**: Le sensor respecte les contraintes HA — state ≤255 chars, attributs ≤16 KiB (CI assertion sur fixture classe lourde)
- [ ] **TIME-04**: Toutes les datetimes des attributs sont timezone-aware (`school_tz` configurable, défaut `Pacific/Noumea`)

### Sensor — Notes

- [ ] **GRADE-01**: Un sensor "Notes" par enfant — state = moyenne générale numérique (virgule → point, `state_class=measurement`)
- [ ] **GRADE-02**: Le sensor expose les N dernières notes en attributs (matière, note, sur, coefficient, date) au format documenté ApexCharts
- [ ] **GRADE-03**: Le sensor respecte les contraintes HA — state ≤255 chars, attributs ≤16 KiB

### Sensor — Notifications/Informations

- [ ] **NOTIF-01**: Un sensor "Notifications" par enfant — state = nombre d'informations non lues
- [ ] **NOTIF-02**: Le sensor expose en attributs les N dernières informations (titre, expéditeur, date, extrait du contenu)

### Calendar Entity

- [ ] **CAL-01**: Une entité Calendar par enfant exposant les lessons sur fenêtre J–7 → J+14
- [ ] **CAL-02**: Les events Calendar incluent matière, salle, professeur, statut (cours annulé visuellement distinct)

### Bus Events

- [ ] **EVENT-01**: Le système émet `pronote_schedule_changed` lors d'un diff EDT pour J ou J+1 (payload: `child_id`, `change_type` [canceled/modified/teacher/room], `day` [today/tomorrow], `lesson_before`, `lesson_after`)
- [ ] **EVENT-02**: Le système émet `pronote_new_grade` quand une nouvelle note apparaît (payload: `child_id`, `subject`, `grade`, `on`, `coefficient`, `date`)
- [ ] **EVENT-03**: Le système émet `pronote_new_information` quand une nouvelle information est publiée (payload: `child_id`, `sender`, `title`, `date`, `excerpt`)
- [ ] **EVENT-04**: Aucun event n'est émis au premier poll après redémarrage (`previous is None` — pas de flood "new")
- [ ] **EVENT-05**: La diff layer distingue identité de lesson (date+start+subject) du contenu (canceled, room, teacher) pour produire un `change_type` non ambigu

### Entities & Identity

- [ ] **ENT-01**: Le système crée un Device HA par enfant avec `DeviceInfo(manufacturer="Pronote", model=<niveau de classe>)`
- [ ] **ENT-02**: Toutes les entités utilisent `unique_id = f"pronote_{child_identifier}_{sensor_kind}"` — format figé v1, jamais altéré par le nickname
- [ ] **ENT-03**: Toutes les entités utilisent `has_entity_name = True` + `_attr_translation_key` (HA modern naming)
- [ ] **ENT-04**: Le système expose `async_migrate_entry` (skeleton vide v1) pour gérer les changements de schéma futurs sans perte d'entités

### Diagnostics & Repair Issues

- [ ] **DIAG-01**: Le système expose `async_get_config_entry_diagnostics` avec `async_redact_data` pour password, uuid, token, URL d'établissement
- [ ] **DIAG-02**: Le système crée une Repair Issue actionable sur détection de ban IP (titre, description, lien FAQ)
- [ ] **DIAG-03**: Le système crée une Repair Issue sur auth fail répétée (suggère le reauth flow)

### Options Flow

- [ ] **OPT-01**: L'utilisateur peut modifier `refresh_interval` depuis Options Flow (sans recréer l'entry)
- [ ] **OPT-02**: L'utilisateur peut activer/désactiver le polling adaptatif 17h–20h
- [ ] **OPT-03**: L'utilisateur peut renommer un enfant (nickname optionnel)
- [ ] **OPT-04**: Le coordinator se recharge automatiquement quand les options changent (`add_update_listener`)

### Translations

- [ ] **I18N-01**: Le système fournit `strings.json` + `translations/fr.json` complets (config flow, options flow, errors, sensor names, repair issues)
- [ ] **I18N-02**: Le système fournit `translations/en.json` complet (fallback HA anglais)

### Distribution & Quality

- [ ] **DIST-01**: Le repo est conforme HACS custom repository (`manifest.json` + `hacs.json` + `info.md`)
- [ ] **DIST-02**: `manifest.json` déclare `iot_class: cloud_polling`, `quality_scale: bronze`, dépendances Python explicites
- [ ] **DIST-03**: GitHub Actions CI exécute hassfest + hacs/action + ruff + pyright + pytest sur chaque PR
- [ ] **DIST-04**: GitHub Actions exécute quotidiennement les tests contre `pronotepy@main` (détection régression upstream)
- [ ] **DIST-05**: Tests pytest unitaires + intégration mockée sur `api/`, `diff/`, `coordinator` (>90% coverage diff layer)
- [ ] **DIST-06**: Test matrix sur timezones `Europe/Paris` ET `Pacific/Noumea`
- [ ] **DIST-07**: README.md documente install HACS, config UI, schéma attributs ApexCharts, exemples automation YAML, rationale du polling conservateur
- [ ] **DIST-08**: Project tooling = `uv` (deps + venv) + `ruff` (lint+format) + `pyright` (typing) + pre-commit hooks
- [ ] **DIST-09**: Release workflow auto-zip `custom_components/ha_pronote/` à chaque tag semver

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Devoirs

- **HW-01**: Sensor "Devoirs" par enfant (state = nombre de devoirs pour J+1)
- **HW-02**: Event `pronote_new_homework` lors d'un nouveau devoir
- **HW-03**: Attributs structurés permettant filtre par matière, deadline

### ENT (Espace Numérique de Travail)

- **ENT-V2-01**: Auth via Educonnect
- **ENT-V2-02**: Auth via ATEN
- **ENT-V2-03**: Auth via ENT générique (Mon Bureau Numérique, Hauts-de-France, etc.)

### Distribution

- **DIST-V2-01**: Soumission au HACS default repository (qualité Silver+ atteinte)

### Quality Scale

- **QUAL-V2-01**: Atteindre HA Quality Scale Silver complète
- **QUAL-V2-02**: Atteindre HA Quality Scale Gold (test coverage 95%+, integration tests complets)

### Misc

- **MISC-V2-01**: QR-code authentication (utile si ENT force ce mode)
- **MISC-V2-02**: Sensors par matière (per-subject averages)
- **MISC-V2-03**: Logbook integration pour les schedule-change events

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Modification des données Pronote | Lecture seule — l'API tierce n'est pas faite pour l'écriture, risque de ban IP élevé |
| Gestion absences/retards complexes | Exclus du MVP par décision EDB pour limiter la surface ; pas critique pour parent monitoring |
| Application mobile dédiée | HA fournit déjà l'app mobile et les notifications push |
| Lovelace card bundlée | README documente ApexCharts/Mushroom YAML examples ; pas de carte custom maintenue côté projet |
| Sensors par période (T1/T2/T3) | Anti-pattern (entity explosion) ; service `pronote.get_period_data(period_id)` en v1.x si demandé |
| Menus de cantine | Niche ; non aligné avec Core Value |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 3 | Pending |
| AUTH-02 | Phase 3 | Pending |
| AUTH-03 | Phase 6 | Pending |
| AUTH-04 | Phase 3 | Pending |
| AUTH-05 | Phase 6 | Pending |
| AUTH-06 | Phase 6 | Pending |
| AUTH-07 | Phase 3 | Pending |
| COORD-01 | Phase 3 | Pending |
| COORD-02 | Phase 3 | Pending |
| COORD-03 | Phase 6 | Pending |
| COORD-04 | Phase 5 | Pending |
| COORD-05 | Phase 5 | Pending |
| COORD-06 | Phase 5 | Pending |
| COORD-07 | Phase 5 | Pending |
| COORD-08 | Phase 5 | Pending |
| COORD-09 | Phase 5 | Pending |
| TIME-01 | Phase 3 | Pending |
| TIME-02 | Phase 4 | Pending |
| TIME-03 | Phase 4 | Pending |
| TIME-04 | Phase 2 | Implemented |
| GRADE-01 | Phase 4 | Pending |
| GRADE-02 | Phase 4 | Pending |
| GRADE-03 | Phase 4 | Pending |
| NOTIF-01 | Phase 4 | Pending |
| NOTIF-02 | Phase 4 | Pending |
| CAL-01 | Phase 4 | Pending |
| CAL-02 | Phase 4 | Pending |
| EVENT-01 | Phase 4 | Pending |
| EVENT-02 | Phase 4 | Pending |
| EVENT-03 | Phase 4 | Pending |
| EVENT-04 | Phase 4 | Pending |
| EVENT-05 | Phase 2 | Partial (diff layer shipped + 6 anon real fixtures; empirical T0/T1 lessons-diff deferred to Phase 4 per S-04) |
| ENT-01 | Phase 4 | Pending |
| ENT-02 | Phase 3 | Pending |
| ENT-03 | Phase 3 | Pending |
| ENT-04 | Phase 3 | Pending |
| DIAG-01 | Phase 7 | Pending |
| DIAG-02 | Phase 7 | Pending |
| DIAG-03 | Phase 7 | Pending |
| OPT-01 | Phase 6 | Pending |
| OPT-02 | Phase 6 | Pending |
| OPT-03 | Phase 6 | Pending |
| OPT-04 | Phase 6 | Pending |
| I18N-01 | Phase 7 | Pending |
| I18N-02 | Phase 7 | Pending |
| DIST-01 | Phase 1 | Implemented |
| DIST-02 | Phase 1 | Implemented |
| DIST-03 | Phase 1 | Partial (CI shipped; branch protection deferred until push) |
| DIST-04 | Phase 7 | Pending |
| DIST-05 | Phase 2 | Implemented |
| DIST-06 | Phase 5 | Pending |
| DIST-07 | Phase 7 | Pending |
| DIST-08 | Phase 1 | Implemented |
| DIST-09 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 54 total
- Mapped to phases: 54
- Unmapped: 0

**Per-Phase Counts:**
- Phase 1 (Foundations): 4 (DIST-01, DIST-02, DIST-03, DIST-08)
- Phase 2 (API & Diff): 3 (TIME-04, EVENT-05, DIST-05)
- Phase 3 (Coordinator + First Sensor): 10 (AUTH-01, AUTH-02, AUTH-04, AUTH-07, COORD-01, COORD-02, TIME-01, ENT-02, ENT-03, ENT-04)
- Phase 4 (Diff, Events & Full Sensor Suite): 14 (TIME-02, TIME-03, GRADE-01, GRADE-02, GRADE-03, NOTIF-01, NOTIF-02, CAL-01, CAL-02, EVENT-01, EVENT-02, EVENT-03, EVENT-04, ENT-01)
- Phase 5 (Politesse): 7 (COORD-04, COORD-05, COORD-06, COORD-07, COORD-08, COORD-09, DIST-06)
- Phase 6 (Auth Lifecycle & Options): 8 (AUTH-03, AUTH-05, AUTH-06, COORD-03, OPT-01, OPT-02, OPT-03, OPT-04)
- Phase 7 (Quality, Diagnostics & Distribution): 8 (DIAG-01, DIAG-02, DIAG-03, I18N-01, I18N-02, DIST-04, DIST-07, DIST-09)

---
*Requirements defined: 2026-05-03*
*Last updated: 2026-05-03 — traceability filled by roadmapper (54/54 mapped, 7 phases)*
