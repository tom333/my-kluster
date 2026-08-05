---
phase: 02-api-diff-layer-ha-free
plan: 02
type: execute
wave: 2
depends_on: ["02-01"]
files_modified:
  - tests/fixtures/real/cancellation_T0.json
  - tests/fixtures/real/cancellation_T1.json
  - tests/fixtures/real/room_change_T0.json
  - tests/fixtures/real/room_change_T1.json
  - tests/fixtures/real/teacher_swap_T0.json
  - tests/fixtures/real/teacher_swap_T1.json
  - tests/fixtures/SPIKE-FINDINGS-bain3-311.md
  - scripts/snapshot.py
  - .env.example
  - tests/test_scripts/test_snapshot.py
user_setup:
  - service: pronote
    why: "Real-Pronote spike requires the author's live credentials to capture the 3 fixture pairs that lock the diff/lessons.py algorithm (D-05, D-07)."
    env_vars:
      - name: PRONOTE_URL
        source: "Local-only .env file at repo root (e.g. https://katiramona.ac-noumea.nc/pronote/parent.html)"
      - name: PRONOTE_USERNAME
        source: ".env"
      - name: PRONOTE_PASSWORD
        source: ".env"
      - name: PRONOTE_ACCOUNT_TYPE
        source: ".env (eleve or parent)"
    dashboard_config:
      - task: "Trigger 3 schedule changes in the Pronote teacher portal between T0 and T1 captures: (a) cancel a lesson, (b) change one classroom, (c) swap one teacher"
        location: "Pronote web UI (teacher login required) — OR coordinate with the school office to do this on a low-stakes day. If teacher access is unavailable, fall back to capturing T0/T1 around any naturally-occurring schedule change in the next school week and re-label the scenario after the fact."
autonomous: false
requirements: [EVENT-05]
must_haves:
  truths:
    - "Three anonymized real-fixture pairs exist in tests/fixtures/real/ (cancellation, room_change, teacher_swap × T0/T1) (D-05, D-10)"
    - "Each anonymized fixture round-trips through Snapshot.from_dict cleanly (D-11) — verified by Plan 02-04's tests/test_fixtures.py"
    - "tests/fixtures/SPIKE-FINDINGS-bain3-311.md documents observed pronotepy 2.14.6 semantics for the bain3#311 bug class (D-06)"
    - "ROADMAP success criterion #2 satisfied: scripts/snapshot.py authenticated against the author's real Pronote instance and produced a valid anonymized JSON snapshot"
    - "Zero raw _raw_*.json files staged in git (gitignored, security threat T-02-02-01)"
    - "Zero PII strings (real child name, real teacher names, real classroom IDs, real school URL) appear in the committed fixture set (security threat T-02-02-02)"
  artifacts:
    - path: "tests/fixtures/real/cancellation_T0.json"
      provides: "Anonymized snapshot before a lesson cancellation"
      contains: '"school_tz"'
    - path: "tests/fixtures/real/cancellation_T1.json"
      provides: "Anonymized snapshot after the lesson cancellation"
      contains: '"canceled": true'
    - path: "tests/fixtures/real/room_change_T0.json"
      provides: "Anonymized snapshot before a classroom change"
      contains: '"school_tz"'
    - path: "tests/fixtures/real/room_change_T1.json"
      provides: "Anonymized snapshot after the classroom change"
      contains: '"classroom"'
    - path: "tests/fixtures/real/teacher_swap_T0.json"
      provides: "Anonymized snapshot before a teacher substitution"
      contains: '"school_tz"'
    - path: "tests/fixtures/real/teacher_swap_T1.json"
      provides: "Anonymized snapshot after the teacher substitution"
      contains: '"teacher"'
    - path: "tests/fixtures/SPIKE-FINDINGS-bain3-311.md"
      provides: "Empirical analysis of pronotepy 2.14.6 cancel/room/teacher semantics (D-06)"
      contains: "## Observed semantics"
  key_links:
    - from: "tests/fixtures/real/*.json"
      to: "custom_components/ha_pronote/api/models.py"
      via: "Snapshot.to_dict() shape (D-11)"
      pattern: "school_tz"
    - from: "tests/fixtures/SPIKE-FINDINGS-bain3-311.md"
      to: "custom_components/ha_pronote/diff/lessons.py (Plan 02-03)"
      via: "Source of truth for identity-vs-content key refinement (D-06, D-07, D-08)"
      pattern: "identity key|content key"
---

<objective>
Execute the real-Pronote spike (D-05, D-07) against the author's live Pronote
instance. This plan SHIPS THE EVIDENCE the diff layer (Plan 02-03) reads:
3 anonymized fixture pairs in `tests/fixtures/real/` plus the
`SPIKE-FINDINGS-bain3-311.md` analysis document.

Purpose: this plan is the hinge of Phase 2's spike-first ordering (D-05/D-07).
Without it, Plan 02-03 is writing diff/lessons.py against a hypothesis instead
of an empirical baseline. The bain3#311 cancel-vs-room-change bug class
(PITFALLS.md §"Pitfall 10") is the single highest-risk surface in Phase 2 —
this plan validates or refines the D-08 starting-hypothesis identity and
content keys.

Output: 6 anonymized JSON fixtures + 1 markdown analysis document. May ALSO
produce small refinements to `scripts/snapshot.py` (e.g. extending
`_build_replacements` with discovered teacher names, fixing a pronotepy field
accessor in `api/fetcher.py` if Plan 02-01's hypothesis is off — strictly
limited to "make the spike succeed" surgical changes).

