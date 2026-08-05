"""Contract tests for api/_strip.py (D-24, C-05)."""

# ruff: noqa: SLF001
# Asserting back-ref nullification REQUIRES reading the private attributes
# (``_session`` / ``_client`` / ``_pronote``) the walker is supposed to clear.
# The whole point of this test module is to verify that private-member state.

from __future__ import annotations

from types import SimpleNamespace

from custom_components.ha_pronote.api._strip import strip_client_refs


class _FakePronotepyObj:
    """Stand-in for a pronotepy object with the documented back-refs."""

    def __init__(self) -> None:
        self.client = object()
        self._session = object()
        self._client = object()
        self._pronote = object()
        self.subject = "Mathématiques"


def test_strip_drops_client_back_ref():
    obj = _FakePronotepyObj()
    strip_client_refs(obj)
    assert obj.client is None
    assert obj._session is None
    assert obj._client is None
    assert obj._pronote is None
    assert obj.subject == "Mathématiques"


def test_strip_returns_same_object():
    obj = _FakePronotepyObj()
    assert strip_client_refs(obj) is obj


def test_strip_handles_object_without_client_ref():
    ns = SimpleNamespace(subject="X")
    # must not raise
    strip_client_refs(ns)
    assert ns.subject == "X"


def test_strip_tolerates_slot_only_object():
    """Pronotepy uses ``autoslot``; mutating a missing slot can raise.

    The walker must catch ``AttributeError`` / ``TypeError`` and continue.
    """

    class _Slotted:
        __slots__ = ("subject",)

        def __init__(self) -> None:
            self.subject = "Maths"

    s = _Slotted()
    # Should not raise even though the slotted object has no ``client`` slot.
    strip_client_refs(s)
    assert s.subject == "Maths"
