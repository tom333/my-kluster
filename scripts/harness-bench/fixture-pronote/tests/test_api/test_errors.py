"""Contract tests for api/errors.py (D-22).

Phase 2 D-22 mandates a 7-member ``ErrorReason`` StrEnum and four convenience
subclasses each forcing a default reason. Phase 5's circuit-breaker reads
``.reason`` to route the long-backoff branch — drift here breaks Phase 5.
"""

from __future__ import annotations

from custom_components.ha_pronote.api import (
    AuthError,
    CommunicationError,
    ErrorReason,
    ParseError,
    PronoteIntegrationError,
    RateLimitedError,
    redact,
)


def test_error_reason_str_enum_values_match_snake_case():
    assert ErrorReason.AUTH_FAILED == "auth_failed"
    assert ErrorReason.IP_SUSPENDED == "ip_suspended"
    assert ErrorReason.PROTOCOL_BROKEN == "protocol_broken"
    assert ErrorReason.SERVER_DOWN == "server_down"
    assert ErrorReason.SESSION_EXPIRED == "session_expired"
    assert ErrorReason.RATE_LIMITED == "rate_limited"
    assert ErrorReason.PARSE_ERROR == "parse_error"


def test_error_reason_has_exactly_seven_members():
    assert set(ErrorReason) == {
        ErrorReason.AUTH_FAILED,
        ErrorReason.IP_SUSPENDED,
        ErrorReason.PROTOCOL_BROKEN,
        ErrorReason.SERVER_DOWN,
        ErrorReason.SESSION_EXPIRED,
        ErrorReason.RATE_LIMITED,
        ErrorReason.PARSE_ERROR,
    }
    assert len(list(ErrorReason)) == 7


def test_auth_error_forces_auth_failed_reason():
    err = AuthError("bad password")
    assert err.reason == ErrorReason.AUTH_FAILED
    assert err.message == "bad password"


def test_rate_limited_error_forces_ip_suspended_reason():
    err = RateLimitedError("Your IP address is suspended")
    assert err.reason == ErrorReason.IP_SUSPENDED
    assert err.message == "Your IP address is suspended"


def test_communication_error_forces_server_down_reason():
    err = CommunicationError("network down")
    assert err.reason == ErrorReason.SERVER_DOWN
    assert err.message == "network down"


def test_parse_error_forces_parse_error_reason():
    err = ParseError("naive datetime in fixture")
    assert err.reason == ErrorReason.PARSE_ERROR
    assert err.message == "naive datetime in fixture"


def test_subclass_is_pronote_integration_error():
    for sub in (
        AuthError("x"),
        CommunicationError("x"),
        RateLimitedError("x"),
        ParseError("x"),
    ):
        assert isinstance(sub, PronoteIntegrationError)


def test_str_repr_includes_reason_in_brackets():
    assert str(AuthError("x")) == "[auth_failed] x"
    assert str(RateLimitedError("y")) == "[ip_suspended] y"


def test_communication_error_accepts_reason_override():
    err = CommunicationError("upstream broke", reason=ErrorReason.PROTOCOL_BROKEN)
    assert err.reason == ErrorReason.PROTOCOL_BROKEN
    assert err.message == "upstream broke"


def test_pronote_integration_error_stores_reason_and_message():
    err = PronoteIntegrationError(ErrorReason.SESSION_EXPIRED, "token expired")
    assert err.reason == ErrorReason.SESSION_EXPIRED
    assert err.message == "token expired"


# ---------------------------------------------------------------------------
# WR-05: redact() — pronotepy can echo URL/credentials in str(err); these
# unit tests lock the redaction surface so a future leak (e.g. a 500 with
# request body echoed back) is scrubbed before reaching HA logs.
# ---------------------------------------------------------------------------


def test_redact_strips_password_kv():
    assert "secret" not in redact("login failed: password=secret")
    assert "<redacted>" in redact("login failed: password=secret")


def test_redact_strips_token_kv():
    out = redact("auth fail token=abc123XYZ.-_=+/ for user")
    assert "abc123XYZ" not in out
    assert "<redacted>" in out


def test_redact_strips_authorization_header_echo():
    out = redact("Server replied: Authorization: Bearer eyJhbGciOi.qq")
    assert "eyJ" not in out
    assert "<redacted>" in out


def test_redact_is_idempotent_on_clean_messages():
    msg = "Your IP address is suspended for 24h"
    assert redact(msg) == msg


def test_typed_exceptions_can_be_built_from_redacted_message():
    raw = "login failed: password=hunter2"
    err = AuthError(redact(raw))
    assert "hunter2" not in err.message
    assert "hunter2" not in str(err)
