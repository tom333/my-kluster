---
phase: 06
phase_name: "auth-lifecycle-options"
project: "HA-Pronote"
generated: "2026-05-30"
counts:
  decisions: 8
  lessons: 6
  patterns: 7
  surprises: 5
missing_artifacts: []
---

# Phase 6 Learnings: Auth Lifecycle & Options

## Decisions

### Re-introduce D-04 typed-exception → form-error mapping in config_flow
Exit the Phase 3 DEBUG MODE. `async_step_user` + `_create_entry` map `AuthError → invalid_auth`, `RateLimitedError → ip_suspended`, `CommunicationError → cannot_connect`, `PronoteIntegrationError → unknown`. A `_map_error()` helper de-duplicates the mapping.

**Rationale:** Phase 6 reauth/reconfigure plans assume `async_step_user` already maps errors. HA quality scale `config-flow` rule requires graceful error handling. The `feedback_no_silent_exceptions.md` memory still holds for runtime/setup paths — config flow form errors are a deliberate scoped exception (user typing credentials needs labeled form error, not 500).
**Source:** baseline-fix commit e4d60b5 + memory update feedback_no_silent_exceptions.md

### OptionsFlowWithReload supersedes entry.add_update_listener (D-12 REVISED)
`HaPronoteOptionsFlow(OptionsFlowWithReload)`. No `entry.async_on_unload(entry.add_update_listener(...))` wiring in `__init__.py`.

**Rationale:** HA deprecated the listener-together-with-reload pattern on 2026-05-07 (error in 2026.6, removed in 2026.12). `OptionsFlowWithReload` triggers `async_unload_entry` + `async_setup_entry` automatically on `async_create_entry`.
**Source:** 06-05-PLAN.md + 06-RESEARCH.md Critical Gotcha #1

### lambda v: v.strip() replaces non-existent vol.Strip (D-16 REVISED)
Nickname voluptuous schema: `vol.All(cv.string, vol.Length(max=NICKNAME_MAX_LEN), lambda v: v.strip())`.

**Rationale:** `vol.Strip` doesn't exist in voluptuous — using it raises `AttributeError` at module import, taking down the integration before HA can show a form.
**Source:** 06-05-PLAN.md + 06-RESEARCH.md Critical Gotcha #2

### OptionsFlow.__init__ takes NO config_entry arg
`def __init__(self) -> None:` — no parameter, no `self.config_entry = config_entry`. HA injects `self.config_entry` as a read-only property.

**Rationale:** Deprecated HA 2024.12, removed HA 2025.12. Assignment raises `AttributeError` at flow start.
**Source:** 06-05-PLAN.md + 06-RESEARCH.md Critical Gotcha #3

### unique_id is FROZEN across reconfigure (SC#4)
`async_step_reconfigure` does NOT call `async_set_unique_id` or `_abort_if_unique_id_mismatch`. Only the explicit `if new_child_identifier != entry.data["child_identifier"]: return self.async_abort(reason="child_identifier_changed")` guards against wrong-child resolution.

**Rationale:** ROADMAP SC#4 requires URL changes to preserve entity history. Entity history (Recorder, energy stats, automations) is keyed on `unique_id`. Calling the unique-id helpers would abort on any host change because `unique_id` embeds `url_host`. Sacrificing the rare collision protection (the OTHER entry on the same install) preserves entity history for THIS entry.
**Source:** 06-04-PLAN.md (objective) + iter-2 plan-checker B-1 resolution

### Reauth commits via async_update_reload_and_abort(data_updates=...) — MERGE, not replace
`return self.async_update_reload_and_abort(entry, data_updates={"username": new, "password": new, "session": None})`.

**Rationale:** `data=` would replace the entire dict, losing `url`, `account_type`, `child_identifier`, `child_name`, `child_index`. `data_updates=` merges. Pitfall #6 in RESEARCH.md.
**Source:** 06-03-PLAN.md + RESEARCH.md Pitfall #6

