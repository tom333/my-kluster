"""Contract tests for api/client.py error mapping (D-21, D-22, Pitfall 1, Pitfall 2)."""

from __future__ import annotations

import pronotepy
import pytest

from custom_components.ha_pronote.api import (
    AuthError,
    CommunicationError,
    ErrorReason,
    RateLimitedError,
    build_client,
    set_active_child,
)


def _make_init_raising(exc: BaseException):
    """Return a replacement ``__init__`` that ignores args and raises ``exc``."""

    def _raise(self, *_args, **_kwargs):
        raise exc

    return _raise


def _make_init_silent():
    """Return a replacement ``__init__`` that succeeds without HTTP."""

    def _ok(self, *_args, **_kwargs):
        # Do not call super().__init__() — pronotepy.Client may have parent
        # init that triggers HTTP; we just want a constructed instance.
        return None

    return _ok


def test_eleve_account_type_returns_pronotepy_client(monkeypatch):
    monkeypatch.setattr(pronotepy.Client, "__init__", _make_init_silent())
    monkeypatch.setattr(pronotepy.ParentClient, "__init__", _make_init_silent())
    client = build_client("https://example.com/pronote/eleve.html", "eleve", "u", "p")
    assert isinstance(client, pronotepy.Client)
    assert not isinstance(client, pronotepy.ParentClient)


def test_parent_account_type_returns_parent_client(monkeypatch):
    monkeypatch.setattr(pronotepy.Client, "__init__", _make_init_silent())
    monkeypatch.setattr(pronotepy.ParentClient, "__init__", _make_init_silent())
    client = build_client("https://example.com/pronote/parent.html", "parent", "u", "p")
    assert isinstance(client, pronotepy.ParentClient)


def test_ip_suspended_message_raises_rate_limited(monkeypatch):
    monkeypatch.setattr(
        pronotepy.Client,
        "__init__",
        _make_init_raising(pronotepy.PronoteAPIError("Your IP address is suspended")),
    )
    with pytest.raises(RateLimitedError) as excinfo:
        build_client("https://example.com/pronote/eleve.html", "eleve", "u", "p")
    assert excinfo.value.reason == ErrorReason.IP_SUSPENDED


def test_crypto_error_raises_auth_error(monkeypatch):
    monkeypatch.setattr(
        pronotepy.Client,
        "__init__",
        _make_init_raising(pronotepy.exceptions.CryptoError("Padding error")),
    )
    with pytest.raises(AuthError) as excinfo:
        build_client("https://example.com/pronote/eleve.html", "eleve", "u", "p")
    assert excinfo.value.reason == ErrorReason.AUTH_FAILED


def test_other_pronote_error_raises_communication_error(monkeypatch):
    monkeypatch.setattr(
        pronotepy.Client,
        "__init__",
        _make_init_raising(pronotepy.PronoteAPIError("Some other failure")),
    )
    with pytest.raises(CommunicationError) as excinfo:
        build_client("https://example.com/pronote/eleve.html", "eleve", "u", "p")
    assert excinfo.value.reason == ErrorReason.PROTOCOL_BROKEN


def test_os_error_raises_communication_error_server_down(monkeypatch):
    monkeypatch.setattr(
        pronotepy.Client,
        "__init__",
        _make_init_raising(OSError("network unreachable")),
    )
    with pytest.raises(CommunicationError) as excinfo:
        build_client("https://example.com/pronote/eleve.html", "eleve", "u", "p")
    assert excinfo.value.reason == ErrorReason.SERVER_DOWN


def test_communication_error_chains_original_via_from(monkeypatch):
    original = pronotepy.PronoteAPIError("Some other failure")
    monkeypatch.setattr(
        pronotepy.Client,
        "__init__",
        _make_init_raising(original),
    )
    with pytest.raises(CommunicationError) as excinfo:
        build_client("https://example.com/pronote/eleve.html", "eleve", "u", "p")
    assert excinfo.value.__cause__ is original


def test_auth_error_chains_original_via_from(monkeypatch):
    original = pronotepy.exceptions.CryptoError("Padding error")
    monkeypatch.setattr(
        pronotepy.Client,
        "__init__",
        _make_init_raising(original),
    )
    with pytest.raises(AuthError) as excinfo:
        build_client("https://example.com/pronote/eleve.html", "eleve", "u", "p")
    assert excinfo.value.__cause__ is original


# ---------------------------------------------------------------------------
# CR-04: set_active_child wraps client.set_child with the typed-error mapping
# so the 3 call sites (__init__.py, coordinator.py, config_flow.py) never see
# raw pronotepy exceptions.
# ---------------------------------------------------------------------------


class _FakeParentClient:
    """Stand-in for pronotepy.ParentClient.set_child with a programmable raise."""

    def __init__(self, raise_exc: BaseException | None = None) -> None:
        self._raise = raise_exc
        self.last_index: object | None = None
        # Phase 3 (5e1aae3) — set_active_child resolves int -> Child via
        # client.children[idx] before delegating to set_child. Configure a
        # list of 3 sentinel child objects so int=0/1/2 indices all resolve.
        self.children = [object(), object(), object()]

    def set_child(self, index: object) -> None:
        self.last_index = index
        if self._raise is not None:
            raise self._raise


def test_set_active_child_passes_index_through_on_success():
    fake = _FakeParentClient()
    set_active_child(fake, 2)
    # 5e1aae3 — int 2 is resolved to fake.children[2] before set_child runs.
    assert fake.last_index is fake.children[2]


def test_set_active_child_maps_crypto_error_to_auth_error():
    fake = _FakeParentClient(raise_exc=pronotepy.exceptions.CryptoError("session torn"))
    with pytest.raises(AuthError) as excinfo:
        set_active_child(fake, 0)
    assert excinfo.value.reason == ErrorReason.AUTH_FAILED


def test_set_active_child_maps_ip_suspended_to_rate_limited():
    fake = _FakeParentClient(raise_exc=pronotepy.PronoteAPIError("Your IP address is suspended for 24h"))
    with pytest.raises(RateLimitedError) as excinfo:
        set_active_child(fake, 0)
    assert excinfo.value.reason == ErrorReason.IP_SUSPENDED


def test_set_active_child_maps_other_pronote_error_to_communication_error():
    fake = _FakeParentClient(raise_exc=pronotepy.PronoteAPIError("Schema drift"))
    with pytest.raises(CommunicationError) as excinfo:
        set_active_child(fake, 0)
    assert excinfo.value.reason == ErrorReason.PROTOCOL_BROKEN


def test_set_active_child_maps_os_error_to_communication_error():
    fake = _FakeParentClient(raise_exc=OSError("network down"))
    with pytest.raises(CommunicationError) as excinfo:
        set_active_child(fake, 0)
    assert excinfo.value.reason == ErrorReason.SERVER_DOWN
