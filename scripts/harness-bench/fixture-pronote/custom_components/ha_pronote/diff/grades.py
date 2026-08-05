"""Grade diff -- first-poll skip + identity-key set difference (D-14, EVENT-02).

Identity key per grade: (subject, date, value) -- same pronotepy-raw string
value so a re-scored grade appears as new (acceptable; user sees it).
First-poll invariant: diff_grades(None, snapshot) -> [] (EVENT-04).

No try/except -- diff bugs surface raw in HA logs (project feedback: no silent exceptions).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .events import NewGrade

if TYPE_CHECKING:
    from custom_components.ha_pronote.api.models import Snapshot


def diff_grades(previous: Snapshot | None, new: Snapshot) -> list[NewGrade]:
    """Return new grades since the previous poll.

    Args:
        previous: Previous Snapshot, or None on first poll after restart.
        new: Current Snapshot.

    Returns:
        List of NewGrade events. Empty when previous is None (EVENT-04).
    """
    if previous is None:
        return []
    prev_keys = {(g.subject, g.date, g.value) for g in previous.grades}
    return [
        NewGrade(
            subject=g.subject,
            value=g.value,
            out_of=g.out_of,
            coefficient=g.coefficient,
            date=g.date,
        )
        for g in new.grades
        if (g.subject, g.date, g.value) not in prev_keys
    ]
