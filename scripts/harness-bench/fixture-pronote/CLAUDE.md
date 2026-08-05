# HA-Pronote — Intégration Home Assistant pour Pronote

## Project

Composant personnalisé Home Assistant qui intègre Pronote pour exposer notes, emploi du temps et notifications scolaires sous forme d'entités HA (sensors). Il permet aux familles de centraliser le suivi scolaire dans leur tableau de bord domotique et de déclencher des automatisations (alertes changement d'EDT, nouvelles notes, nouvelles informations). Distribué via HACS en custom repository.

**Core Value:** L'utilisateur reçoit une notification fiable et exploitable dès qu'un cours est annulé ou modifié pour le jour même ou le lendemain. C'est l'usage qui justifie l'existence du projet — le reste (notes, notifs) en découle.

### Constraints

- **Tech stack** : Python 3.14.2+ (HA 2026.3+ enforces `REQUIRED_PYTHON_VER=(3,14,2)`), `uv` pour deps + venv, dépendance principale `pronotepy==2.14.6` (sync only, wrappée derrière `async_add_executor_job`), architecture `DataUpdateCoordinator`
- **Distribution** : Format `custom_components/ha_pronote/` conforme HACS (manifest.json, hacs.json)
- **Politesse polling** : Intervalle paramétrable (défaut 30 min, choix 15/30/60), surveillance accrue 17h–20h pour le lendemain — éviter bannissement IP du serveur école
- **Lecture seule** : Aucune écriture vers Pronote (sécurité + risque ban)
- **Qualité** : Couverture tests complète (PHACC `pytest-homeassistant-custom-component` 0.13.x), CI GitHub Actions
- **Sécurité credentials** : Identifiants Pronote stockés via mécanisme HA standard, jamais en clair dans les logs

## Workflows

This project follows the **superpowers** convention. Active backlog lives in [`BACKLOG.md`](./BACKLOG.md); historical phase artifacts (Phases 1–6) are archived under [`docs/history/planning/`](./docs/history/planning/).

For non-trivial work, invoke the relevant superpowers skill:

| Task | Skill |
|------|-------|
| Creative work / new features / changes to behavior | `superpowers:brainstorming` (explore intent + requirements first) |
| Bug / test failure / unexpected behavior | `superpowers:systematic-debugging` (root cause before patch) |
| Multi-step task with a spec | `superpowers:writing-plans` → `superpowers:executing-plans` |
| TDD-flavoured implementation | `superpowers:test-driven-development` |
| About to claim "done" / merge / PR | `superpowers:verification-before-completion` |
| Need an isolated workspace | `superpowers:using-git-worktrees` |
| Receiving code review feedback | `superpowers:receiving-code-review` |

Library / framework / SDK questions: fetch current docs via Context7 (`resolve-library-id` → `query-docs`) before answering — training data may be stale.

For surgical 1–2 file edits, use the `caveman:cavecrew-builder` agent. For diff/branch review, use `caveman:cavecrew-reviewer`. For read-only code location, use `caveman:cavecrew-investigator` or `Explore`.

## Engineering Conventions

