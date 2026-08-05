# Phase 6: Auth Lifecycle & Options - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Lifecycle complet d'une `ConfigEntry` HA-Pronote :

1. **Reauth flow (AUTH-05)** — un changement de mot de passe Pronote ne brique plus l'entry ; l'utilisateur récupère son intégration en un click via le formulaire reauth déclenché par `ConfigEntryAuthFailed`.
2. **Reconfigure flow (AUTH-06)** — l'utilisateur peut éditer URL ou type de compte (parent/eleve) sans perdre l'historique des entités ; le `unique_id` figé par Phase 3 D-05 reste préservé.
3. **OptionsFlow (COORD-03 + OPT-01..04)** — un formulaire `async_step_init` à 2 étapes ("Polling" + "Affichage") qui expose les 10 leviers utilisateur, lit ses defaults depuis `const.py`, déclenche un reload du coordinator à chaque sauvegarde via `entry.add_update_listener`.
4. **Multi-child (AUTH-03)** — déjà résolu par le pattern Phase 3 D-05 (une `ConfigEntry` par enfant, créée en re-runner "Add Integration" avec un `child_index` différent) ; Phase 6 vérifie que ça fonctionne en présence du nouveau wiring options/reload.

**Out of scope** (déferré explicitement) :
- Repair Issue avec bouton "Reauth" (Phase 7 DIAG-03)
- Diagnostics dump redactée (Phase 7 DIAG-01)
- Migration `entry.version` ≥ 2 (skeleton vide v1 — D-26 Phase 3 ; sera invoqué si une vraie évolution de schéma intervient en v2)
- HUMAN-UAT live sur un compte Pronote réel (Phase 7 release)
- Test matrix `Europe/Paris` × `Pacific/Noumea` sur les flows config — DIST-06 est déjà couvert par Phase 5, Phase 6 réutilise sans nouveaux markers

**Hérité (Phase 3/5) :**
- AUTH-04 (session export) — Phase 3 D-06 déjà actif ; Phase 6 le préserve, ne le modifie pas
- AUTH-07 (device_name `home-assistant-{entry_id[:8]}`) — stable across reauth (entry_id immuable)
- Surveillance breaker + persistent notifications (Phase 5 D-10..D-15) — Phase 6 ne touche pas le runtime

</domain>

<decisions>
## Implementation Decisions

### Reauth flow (AUTH-05)
- **D-01:** Le formulaire `async_step_reauth_confirm` expose **deux champs** : `password` + `username`. URL et `account_type` sont lus depuis `entry.data` et jamais demandés. Rationale : un parent qui change d'identifiant Pronote ne doit pas avoir à supprimer + recréer l'entry. Coût marginal : un champ texte supplémentaire et une assertion dans le test que `entry.data["username"]` est bien mis à jour.
- **D-02:** Après reauth réussi, **clear `entry.data["session"]`** dans le `async_update_entry(data={...sans session...})`. La prochaine `async_setup_entry` appellera `build_or_resume_client(session=None)` qui tombera direct sur le fresh-login branch — pas de tentative de `token_login` avec une session orphan. Garantie de cohérence post-rotation password.
- **D-03:** **Réutiliser le `device_name` existant** `f"home-assistant-{entry.entry_id[:8]}"`. L'`entry_id` est stable across reauth (HA n'en émet pas de nouveau), donc Pronote voit le même device dans son interface "Appareils autorisés" — pas de device fantôme, contrat AUTH-07 préservé.
- **D-04:** **Trigger natif `ConfigEntryAuthFailed`** — aucune plomberie nouvelle de déclenchement. `__init__.py:async_setup_entry` et `coordinator._recover_from_auth_error` lèvent déjà cette exception ; HA crée automatiquement la "notification reauth" en haut de la sidebar. Repair Issue + bouton "Reauth" sont **explicitement déférés à Phase 7 DIAG-03**.