### ZoneInfoNotFoundError propagates raw on setup (memory rule preserved)
`__init__.py:async_setup_entry`: `school_tz = ZoneInfo(school_tz_name)` — no try/except. Entry enters `SETUP_ERROR` with full traceback. The OptionsFlow display step validates the same value inside the flow (where mapping IS wanted).

**Rationale:** School_tz drift is user-config corruption, not transient infra. `ConfigEntryNotReady` would retry-loop. Raw propagation matches the memory rule for runtime/setup paths.
**Source:** 06-02-PLAN.md must_haves + memory feedback_no_silent_exceptions.md

### Single source of truth: _options_schema_defaults vs coordinator._resolve_options
A module-level helper `_options_schema_defaults(entry)` returns the 11-key default dict. The form's `add_suggested_values_to_schema` reads it; `coordinator._resolve_options` reads the same `entry.options.get(...)` paths from the same `const.DEFAULT_*` symbols. An invariant test asserts agreement.

**Rationale:** Drift between the form's defaults and the runtime read would silently break "what you see is what runs."
**Source:** 06-05-PLAN.md D-11 + test_options_defaults_match_resolve_options

---

## Lessons

### The "discuss-phase + plan-phase" snapshot can assume code state that isn't true
CONTEXT.md D-07 + D-01 said reauth/reconfigure reuse "the same mapping as async_step_user" — but the production `async_step_user` was in DEBUG MODE with NO mapping. Plan 06-03 + 06-04 would have implemented a non-functional mapping (the helper they reused didn't exist).

**Context:** Caught at Wave 1 boundary by running the FULL suite and finding 14 pre-existing baseline failures (10 in test_config_flow.py related to error mapping). Without the post-merge gate, Phase 6's reauth/reconfigure plans would have shipped on top of a broken assumption.
**Source:** baseline-fix commit e4d60b5 + memory update

### Memory rules need scope boundaries
`feedback_no_silent_exceptions.md` was originally written during Phase 3 UAT as "let typed exceptions propagate raw" — broad scope. Phase 6 discuss-phase committed to mapping in config flows, contradicting the broad reading. Resolution: scope the memory to runtime/setup paths only; config-flow form errors are deliberately scoped exception.

**Context:** The memory was correctly written but lacked a scope clause. Surfacing the contradiction during the baseline-fix decision was the only way to detect it. Future memory writes should include a **Scope:** line.
**Source:** baseline-fix conversation + memory update

### MagicMock auto-attrs make isinstance silently fail
`mock_parent_client_two_children = MagicMock()` — `isinstance(client, pronotepy.ParentClient)` returns False even when the mock is meant to represent a ParentClient. The flow falls through the wrong branch (eleve path), then `slugify(client.info.name)` crashes on auto-MagicMock.

**Context:** Two pre-existing config_flow tests (`test_user_step_parent_two_children_transitions_to_pick_child`, `test_user_step_pick_child_creates_entry`) had been red for months because of this exact gotcha. Fix: `client.__class__ = pronotepy.ParentClient` after construction.
**Source:** baseline-fix Group 2b

### Test mock signatures drift from production faster than expected
`test_build_or_resume_client_uses_token_login_when_session_present`'s mock `def _token_login(cls, url, **kwargs)` required positional `url` — but production was deliberately changed in Phase 3 to call `token_login(device_name=..., **session)` with `**session` providing `pronote_url` etc. The test stayed green only because every other token_login test used `*_a, **_kw`.

**Context:** A flexible mock signature (`*args, **kwargs`) is the conservative default — tight signatures break silently when production refactors. Worth standardising in conftest.
**Source:** baseline-fix Group 3

### Subagent permissions are session-dependent and unreliable
Wave 1's gsd-executor subagents had Bash. Wave 2's retry attempts both returned without Bash access, leaving file edits in place but no commits. Switched to inline execution from Wave 2 onwards.

**Context:** When subagent_type ostensibly has the same permission profile but two consecutive spawns behave differently, the safest pivot is inline execution (the main loop has the user-granted permission set). The cost is more orchestrator context burn; the benefit is determinism.
**Source:** Wave 2 retry + user decision to switch inline

### Comments inside method bodies trigger inspect.getsource regression guards
Plan 06-04 first revision wrote `# SC#4: NO async_set_unique_id, NO _abort_if_unique_id_mismatch.` inside `async_step_reconfigure` body. The same plan's `<verify>` asserted `'async_set_unique_id' not in inspect.getsource(method)` — the comment broke its own assertion.

**Context:** Iter-3 plan-checker pass caught this. Resolution: move rationale to class-level block-comment ABOVE the method (outside `inspect.getsource(method)`) AND tighten regex to call-site patterns (`self.async_set_unique_id(`) so even bare-token mentions in docstrings/narrative stay safe.
**Source:** 06-04-PLAN.md iter-3 fix + checker B-1 → N-1

---

## Patterns

### Per-phase _map_error helper for typed-exception → form-error keys
Define `_map_error(exc) -> str` at module level in `config_flow.py`. Each flow's try/except wraps the build_client/token_login call and uses `_map_error(err)` for the `errors["base"]` value. Reduces 4-arm except blocks to 1-arm, satisfies PLR0912 branch limit.

**When to use:** Any config_flow that calls a function raising the four standard typed pronote exceptions. Also reusable for the integration's runtime error mapping if/when needed.
**Source:** 06-03-PLAN.md + baseline fix commit e4d60b5

### Walk-and-grep regression guards in tests/test_init.py
Three sibling tests (`test_no_deprecated_add_update_listener_in_production`, `test_no_vol_strip_in_production`, `test_no_options_flow_init_config_entry_assignment`) each walk `custom_components/ha_pronote/*.py` and assert the forbidden pattern is absent. Skip lines starting with `#` to allow documentation that warns against the pattern.

**When to use:** Any time RESEARCH flags a "if-you-do-X-the-integration-breaks-at-import" gotcha. Cheaper than runtime detection, runs in <100ms, catches regressions on every CI run.
**Source:** 06-05-PLAN.md Task 3 (3 permanent guards)

### Class-level block comment above method body for documentation that mentions forbidden tokens
For methods that have a `inspect.getsource(method)`-based AST assertion, put the rationale OUTSIDE the function in a `# ---` block ABOVE `async def ...`. `inspect.getsource(method)` does NOT capture the surrounding comment block.

**When to use:** When CI guards check for token absence inside a method body but the method needs prose explaining WHY the tokens are absent.
**Source:** 06-04 config_flow.py:async_step_reconfigure rationale block

### `client.__class__ = pronotepy.ParentClient` for MagicMock isinstance
For test fixtures that need `isinstance(mock, SomeClass)` to return True without paying the spec-attribute restriction cost: `mock = MagicMock(); mock.__class__ = SomeClass`. Keeps full MagicMock auto-attribute behaviour for `.children`, `.info`, etc.

**When to use:** Any fixture where production branches on `isinstance(client, ParentClient)` and the eleve else-branch would mis-handle.
**Source:** baseline-fix conftest.py fix + Group 2b

### `add_suggested_values_to_schema(SCHEMA, defaults_dict)` for pre-filled forms
HA 2024.10+ helper. Pass a voluptuous schema and a dict; HA renders the form with the dict values as the visible defaults (preserving the schema's validation). Cleaner than building per-instance `vol.Optional(KEY, default=value)`.

**When to use:** Any form that pre-fills from `entry.options` or `entry.data` (reconfigure, OptionsFlow polling/display).
**Source:** 06-04 + 06-05 + RESEARCH Pattern 2 + 3

### `async_update_reload_and_abort(entry, data_updates={...})` for merge-commit-then-reload
HA 2024.10+ helper. Returns `ConfigFlowResult`, merges the dict into `entry.data`, triggers `async_unload_entry` + `async_setup_entry`. Single line handles three operations atomically.

**When to use:** Reauth + reconfigure success commits. NEVER `data=` (replace) — always `data_updates=` (merge).
**Source:** 06-03 + 06-04 + RESEARCH Pattern 1+2

### `MockConfigEntry.add_to_hass(hass)` + `async_setup(entry_id)` + `async_block_till_done` — sequentially for multi-entry tests
For tests with two entries, calling `async_setup` for entry_B after `add_to_hass(entry_B)` raises `OperationNotAllowed` because PHACC auto-loads on add. Solution: set up each entry inside its own `add_to_hass`+`async_setup`+`block_till_done` sequence, with the patches in scope.

**When to use:** Multi-child isolation tests, any time two MockConfigEntries need to coexist and exercise per-entry runtime_data.
**Source:** 06-06 multi-child tests + iter fix

---

## Surprises

### `vol.Strip` doesn't exist in voluptuous
The CONTEXT.md D-16 specified `vol.All(cv.string, vol.Length(max=40), vol.Strip)` as the nickname schema. RESEARCH flagged at iter-0 that there is no `voluptuous.Strip` attribute — it would raise `AttributeError` at module import time and the integration would fail to load. Replacement: `lambda v: v.strip()`.

**Impact:** CONTEXT.md was written by a confident developer (and confidently approved during discuss-phase), but encoded a non-existent API. The plan-checker would not have caught this without RESEARCH. The 3-Gotcha regression guards now lock all three classes of "the integration breaks at import" into CI.
**Source:** 06-RESEARCH.md Critical Gotcha #2

### Phase 5 marked "regression delta = 0" hid 14 pre-existing failures
Phase 5 completion claimed 22/22 V-IDs and "0 regressions". True locally relative to Phase 5's own scope, but the full project suite had 14 pre-existing failures (manifest URL drift, DEBUG-MODE-vs-test mismatches, MagicMock fixture drift, stale token_login mock signature, WR-09 cooldown contradiction). All went undetected for months because each phase only ran the tests it added.

**Impact:** The Wave 1 post-merge gate caught this. Worth running the FULL suite at every phase boundary going forward — not just the phase's own tests. Cost: ~13 seconds. Benefit: catches stealth regressions before they compound.
**Source:** baseline-fix discovery

### Python 3.13 silently rejects Python 3.14 syntax in production code
`except ZoneInfoNotFoundError, ValueError:` — bare tuple in except clause without parentheses — is valid Python 3.14 syntax. Python 3.13 and earlier raise `SyntaxError`. Verifier initially ran with system Python 3.13 and reported a "blocker" that disappeared once `.venv/bin/python3` (3.14.2) was used.

**Impact:** Worth noting in CLAUDE.md or pyproject.toml banner that development requires Python 3.14+. Contributors using system Python 3.13 will get confusing parse errors. The HA 2026.3+ requirement (REQUIRED_PYTHON_VER=3.14.2) already enforces this at install time, but a developer banner saves the first-tool-output confusion.
**Source:** 06-VERIFICATION.md Critical Environment Note

### OptionsFlowWithReload re-instantiates the coordinator (and you can test it by identity)
After `async_create_entry(title="", data=merged)` inside the OptionsFlow, HA tears down `runtime_data` and re-runs `async_setup_entry`. The coordinator is a fresh instance: `coord_after is not coord_before`. The test asserts identity (`is not`), not just equality.

**Impact:** Saves explicit listener wiring (Gotcha #1) AND gives a clean test signal. The reload's blast radius is wider than `entry.add_update_listener` (full unload + setup, not just a coordinator refresh) — worth keeping in mind for any cross-entity wiring (e.g. a singleton dispatcher would also reset).
**Source:** test_options_change_triggers_reload

### "Pause Phase 6 to fix baseline first" was correctly the user's call, not the agent's
The agent at Wave 1 boundary surfaced the 14 baseline failures and presented 3 options (pause-and-fix / continue with delta=0 / investigate-first). User chose pause-and-fix. Resulted in a cleaner ship (8 dimensions of stale-test root-cause analysis, surgical fixes, scoped memory update) AND prevented the Phase 6 plans from inheriting broken patterns.

**Impact:** The "surface and ask" memory rule paid off concretely here. A confident agent might have continued; the user's structural call saved a downstream debug session.
**Source:** Wave 1 boundary AskUserQuestion + baseline-fix
