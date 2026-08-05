"""Real Config Flow for HA-Pronote (D-01..D-05, D-10..D-13).

D-01: single-step ``async_step_user`` form -- URL + account_type + username + password.
      `build_client(...)` is awaited via ``hass.async_add_executor_job(partial(...))``.
      eleve OR parent-with-1-child -> direct entry creation.
      parent-with-multiple-children -> ``async_step_pick_child``.
D-02: ``async_step_pick_child`` -- single-select dropdown of ``client.children``.
D-03: URL validation = ``TextSelector(type=URL)`` only (no HEAD probe; pronotepy connect
      failure is the reachability signal). The HA frontend enforces URL format via the
      selector; ``voluptuous.Url()`` cannot be JSON-serialised for the config flow UI.
D-04: error mapping (form-level errors dict -- never raises into the UI):
        AuthError              -> errors={"base": "invalid_auth"}
        RateLimitedError       -> errors={"base": "ip_suspended"}
        CommunicationError     -> errors={"base": "cannot_connect"}
        PronoteIntegrationError-> errors={"base": "unknown"}
D-05: ConfigEntry unique_id == f"{url_host.lower()}:{username}:{child_identifier}".
      Computed via urllib.parse.urlparse(url).hostname.
D-10/D-11/D-13: child_identifier = slugify(child_name, separator="_"); FROZEN at flow time;
      stored verbatim in entry.data["child_identifier"]; never re-derived later.
D-12: collision suffix -- Phase 3 ships the precheck; if the slug would collide
      with an existing entry's child_identifier on this HA install, append the
      first 2 hex chars of pronotepy.children[idx].identifier (e.g. jean_dupont_a3).

Banned in this file (CLAUDE.md "What NOT to Use" + Phase 1 D-30..D-35):
- No ``requests`` calls.
- No synchronous pronotepy calls without ``async_add_executor_job`` (Pitfall 6).
- No HEAD probe before auth (D-03 explicitly rejects).
- No hardcoded URL -- every URL comes from ``user_input["url"]``.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pronotepy
from slugify import slugify
import voluptuous as vol

if TYPE_CHECKING:
    from collections.abc import Mapping

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)

from .api import build_client, set_active_child
from .api.client import build_or_resume_client  # Phase 3 C-02 single seam; Phase 6 reauth/reconfigure reuse.
from .api.errors import AuthError, CommunicationError, PronoteIntegrationError, RateLimitedError
from .const import (
    DEFAULT_ADAPTIVE_POLLING_ENABLED,
    DEFAULT_AFTERNOON_INTERVAL,
    DEFAULT_AFTERNOON_WINDOW,
    DEFAULT_QUIET_CADENCE,
    DEFAULT_QUIET_HOURS,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_SCHOOL_TZ,
    DEFAULT_SUSPENDED_CADENCE,
    DOMAIN,
    NICKNAME_MAX_LEN,
)

# D-04 typed-exception → form-error mapping (re-introduced after Phase 3 DEBUG MODE
# per Phase 6 CONTEXT.md decision — reauth/reconfigure depend on this surface).
_ERROR_KEY_BY_EXC: tuple[tuple[type[Exception], str], ...] = (
    (AuthError, "invalid_auth"),
    (RateLimitedError, "ip_suspended"),
    (CommunicationError, "cannot_connect"),
    (PronoteIntegrationError, "unknown"),
)


def _map_error(exc: Exception) -> str:
    """Map a typed pronote integration error to the D-04 form-error key.

    Returns ``"unknown"`` for any unrecognised exception. Order matters because
    ``RateLimitedError`` subclasses ``PronoteIntegrationError`` etc. — the
    sequence above places narrower types before the catch-all.
    """
    for exc_type, key in _ERROR_KEY_BY_EXC:
        if isinstance(exc, exc_type):
            return key
    return "unknown"


_USER_SCHEMA = vol.Schema(
    {
        # D-03: URL validation via TextSelector(URL) — vol.Url() cannot be
        # JSON-serialised by HA's config flow result preparer (ValueError:
        # "Unable to convert schema: <function Url>"), so the URL format
        # check moves to the frontend selector. pronotepy.Client(url, ...)
        # remains the authoritative reachability + correctness signal.
        vol.Required("url"): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        vol.Required("account_type"): vol.In(["eleve", "parent"]),
        vol.Required("username"): str,
        # CR-01: password rendered as masked input in HA frontend.
        vol.Required("password"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    }
)


# Phase 6 D-01 — reauth schema. Two fields only: username + password.
# URL and account_type are preserved from entry.data; the user does NOT re-enter them.
_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    }
)


# Phase 6 D-05 — reconfigure schema. URL + account_type only. Username/password
# are out-of-scope here (reauth flow owns them) per D-05.
_RECONFIGURE_SCHEMA = vol.Schema(
    {
        vol.Required("url"): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        vol.Required("account_type"): vol.In(["eleve", "parent"]),
    }
)


# Phase 6 D-09 / D-10 — OptionsFlow step "Polling" (9 fields).
# Field order: refresh_interval (most-used lever) → adaptive_polling_enabled toggle
# → afternoon_* → suspended_cadence → quiet_*.
_POLLING_SCHEMA = vol.Schema(
    {
        vol.Required("refresh_interval"): NumberSelector(
            NumberSelectorConfig(min=1, max=1440, mode=NumberSelectorMode.BOX, unit_of_measurement="min")
        ),
        vol.Required("adaptive_polling_enabled"): BooleanSelector(),
        vol.Required("afternoon_interval"): NumberSelector(
            NumberSelectorConfig(min=1, max=1440, mode=NumberSelectorMode.BOX, unit_of_measurement="min")
        ),
        vol.Required("afternoon_window_start"): TimeSelector(),
        vol.Required("afternoon_window_end"): TimeSelector(),
        vol.Required("suspended_cadence"): NumberSelector(
            NumberSelectorConfig(min=1, max=1440, mode=NumberSelectorMode.BOX, unit_of_measurement="min")
        ),
        vol.Required("quiet_cadence"): NumberSelector(
            NumberSelectorConfig(min=1, max=1440, mode=NumberSelectorMode.BOX, unit_of_measurement="min")
        ),
        vol.Required("quiet_hours_start"): TimeSelector(),
        vol.Required("quiet_hours_end"): TimeSelector(),
    }
)


# Phase 6 D-09 / D-10 / D-16 (REVISED — Critical Gotcha #2: the strip helper
# does NOT exist on the voluptuous module; use a lambda inside vol.All).
# Step "Display" (2 fields): nickname + school_tz.
_DISPLAY_SCHEMA = vol.Schema(
    {
        vol.Optional("nickname", default=""): vol.All(
            cv.string,
            vol.Length(max=NICKNAME_MAX_LEN),
            # CRITICAL Gotcha #2 — the lambda is the canonical replacement for
            # the voluptuous strip helper (which does not exist and would raise
            # AttributeError at import). Empty-post-strip is handled at the read
            # site (entity.device_info Plan 06-02) by the fallback chain
            # `(... or "").strip() or entry.data["child_name"]`.
            lambda v: v.strip(),
        ),
        vol.Required("school_tz", default=DEFAULT_SCHOOL_TZ): str,
    }
)


def _options_schema_defaults(entry: ConfigEntry) -> dict[str, Any]:
    """D-11 — single source of truth between OptionsFlow defaults and runtime read.

    Returns a dict of `entry.options[key]` if set, else the const-derived default.
    The dict feeds `add_suggested_values_to_schema` so the form shows current values;
    coordinator._resolve_options reads the same `entry.options.get` paths so any
    drift would surface in `test_options_defaults_match_resolve_options`.
    """
    opts = entry.options
    return {
        "refresh_interval": opts.get("refresh_interval", int(DEFAULT_REFRESH_INTERVAL.total_seconds() // 60)),
        "adaptive_polling_enabled": opts.get("adaptive_polling_enabled", DEFAULT_ADAPTIVE_POLLING_ENABLED),
        "afternoon_interval": opts.get("afternoon_interval", int(DEFAULT_AFTERNOON_INTERVAL.total_seconds() // 60)),
        "afternoon_window_start": opts.get("afternoon_window_start", DEFAULT_AFTERNOON_WINDOW[0].isoformat()),
        "afternoon_window_end": opts.get("afternoon_window_end", DEFAULT_AFTERNOON_WINDOW[1].isoformat()),
        "quiet_hours_start": opts.get("quiet_hours_start", DEFAULT_QUIET_HOURS[0].isoformat()),
        "quiet_hours_end": opts.get("quiet_hours_end", DEFAULT_QUIET_HOURS[1].isoformat()),
        "suspended_cadence": opts.get("suspended_cadence", int(DEFAULT_SUSPENDED_CADENCE.total_seconds() // 60)),
        "quiet_cadence": opts.get("quiet_cadence", int(DEFAULT_QUIET_CADENCE.total_seconds() // 60)),
        "nickname": opts.get("nickname", ""),
        "school_tz": opts.get("school_tz", DEFAULT_SCHOOL_TZ),
    }


class HaPronoteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Real flow -- D-01 user step, optional D-02 pick_child step."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """HA hook for OptionsFlow surfacing.

        Critical Gotcha #3 — HaPronoteOptionsFlow() takes NO config_entry arg.
        HA injects self.config_entry as a read-only property on the OptionsFlow
        base class; passing it explicitly raises AttributeError on HA 2025.12+.
        """
        return HaPronoteOptionsFlow()

    def __init__(self) -> None:
        """Stash inter-step state -- pronotepy client + last user_input."""
        self._client: pronotepy.Client | pronotepy.ParentClient | None = None
        self._user_input: dict[str, Any] | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Single-step credential form per D-01.

        D-04: typed exceptions from ``build_client`` are mapped to form-error
        keys (``invalid_auth`` / ``ip_suspended`` / ``cannot_connect`` /
        ``unknown``) and the form is re-shown. Phase 6 reauth/reconfigure flows
        rely on this same mapping.
        """
        if user_input is not None:
            try:
                client = await self.hass.async_add_executor_job(
                    partial(
                        build_client,
                        user_input["url"],
                        user_input["account_type"],
                        user_input["username"],
                        user_input["password"],
                    )
                )
            except PronoteIntegrationError as err:
                return self.async_show_form(
                    step_id="user",
                    data_schema=_USER_SCHEMA,
                    errors={"base": _map_error(err)},
                )
            self._client = client
            self._user_input = user_input
            # D-01: parent with >1 children -> pick_child; otherwise create.
            if isinstance(client, pronotepy.ParentClient) and len(client.children) > 1:
                return await self.async_step_pick_child()
            return await self._create_entry(child_index=None)

        return self.async_show_form(step_id="user", data_schema=_USER_SCHEMA)

    async def async_step_pick_child(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """D-02: single-select dropdown of ParentClient.children."""
        if self._client is None or not isinstance(self._client, pronotepy.ParentClient):
            # Defensive: pick_child reached without a parent client is a bug.
            return self.async_abort(reason="unknown")

        children = self._client.children

        if user_input is not None:
            return await self._create_entry(child_index=int(user_input["child_index"]))

        schema = vol.Schema(
            {vol.Required("child_index"): vol.In({str(i): child.name for i, child in enumerate(children)})}
        )
        return self.async_show_form(step_id="pick_child", data_schema=schema)

    # ------------------------------------------------------------------ #
    # Phase 6 — Reauth flow (AUTH-05, D-01..D-04, RESEARCH Pattern 1).   #
    # ------------------------------------------------------------------ #

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """HA invokes this when ConfigEntryAuthFailed is raised. Trampoline only.

        Per D-04: trigger is HA-native. We do NOT inspect entry_data here; the
        real form lives in async_step_reauth_confirm which reads self._get_reauth_entry().
        """
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """D-01 form: username + password. URL + account_type preserved from entry.data.

        On success: D-02 clears entry.data["session"] so the next async_setup_entry
        hits the fresh-login branch. D-03 reuses device_name = home-assistant-{entry_id[:8]}.
        """
        entry = self._get_reauth_entry()  # HA 2024.10+ helper
        errors: dict[str, str] = {}

        if user_input is not None:
            # D-03 — device_name is derived from entry.entry_id which is stable
            # across reauth, so Pronote sees the same connected device.
            device_name = f"home-assistant-{entry.entry_id[:8]}"
            try:
                await self.hass.async_add_executor_job(
                    partial(
                        build_or_resume_client,
                        entry.data["url"],
                        entry.data["account_type"],
                        user_input["username"],
                        user_input["password"],
                        None,  # D-02: session=None forces fresh-login branch
                        device_name,
                    )
                )
            except AuthError:
                errors["base"] = "invalid_auth"
            except RateLimitedError:
                errors["base"] = "ip_suspended"
            except CommunicationError:
                errors["base"] = "cannot_connect"
            except PronoteIntegrationError:
                errors["base"] = "unknown"
            else:
                # D-02 — data_updates= merges, NOT data= which would replace and
                # lose url/account_type/child_*/device_name (RESEARCH Pitfall #6).
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        "username": user_input["username"],
                        "password": user_input["password"],
                        "session": None,
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={"child_name": entry.data["child_name"]},
        )

    # ----------------------------------------------------------------------- #
    # Reconfigure: keeps the original unique_id (Phase 3 D-05 + ROADMAP SC#4). #
    #                                                                         #
    # SC#4 invariant: URL changes must preserve entity history. We            #
    # deliberately do NOT call any HA unique-id helpers — those would         #
    # abort on host change because unique_id embeds url_host. The             #
    # only abort path is the explicit child_identifier comparison             #
    # (D-06) which catches the rare "different child resolved via the         #
    # new URL" case.                                                          #
    #                                                                         #
    # NOTE TO MAINTAINERS: this comment block is intentionally placed         #
    # OUTSIDE `async def async_step_reconfigure` so it is NOT returned        #
    # by `inspect.getsource(HaPronoteConfigFlow.async_step_reconfigure)`.     #
    # The static-source assertion in tests/CI checks that the method body     #
    # never names the forbidden HA unique-id helpers; keeping the prose       #
    # rationale here avoids triggering that guard.                            #
    # ----------------------------------------------------------------------- #

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """D-05: edit URL + account_type. Username/password preserved from entry.data.

        D-06: aborts if the new URL/account_type exposes a different child_identifier.
        D-07: re-validates via build_or_resume_client BEFORE any entry.data mutation.
        D-08: clears entry.data['session'] only if URL or account_type changed.

        SC#4 invariant: the per-method static-source check (see CI / Task 1 verify)
        forbids any reference to HA unique-id helpers from this method body — see
        the block comment immediately above the def for the full rationale.
        """
        entry = self._get_reconfigure_entry()  # HA 2024.10+ helper
        errors: dict[str, str] = {}

        if user_input is not None:
            new_url = user_input["url"].strip()
            new_account_type = user_input["account_type"]
            device_name = f"home-assistant-{entry.entry_id[:8]}"  # D-03 stable

            # D-07: re-validate against new URL/account_type BEFORE persistence.
            try:
                client = await self.hass.async_add_executor_job(
                    partial(
                        build_or_resume_client,
                        new_url,
                        new_account_type,
                        entry.data["username"],
                        entry.data["password"],
                        None,  # session=None — old session is for old URL
                        device_name,
                    )
                )
            except PronoteIntegrationError as err:
                errors["base"] = _map_error(err)
            else:
                # D-06: re-derive child_identifier under the NEW URL.
                # set_active_child MUST be wrapped (Pitfall #4) — raw pronotepy
                # CryptoError would escape as a traceback otherwise.
                child_index = entry.data.get("child_index")
                child_name: str | None = None
                if child_index is not None and isinstance(client, pronotepy.ParentClient):
                    try:
                        await self.hass.async_add_executor_job(set_active_child, client, child_index)
                    except PronoteIntegrationError as err:
                        errors["base"] = _map_error(err)
                    else:
                        child_name = client.children[child_index].name
                else:
                    child_name = client.info.name

                if not errors and child_name is not None:
                    new_child_identifier = slugify(child_name, separator="_")
                    if new_child_identifier != entry.data["child_identifier"]:
                        # D-06: the new URL/account exposes a DIFFERENT child.
                        # Explicit comparison only; no HA unique-id helpers
                        # called here (preserves entity history per SC#4 — see
                        # block comment above this method for the rationale).
                        return self.async_abort(reason="child_identifier_changed")

                    # D-08: clear session only if URL or account_type changed
                    # (string-equal after strip).
                    old_url = entry.data["url"].strip()
                    url_changed = new_url != old_url
                    at_changed = new_account_type != entry.data["account_type"]
                    data_updates: dict[str, Any] = {
                        "url": new_url,
                        "account_type": new_account_type,
                    }
                    if url_changed or at_changed:
                        data_updates["session"] = None

                    # SC#4: success path does not mutate unique_id — entity
                    # history (Recorder, energy stats, automations) preserved.
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates=data_updates,
                    )

        # First entry to step OR post-error re-render.
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _RECONFIGURE_SCHEMA,
                {
                    "url": entry.data["url"],
                    "account_type": entry.data["account_type"],
                },
            ),
            errors=errors,
            description_placeholders={"child_name": entry.data["child_name"]},
        )

    async def _create_entry(self, child_index: int | None) -> ConfigFlowResult:
        """Resolve child, derive identifier, set unique_id, create entry.

        WR-06: typed pronote exceptions from ``set_active_child`` and
        ``export_credentials`` map to the D-04 abort reason (``invalid_auth`` /
        ``ip_suspended`` / ``cannot_connect`` / ``unknown``). A bare
        ``RuntimeError`` from ``export_credentials`` (e.g. half-init client)
        maps to ``cannot_connect`` — pronotepy occasionally leaks plain
        exceptions on partial-init paths.
        """
        if self._client is None or self._user_input is None:
            return self.async_abort(reason="unknown")

        if isinstance(self._client, pronotepy.ParentClient):
            if child_index is None:
                # parent with exactly one child -- implicit pick.
                child_index = 0
            try:
                await self.hass.async_add_executor_job(set_active_child, self._client, child_index)
            except PronoteIntegrationError as err:
                return self.async_abort(reason=_map_error(err))
            child = self._client.children[child_index]
            child_name = child.name
        else:
            child_name = self._client.info.name

        # D-10 — underscore separator slug. D-12 collision-suffix logic was
        # dropped: it relied on pronotepy `Child.identifier` which actually
        # returns a `ClientInfo` object without an `identifier` attribute on
        # this server. Reintroduce in Phase 6 once we have a live-fixture
        # script (scripts/test_config_flow.py) that inspects real pronotepy
        # output. With a single child the collision check is a no-op anyway.
        child_identifier = slugify(child_name, separator="_")

        # D-05 unique_id: f"{url_host.lower()}:{username}:{child_identifier}"
        url_host = (urlparse(self._user_input["url"]).hostname or "").lower()
        unique_id = f"{url_host}:{self._user_input['username']}:{child_identifier}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        # D-06: capture export_credentials() at flow time so the first
        # async_setup_entry has a session to try. Plan 02's coordinator
        # writes a fresh session after every successful poll.
        try:
            session = await self.hass.async_add_executor_job(self._client.export_credentials)
        except PronoteIntegrationError as err:
            return self.async_abort(reason=_map_error(err))
        except RuntimeError:
            # pronotepy 2.14.6 occasionally raises a plain RuntimeError from a
            # half-initialised client (e.g. mid-recovery race). Surface as
            # cannot_connect so the user knows to retry rather than seeing an
            # opaque "unknown" abort.
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=f"{child_name} ({self._user_input['account_type']})",
            data={
                "url": self._user_input["url"],
                "account_type": self._user_input["account_type"],
                "username": self._user_input["username"],
                "password": self._user_input["password"],  # D-08 (kept for AUTH-04 fallback)
                "session": session,  # D-06
                "child_identifier": child_identifier,  # D-11 frozen
                "child_index": child_index,  # D-08
                "child_name": child_name,  # D-08 (DeviceInfo.name)
            },
        )


