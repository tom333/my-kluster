"""Spécification exécutable de taskmgr. NE PAS MODIFIER."""

from datetime import date

import pytest

from taskmgr import (
    TaskStore,
    by_tag,
    completion_percent,
    days_until,
    done,
    highest,
    is_overdue,
    pending,
    sort_by_priority,
    summary_line,
)


def make_store():
    store = TaskStore()
    store.add("courses", priority=2, tags=["maison"])
    store.add("rapport", priority=1, tags=["boulot", "urgent"])
    store.add("vidange", priority=3, tags=["voiture"])
    return store


# --- store ---------------------------------------------------------------


def test_add_returns_the_id_of_the_task_it_created():
    store = TaskStore()
    first = store.add("a")
    second = store.add("b")
    assert first == 1
    assert second == 2
    assert store.get(first)["title"] == "a"
    assert store.get(second)["title"] == "b"


def test_complete_marks_the_task_done():
    store = make_store()
    task = store.complete(1)
    assert task["done"] is True
    assert store.get(1)["done"] is True


def test_all_is_sorted_by_id_and_count_matches():
    store = make_store()
    assert [task["id"] for task in store.all()] == [1, 2, 3]
    assert store.count() == 3


def test_remove_then_get_returns_none():
    store = make_store()
    store.remove(2)
    assert store.get(2) is None
    with pytest.raises(KeyError):
        store.remove(2)


# --- filters -------------------------------------------------------------


def test_by_tag_keeps_tasks_that_carry_the_tag():
    tasks = make_store().all()
    titles = [task["title"] for task in by_tag(tasks, "boulot")]
    assert titles == ["rapport"]


def test_by_tag_returns_empty_for_unknown_tag():
    tasks = make_store().all()
    assert by_tag(tasks, "inconnu") == []


def test_pending_and_done_partition_the_list():
    store = make_store()
    store.complete(2)
    tasks = store.all()
    assert [task["title"] for task in pending(tasks)] == ["courses", "vidange"]
    assert [task["title"] for task in done(tasks)] == ["rapport"]


# --- priority ------------------------------------------------------------


def test_highest_returns_priority_one_because_one_is_the_top():
    tasks = make_store().all()
    assert highest(tasks)["title"] == "rapport"


def test_highest_of_empty_list_is_none():
    assert highest([]) is None


def test_highest_breaks_ties_on_smallest_id():
    tasks = [
        {"id": 5, "title": "b", "priority": 1, "tags": [], "done": False},
        {"id": 2, "title": "a", "priority": 1, "tags": [], "done": False},
    ]
    assert highest(tasks)["id"] == 2


def test_sort_by_priority_puts_the_top_first():
    tasks = make_store().all()
    assert [task["title"] for task in sort_by_priority(tasks)] == [
        "rapport",
        "courses",
        "vidange",
    ]


# --- report --------------------------------------------------------------


def test_completion_percent_rounds_to_nearest():
    tasks = [
        {"id": index, "title": "t", "priority": 2, "tags": [], "done": index < 3}
        for index in range(7)
    ]
    # 3 sur 7 = 42.857... -> 43 en arrondi au plus proche, 42 en troncature
    assert completion_percent(tasks) == 43


def test_completion_percent_of_empty_list_is_zero():
    assert completion_percent([]) == 0


def test_summary_line_format():
    tasks = [
        {"id": index, "title": "t", "priority": 2, "tags": [], "done": index < 3}
        for index in range(7)
    ]
    assert summary_line(tasks) == "3/7 terminees (43%)"


# --- dates ---------------------------------------------------------------


def test_days_until_is_positive_for_a_future_due_date():
    assert days_until(date(2026, 8, 10), date(2026, 8, 1)) == 9


def test_days_until_is_zero_on_the_due_day():
    assert days_until(date(2026, 8, 1), date(2026, 8, 1)) == 0


def test_days_until_is_negative_once_past():
    assert days_until(date(2026, 7, 30), date(2026, 8, 1)) == -2


def test_is_overdue_is_false_on_the_due_day():
    assert is_overdue(date(2026, 8, 1), date(2026, 8, 1)) is False


def test_is_overdue_is_true_after_the_due_day():
    assert is_overdue(date(2026, 7, 30), date(2026, 8, 1)) is True