### Reconfigure flow (AUTH-06)
- **D-05:** Le formulaire `async_step_reconfigure` expose **uniquement URL + account_type**. `username` reste figé (s'il change, l'utilisateur passe par reauth flow D-01) ; `password` reste figé (idem). Justification : la frontière reauth/reconfigure doit rester nette pour la review HA quality scale et pour les tests (les deux flows ont des assertions distinctes sur ce qui change dans `entry.data`).
- **D-06:** **Abort si `child_identifier` résolu via la nouvelle URL diffère** de `entry.data["child_identifier"]`. Implémentation : après re-validation des nouveaux credentials (D-07), re-fetch des `client.children` et résolution du même `child_identifier` (cf. Phase 3 D-15 — `ClientInfo.id` est le canonical identifier). Si différent → `async_abort(reason="child_identifier_changed")` avec message i18n expliquant que l'utilisateur doit supprimer l'entrée et recréer. Préserve `unique_id` figé (ENT-02) + historique Recorder intact.
- **D-07:** **Re-validation systématique** via `build_or_resume_client(new_url, new_account_type, entry.data["username"], entry.data["password"], session=None, device_name=existing_device_name)` AVANT `async_update_entry`. Si auth échoue → erreur dans le form (`"invalid_auth"` / `"cannot_connect"` / `"ip_suspended"` via le même mapping que `async_step_user`) ; **aucune modification de `entry.data` persistée**. Si auth OK → on commit. Single-seam préservé (C-02 Phase 3).
- **D-08:** **Clear `entry.data["session"]` uniquement si URL OU account_type a changé**. La session pronotepy est liée à l'établissement ET au type de compte (côté serveur Pronote). La rejouer après un changement d'URL plante côté pronotepy. Si reconfigure ne fait que normaliser (espaces / casing), keep la session. Comparaison stricte string-equal après strip.

### OptionsFlow (COORD-03 + OPT-01..04)
- **D-09:** **Surface complète** = **10 clés** exposées dans l'OptionsFlow :
  - **8 clés héritées Phase 5** (déjà lues par `_resolve_options` avec defaults const.py) : `refresh_interval`, `afternoon_interval`, `afternoon_window_start`, `afternoon_window_end`, `quiet_hours_start`, `quiet_hours_end`, `suspended_cadence`, `quiet_cadence`
  - **2 nouvelles clés** : `nickname` (OPT-03, str | None), `school_tz` (OPT-04 / hint D-23 Phase 5 — IANA tz string, default `"Pacific/Noumea"`)
  - **1 toggle dérivé** : `adaptive_polling_enabled` (OPT-02 ; bool, default True). Quand False, `compute_interval` renvoie `refresh_interval` sans branchifier (politesse.py reçoit ce flag via `PolitesseOptions.adaptive_enabled` — petit ajout dataclass).
  - Total **11 entrées** dans le schema voluptuous (le toggle compte).
