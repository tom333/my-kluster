"""Information diff -- first-poll skip + identity-key set difference (D-14, EVENT-03).

Identity key per information: (info_id, date.date()) -- info_id is stable;
Information.date is a tz-aware datetime, call .date() per C-03 decision
(NewInformation.date is date not datetime -- ApexCharts granularity).
First-poll invariant: diff_notifications(None, snapshot) -> [] (EVENT-04).

No try/except -- diff bugs surface raw (project feedback: no silent exceptions).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .events import NewInformation

if TYPE_CHECKING:
    from custom_components.ha_pronote.api.models import Snapshot


def diff_notifications(previous: Snapshot | None, new: Snapshot) -> list[NewInformation]:
    """Return new informations since the previous poll.

    Args:
        previous: Previous Snapshot, or None on first poll after restart.
        new: Current Snapshot.

    Returns:
        List of NewInformation events. Empty when previous is None (EVENT-04).
    """
    if previous is None:
        return []
    prev_keys = {(i.info_id, i.date.date()) for i in previous.information}
    return [
        NewInformation(
            info_id=i.info_id,
            title=i.title,
            sender=i.sender,
            date=i.date.date(),  # C-03: Information.date is datetime; NewInformation.date is date
            excerpt=i.excerpt,
        )
        for i in new.information
        if (i.info_id, i.date.date()) not in prev_keys
    ]
