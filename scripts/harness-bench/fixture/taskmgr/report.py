"""Rapports textuels et statistiques."""


def completion_percent(tasks):
    """Pourcentage de tâches terminées, arrondi à l'entier le plus proche.

    Retourne 0 si la liste est vide.
    """
    if not tasks:
        return 0
    finished = len([task for task in tasks if task["done"]])
    return int(finished / len(tasks) * 100)


def summary_line(tasks):
    """Retourne une ligne de la forme '3/7 terminees (43%)'."""
    finished = len([task for task in tasks if task["done"]])
    return "{}/{} terminees ({}%)".format(
        finished, len(tasks), completion_percent(tasks)
    )