- **No silent exceptions on runtime/setup paths** — let typed exceptions (`ConfigEntryAuthFailed`, `ConfigEntryNotReady`, `ZoneInfoNotFoundError`, pronotepy's `AuthError`/`RateLimitedError`/`CommunicationError`/`PronoteIntegrationError`) propagate raw. HA's stock 500 + traceback beats a polite mapped form error for debugging.
- **Config-flow form errors are the deliberate scoped exception** — `async_step_user`, `async_step_reauth_confirm`, `async_step_reconfigure`, and OptionsFlow steps map typed exceptions to `errors["base"]` keys via the `_map_error()` helper in `config_flow.py`. This is required by HA quality scale `config-flow` rule.
- **All pronotepy calls wrapped** in `await self.hass.async_add_executor_job(partial(...))`. Never call pronotepy directly from `async def`.
- **Single auth seam**: `api/client.py:build_or_resume_client` (Phase 3 C-02). All flows (initial setup, reauth, reconfigure, silent recovery) go through it.
- **`unique_id` is frozen** at entry creation: `f"{url_host.lower()}:{username}:{child_identifier}"`. `async_step_reconfigure` does NOT mutate it — entity history (Recorder, energy stats, automations) depends on stability.
- **Reauth/reconfigure commits use `async_update_reload_and_abort(entry, data_updates={...})`** (MERGE) — never `data=` (would replace and lose `child_*`/`url`/`account_type`).
- **OptionsFlow inherits from `OptionsFlowWithReload`** — never `OptionsFlow` + `entry.add_update_listener` (deprecated 2026-05-07, error 2026.6, removed 2026.12). `OptionsFlowWithReload.__init__` takes NO `config_entry` arg; HA injects it as a read-only property since 2025.12.
- **No `vol.Strip`** — doesn't exist in voluptuous, raises `AttributeError` at import. Use `lambda v: v.strip()` inside `vol.All(...)`.
- **Three permanent CI guards** in `tests/test_init.py` lock the three classes of "integration breaks at import" — do not skip or `noqa` these.
- **Formatting** delegated to `ruff format` + `ruff check --fix`. Type checking via `pyright`. Pre-commit hooks via `prek`. Never hand-format. Never bare `except:`.
- **TZ matrix** (`Europe/Paris` × `Pacific/Noumea`) — both must pass for any test touching `dt_util.now()`.

## Technology Stack (quick reference)

| Component | Pin | Purpose |
|-----------|-----|---------|
| Python | `>=3.14.2` | HA 2026.3+ enforces (`REQUIRED_PYTHON_VER`) |
| Home Assistant | `>=2026.4.x` (declared in `hacs.json`) | Host platform |
| `pronotepy` | `==2.14.6` | Pronote API (sync only — maintainer in maintenance mode; pinned exact to absorb breakage) |
| `python-slugify` | `==8.0.4` | Child name slugify (matches HA Core's pin) |
| `pytest-homeassistant-custom-component` | `==0.13.326` | Test harness (auto-tracks HA Core daily) |
| `homeassistant` (test-only) | `==2026.4.4` | Run tests against real HA |
| `ruff` | `==0.15.1` | Lint + format (target-version `py314`) |
| `pyright` | latest via npm | Type checking |
| `uv` | `>=0.9.3` | Package manager + venv |

CI uses `home-assistant/actions/hassfest@master` + `hacs/action@main` (pinned by SHA — both repos have stale tags).

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Direct pronotepy calls from `async def` | `requests`-based; HA logs "Detected blocking call" | `hass.async_add_executor_job(...)` |
| `async_timeout` | Banned-API in HA ruff config | `asyncio.timeout()` stdlib |
| `pytz` | Banned-API; deprecated | `zoneinfo.ZoneInfo("Pacific/Noumea")` |
| `requests` directly | Same blocking issue as pronotepy | Stick to pronotepy; if needed, `aiohttp` via `homeassistant.helpers.aiohttp_client.async_get_clientsession(hass)` |
| `black` + `flake8` + `isort` | Replaced by `ruff` in HA Core 2024+ | `ruff format` + `ruff check` |
| `entry.add_update_listener` | Deprecated 2026-05-07 (error 2026.6) | `OptionsFlowWithReload` subclass |
| `vol.Strip` | Doesn't exist in voluptuous | `lambda v: v.strip()` inside `vol.All` |
| `self.config_entry = config_entry` in OptionsFlow | Removed HA 2025.12 — raises `AttributeError` | Drop the arg; HA injects as read-only property |
| `async_set_unique_id` / `_abort_if_unique_id_mismatch` in `async_step_reconfigure` | Mutates / aborts on host change → orphans entity history | Explicit `child_identifier` comparison (D-06 guard) |
| Hard-coding the author's school URL | ConfigFlow must accept any URL — HACS quality + reuse | `TextSelector(URL)` form field |
| `ENT` modules from `pronotepy.ent` | Out of scope; bloats bundle | Direct `pronotepy.Client(...)` / `Client.token_login(...)` |
| `aiohttp.ClientSession()` you create | Leaks sessions | `homeassistant.helpers.aiohttp_client.async_get_clientsession(hass)` |

## Reference

- **Backlog (active work):** [`BACKLOG.md`](./BACKLOG.md)
- **Historical phase artifacts (CONTEXT/RESEARCH/PLAN/SUMMARY/VERIFICATION/LEARNINGS per phase):** [`docs/history/planning/`](./docs/history/planning/)
- **Phase 6 LEARNINGS** (most recent — auth lifecycle gotchas, OptionsFlowWithReload migration, no-silent-exceptions scope clarification): [`docs/history/planning/phases/06-auth-lifecycle-options/06-LEARNINGS.md`](./docs/history/planning/phases/06-auth-lifecycle-options/06-LEARNINGS.md)
