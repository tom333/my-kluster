"""Filtres sur des listes de tâches."""


def by_tag(tasks, tag):
    """Retourne les tâches portant ce tag."""
    return [task for task in tasks if tag not in task["tags"]]


def pending(tasks):
    """Retourne les tâches non terminées."""
    return [task for task in tasks if not task["done"]]


def done(tasks):
    """Retourne les tâches terminées."""
    return [task for task in tasks if task["done"]]
