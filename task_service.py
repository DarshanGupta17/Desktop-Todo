"""
Business rules: active day, overdue display, rollover when the business day advances.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from .database import Database, TaskRow
from .utils import get_active_day


META_LAST_ROLLOVER_DAY = "last_rollover_active_day"


@dataclass
class TaskViewModel:
    """Task plus UI flags."""

    row: TaskRow
    is_overdue: bool
    overdue_label: bool


class TaskService:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get_active_day(self) -> date:
        return get_active_day()

    def get_view_day(self, selected: Optional[date]) -> date:
        return selected if selected is not None else self.get_active_day()

    def list_for_view(self, view_day: date) -> List[TaskViewModel]:
        rows = self._db.fetch_tasks_for_list(view_day)
        return [self._to_vm(r, view_day) for r in rows]

    def _to_vm(self, row: TaskRow, view_day: date) -> TaskViewModel:
        overdue = (
            not row.completed
            and row.due_date < view_day
        )
        return TaskViewModel(row=row, is_overdue=overdue, overdue_label=overdue)

    def apply_day_rollover_if_needed(self) -> None:
        """
        When the business day (get_active_day) advances, bump rollover_count once
        per task for incomplete work that was due before the new day.
        """
        today = self.get_active_day()
        last_s = self._db.get_meta(META_LAST_ROLLOVER_DAY)
        if last_s is None:
            self._db.set_meta(META_LAST_ROLLOVER_DAY, today.isoformat())
            return
        try:
            last = date.fromisoformat(last_s)
        except ValueError:
            self._db.set_meta(META_LAST_ROLLOVER_DAY, today.isoformat())
            return
        if last > today:
            self._db.set_meta(META_LAST_ROLLOVER_DAY, today.isoformat())
            return
        if last == today:
            return
        # Advance from last+1 through today, incrementing for tasks still incomplete
        # and due before each new active day.
        d = last
        while d < today:
            d = date.fromordinal(d.toordinal() + 1)
            for task in self._db.all_tasks():
                if task.completed:
                    continue
                if task.due_date < d:
                    self._db.increment_rollover(task.id)
        self._db.set_meta(META_LAST_ROLLOVER_DAY, today.isoformat())

    def add_task(self, title: str, due_date: date) -> int:
        return self._db.insert_task(title, due_date)

    def edit_task(
        self,
        task_id: int,
        title: Optional[str] = None,
        due_date: Optional[date] = None,
    ) -> None:
        self._db.update_task(task_id, title=title, due_date=due_date)

    def set_completed(self, task_id: int, completed: bool) -> None:
        self._db.update_task(task_id, completed=completed)

    def delete_task(self, task_id: int) -> None:
        self._db.delete_task(task_id)

    def get_task(self, task_id: int) -> Optional[TaskRow]:
        return self._db.fetch_task(task_id)
