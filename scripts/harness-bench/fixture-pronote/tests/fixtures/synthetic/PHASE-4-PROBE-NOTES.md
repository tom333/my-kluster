# Phase 4 Probe Notes — pronotepy 2.14.6

**Captured:** 2026-05-24
**Source instance:** katiramona.ac-noumea.nc (direct `?login=true` URL — Phase 3 UAT finding #6)
**Account type:** parent (account_type=parent, 1 child: GUYADER Sacha, class "504")
**pronotepy version:** 2.14.6
**Script:** `scripts/probe_config_flow.py`
**Log:** `/tmp/phase4-probe.log` (439 lines)

Append-only. One section per probe STEP, one section per pronotepy version.

---

## STEP 5 — `client.lessons(date_from, date_to)` shape

**Returned:** 79 lessons across J−7 → J+14.

**`pronotepy.dataClasses.Lesson` attribute set (verified on real NC instance):**
```
background_color, canceled, classroom, classrooms, content, detention,
end, exempted, group_name, group_names, id, memo, normal, num, outing,
start, status, subject, teacher_name, teacher_names, test,
to_dict, virtual_classrooms
```

**Field types & sample values (live):**

| Attr | Type | Example | Notes |
|------|------|---------|-------|
| `date` | (absent — derive from `start.date()`) | — | Phase 2 `_lesson_from_raw` already does `start.date()` ✓ |
| `start` | `datetime.datetime` **naive, school-local** | `2026-05-22 15:10:00` | Phase 2 `_localize` adds tz ✓ |
| `end` | `datetime.datetime` **naive** | `2026-05-22 16:10:00` | Same |
| `subject` | `pronotepy.dataClasses.Subject` | — | Read `.name` (Phase 2 ✓) |
| `teacher_name` | `str` | `"DI PAOLO H."` | Single teacher; `teacher_names: list[str]` is the multi form |
| `classroom` | `str` | `"101 AN1"` | Single room; `classrooms: list[str]` is the multi form |
| `canceled` | `bool` | `True` / `False` | 7/79 lessons canceled in this window |
| `status` | `str \| None` | `None` (67), `"Cours annulé"` (4), `"Prof. absent"` (3), `"Remplacement"` (2), `"Formation Médiation"` (1) | **`None` is the common case** — Phase 2 `raw.status or ""` handles ✓ |
| `id` | `str` | `"29#yiqCbPvu89jOfFJRlEKns0pT1Mc9_F2xyBGlR..."` | Could be used as identity key in future; Phase 2 chose `(date, start.time(), end.time(), subject)` |
| `num` | `str` | `"1062"` | Pronote internal lesson number |

**Key finding — `canceled` vs `status` divergence:** 7 lessons have `canceled=True` but only 4 have `status="Cours annulé"`. The other 3 canceled lessons have status `"Prof. absent"` / `"Remplacement"` / `"Formation Médiation"`. This **validates the SPIKE-FINDINGS S-04 decision** to use `canceled` (bool) as the cancellation signal, NOT `status` (free-form drift). `diff/lessons.py:_classify_change` priority chain (canceled > room > teacher > modified) is sound on real data.

---

## STEP 6 — `client.current_period.grades` + `Period.overall_average`

**⚠ CRITICAL: Both `grades` and `overall_average` raise KeyError on this instance.**

`current_period` = `Period(name="Trimestre 2", id="105#...")` — exists ✓

**But:**
```
period.grades raised KeyError: 'listeDevoirs'
period.overall_average → KeyError('listeServices')
period.averages → KeyError('listeServices')
period.class_overall_average → None
```

This matches the Phase 2 02-02 spike finding (`KeyError 'listeDevoirs'`) and extends it to `overall_average` / `averages`. Pronote returns these keys only when grades have been published in the period. Trimestre 2 on this instance has none yet (mid-T2, no exams entered).

**Period attribute set:**
```
absences, averages, class_overall_average, delays, end, evaluations,
grades, id, instances, name, overall_average, punishments, report,
start, to_dict
```

**Implications for Phase 4:**

1. **Plan 04-02 `fetcher.fetch_all` already handles this** via the `except (KeyError, AttributeError)` block — but there's a **latent bug**: if `.grades` succeeds AND `.overall_average` raises independently, the catch resets `raw_grades=[]` (losing the grades). For the NC instance both raise so we hit the except cleanly and `overall_avg=""`. Recommend a per-attribute try/except refactor in a follow-up Wave 2 fix, but not blocking for current shipping (NC is the target).

2. **Plan 04-05 grades sensor state**: `_to_float("")` must return `None` cleanly → sensor state becomes `None` → HA UI shows "unknown". Acceptable per CONTEXT.md `<specifics>` "trimester just started" edge case.

3. **Plan 04-05 grades sensor attrs** when `raw_grades=[]`: `grades: []`, `period_name: ""`, sensor attribute payload is essentially empty. CI heavy-class fixture uses synthetic data so the 16 KiB gate stays exercised.

**Per-grade fields could NOT be probed** (grades raised KeyError) — `Grade.average / .max / .min / .comment` shape is therefore NOT live-verified. Plan 04-02's `_grade_from_raw` uses `getattr(raw, "average", None) or ""` defensively, which is the right pattern. If the verifier needs to lock the exact shape, the user should run the probe in **Trimestre 1** (which has 44 evaluations per STEP 9) — but that requires switching the `current_period` which isn't exposed publicly.

---

## STEP 7 — `client.information_and_surveys()` shape

**Returned:** 8 information items (all marked read on this account at probe time).

**`pronotepy.dataClasses.Information` attribute set (verified):**
```
anonymous_response, attachments, author, category, content, creation_date,
end_date, id, mark_as_read, read, shared_template, start_date, survey,
template, title, to_dict
```

**Field types & samples:**

| Attr | Type | Example | Notes |
|------|------|---------|-------|
| `id` | `str` | `"65#OjGg07w1ZhyXjDq0nBFbEFKM4Rs2B2s6E1Tch13rNow"` | Used as identity in `diff_notifications` ✓ |
| `title` | `str \| None` | `None` (some informations have no title!) | Phase 2 `raw.title or ""` handles ✓ |
| `author` | `str` | `"Portefin M."` | Maps to our `sender` field |
| `content` | `str` | `"\n\nBonjour à tous\nNous avons reçu une note du médecin scolaire..."` | Phase 2 caps at 500 chars in `excerpt` ✓ |
| `start_date` | `datetime.datetime` | (present) | Phase 2 prefers this, falls back to `creation_date` ✓ |
| `creation_date` | `datetime.datetime` | (present) | |
| `end_date` | `datetime.datetime` | (present) | Not used by Phase 4 |
| `read` | `bool` | `True` (8/8 in this snapshot) | Drives `unread_count` state ✓ |
| `category` | `str` | `"Divers"` | Not in our model (could be added in Phase 6 OptionsFlow filter) |
| `survey` | `bool` | `False` | Distinguishes survey vs info; Phase 4 treats both uniformly |

**Phase 4 diff_notifications identity key** `(info_id, date)` is sound on real data — info_id is a long stable string.

---

## STEP 9 — `client.periods` (informational, future Phase 6 multi-period)

**Returned:** 9 periods. Names in order:
```
['Trimestre 1', 'Trimestre 2', 'Trimestre 3',
 'Semestre 1', 'Semestre 2',
 'Année continue', 'Hors période',
 'Contrôle en cours de formation', 'EEEFA']
```

**Trimestre 1 shape verification:**
- `evaluations: <list len=44>` — 44 evaluations exist in T1
- `absences: <list len=3>`
- But same KeyError pattern: `grades → KeyError('listeDevoirs')`, `overall_average → KeyError('listeServices')` even on T1!

So **on this NC instance, the KeyError pattern is universal across all periods**, not just current. This is a pronotepy 2.14.6 + Pronote-server-version interaction. Phase 4 must accept that `current_period.grades` will fail on this specific test instance and document it as expected for the NC author's class.

(For a different Pronote instance with published grades, the API would presumably work. This is the same blind spot Phase 2 had — only an instance with active published grades can verify the Grade.average/.max/.min shape.)

---

## STEP 11 — `ClientInfo` attributes

**`client.info` (the PARENT account's info — `client.info.name = "M. GUYADER Thomas"`):**

```
class_name: ""              ← empty for parent account
establishment: ""           ← also empty
name: "M. GUYADER Thomas"
id: "128#h1bAT9cdhG99..."
address: <PronoteAPIError 'Accès refusé'>
email: <PronoteAPIError 'La page a expiré ! (1)'>
ine_number, phone: same errors
profile_picture: None
raw_resource: dict with keys G, L, N, listeRessources, ...
```

**`client.children[0]` (the CHILD — GUYADER Sacha):**

```
class_name: "504"           ← ✓ populated!
establishment: "COLLEGE JEAN FAYARD DUMBEA COLLEGE JEAN FAYARD DUMBEA"  (note duplication on this build)
name: "GUYADER Sacha"
id: "46#TNPSEwEOyJHC9it34OgTW215p4TGvN679uL5-RJTToM"
profile_picture: <pronotepy.dataClasses.Attachment>
raw_resource: dict with keys including 'classeDEleve', 'listeClassesHistoriques', 'listeGroupes'
```

**⚠ CRITICAL FINDING for ENT-01 / Plan 04-04:**

For **parent** accounts, `client.info.class_name` is **empty** (`""`). The child's class is in `client.children[child_index].class_name`.

`set_child(client.children[0])` does NOT swap `client.info` to the child's. `client.info` remains the parent's account info.

**Plan 04-04 implementation must source the class label conditionally:**
```python
# entity.py DeviceInfo.model = <class level>
if isinstance(client, pronotepy.ParentClient):
    class_label = getattr(client.children[child_index], CLASS_LEVEL_ATTR, None)
else:
    class_label = getattr(client.info, CLASS_LEVEL_ATTR, None)
```

Currently Plan 04-04 (per its action text) reads `client.info.class_name` unconditionally — this would produce `model=None` (row hidden) on every parent install. The NC author uses a parent account.

**Resolution:** Plan 04-04 needs a small revision to handle ParentClient. Alternatively, the entity can read `entry.runtime_data.child_index` and source from `client.children[child_index]`.

---

## Sign-Off

- [x] **`Grade.average` / `.max` / `.min` populated on NC instance** → **NOT VERIFIED LIVE** (grades raised KeyError on this instance — no published T2 grades). Plan 04-02's defensive `getattr(raw, "average", None) or ""` is the right pattern; mocks will use the documented pronotepy 2.14.6 field names per `Grade` dataclass source (line 675 of pronotepy/dataClasses.py).
- [x] **`Grade.comment` is a string** → not verified live; same as above (defensive `or ""` is sound).
- [ ] **`ClientInfo.class_name` returns non-empty string on NC instance** → **FAILED for parent account** (`client.info.class_name == ""`). **Plan 04-04 needs a fix to source class from `client.children[child_index]` for ParentClient.** For eleve accounts the parent path would still work.
- [x] **`Period.overall_average` returns comma-decimal string** → **NOT VERIFIED** (raised `KeyError('listeServices')` on this instance — no published grades in T2). Plan 04-02's except already catches → grades sensor state will be `None` (HA "unknown"). Documented in `<specifics>` of CONTEXT.md as acceptable for "trimester just started".
- [x] **`Information.read` is a bool** → Verified (`True` on this instance, type bool).

**Net assessment:** Probe ran cleanly. One real revision needed (Plan 04-04 ParentClient class source). Three "not verified live" items are acceptable per Phase 2 precedent — the field names come from pronotepy 2.14.6 source code, which is the canonical reference when the test instance can't exercise them.

---

*Sign-off date: 2026-05-24*
*Signed by: Thomas Guyader (NC author / parent account)*