- **D-10:** **Multi-step layout** :
  - **Step 1 "Polling"** (`async_step_polling`) : `refresh_interval`, `adaptive_polling_enabled` (toggle), `afternoon_interval`, `afternoon_window_start`, `afternoon_window_end`, `suspended_cadence`, `quiet_cadence`, `quiet_hours_start`, `quiet_hours_end`
  - **Step 2 "Affichage"** (`async_step_display`) : `nickname`, `school_tz`
  - `async_step_init` redirige vers `async_step_polling` (pas d'écran de menu) ; le bouton "Submit" du step 1 transite vers step 2 ; le step 2 commit toutes les options via `async_create_entry(title="", data={**step1, **step2})`.
- **D-11:** **Defaults lus depuis const.py via `_options_schema_defaults(entry: ConfigEntry) -> dict`**, un helper qui produit les voluptuous defaults à partir des mêmes `DEFAULT_*` constants que `coordinator._resolve_options`. Single source of truth — l'UI ne peut pas drifter de la lecture runtime. Tests : un test d'invariant assert que pour chaque clé Phase 5, `_options_schema_defaults({}) == _resolve_options(empty_entry).asdict()` (modulo le typing minutes int ↔ timedelta).
- **D-12:** **Reload-on-options-change naïf** :
  ```python
  entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
  async def _async_reload_entry(hass, entry): await hass.config_entries.async_reload(entry.entry_id)
  ```
  Wired dans `__init__.py:async_setup_entry` à côté du `entry.runtime_data = ...`. ~1s overhead à chaque sauvegarde options, négligeable. Nickname propage automatiquement vers `DeviceInfo.name` au reload.

### Nickname (OPT-03)
- **D-13:** Le nickname **affecte `DeviceInfo.name`** (donc le label du Device HA + via `has_entity_name=True` ENT-03, le headline de tous les sensors associés). `unique_id` et `entity_id` restent intacts (ENT-02 figé). Une seule clef à muter, propagation automatique.
- **D-14:** **Fallback : `entry.options.get("nickname") or entry.data["child_name"]`**. `entry.data["child_name"]` existe depuis Phase 3 D-08 — pas de re-fetch Pronote nécessaire. Comportement identique à aujourd'hui (Phase 4 `entity.py`) tant que l'utilisateur ne renseigne pas OPT-03.
- **D-15:** **Mise à jour de `entry.title`** dans `_async_reload_entry` : si `entry.options.get("nickname")` ≠ None ET ≠ `entry.title`, appeler `hass.config_entries.async_update_entry(entry, title=nickname)`. L'UI "Devices & Services" affiche `"HA-Pronote (Petit Louïc)"` au lieu de `"HA-Pronote (LOUÏC DUPONT)"`. Cohérence visuelle.
- **D-16:** **Validation voluptuous** : `vol.Optional("nickname", default=""): vol.All(cv.string, vol.Length(max=40), vol.Strip)`. Empty string après strip → traité comme `None` dans `_resolve_options` (`(entry.options.get("nickname") or "").strip() or None`). Pas de regex sur le contenu — emojis OK, 40 chars suffisants pour des prénoms d'animation longs sans risquer la limite 255 chars sur les sensors `state`.

### Multi-child interaction (AUTH-03)
- **D-17:** **Aucun nouveau code requis** — le pattern Phase 3 D-05 (`unique_id = f"{url_host}:{username}:{child_identifier}"` + `_abort_if_unique_id_configured()`) permet déjà la création d'une `ConfigEntry` par enfant via re-execution de `async_step_user` avec sélection d'un `child_index` différent. Phase 6 ne touche pas à cette mécanique ; un test Phase 6 vérifie que deux entries multi-child cohabitent avec des options indépendantes (`_async_reload_entry` opère bien sur le bon `entry.entry_id`).

### Claude's Discretion
- **Tests TZ matrix sur les flows** — DIST-06 (matrix Europe/Paris × Pacific/Noumea) est déjà ON sur les tests politesse + coordinator depuis Phase 5. Les nouveaux tests config_flow (reauth, reconfigure, OptionsFlow) n'ajoutent pas de marker TZ — ces flows sont tz-indépendants (pas de `dt_util.now()` dans la décision-tree). Claude code les tests en single-TZ (default `Pacific/Noumea`).
- **Ordering des sous-steps Polling** — l'ordre des champs dans la voluptuous schema de step 1 reste à Claude (toutes les clés sont sémantiquement sœurs sous "Polling"). Suggestion: refresh_interval en premier (le levier le plus utilisé), suivi du toggle adaptive_polling_enabled, puis afternoon_window_*, puis suspended_cadence, puis quiet_*. Mais c'est de la cosmétique.
- **Translations i18n** — `strings.json` et `translations/{en,fr}.json` doivent gagner les nouvelles clés (`config.step.reauth_confirm.*`, `config.step.reconfigure.*`, `options.step.polling.*`, `options.step.display.*`, `options.error.invalid_auth`, etc.). Phase 7 I18N-01/I18N-02 fait la pass complète ; Phase 6 ajoute les clés au fur et à mesure (en + fr) pour que les flows soient utilisables. Claude rédige les FR ; EN par mirror.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### ROADMAP & Requirements
- `.planning/ROADMAP.md` §"Phase 6: Auth Lifecycle & Options" — 4 success criteria, dépend de Phase 5
- `.planning/REQUIREMENTS.md` — 8 reqs Phase 6 (AUTH-03, AUTH-05, AUTH-06, COORD-03, OPT-01, OPT-02, OPT-03, OPT-04)
- `.planning/PROJECT.md` — Core Value (notification J/J+1 fiable), constraint "lecture seule" qui s'applique aussi à l'absence d'écriture options vers Pronote

### Prior phase decisions (carry-forward, NE PAS re-discuter)
- `.planning/phases/03-coordinator-first-sensor/03-CONTEXT.md`
  - **D-05** — `unique_id = f"{url_host}:{username}:{child_identifier}"` (figé, jamais altéré par le nickname OPT-03)
  - **D-06** — `client.export_credentials()` après chaque poll réussi (AUTH-04 actif ; Phase 6 ne touche pas, mais reauth clear `entry.data["session"]` D-02 pour forcer un nouveau cycle)
  - **D-07** — strategy session-first dans `async_setup_entry` ; D-02 Phase 6 clear session = direct fresh login path
  - **D-08** — `entry.data` keys (url, account_type, username, password, session, child_identifier, child_index, child_name) — Phase 6 reauth update `password`, `username`, clear `session` ; reconfigure update `url`, `account_type`, clear `session` conditionnel
  - **D-09** — `_recover_from_auth_error` silent recovery branch (Phase 3) lève `ConfigEntryAuthFailed` en fin de chaîne — c'est le trigger D-04 Phase 6
  - **D-15** — `child_identifier` derivation rule (ClientInfo.id ou child_index fallback) — Phase 6 reconfigure D-06 réutilise cette même règle
  - **C-02** — `api/client.py:build_or_resume_client` single seam — Phase 6 reauth (D-04) et reconfigure (D-07) y branchent sans duplication
  - **D-26** — `async_migrate_entry` skeleton vide (v1) ; Phase 6 ne crée pas de migration (entry.version reste 1)

- `.planning/phases/05-politesse-adaptive-polling-quiet-hours-circuit-breaker/05-CONTEXT.md`
  - **D-17** — `entry.options` shape locked (8 clés). Phase 6 expose ces 8 + 3 nouvelles (D-09 Phase 6)
  - **D-23** — school_tz hint default `Pacific/Noumea` ; Phase 6 wire le per-entry override via OptionsFlow
  - **D-24** — `DEFAULT_REFRESH_INTERVAL = timedelta(minutes=30)` — Phase 6 default de l'option `refresh_interval`
  - **Phase 5 → Phase 6 interface** section — Phase 5 a shippé le runtime read path ; Phase 6 ne fait que le UI + reload listener

### Existing integration code (Phase 6 surface)
- `custom_components/ha_pronote/config_flow.py` — actuel : `async_step_user` + `async_step_pick_child` + `_create_entry`. Phase 6 ajoute `async_step_reauth` + `async_step_reauth_confirm`, `async_step_reconfigure`, `async_get_options_flow` (staticmethod) + classe `HaPronoteOptionsFlow(OptionsFlow)`.
- `custom_components/ha_pronote/api/client.py:build_or_resume_client` — single seam (Phase 3 C-02) ; Phase 6 reauth + reconfigure y branchent direct
- `custom_components/ha_pronote/__init__.py:async_setup_entry` — Phase 6 ajoute `entry.async_on_unload(entry.add_update_listener(_async_reload_entry))` (D-12)
- `custom_components/ha_pronote/coordinator.py:_resolve_options` — read path déjà actif (Phase 5) ; Phase 6 étend `PolitesseOptions` pour `adaptive_enabled` (D-09 Phase 6) + lit `nickname` / `school_tz` depuis `entry.options`
- `custom_components/ha_pronote/entity.py` — `DeviceInfo.name` actuel = `entry.data["child_name"]` ; Phase 6 fait `entry.options.get("nickname") or entry.data["child_name"]` (D-14)
- `custom_components/ha_pronote/const.py` — Phase 6 ajoute `DEFAULT_SCHOOL_TZ` const (déjà présent l'idée en Phase 5 const.py, à vérifier), `NICKNAME_MAX_LEN = 40`

### Translations / i18n
- `custom_components/ha_pronote/strings.json` — ajout des clés Phase 6
- `custom_components/ha_pronote/translations/en.json` et `fr.json` — mirror
- Phase 7 I18N-01/I18N-02 fera la pass exhaustive ; Phase 6 ajoute les clés au fil de l'eau

### Tests
- `tests/test_config_flow.py` — actuel : user step + pick_child step + error mapping. Phase 6 ajoute test_reauth_flow_*, test_reconfigure_flow_*, test_options_flow_*
- `tests/conftest.py` — `mock_persistent_notification` (Phase 5) restera ; pas de nouvelle fixture autouse phase 6 (les flows sont synchrones côté UI)
- `tests/test_coordinator.py` — un nouveau test `test_options_change_triggers_reload` qui assert `hass.config_entries.async_reload.called` après `async_update_entry(options=...)`
- Tests DIST-06 (TZ matrix) — pas étendus aux nouveaux flows (justification : flows tz-indépendants)

### External docs (HA dev — pour pattern reference)
- https://developers.home-assistant.io/docs/config_entries_config_flow_handler — reauth + reconfigure patterns, `async_step_reauth(entry_data)`, `async_step_reauth_confirm`, `async_step_reconfigure`
- https://developers.home-assistant.io/docs/config_entries_options_flow_handler — OptionsFlow pattern, `async_get_options_flow`, multi-step OptionsFlow

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`build_or_resume_client(url, account_type, username, password, session, device_name)`** — `api/client.py`. Single seam pour fresh-login + token_login. Reauth (D-04) et reconfigure (D-07) l'appellent verbatim. Aucun fork de logique d'auth.
- **`set_active_child(client, child_index)`** — `api/client.py`. Reconfigure (D-06) le réutilise pour re-fetch le child_identifier post-validation.
- **`_create_entry(child_index)` interne à `HaPronoteConfigFlow`** — actuellement utilisé par user step + pick_child. Phase 6 reconfigure ne le réutilise pas (il crée une entry au lieu de la modifier) ; mais la sequence "validate + resolve child + commit" est le pattern à mimer.
- **`PolitesseOptions` dataclass** (`politesse.py`) — frozen, options snapshot. Phase 6 ajoute `adaptive_enabled: bool = True` field ; `compute_interval` lit ce flag et bypass la branche afternoon si False.
- **`_resolve_options(entry)`** (`coordinator.py`) — fallback-aware reader avec `(ValueError, TypeError)` catch + warning log (jamais bare except). Phase 6 extend pour `nickname` + `school_tz` + `adaptive_enabled`.

### Established Patterns
- **`hass.async_add_executor_job(...)`** — toute interaction pronotepy (auth, set_child) est wrappée. Reauth + reconfigure suivent.
- **`raise ConfigEntryAuthFailed / ConfigEntryNotReady`** — typed exceptions, jamais swallowed (`feedback_no_silent_exceptions.md`). Reauth/reconfigure surface les erreurs via les keys voluptuous d'`errors={}` du form, JAMAIS via `try/except: pass`.
- **`async_set_unique_id` + `_abort_if_unique_id_configured()`** dans config_flow — pattern AUTH-03 actif pour empêcher la duplication d'entries pour le même enfant.
- **`schema = vol.Schema({...})`** — voluptuous + `cv.string` / `vol.All(int, vol.Range(min=...))` / `cv.time_period_dict`. Phase 6 utilise les mêmes validators avec en plus `vol.Strip` pour le nickname (D-16).
- **i18n keys live in `strings.json`** — `config.step.user.data.url`, `config.error.invalid_auth`, etc. Pattern dotted-path. Phase 6 ajoute `config.step.reauth_confirm.*`, `config.step.reconfigure.*`, `options.step.polling.*`, `options.step.display.*`.
- **`@callback` pour `async_get_options_flow`** — HA exige `@staticmethod` + `@callback` decorator. Pattern HA standard.

### Integration Points
- **`config_flow.py:async_step_reauth(entry_data)`** — HA appelle automatiquement ce step quand `ConfigEntryAuthFailed` est levée et qu'aucun flow reauth n'est déjà en cours. Phase 6 implémente le step puis redirige vers `async_step_reauth_confirm` qui montre le form D-01.
- **`config_flow.py:async_step_reconfigure(entry_data)`** — HA expose le bouton "Reconfigure" dans le menu kebab d'une entrée existante quand ce step existe.
- **`__init__.py:async_setup_entry` ↔ `_async_reload_entry`** — `entry.async_on_unload(entry.add_update_listener(...))` enregistre le listener au setup ; HA appelle automatiquement le listener quand `async_update_entry(options=...)` est invoqué depuis l'OptionsFlow.
- **`entity.py:_attr_device_info` ↔ `entry.options["nickname"]`** — au reload (D-12), `PronoteEntity.__init__` recalcule `DeviceInfo.name` avec le nickname courant. Pas de mutation post-construction nécessaire.
- **`coordinator.py:_resolve_options` ↔ `entry.options["adaptive_polling_enabled"]`** — read path déjà actif (Phase 5 pattern) ; Phase 6 ajoute le booléen sans changer la mécanique fallback.

</code_context>

<specifics>
## Specific Ideas

- **Nickname strip + empty-to-None**: l'utilisateur peut saisir `"   "` ou `""` dans le champ et s'attendre à "pas de nickname". Le code traite empty string post-strip comme `None` (D-16) — c'est l'idée explicitement validée pendant la discussion.
- **child_identifier_changed = abort, pas migration**: l'utilisateur valide qu'un parent qui change d'établissement (rare) doit supprimer + recréer son entry. Préserve l'historique Recorder pour les entries non-impactées. Anti-pattern : tentative de migration auto-magique. Le message d'erreur i18n explicite l'opération attendue.
- **Reauth = password + username (pas just password)**: explicitement choisi pour offrir une porte de sortie quand le parent change d'identifiant Pronote. C'est plus large que la lecture stricte d'AUTH-05 ("password-only") mais reste sémantiquement "reauth" (pas reconfigure).
- **OptionsFlow surface = 10+1 clés dès v1, pas progressif sur les versions**: l'utilisateur valide qu'il préfère exposer tous les leviers en une fois plutôt que les ajouter par minor releases successives. Coût: formulaire plus dense, plus de combinaisons à tester. Bénéfice: pas de "tu peux pas régler X depuis l'UI" frustrant pour les early adopters HACS.

</specifics>

<deferred>
## Deferred Ideas

- **Repair Issue avec bouton "Reauth" + lien troubleshooting** — Phase 7 DIAG-03. Phase 5 a déjà mis en place `TROUBLESHOOTING_DOC_URL_BASE` ; Phase 7 fait sauter le `<placeholder-owner>` et crée le Repair Issue qui consomme le trigger D-04 Phase 6.
- **Diagnostics dump avec redact pour les nouvelles clés options** — Phase 7 DIAG-01. La redact list devra couvrir `password` + `session` + `username` + `url` (déjà prévu Phase 3 D-08) ; le nickname et school_tz sont safe à dump tel quel.
- **Translations exhaustives** — Phase 7 I18N-01/I18N-02 fera la pass complète sur toutes les clés. Phase 6 ajoute les clés Phase 6 au fil de l'eau (en + fr) mais ne re-traduit pas Phase 1-5.
- **TZ matrix tests sur les config flows** — décidé hors scope car les flows sont tz-indépendants ; si une régression future introduit un `dt_util.now()` dans un step, la matrix sera étendue à ce moment-là.
- **Hot-swap `school_tz` sans reload** — le reload naïf D-12 suffit (1s d'overhead). Optimisation diff-aware retenue mais déférée (pas un blocker, et complique la testabilité).
- **`async_migrate_entry` v1 → v2 quand le schema entry.options évolue** — pas besoin pour Phase 6 (on ajoute des clés, mais `entry.options.get(KEY, DEFAULT)` est forward-compatible). Si Phase 7+ introduit un break-change (rename de clé, type change), un `async_migrate_entry` réel sera ajouté à ce moment-là, en utilisant le skeleton ENT-04 déjà en place.
- **Multi-child "Add another child" shortcut depuis une entry existante** — `gsd-explore` matter. Le pattern actuel "re-runner Add Integration" fonctionne, juste moins découvrable. Backlog v2.

</deferred>

---

*Phase: 06-Auth Lifecycle & Options*
*Context gathered: 2026-05-25*
