"""Gestion des priorités. Convention : 1 = la plus haute, 3 = la plus basse."""


def highest(tasks):
    """Retourne la tâche de plus haute priorité, ou None si la liste est vide.

    À priorité égale, la tâche d'identifiant le plus petit gagne.
    """
    if not tasks:
        return None
    return max(tasks, key=lambda task: (task["priority"], task["id"]))


def sort_by_priority(tasks):
    """Trie de la plus haute à la plus basse priorité, puis par identifiant."""
    return sorted(tasks, key=lambda task: (task["priority"], task["id"]))
