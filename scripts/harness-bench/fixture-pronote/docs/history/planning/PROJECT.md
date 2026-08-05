# HA-Pronote — Intégration Home Assistant pour Pronote

## What This Is

Composant personnalisé Home Assistant qui intègre Pronote pour exposer notes, emploi du temps et notifications scolaires sous forme d'entités HA (sensors). Il permet aux familles de centraliser le suivi scolaire dans leur tableau de bord domotique et de déclencher des automatisations (alertes changement d'EDT, nouvelles notes, nouvelles informations). Distribué via HACS en custom repository.

## Core Value

L'utilisateur reçoit une notification fiable et exploitable dès qu'un cours est annulé ou modifié pour le jour même ou le lendemain. C'est l'usage qui justifie l'existence du projet — le reste (notes, notifs) en découle.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

**From Phase 1 — Foundations & Skeleton (2026-05-03)**
- [x] Structure conforme HACS custom repository (manifest.json, hacs.json) — *Validated in Phase 1: 01-02 integration skeleton; D-01 frozen invariant*
- [x] CI GitHub Actions (lint, tests, validation HACS) — *Partially validated in Phase 1: 01-04 ships lint/validate/test/release workflows SHA-pinned; branch protection on `main` deferred to first push (HUMAN-UAT #4)*
- [x] Test harness foundation (unit + integration via PHACC) — *Validated in Phase 1: 01-03 ships pytest + PHACC fixture wiring + manifest contract regression test; production tests grow per-feature in subsequent phases*

**From Phase 2 — API & Diff Layer (HA-free) (2026-05-06)**
- [x] Pure-Python `api/` subpackage (auth, fetch, snapshot, error mapping) — *Validated in Phase 2: 02-01 ships `build_client` + `fetch_all` sync facade with full pronotepy error mapping; 100% covered; zero `homeassistant.*` imports (D-19 AST guard)*
- [x] Pronote integration end-to-end proven via `scripts/snapshot.py` against the author's real instance — *Validated in Phase 2: 02-02 spike captured 6 anonymized fixture pairs; surfaced and fixed three pronotepy 2.14.6 production bugs (S-01 grades KeyError, S-02 URL `?login=true`, S-03 `information_and_surveys` is a method) before any HA wiring*
- [x] Diff layer detecting cancellation / room change / teacher swap from snapshot pairs — *Validated in Phase 2: 02-03 ships `diff/lessons.py` with the identity-vs-content key contract from SPIKE-FINDINGS-bain3-311.md; 100% line coverage; 11 synthetic fixtures cover all algorithm branches*
- [x] CI gates locking the HA-free contract: zero-HA-imports AST guard, fixture round-trip schema gate, TZ matrix (Europe/Paris × Pacific/Noumea), `--cov-fail-under=90` — *Validated in Phase 2: 02-04 wires all four gates into `.github/workflows/test.yml`; 186 tests pass + 7 expected S-04 skips in 0.74s*
- **Acknowledged carry-over (S-04):** No empirical T0/T1 lessons-diff was captured (no teacher-side access to trigger schedule changes between captures); diff layer cancel/room/teacher classification is built against pronotepy's documented `Lesson` model + synthetic fixtures. Phase 4's first user-observed real schedule change is the empirical re-validation gate.

### Active

<!-- Current scope. Building toward these. -->

**Authentification & Configuration**
- [ ] Config Flow UI HA pour ajouter un compte Pronote (URL + identifiants + type compte)
- [ ] Support multi-comptes (plusieurs enfants dans une même famille)
- [ ] Stockage sécurisé des identifiants dans le store HA
- [ ] Gestion des erreurs d'auth (mauvais mot de passe, serveur down) avec feedback clair

**Données — Emploi du temps**
- [ ] Sensor "Emploi du temps" par enfant : état = nombre de cours du jour ou prochain cours
- [ ] Attributs détaillés : matière, professeur, salle, heure début/fin, statut (maintenu/annulé/modifié) pour J et J+1

**Données — Notes**
- [ ] Sensor "Notes" par enfant : état = moyenne générale actuelle
- [ ] Attributs : liste des dernières notes (matière, note, sur, coefficient, date) au format consommable par apexcharts-card

**Données — Notifications / Informations**
- [ ] Sensor "Notifications" par enfant : état = nombre de notifs non lues
- [ ] Attributs : contenu, date, expéditeur des dernières informations établissement

**Alertes & Événements**
- [ ] Détection des changements d'EDT (annulation, modif, prof absent) entre deux polls pour J et J+1
- [ ] Émission d'événement HA (`pronote_schedule_changed`) exploitable en automatisation
- [ ] Émission d'événement HA pour nouvelle notification / nouvelle note

**Polling & Performance**
- [ ] Architecture DataUpdateCoordinator (async, non bloquant)
- [ ] Intervalle de polling paramétrable depuis l'UI (défaut 30min)
- [ ] Vérification accrue de l'EDT du lendemain en fin de journée (17h–20h)

**Qualité & Distribution**
- [ ] Tests unitaires (logique alertes, parsing, comparaison EDT)
- [ ] Tests d'intégration avec mock pronotepy
- [ ] Documentation README installation + configuration

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- **Modification des données Pronote** — Lecture seule uniquement, l'API tierce n'est pas faite pour l'écriture et le risque de ban IP est élevé
- **Devoirs (homework)** — Différé v2 pour limiter le scope MVP ; les notes + EDT + notifs couvrent déjà le cas critique parent
- **Support ENT générique** (Educonnect, ATEN, multi-ENT) — Différé v2 ; cas d'usage personnel cible Pronote direct (ac-noumea.nc) sans ENT
- **Gestion absences/retards complexes** — Exclus du MVP par décision EDB pour limiter la surface
- **Application mobile dédiée** — Home Assistant fournit déjà l'app mobile et les notifications push
- **Soumission au HACS default repository** — v2+ une fois l'intégration mature ; v1 = custom repository pour itération rapide
- **Support graphique intégré** — On expose les attributs au format apexcharts-card mais on ne fournit pas la carte custom

## Context

- **Cas d'usage personnel** : Collège Jean Fayard, Dumbéa, Nouvelle-Calédonie. Instance Pronote sur rectorat (`katiramona.ac-noumea.nc`), accès parent direct sans ENT intermédiaire
- **Domaine** : intégration Home Assistant + scraping Pronote via librairie tierce non officielle (pronotepy)
- **Existant** : delphiki/HomeAssistant-Pronote et autres intégrations existent dans HACS — décision de repartir from scratch pour bénéficier d'une architecture DataUpdateCoordinator moderne et d'une meilleure gestion des alertes (point critique)
- **Risques inhérents** : pas d'API officielle Pronote → risque de cassure à chaque mise à jour Pronote, nécessité d'un polling poli pour éviter bannissement IP du serveur école
- **Distribution** : HACS custom repository dès la v1 (objectif default repo en v2+)

## Constraints

- **Tech stack** : Python 3 (standard HA), gestion projet avec `uv`, dépendance principale `pronotepy`, architecture `DataUpdateCoordinator` (async HA)
- **Distribution** : Format `custom_components/` conforme HACS (manifest.json, hacs.json, structure standard)
- **Politesse polling** : Intervalle paramétrable (défaut 30 min, choix 15/30/60), surveillance accrue 17h–20h pour le lendemain — éviter bannissement IP du serveur école
- **Lecture seule** : Aucune écriture vers Pronote (sécurité + risque ban)
- **Compatibilité HA** : Versions récentes de Home Assistant (à figer dans `manifest.json` au début de l'implémentation)
- **Qualité** : Couverture tests complète (unitaires + intégration mockée `pronotepy`) + CI GitHub Actions dès la v1
- **Sécurité credentials** : Identifiants Pronote stockés via mécanisme de stockage HA standard, jamais en clair dans les logs

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| From scratch (pas fork de l'existant) | Architecture DataUpdateCoordinator propre dès le départ + meilleure gestion alertes EDT (point critique) | Confirmed in Phase 1 — buildable HACS-conformant skeleton shipped without forking |
| Devoirs en v2 | Réduit scope MVP, ship plus rapide ; notes + EDT + notifs couvrent le cas critique | — Pending |
| Auth Pronote directe seulement (pas ENT) en v1 | Cas d'usage personnel = `ac-noumea.nc` sans ENT ; ENT ajouterait complexité disproportionnée | — Pending |
| HACS custom repository (pas default) en v1 | Pas de friction soumission, itération rapide ; default visé v2+ | — Pending |
| Couverture tests complète + CI dès v1 | Standard qualité HACS ; pronotepy peut casser à chaque MAJ Pronote → tests = filet de sécurité régression | — Pending |
| Stack Python + `uv` | Standard HA (Python 3) ; `uv` = préférence projet pour vitesse + lock reproductibles | — Pending |
| Polling adaptatif fin de journée | Les changements d'EDT du lendemain sont publiés tard ; détection rapide = valeur principale du produit | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-06 after Phase 2 (API & Diff Layer, HA-free) completion — code-side PASSED (186 tests + 100% diff coverage), 2 operator-action items tracked in `02-HUMAN-UAT.md`, S-04 carry-over to Phase 4*
