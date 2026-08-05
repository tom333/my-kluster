---
phase: 6
slug: auth-lifecycle-options
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-25
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x via `pytest-homeassistant-custom-component==0.13.326` |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` + `tests/conftest.py` |
| **Quick run command** | `uv run pytest tests/test_config_flow.py -x -q` |
| **Full suite command** | `uv run pytest -x` |
| **Estimated runtime** | ~30 seconds (full suite ~60s after Phase 6 additions) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_config_flow.py -x -q` (or `tests/test_coordinator.py` for D-12 reload listener task)
- **After every plan wave:** Run `uv run pytest -x`
- **Before `/gsd-verify-work`:** Full suite must be green (`uv run pytest -x` exits 0)
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> Filled in by planner — each task in each PLAN.md gets a row mapping to the automated command that verifies it.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| {filled-by-planner} | {plan} | {wave} | {REQ-ID} | — | {behavior} | unit | `{command}` | ✅ / ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_config_flow.py` — new test functions for reauth (D-01..D-04), reconfigure (D-05..D-08), options multi-step (D-09..D-12), nickname (D-13..D-16), multi-child (D-17)
- [ ] `tests/test_coordinator.py` — new `test_options_change_triggers_reload` (D-12) and `test_adaptive_polling_disabled_skips_branch` (D-09 toggle)
- [ ] `tests/conftest.py` — no new autouse fixtures (per CONTEXT.md "Tests" section); reuse existing `mock_persistent_notification` (Phase 5)
- [ ] No framework install needed — `pytest-homeassistant-custom-component` already present

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Sidebar reauth notification rendering | AUTH-05 | HA renders the notification natively; only visible in a running HA instance | Trigger `ConfigEntryAuthFailed` in a dev HA, observe sidebar "Repairs" / notification |
| Devices & Services title update when nickname is set | OPT-03 / D-15 | Visual confirmation in HA frontend (Devices & Services panel) | Set nickname via OptionsFlow, refresh Devices page, confirm title changes from `LOUÏC DUPONT` to `Petit Louïc` |
| HUMAN-UAT on live Pronote account | All Phase 6 | Live Pronote rotation has unpredictable timing | Deferred to Phase 7 release (per CONTEXT.md `<deferred>`) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