This plan is **`autonomous: false`** because:
1. It runs against a live external service (the author's Pronote instance).
2. It requires real credentials in `.env` that only the human operator has.
3. It captures real PII that needs the anonymizer to run BEFORE `git add`.
4. It cannot be cached — pronotepy may break or rate-limit at any time.
5. It needs a checkpoint:human-action between T0 and T1 captures (the human
   triggers the schedule change in Pronote; Claude can't).
</objective>

<execution_context>
@/home/moi/projets/perso/pronote/.claude/get-shit-done/workflows/execute-plan.md
@/home/moi/projets/perso/pronote/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/phases/02-api-diff-layer-ha-free/02-CONTEXT.md
@.planning/phases/02-api-diff-layer-ha-free/02-PATTERNS.md
@.planning/research/PITFALLS.md
@.planning/research/STACK.md

# Plan 02-01 outputs that this plan uses
@custom_components/ha_pronote/api/__init__.py
@custom_components/ha_pronote/api/client.py
@custom_components/ha_pronote/api/fetcher.py
@custom_components/ha_pronote/api/models.py
@custom_components/ha_pronote/api/errors.py
@scripts/snapshot.py
@.env.example
@.gitignore

<interfaces>
<!-- The fixture file shape this plan emits is the contract Plan 02-03 reads
     and Plan 02-04 schema-validates. -->

# tests/fixtures/real/<scenario>_<phase>.json shape (D-11, mirrors Snapshot.to_dict()):
{
  "today": "YYYY-MM-DD",                          # ISO date
  "school_tz": "Pacific/Noumea",                  # IANA tz name
  "lessons": [
    {
      "date": "YYYY-MM-DD",
      "start": "YYYY-MM-DDTHH:MM:SS+11:00",       # tz-aware ISO with offset (D-23)
      "end": "YYYY-MM-DDTHH:MM:SS+11:00",
      "subject": "Mathematiques",                 # anonymized (D-12)
      "teacher": "M. Prof",                       # anonymized
      "classroom": "Salle A1",                    # anonymized
      "canceled": false,
      "status": ""                                # raw pronotepy status string
    }
  ],
  "grades": [...],                                # full Grade list (Phase 4 cares)
  "information": [...]                            # full Information list (Phase 4 cares)
}

# tests/fixtures/SPIKE-FINDINGS-bain3-311.md required sections (D-06):
# 1. Observed pronotepy 2.14.6 semantics:
#    - canceled field: bool, always present? populated only on the canceled lesson, or also on its replacement?
#    - status field: enum-like strings? exact values seen ("Cours annulé", "Changement de salle", "Prof. absent", ...)
#    - paired-vs-unpaired lessons at same datetime: does pronotepy return ONE entry with new content + canceled=False, or TWO entries (old canceled=True + new canceled=False)?
#    - teacher representation under substitution: same teacher_name with different field somewhere? Or new teacher_name and old lesson canceled?
# 2. D-08 hypothesis verdict:
#    - Identity key (date, start_time, end_time, subject) — confirmed / refined how?
#    - Content key (canceled, status, classroom, teacher_full_name) — confirmed / refined how?
# 3. Concrete diffs from each of the 3 fixture pairs (which fields actually changed between T0 and T1).
# 4. Algorithm decision: how diff/lessons.py (Plan 02-03) handles each scenario.
</interfaces>
</context>

<tasks>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 0: Human creates local .env with real Pronote credentials</name>
  <what-built>Plan 02-01 already shipped `.env.example`, `scripts/snapshot.py`, and `.gitignore` entries for `.env` and `tests/fixtures/real/_raw_*.json`. The infrastructure to run the spike is in place.</what-built>
  <how-to-verify>
    Before this task: confirm `.env.example` is committed (`git ls-files .env.example` shows it) and `.env` is gitignored (`git check-ignore -v .env` confirms ignore rule).

    Steps for the human operator:
    1. From repo root: `cp .env.example .env`
    2. Edit `.env` and replace the 4 placeholder values with real credentials:
       - `PRONOTE_URL=https://katiramona.ac-noumea.nc/pronote/<eleve|parent>.html` (the author's actual Pronote space URL)
       - `PRONOTE_USERNAME=<your real username>`
       - `PRONOTE_PASSWORD=<your real password>`
       - `PRONOTE_ACCOUNT_TYPE=<eleve or parent>` (matches the URL path)
    3. Confirm `.env` is gitignored: `git status` MUST NOT show `.env` as a tracked or staged file. Run `git check-ignore .env` — exit code 0 confirms it's ignored.
    4. Reply with `approved` to confirm the .env file exists and is correctly gitignored, OR with `blocked: <reason>` if you don't have working credentials right now (in which case Plan 02-03 will need to proceed with synthetic fixtures only and Plan 02-02 reruns later).

    SECURITY (security_gate threats T-02-02-01 + T-02-02-02): Do NOT paste the credential values into the chat or anywhere outside `.env`. The file content stays on the local filesystem and the gitignore rule prevents commits.
  </how-to-verify>
  <resume-signal>Type `approved` when .env exists with real credentials and is gitignored. Type `blocked: <reason>` if credentials are unavailable — Plan 02-03 will execute against synthetic fixtures only and this plan reruns later.</resume-signal>
</task>

<task type="auto">
  <name>Task 1: Capture T0 baseline for all 3 scenarios</name>
  <read_first>
    - .planning/phases/02-api-diff-layer-ha-free/02-CONTEXT.md §"Fixture Sourcing" (D-10..D-14)
    - scripts/snapshot.py (Plan 02-01) — confirm the CLI signature and the `_build_replacements` extension point
    - .gitignore (Plan 02-01) — confirm `_raw_*.json` and `.env` are ignored
    - tests/test_scripts/test_snapshot.py (Plan 02-01) — confirm anonymizer invariants
    - .planning/research/PITFALLS.md §"Pitfall 1" — IP suspension risk during repeated polling
  </read_first>
  <acceptance_criteria>
    - All three T0 raw and anonymized JSON files exist:
      `tests/fixtures/real/_raw_cancellation_T0.json`,
      `tests/fixtures/real/_raw_room_change_T0.json`,
      `tests/fixtures/real/_raw_teacher_swap_T0.json` (raw — gitignored)
      and `tests/fixtures/real/cancellation_T0.json`,
      `tests/fixtures/real/room_change_T0.json`,
      `tests/fixtures/real/teacher_swap_T0.json` (anonymized — staged for commit later).
    - `git status tests/fixtures/real/` shows the three anonymized files as untracked. The three `_raw_*.json` files are listed by `git status --ignored tests/fixtures/real/` but NOT by `git status` alone.
    - Each anonymized JSON file is valid JSON (`python -c "import json; json.load(open('tests/fixtures/real/cancellation_T0.json'))"` exits 0 for all three).
    - Each anonymized JSON file contains the top-level keys `today`, `school_tz`, `lessons`, `grades`, `information` (matching `Snapshot.to_dict()` shape, D-11).
    - Each anonymized JSON's `school_tz` field is a non-empty string (typically `"Pacific/Noumea"`).
    - Each anonymized JSON's `lessons` array has at least 1 lesson covering the J-7..J+14 window (D-15).
    - Every datetime string in the anonymized JSON contains an ISO offset suffix (matches regex `[+-]\\d{2}:\\d{2}$`) — proves D-23 tz-localization worked.
    - `python -c "from urllib.parse import urlparse; import json; data = json.load(open('tests/fixtures/real/cancellation_T0.json')); assert 'ac-noumea.nc' not in json.dumps(data); assert 'katiramona' not in json.dumps(data)"` exits 0 (anonymizer stripped the school URL).
  </acceptance_criteria>
  <action>
    The author needs to run `scripts/snapshot.py` against the LIVE Pronote instance THREE times (one per scenario) BEFORE making any schedule changes. The output is the "before" baseline (T0).

    **Important pre-flight check:**
    Before the first run, validate the anonymizer's PII allowlist is complete. Plan 02-01's `_build_replacements` ships with a minimal allowlist (username + URL host). The human operator MUST extend it BEFORE the first capture so the anonymized fixtures have NO PII residue. Add to `_build_replacements` in `scripts/snapshot.py` (per D-12, C-03 — explicit name list, NOT regex):

    ```python
    def _build_replacements(env: dict[str, str]) -> dict[str, str]:
        repls = {}
        if env.get("PRONOTE_USERNAME"):
            repls[env["PRONOTE_USERNAME"]] = "Eleve Test"
        if env.get("PRONOTE_URL"):
            from urllib.parse import urlparse
            host = urlparse(env["PRONOTE_URL"]).netloc
            if host:
                repls[host] = "pronote.example.fr"

        # ─── HUMAN-AUTHORED PII LIST (per spike — extend during Task 1) ───
        # Add the real values here BEFORE the first capture. These get replaced
        # everywhere they appear in the snapshot (recursive walk, D-12, C-03).
        # NOT regex — exact-match strings only.
        repls.update({
            # CHILD identity
            "<real_first_name>": "Eleve",
            "<real_last_name>": "Test",
            # ESTABLISHMENT
            "<real_establishment_name>": "Établissement Test",
            # TEACHERS (extend as the spike captures them)
            # "M. <real_teacher_name>": "M. Prof",
            # "Mme <real_teacher_name>": "Mme Profa",
            # CLASSROOMS (extend as the spike captures them)
            # "<real_classroom_id>": "Salle A1",
            # "<real_classroom_id_2>": "Salle B2",
        })
        return repls
    ```

    The placeholders `<real_first_name>` etc. MUST be replaced with the actual values BEFORE running the spike — but the placeholder strings themselves should never be committed. The simplest workflow:
    1. Edit the file locally.
    2. Run the spike.
    3. Verify the anonymized output has no PII.
    4. Reset that local edit (`git diff scripts/snapshot.py` should show ONLY the structural empty-allowlist scaffold being expanded — the actual real names get replaced by placeholders BEFORE commit).

    Alternative (cleaner — RECOMMENDED): the human operator passes PII via a NEW env var `PRONOTE_PII_REPLACEMENTS` (semicolon-separated `old1=new1;old2=new2`) and `_build_replacements` parses it. This avoids editing `scripts/snapshot.py` at all. Implement this option:

    ```python
    # In _build_replacements, after the URL/username block:
    if env.get("PRONOTE_PII_REPLACEMENTS"):
        for entry in env["PRONOTE_PII_REPLACEMENTS"].split(";"):
            entry = entry.strip()
            if not entry or "=" not in entry:
                continue
            old, _, new = entry.partition("=")
            old, new = old.strip(), new.strip()
            if old and new:
                repls[old] = new
    return repls
    ```

    Document the new env var in `.env.example` with a commented-out hint:
    ```bash
    # Optional. Semicolon-separated old=new replacements applied to spike output
    # before anonymized JSON is written. Example:
    # PRONOTE_PII_REPLACEMENTS="Alice Dupont=Eleve Test;Mme Martin=Mme Profa;Salle 102=Salle A1"
    # PRONOTE_PII_REPLACEMENTS=
    ```

    Add a small test in `tests/test_scripts/test_snapshot.py`:
    ```python
    def test_build_replacements_parses_pronote_pii_replacements_env_var():
        env = {
            "PRONOTE_URL": "https://x.example.com/pronote/eleve.html",
            "PRONOTE_USERNAME": "u",
            "PRONOTE_PII_REPLACEMENTS": "Alice Dupont=Eleve Test;Mme Martin=Mme Profa",
        }
        repls = _build_replacements(env)
        assert repls["Alice Dupont"] == "Eleve Test"
        assert repls["Mme Martin"] == "Mme Profa"
    ```

    Run the test (`pytest tests/test_scripts/test_snapshot.py -v`) and confirm green BEFORE running the live spike.

    **The three T0 captures:**

    Run each command from the repo root, ONE AT A TIME, with at least 30 seconds between commands (politesse / Pitfall 1 — IP-ban risk):

    ```bash
    python scripts/snapshot.py --scenario cancellation --phase T0
    sleep 30
    python scripts/snapshot.py --scenario room_change --phase T0
    sleep 30
    python scripts/snapshot.py --scenario teacher_swap --phase T0
    ```

    Each command should:
    - Connect to the live Pronote instance (output may take 5-30 seconds).
    - Print `wrote tests/fixtures/real/_raw_<scenario>_T0.json (gitignored) and tests/fixtures/real/<scenario>_T0.json (committable)`.
    - Exit 0.

    **If the IP gets suspended during this task:** The CLI will raise `RateLimitedError(IP_SUSPENDED)`. Stop immediately, document the timestamp in the SPIKE-FINDINGS doc, and resume after 24h. Do NOT retry in a tight loop (Pitfall 1 — that's how IPs get suspended in the first place).

    **If pronotepy raises a different unexpected error:** This is a surface-area finding. Capture the full traceback into a temporary text file (do NOT commit) and document the field-name mismatch or other discrepancy in the SPIKE-FINDINGS draft (Task 4). May require a small fix to `api/fetcher.py` field accessors — make the surgical change and rerun.

    **Inspect the three anonymized JSON files:**
    ```bash
    for f in tests/fixtures/real/cancellation_T0.json tests/fixtures/real/room_change_T0.json tests/fixtures/real/teacher_swap_T0.json; do
      echo "=== $f ==="
      python -c "import json; d = json.load(open('$f')); print(f'  lessons: {len(d[\"lessons\"])}, grades: {len(d[\"grades\"])}, information: {len(d[\"information\"])}, school_tz: {d[\"school_tz\"]}')"
    done
    ```

    **Verify no PII leaks:**
    ```bash
    # Adjust the search list to include every real-name token that should have been anonymized.
    # Replace <pii_token> with the real values you put in PRONOTE_PII_REPLACEMENTS — but DON'T
    # paste them in the chat. Run this command in your local terminal and inspect the output.
    grep -rE '<pii_token_1>|<pii_token_2>|katiramona|ac-noumea\\.nc' tests/fixtures/real/*.json
    ```
    The grep MUST return zero matches. If it returns matches, extend `PRONOTE_PII_REPLACEMENTS` and re-run the captures.
  </action>
  <verify>
    <automated>ls tests/fixtures/real/cancellation_T0.json tests/fixtures/real/room_change_T0.json tests/fixtures/real/teacher_swap_T0.json &amp;&amp; python -c "import json; [json.load(open(p)) for p in ('tests/fixtures/real/cancellation_T0.json', 'tests/fixtures/real/room_change_T0.json', 'tests/fixtures/real/teacher_swap_T0.json')]" &amp;&amp; ! grep -rE 'katiramona|ac-noumea' tests/fixtures/real/*.json</automated>
  </verify>
  <done>
    - 3 anonymized T0 fixture files exist and parse as valid JSON.
    - Each file has the 5 expected top-level keys (today, school_tz, lessons, grades, information).
    - Each file's `school_tz` is non-empty.
    - `grep -rE 'katiramona|ac-noumea' tests/fixtures/real/*.json` returns nothing.
    - 3 `_raw_*_T0.json` files exist and are gitignored (`git check-ignore tests/fixtures/real/_raw_cancellation_T0.json` exits 0).
  </done>
</task>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 2: Human triggers schedule changes in Pronote between T0 and T1</name>
  <what-built>Task 1 captured the T0 (before) baseline for all 3 scenarios.</what-built>
  <how-to-verify>
    The human operator now needs to make 3 distinct changes in the live Pronote system so that T1 captures (Task 3) show meaningful diffs:

    1. **Cancellation:** Coordinate with a teacher (or use a teacher account if available) to cancel ONE specific lesson in the J-7..J+14 window. Note the (date, start time, subject) of the canceled lesson — you'll need this to verify in Task 3.

    2. **Room change:** Change the classroom of ONE specific lesson (different lesson from #1). Same: note the identity tuple.

    3. **Teacher swap:** Mark ONE specific lesson with a substitute teacher (different lesson from #1 and #2). Same: note the identity tuple.

    **Reality check:** if you don't have teacher access OR can't coordinate this in a low-stakes way:
    - Option A (RECOMMENDED): wait for naturally-occurring schedule changes over the next 1-2 school weeks. After each natural change you observe in the Pronote app, run the corresponding T1 capture and re-label scenarios after the fact.
    - Option B (FALLBACK): capture only the scenarios you can actually trigger (e.g. only `cancellation` if that's all that happens in a given week). Plan 02-03 will use synthetic fixtures (D-10) for the missing scenarios. The SPIKE-FINDINGS doc will mark the un-captured scenarios as "covered by synthetic fixtures only — algorithm tuned to Pitfall 10 hypothesis".

    Reply with `approved: <notes about which scenarios were triggered>` to proceed. If only 1 or 2 of the 3 scenarios were triggered, list which ones.
  </how-to-verify>
  <resume-signal>Type `approved: <notes>` once schedule changes are reflected in Pronote (verify by browsing the Pronote app — the changes should be visible there before the T1 capture). Type `partial: <list which scenarios were captured>` if only some scenarios are available.</resume-signal>
</task>

<task type="auto">
  <name>Task 3: Capture T1 (after) state for all triggered scenarios</name>
  <read_first>
    - tests/fixtures/real/cancellation_T0.json (Task 1 — for diff comparison sanity check)
    - tests/fixtures/real/room_change_T0.json (Task 1)
    - tests/fixtures/real/teacher_swap_T0.json (Task 1)
    - scripts/snapshot.py (Plan 02-01 + Task 1 modifications)
  </read_first>
  <acceptance_criteria>
    - For every scenario approved in Task 2, the corresponding `tests/fixtures/real/<scenario>_T1.json` file exists.
    - Each T1 file is valid JSON and contains the 5 top-level keys (today, school_tz, lessons, grades, information).
    - For the `cancellation` scenario specifically: at least one lesson in `cancellation_T1.json[lessons]` has `canceled: true` AND that same identity tuple (date, start time, subject) was NOT canceled in `cancellation_T0.json`. (Run a small Python script to verify — see <action>.)
    - For the `room_change` scenario: at least one identity tuple (date, start time, subject) appears in BOTH T0 and T1 files with DIFFERENT `classroom` values.
    - For the `teacher_swap` scenario: at least one identity tuple appears in BOTH T0 and T1 files with DIFFERENT `teacher` values.
    - Same anonymization invariant: `! grep -rE 'katiramona|ac-noumea' tests/fixtures/real/*.json` passes.
  </acceptance_criteria>
  <action>
    Run the T1 captures for whichever scenarios were approved in Task 2:

    ```bash
    python scripts/snapshot.py --scenario cancellation --phase T1
    sleep 30
    python scripts/snapshot.py --scenario room_change --phase T1
    sleep 30
    python scripts/snapshot.py --scenario teacher_swap --phase T1
    ```

    (Skip any scenario marked as `partial:` in Task 2's resume signal.)

    After each capture, verify the diff is meaningful by comparing T0 vs T1:

    ```python
    # Save as /tmp/verify_diff.py and run with `python /tmp/verify_diff.py`.
    import json
    from pathlib import Path

    for scenario in ("cancellation", "room_change", "teacher_swap"):
        t0_path = Path(f"tests/fixtures/real/{scenario}_T0.json")
        t1_path = Path(f"tests/fixtures/real/{scenario}_T1.json")
        if not t1_path.is_file():
            print(f"{scenario}: SKIPPED (no T1 fixture)")
            continue
        t0 = json.loads(t0_path.read_text())
        t1 = json.loads(t1_path.read_text())

        # Identity-key index by (date, start, subject)
        idx0 = {(L["date"], L["start"], L["subject"]): L for L in t0["lessons"]}
        idx1 = {(L["date"], L["start"], L["subject"]): L for L in t1["lessons"]}

        print(f"\n=== {scenario} ===")
        print(f"  T0 lessons: {len(idx0)}, T1 lessons: {len(idx1)}")

        if scenario == "cancellation":
            newly_canceled = [
                k for k in idx0 if k in idx1 and idx1[k]["canceled"] and not idx0[k]["canceled"]
            ]
            print(f"  newly-canceled identities: {len(newly_canceled)}")
            assert newly_canceled, f"{scenario}: no lesson newly canceled between T0 and T1"

        if scenario == "room_change":
            room_changes = [
                k for k in idx0 & idx1.keys()
                if idx0[k]["classroom"] != idx1[k]["classroom"]
            ]
            print(f"  classroom changes: {len(room_changes)}")
            assert room_changes, f"{scenario}: no classroom change between T0 and T1"

        if scenario == "teacher_swap":
            teacher_changes = [
                k for k in idx0 & idx1.keys()
                if idx0[k]["teacher"] != idx1[k]["teacher"]
            ]
            print(f"  teacher changes: {len(teacher_changes)}")
            assert teacher_changes, f"{scenario}: no teacher change between T0 and T1"
    ```

    If a scenario fails its assertion (e.g. cancellation_T1 doesn't actually have a canceled lesson because the change wasn't applied yet, or pronotepy returned a paired lesson with `canceled=False` instead — bain3#311 territory), document this in Task 4's SPIKE-FINDINGS doc and decide whether to retry or accept the empirical reality. The bain3#311 finding IS the goal: we want to know whether pronotepy 2.14.6 returns the canceled lesson at all, or just replaces it with the changed lesson.

    **Anonymization sanity check (final):**
    ```bash
    grep -rE 'katiramona|ac-noumea' tests/fixtures/real/*.json
    ```
    Must return nothing. If it does, fix `_build_replacements` and re-run.
  </action>
  <verify>
    <automated>python -c "
import json
from pathlib import Path
results = []
for scenario in ('cancellation', 'room_change', 'teacher_swap'):
    p = Path(f'tests/fixtures/real/{scenario}_T1.json')
    if p.is_file():
        d = json.loads(p.read_text())
        assert set(d.keys()) &gt;= {'today', 'school_tz', 'lessons', 'grades', 'information'}
        results.append(scenario)
print('captured T1 scenarios:', results)
assert results, 'at least one T1 fixture must exist'
" &amp;&amp; ! grep -rE 'katiramona|ac-noumea' tests/fixtures/real/*.json</automated>
  </verify>
  <done>
    - At least 1 (preferably 3) `tests/fixtures/real/<scenario>_T1.json` files exist.
    - For every captured scenario, the meaningful-diff assertion (newly canceled / room change / teacher change identity tuple) holds OR is documented as an empirical pronotepy 2.14.6 finding in SPIKE-FINDINGS.
    - `grep -rE 'katiramona|ac-noumea' tests/fixtures/real/*.json` returns nothing.
    - All raw `_raw_*_T1.json` files are gitignored.
  </done>
</task>

<task type="auto">
  <name>Task 4: Author SPIKE-FINDINGS-bain3-311.md and verify Snapshot.from_dict round-trip</name>
  <read_first>
    - .planning/research/PITFALLS.md §"Pitfall 10" (the prior hypothesis the spike confirms or refines)
    - .planning/phases/02-api-diff-layer-ha-free/02-CONTEXT.md §"Diff Algorithm" (D-05, D-06, D-07, D-08, D-09)
    - .planning/phases/02-api-diff-layer-ha-free/02-PATTERNS.md §"tests/fixtures/SPIKE-FINDINGS-bain3-311.md"
    - All `tests/fixtures/real/*.json` files captured in Tasks 1+3
    - custom_components/ha_pronote/api/models.py (Snapshot.from_dict — the round-trip target)
  </read_first>
  <acceptance_criteria>
    - `tests/fixtures/SPIKE-FINDINGS-bain3-311.md` exists.
    - The doc contains all four required sections from D-06 (PATTERNS.md §"SPIKE-FINDINGS-bain3-311.md"):
      1. `## Observed semantics` (canceled / status / paired lessons / teacher representation)
      2. `## D-08 hypothesis verdict` (identity key + content key — confirmed or refined)
      3. `## Concrete diffs` (one subsection per captured scenario)
      4. `## Algorithm decision` (how diff/lessons.py handles each scenario)
    - The doc explicitly states which scenarios were captured live vs which fall back to synthetic fixtures (D-10 covers the gap).
    - Every committed JSON file in `tests/fixtures/real/` round-trips cleanly through `Snapshot.from_dict(...).to_dict() == loaded_json` (verified by a small ad-hoc script — Plan 02-04 will encode this as `tests/test_fixtures.py`).
  </acceptance_criteria>
  <action>
    **1. Round-trip every committed fixture through `Snapshot.from_dict`** to confirm the captured data conforms to the dataclass shape (D-11):

    ```python
    # /tmp/roundtrip.py
    import json
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path.cwd()))
    from custom_components.ha_pronote.api.models import Snapshot

    for path in sorted(Path("tests/fixtures/real").glob("*.json")):
        if path.name.startswith("_raw_"):
            continue
        raw = json.loads(path.read_text())
        snap = Snapshot.from_dict(raw)
        rt = snap.to_dict()
        assert rt == raw, f"{path}: round-trip drift\\n  expected={raw}\\n  got={rt}"
        print(f"OK  {path}")
    ```

    Run it: `python /tmp/roundtrip.py`. If any fixture fails round-trip, inspect the discrepancy:
    - If a pronotepy field accessor in `api/fetcher.py` is wrong (e.g. `raw.teacher_name` should be `raw.teacherName`), fix it and re-run the spike capture for the affected scenarios.
    - If `Snapshot.from_dict` is missing a field that the live Pronote actually returns (e.g. pronotepy 2.14.6 surfaces a field Plan 02-01 didn't anticipate), extend `api/models.py` to include it AND re-run the round-trip. Coordinate with Plan 02-03 — the new field becomes part of the diff key surface.

    **2. Author `tests/fixtures/SPIKE-FINDINGS-bain3-311.md`** with this exact structure:

    ```markdown
    # SPIKE FINDINGS: bain3/pronotepy#311 — Cancel vs Room Change Semantics

    **Captured:** YYYY-MM-DD by spike against author's `<pronote_host>` instance via `scripts/snapshot.py`.
    **pronotepy version:** 2.14.6 (as pinned in `manifest.json`).
    **Phase:** 02 — API & Diff Layer (HA-free).
    **Decisions referenced:** D-05 (spike-first), D-06 (this document), D-07 (Plan 02-03 reads this), D-08 (identity/content keys), D-09 (change_type taxonomy).

    ## Captured fixtures

    | Scenario | T0 fixture | T1 fixture | Source |
    |---|---|---|---|
    | cancellation | tests/fixtures/real/cancellation_T0.json | tests/fixtures/real/cancellation_T1.json | live spike |
    | room_change | tests/fixtures/real/room_change_T0.json | tests/fixtures/real/room_change_T1.json | live spike OR fallback to synthetic (state which) |
    | teacher_swap | tests/fixtures/real/teacher_swap_T0.json | tests/fixtures/real/teacher_swap_T1.json | live spike OR fallback to synthetic |

    ## Observed semantics

    ### `canceled` field
    - Type: `bool`. Always present? <yes/no, with example>.
    - Populated on the canceled lesson only, or also on its replacement? <observed>.

    ### `status` field
    - Type: <observed>.
    - Exact values seen across captures: <list, e.g. `""`, `"Cours annulé"`, `"Changement de salle"`, `"Prof. absent"`>.

    ### Paired vs unpaired lessons at the same datetime
    The bain3#311 bug class. When a teacher cancels lesson L1 (Math, Salle 102, M. X) and the office reschedules to L2 (Math, Salle 105, M. X), does pronotepy 2.14.6 return:
    - **Option A:** TWO entries — old `(canceled=True, classroom="Salle 102")` + new `(canceled=False, classroom="Salle 105")`.
    - **Option B:** ONE entry — only `(canceled=False, classroom="Salle 105")`, the original is dropped.
    - **Option C:** ONE entry with `(canceled=True, classroom="Salle 102")`, the new one shows up the next day or never.

    Observed: <A | B | C>. Evidence: <reference fixture file + array indices>.

    ### Teacher representation under substitution
    - Same `teacher_name` field with a different value? Observed: <yes/no>.
    - Or new lesson + old canceled? Observed: <yes/no>.

    ## D-08 hypothesis verdict

    Starting hypothesis (D-08):
    - Identity key = `(date, start_time, end_time, subject)`.
    - Content key = `(canceled, status, classroom, teacher_full_name)`.

    **Verdict:** <CONFIRMED | REFINED | REJECTED>.

    If REFINED, the new keys are:
    - Identity key = `(...)`. Reason: <observed evidence>.
    - Content key = `(...)`. Reason: <observed evidence>.

    ## Concrete diffs

    ### cancellation_T0 → cancellation_T1
    - `lessons` count: T0=N, T1=N (paired or unpaired? — see Observed semantics).
    - The canceled lesson identity tuple: `(YYYY-MM-DD, HH:MM-HH:MM, <subject>)`.
    - Field-by-field diff: <list>.

    ### room_change_T0 → room_change_T1
    - <same shape>.

    ### teacher_swap_T0 → teacher_swap_T1
    - <same shape>.

    ## Algorithm decision (Plan 02-03 implements this)

    Given Observed semantics and the D-08 verdict, `diff/lessons.py:diff_lessons(previous, new, day)`
    will:

    1. **First-poll skip:** `previous is None → return []` (D-08 invariant, Pitfall 10).
    2. **Reorder no-op:** if every lesson in `previous.lessons_<day>` has the same identity AND content key in `new.lessons_<day>`, return `[]`.
    3. **Identity-stable content change:** for each identity tuple appearing in both T0 and T1:
       - If `canceled` flipped True → emit `LessonChange(change_type="canceled", before=T0_dict, after=T1_dict)`.
       - Else if `classroom` changed → emit `LessonChange(change_type="room", ...)`.
       - Else if `teacher` changed → emit `LessonChange(change_type="teacher", ...)`.
       - Else if any other content field changed → emit `LessonChange(change_type="modified", ...)`.
    4. **Identity present only in T0 (lesson removed):** depending on `<observed semantics>`,
       either emit `change_type="canceled"` OR stay silent (D-10's "lesson removed" synthetic
       fixture covers the second branch — period rollover noise should be silent).
    5. **Identity present only in T1 (lesson added):** depending on `<observed semantics>`,
       either silent OR emit `change_type="modified"` (D-10's "lesson added" synthetic fixture
       covers the case).
    6. **Paired-canceled+room-change special case (bain3#311):** based on Option A/B/C above,
       the algorithm <consolidates the pair into one `change_type="room"` event | treats them
       as separate canceled+modified events | other>.

    ## Open questions / followups

    - <Any pronotepy 2.14.6 surface details that need a future bug report at bain3/pronotepy>.
    - <Any field that we couldn't capture due to missing access to a teacher account>.
    - <Any synthetic-fallback scenarios that need extra synthetic fixtures in Plan 02-03>.
    ```

    Fill in every `<placeholder>` with the actual observed evidence. Do NOT leave the doc with TBD markers — Plan 02-03 reads this as a contract.

    **3. Reset any temporary local edits to `scripts/snapshot.py`** that contained real PII:
    ```bash
    git diff scripts/snapshot.py   # review
    # If the only changes are the structural _build_replacements scaffold + the
    # PRONOTE_PII_REPLACEMENTS env-var support + the corresponding test, those are KEEP.
    # Any actual real-name strings: REMOVE before committing.
    ```

    **4. Stage the files** that should be committed:
    ```bash
    git add tests/fixtures/real/cancellation_T0.json
    git add tests/fixtures/real/cancellation_T1.json   # if captured
    git add tests/fixtures/real/room_change_T0.json
    git add tests/fixtures/real/room_change_T1.json    # if captured
    git add tests/fixtures/real/teacher_swap_T0.json
    git add tests/fixtures/real/teacher_swap_T1.json   # if captured
    git add tests/fixtures/SPIKE-FINDINGS-bain3-311.md
    git add scripts/snapshot.py     # only if PRONOTE_PII_REPLACEMENTS support was added
    git add .env.example            # only if the new env var was documented
    git add tests/test_scripts/test_snapshot.py   # the new test for the env-var parser

    git status   # final verification — NO _raw_*.json, NO .env, NO real PII
    ```

    Final security gate (security_gate threats T-02-02-01 + T-02-02-02):
    ```bash
    git diff --cached -- tests/fixtures/real/ | grep -E 'katiramona|ac-noumea\\.nc'   # MUST return nothing
    git diff --cached -- '*' | grep -E '<known_real_first_name>|<known_real_last_name>'   # MUST return nothing (run with actual values, locally)
    git status --porcelain | grep -E '^A.*\\.env$'   # MUST return nothing — .env never staged
    git status --porcelain | grep -E '_raw_.*\\.json'   # MUST return nothing — raw fixtures never staged
    ```
  </action>
  <verify>
    <automated>test -f tests/fixtures/SPIKE-FINDINGS-bain3-311.md &amp;&amp; grep -E '## Observed semantics|## D-08 hypothesis|## Concrete diffs|## Algorithm decision' tests/fixtures/SPIKE-FINDINGS-bain3-311.md | wc -l | grep -q '^4$' &amp;&amp; python -c "
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from custom_components.ha_pronote.api.models import Snapshot
for p in sorted(Path('tests/fixtures/real').glob('*.json')):
    if p.name.startswith('_raw_'):
        continue
    raw = json.loads(p.read_text())
    snap = Snapshot.from_dict(raw)
    assert snap.to_dict() == raw, f'{p}: round-trip drift'
    print(f'OK  {p}')
" &amp;&amp; ! grep -rE 'katiramona|ac-noumea' tests/fixtures/real/*.json &amp;&amp; ! git status --porcelain | grep -E '_raw_.*\.json|^.. \.env$'</automated>
  </verify>
  <done>
    - `tests/fixtures/SPIKE-FINDINGS-bain3-311.md` exists with all 4 required sections populated (no TBD markers).
    - Every committed `tests/fixtures/real/<scenario>_<phase>.json` file round-trips through `Snapshot.from_dict(...).to_dict()` cleanly.
    - At least the cancellation scenario has T0 + T1 fixtures (room_change and teacher_swap may fall back to synthetic per Task 2's resume-signal — documented in SPIKE-FINDINGS).
    - `grep -rE 'katiramona|ac-noumea' tests/fixtures/real/*.json` returns nothing.
    - `git status --porcelain` does NOT show any `_raw_*.json` files staged or `.env` staged.
    - `git diff --cached` review shows no real PII tokens.
    - The PRONOTE_PII_REPLACEMENTS env-var enhancement (if implemented) has a corresponding test in `tests/test_scripts/test_snapshot.py` that passes.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Live Pronote server → `pronotepy` → `api/fetcher.py` → raw JSON file | Real student data crosses here. Raw output contains PII (child name, teachers, classroom IDs, school URL). |
| Raw JSON file → `anonymize()` → committed JSON file | Anonymizer is the security boundary. A miss here = PII commit. |
| `git add` → public GitHub repo | The author's personal repo will eventually be public (HACS distribution). Anything committed here is permanent. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-02-01 | Information Disclosure | `tests/fixtures/real/_raw_*.json` (raw spike output) | mitigate | Plan 02-01 added `tests/fixtures/real/_raw_*.json` to `.gitignore`. Task 4 verification gate: `git status --porcelain | grep '_raw_.*\.json'` MUST return nothing. **Severity: HIGH** if missed — would leak full Pronote API response including child PII. |
| T-02-02-02 | Information Disclosure | Insufficient anonymizer allowlist (PII residue) | mitigate | The `PRONOTE_PII_REPLACEMENTS` env-var (Task 1) lets the human extend the allowlist with every PII token observed in the raw output. Task 1 verification: `grep -rE 'katiramona|ac-noumea\\.nc' tests/fixtures/real/*.json` MUST return nothing. Task 4 final gate: `git diff --cached` review by the human + grep against any known real names. **Severity: HIGH** if missed — would leak PII of minors. |
| T-02-02-03 | Information Disclosure | `.env` accidentally committed | mitigate | Phase 1 + Plan 02-01 added `.env` to `.gitignore`. Task 0 verification: `git check-ignore .env` exits 0. Task 4 final gate: `git status --porcelain | grep '\\.env$'` MUST return nothing. **Severity: HIGH** if missed — would leak the author's Pronote credentials. |
| T-02-02-04 | Denial of Service (self-inflicted) | IP suspension during repeated spike runs (Pitfall 1) | mitigate | Task 1 enforces 30s sleep between captures. If `RateLimitedError(IP_SUSPENDED)` fires, the CLI surfaces it cleanly (D-22) and the human waits 24h. Plan 02-04's coverage matrix doesn't run against live Pronote — only against committed fixtures. **Severity: MEDIUM** — recoverable but disruptive. |
| T-02-02-05 | Repudiation | Fixture authorship and timestamp not traceable | mitigate | SPIKE-FINDINGS-bain3-311.md captures the spike timestamp, the pronotepy version (`2.14.6`), and the author identity. Git commit metadata captures the rest. No further action needed. **Severity: LOW**. |
| T-02-02-06 | Tampering / Spoofing | A fixture is hand-edited later in a way that breaks the diff invariants without rerunning the spike | mitigate | Plan 02-04 adds `tests/test_fixtures.py` (D-11) which round-trips every fixture through `Snapshot.from_dict`/`to_dict` — any drift fails CI. Plan 02-04's tz matrix re-runs the diff tests against the fixtures on every CI build. **Severity: LOW**. |
</threat_model>

<verification>
**Plan-level checks** (all must pass after Tasks 0-4):

1. **No PII committed:**
   - `! grep -rE 'katiramona|ac-noumea\\.nc' tests/fixtures/real/*.json` succeeds.
   - `git status --porcelain | grep -E '_raw_.*\\.json'` returns nothing.
   - `git status --porcelain | grep -E '^.. \\.env$'` returns nothing.

2. **All committed fixtures conform to Snapshot.to_dict() shape:**
   - For every `tests/fixtures/real/*.json` (excluding `_raw_*`): `Snapshot.from_dict(json.loads(...)).to_dict() == json.loads(...)`.

3. **SPIKE-FINDINGS doc complete:**
   - `tests/fixtures/SPIKE-FINDINGS-bain3-311.md` exists.
   - Contains all 4 required sections (count of `## Observed semantics`, `## D-08 hypothesis`, `## Concrete diffs`, `## Algorithm decision` headers == 4).
   - No `TBD` or `<placeholder>` markers remain.

4. **At least the cancellation scenario captured live:**
   - Both `cancellation_T0.json` and `cancellation_T1.json` exist.
   - The cancellation T0→T1 diff shows at least one identity tuple with `canceled` flipping True (proves the spike captured a real schedule change, not just a no-op poll).

5. **Plan 02-01's contract preserved:**
   - `pytest tests/test_api/ tests/test_scripts/` still passes (any modifications to `scripts/snapshot.py` for the PII env var are covered by the new test).
</verification>

<success_criteria>
- 6 anonymized fixture JSON files in `tests/fixtures/real/` (3 scenarios × T0/T1) — OR fewer if Task 2 was `partial:`, with the missing scenarios documented in SPIKE-FINDINGS as synthetic-only.
- `tests/fixtures/SPIKE-FINDINGS-bain3-311.md` exists with all 4 required sections completely filled in.
- Every committed fixture round-trips through `Snapshot.from_dict`/`to_dict` cleanly (proven manually in Task 4; CI-enforced by Plan 02-04's `tests/test_fixtures.py`).
- ROADMAP success criterion #2 satisfied: `python scripts/snapshot.py` authenticated against the author's real Pronote instance and produced a valid anonymized JSON snapshot.
- EVENT-05 partially satisfied: the empirical evidence (D-06) for the identity-vs-content key separation is captured. Plan 02-03 implements the algorithm.
- All 6 STRIDE threats are mitigated and verified.
- No PII leaks: `grep -rE 'katiramona|ac-noumea' tests/fixtures/` returns nothing; no `_raw_*.json` files staged; no `.env` staged.
</success_criteria>

<output>
After completion, create `.planning/phases/02-api-diff-layer-ha-free/02-02-SUMMARY.md` documenting:
- Which scenarios were captured live vs fell back to synthetic (Plan 02-03 inputs).
- The exact pronotepy 2.14.6 surface findings (which Option A/B/C the bain3#311 paired-lesson behavior actually exhibits).
- The D-08 verdict: identity and content keys CONFIRMED or REFINED — and if refined, what the new keys are.
- Any small fixes applied to `scripts/snapshot.py` or `api/fetcher.py` during the spike (e.g. field-accessor corrections — surgical only).
- A pointer to `tests/fixtures/SPIKE-FINDINGS-bain3-311.md` as the contract Plan 02-03 reads.
- Security audit: confirmation that no PII was committed (re-grep at commit time, document the result).
</output>
</content>
</invoke>