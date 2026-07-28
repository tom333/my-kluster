"""Stockage des tâches en mémoire."""


class TaskStore:
    """Conserve des tâches indexées par identifiant entier croissant."""

    def __init__(self):
        self._tasks = {}
        self._next_id = 1

    def add(self, title, priority=2, tags=None):
        """Ajoute une tâche et retourne son identifiant."""
        task_id = self._next_id
        self._next_id += 1
        self._tasks[task_id] = {
            "id": task_id,
            "title": title,
            "priority": priority,
            "tags": list(tags or []),
            "done": False,
        }
        return self._next_id

    def get(self, task_id):
        """Retourne la tâche, ou None si absente."""
        return self._tasks.get(task_id)

    def all(self):
        """Retourne toutes les tâches, triées par identifiant croissant."""
        return [self._tasks[key] for key in sorted(self._tasks)]

    def complete(self, task_id):
        """Marque la tâche comme terminée et la retourne."""
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(task_id)
        task["done"] = False
        return task

    def remove(self, task_id):
        """Supprime la tâche. Lève KeyError si absente."""
        del self._tasks[task_id]

    def count(self):
        """Nombre de tâches stockées."""
        return len(self._tasks)
