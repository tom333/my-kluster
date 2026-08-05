"""Constants for HA-Pronote."""

from __future__ import annotations

from datetime import date, time, timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "ha_pronote"

# Phase 2 additions (D-15, D-18) — defaults consumed by Phase 3 coordinator.
# NOT imported by api/ — fetcher.py takes today / school_tz as arguments
# (D-17, D-18) so the api/ subpackage stays free of ambient state.
DEFAULT_SCHOOL_TZ: Final = "Pacific/Noumea"
DEFAULT_LOOKBACK_DAYS: Final = 7  # J-7
DEFAULT_LOOKAHEAD_DAYS: Final = 14  # J+14

# Phase 3 additions (D-24, D-25) — HA-side runtime defaults consumed by the
# coordinator (update_interval) and __init__.py (platform forwarding).
DEFAULT_REFRESH_INTERVAL: Final = timedelta(minutes=30)  # D-24 — Phase 5 makes adaptive
# D-10 — Phase 4 extends to include CALENDAR.
# __init__.py:async_forward_entry_setups(entry, PLATFORMS) already iterates this const.
PLATFORMS: Final = (Platform.SENSOR, Platform.CALENDAR)

# Phase 4 additions — event-type constants (D-13, EVENT-01..03),
# class level attribute (D-19, ENT-01), attribute caps (D-05, D-04),
# platform extension (D-10).

EVENT_SCHEDULE_CHANGED: Final = "pronote_schedule_changed"  # D-13, EVENT-01
EVENT_NEW_GRADE: Final = "pronote_new_grade"  # D-13, EVENT-02
EVENT_NEW_INFORMATION: Final = "pronote_new_information"  # D-13, EVENT-03

# Probe-locked class level attribute on pronotepy.ClientInfo (D-19, ENT-01).
# PHASE-4-PROBE-NOTES.md STEP 11 confirms: ClientInfo.class_name returns
#   raw_resource.get("classeDEleve", {}).get("L", "") — returns "" not None when absent.
# For ParentClient, client.info.class_name is "" (parent has no class);
# the child's class lives in client.children[child_index].class_name.
CLASS_LEVEL_ATTR: Final = "class_name"

NOTIFICATIONS_WINDOW: Final = 20  # D-05 — cap on informations list in sensor attrs
GRADE_COMMENT_MAX_LEN: Final = 200  # D-04 — comment truncation length at sensor render
# D-04 (revised post-UAT): CONTEXT.md called for "all current-period grades",
# but the heavy-class CI gate (D-17 + 100 grades fixture) measured the JSON
# payload at 18 365 bytes — exceeds the 16 384-byte recorder cap. Cap the
# attribute at the 50 most recent (sorted by date desc) so the 9-field
# ApexCharts schema fits comfortably. Realistic trimester counts (~30–60)
# remain fully covered; only the synthetic 100-grade stress case is trimmed.
GRADES_WINDOW: Final = 50

# Phase 5 additions — adaptive polling cadence, quiet hours, circuit breaker.
# D-04: compute_interval branch defaults. D-08: quiet hours default 22h-6h NC.
# D-11: backoff curve per PITFALLS §2.1. D-18: const wording locked in CONTEXT.md.
# BLOCKER-3 (checker revision): TROUBLESHOOTING_DOC_URL_BASE consolidates the
# troubleshooting URL into ONE symbol; coordinator._handle_failure builds
# kind-specific anchors as f"{BASE}#troubleshooting-{kind}" matching D-15's
# anchor wording (#troubleshooting-ip-suspended / #troubleshooting-auth-circuit).
# Phase 7 DIST-07 fills the <placeholder-owner> in this one const, not many call sites.

BACKOFF_SCHEDULE: Final[tuple[timedelta, ...]] = (
    timedelta(hours=1),
    timedelta(hours=2),
    timedelta(hours=4),
    timedelta(hours=12),
    timedelta(hours=24),
)
JITTER_SECONDS: Final = 30
DEFAULT_AFTERNOON_INTERVAL: Final = timedelta(minutes=15)
DEFAULT_AFTERNOON_WINDOW: Final = (time(17, 0), time(20, 0))
DEFAULT_QUIET_HOURS: Final = (time(22, 0), time(6, 0))
DEFAULT_SUSPENDED_CADENCE: Final = timedelta(hours=6)
DEFAULT_QUIET_CADENCE: Final = timedelta(hours=4)
NC_VACATION_RANGES_2026: Final[tuple[tuple[date, date], ...]] = (
    (date(2026, 4, 4), date(2026, 4, 19)),
    (date(2026, 6, 6), date(2026, 6, 21)),
    (date(2026, 8, 8), date(2026, 8, 23)),
    (date(2026, 10, 10), date(2026, 10, 25)),
    (date(2026, 12, 19), date(2027, 2, 14)),
)
NC_LOCAL_HOLIDAYS_SUPPLEMENT: Final[frozenset[date]] = frozenset()
IP_SUSPENDED_NOTIFICATION_ID_SUFFIX: Final = "ip_suspended"
AUTH_CIRCUIT_NOTIFICATION_ID_SUFFIX: Final = "auth_circuit"
# BLOCKER-3 fix: single-source base URL. Phase 7 DIST-07 fills the owner
# placeholder in this ONE const. coordinator._handle_failure builds
# f"{TROUBLESHOOTING_DOC_URL_BASE}#troubleshooting-{kind}" where
# kind in {"ip-suspended", "auth-circuit"} (hyphen-form per D-15).
TROUBLESHOOTING_DOC_URL_BASE: Final = "https://github.com/<placeholder-owner>/ha_pronote"

# Phase 6 additions — OptionsFlow OPT-02 + OPT-03 defaults.
# D-09 Phase 6 — adaptive polling toggle defaults to ON (preserve Phase 5 behavior).
# D-16 Phase 6 — nickname length cap (40 chars covers long French + emoji names
# without risking the 255-char limit on sensor state strings).
DEFAULT_ADAPTIVE_POLLING_ENABLED: Final = True
NICKNAME_MAX_LEN: Final = 40