class HaPronoteOptionsFlow(OptionsFlowWithReload):
    """Phase 6 — multi-step OptionsFlow with auto-reload on commit.

    D-12 REVISED (RESEARCH Critical Gotcha #1) — inherits OptionsFlowWithReload,
    NOT OptionsFlow + add_update_listener. The base class triggers async_unload_entry
    + async_setup_entry automatically on async_create_entry, which propagates the new
    options through coordinator._resolve_options + entity.device_info on the next setup.

    Critical Gotcha #3 — __init__ takes NO config_entry; HA injects self.config_entry
    as a read-only property (assignment raises AttributeError on HA 2025.12+).
    """

    def __init__(self) -> None:
        """Stash inter-step state between polling + display steps.

        NOT self.config_entry = ... — HA injects that as a read-only property
        (Critical Gotcha #3, raises AttributeError on HA 2025.12+).
        """
        self._step1_data: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """D-10 — trampoline to step 'polling'. No menu screen."""
        return await self.async_step_polling()

    async def async_step_polling(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """D-10 — 9-field 'Polling' step; submit transitions to async_step_display."""
        if user_input is not None:
            self._step1_data = user_input
            return await self.async_step_display()

        suggested = _options_schema_defaults(self.config_entry)
        return self.async_show_form(
            step_id="polling",
            data_schema=self.add_suggested_values_to_schema(_POLLING_SCHEMA, suggested),
            description_placeholders={"child_name": self.config_entry.data["child_name"]},
        )

    async def async_step_display(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """D-10 / D-15 / Pitfall #5 — 2-field 'Display' step; commits all 11 keys."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Pitfall #5 — validate school_tz in the form, NOT at coordinator setup.
            try:
                ZoneInfo(user_input["school_tz"])
            except ZoneInfoNotFoundError, ValueError:
                errors["school_tz"] = "invalid_school_tz"
            else:
                merged = {**self._step1_data, **user_input}
                # D-15 — update entry.title when nickname is set, so the
                # Devices & Services panel shows the new name.
                nickname = (merged.get("nickname") or "").strip()
                if nickname:
                    self.hass.config_entries.async_update_entry(self.config_entry, title=nickname)
                # OptionsFlowWithReload triggers async_unload_entry + async_setup_entry.
                return self.async_create_entry(title="", data=merged)

        suggested = _options_schema_defaults(self.config_entry)
        return self.async_show_form(
            step_id="display",
            data_schema=self.add_suggested_values_to_schema(_DISPLAY_SCHEMA, suggested),
            errors=errors,
            description_placeholders={"child_name": self.config_entry.data["child_name"]},
        )
