# Plan 04-04 Summary — Phase 4 Constants + DeviceInfo.model

**Completed:** 2026-05-24
**Wave:** 2
**Requirements:** ENT-01
**Status:** complete

## What shipped

### Task 1 — `const.py` Phase 4 constants
- `PLATFORMS = (Platform.SENSOR, Platform.CALENDAR)` — extends Phase 3's tuple per D-10 so `async_forward_entry_setups` picks up the new calendar platform automatically (no `__init__.py` change needed).
- Event-type constants (D-13, verbatim REQUIREMENTS strings):
  - `EVENT_SCHEDULE_CHANGED = "pronote_schedule_changed"` (EVENT-01)
  - `EVENT_NEW_GRADE = "pronote_new_grade"` (EVENT-02)
  - `EVENT_NEW_INFORMATION = "pronote_new_information"` (EVENT-03)
- `CLASS_LEVEL_ATTR = "class_name"` (D-19, ENT-01) — probe-locked at STEP 11 of `PHASE-4-PROBE-NOTES.md`.
- `NOTIFICATIONS_WINDOW = 20` (D-05) — cap on informations list in sensor attrs (Plan 04-05 will consume).
- `GRADE_COMMENT_MAX_LEN = 200` (D-04) — comment truncation at sensor render (Plan 04-05 will consume).
- **Verification test** in `tests/test_init.py`: `test_phase4_const_values` asserts each constant by exact value/identity, locking the contract.

Commit: const.py + test_init.py atomically.

### Task 2 — `entity.py` DeviceInfo.model
- `PronoteEntity.device_info` now adds the `model` field (`<class level>` per ROADMAP SC#2 and D-19).
- **ParentClient-aware sourcing** (probe-derived, see Wave 1 SUMMARY 04-03):
  ```python
  client = self._entry.runtime_data.client
  if isinstance(client, pronotepy.ParentClient):
      child_index = self._entry.runtime_data.child_index
      if child_index is not None:
          info_obj = client.children[child_index]
      else:
          info_obj = client.info  # corrupted-entry fallback
  else:
      info_obj = client.info
  class_label = getattr(info_obj, CLASS_LEVEL_ATTR, None) or None  # "" → None
  ```
- Empty string `""` → `model=None` → HA hides the Model row in the device panel (acceptable degradation per D-19 "no silent absence" — explicit visible default, not a swallowing catch).

**Tests added in `tests/test_sensor.py`:**
- `test_device_info_model_set_from_class_name` — eleve account, `client.info.class_name = "3ème A"` → `model == "3ème A"`
- `test_device_info_model_none_when_class_name_empty` — empty string → `model=None`
- `test_device_info_model_for_parent_client` — ParentClient, `client.children[child_index].class_name = "504"` → `model == "504"` (validates the NC author's account works correctly)

**`tests/conftest.py`** mock gets `client.info.class_name = "3ème A"` so existing fixtures continue to work without surprises.

**Existing test deviation:** `test_sensor_class_attributes_lock_d15_d16` no longer asserts the absence of `_attr_extra_state_attributes` because Plan 04-05 will introduce TIME-02 attrs on the lessons sensor. The pre-Phase-4 assertion was Phase 3's lock; Plan 04-05 takes ownership.

## Files modified

- `custom_components/ha_pronote/const.py` — 7 const additions, PLATFORMS extended (+21 lines, -1 line)
- `custom_components/ha_pronote/entity.py` — DeviceInfo.model branching (+36 lines, -7 lines)
- `tests/conftest.py` — mock `client.info.class_name = "3ème A"` (+1 line)
- `tests/test_init.py` — `test_phase4_const_values` (+20 lines)
- `tests/test_sensor.py` — 3 DeviceInfo.model tests + adjust Phase 3 lock test (+139 lines, -3 lines)

## Self-Check

- [x] PLATFORMS includes Platform.CALENDAR
- [x] All 3 event constants present + assertable by grep
- [x] CLASS_LEVEL_ATTR / NOTIFICATIONS_WINDOW / GRADE_COMMENT_MAX_LEN added
- [x] entity.py DeviceInfo.model handles ParentClient + Client cases
- [x] Empty class_name → model=None
- [x] 3 model tests in test_sensor.py
- [x] No modifications to STATE.md, ROADMAP.md
- [x] Probe-derived constraint (parent vs child class source) implemented faithfully
- [x] No silent exception handling — `getattr(obj, attr, default)` is explicit visible default

**Done.**
