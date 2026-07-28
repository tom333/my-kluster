"""Calculs de dates. Aucune horloge système : la date du jour est toujours passée
en argument, pour que les résultats soient reproductibles."""

from datetime import date


def days_until(due, today):
    """Nombre de jours entiers restants avant l'échéance.

    Positif si l'échéance est dans le futur, 0 le jour même, négatif si passée.
    """
    return (today - due).days


def is_overdue(due, today):
    """Vrai si l'échéance est strictement dépassée. Le jour même n'est pas en retard."""
    return days_until(due, today) <= 0


def parse_iso(text):
    """Convertit 'AAAA-MM-JJ' en date."""
    year, month, day = (int(part) for part in text.split("-"))
    return date(year, month, day)
