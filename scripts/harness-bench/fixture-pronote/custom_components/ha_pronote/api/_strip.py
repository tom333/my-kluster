"""Private — imported only by api/fetcher.py. Defense-in-depth against pronotepy back-refs (Anti-Pattern 5)."""

from __future__ import annotations

from typing import Any

_BACK_REF_NAMES = ("client", "_session", "_client", "_pronote")

_SWALLOWED_EXC = (AttributeError, TypeError)


def strip_client_refs(obj: Any) -> Any:
    """Null out pronotepy back-references on a fetched object (D-24, C-05).

    Pronotepy attaches large ``client`` / ``_session`` / ``_client`` /
    ``_pronote`` back-pointers on each ``Lesson`` / ``Grade`` / ``Information``
    object. Those break JSON serialization and bloat memory. The fetcher's
    field-by-field copy is the primary defense; this walker is the
    defense-in-depth net (Anti-Pattern 5).

    The walker is silent when an attribute is missing (``hasattr`` check) and
    tolerant of slot-only objects (``autoslot``) that forbid arbitrary mutation
    — those raise ``AttributeError`` / ``TypeError`` which we swallow.

    Args:
        obj: Any pronotepy data object (or a plain dataclass — no-op then).

    Returns:
        The same object, with the four back-ref attributes set to ``None``
        wherever they exist.
    """
    for attr in _BACK_REF_NAMES:
        if hasattr(obj, attr):
            try:
                setattr(obj, attr, None)
            except _SWALLOWED_EXC:
                # Slot-only objects without this slot, or read-only descriptors:
                # there's nothing to drop here, move on.
                continue
    return obj
