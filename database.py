"""
SQLite persistence for tasks. UI layers must not import sqlite3 directly.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Generator, List, Optional


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    due_date DATE NOT NULL,
    completed INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    rollover_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass
class TaskRow:
    id: int
    title: str
    due_date: date
    completed: bool
    created_at: datetime
    completed_at: Optional[datetime]
    rollover_count: int


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if s is None:
        return None
    text = str(s).strip().replace(" ", "T", 1)
    return datetime.fromisoformat(text)


class Database:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        base = Path.home() / ".todo_widget"
        base.mkdir(parents=True, exist_ok=True)
        self._path = db_path or (base / "tasks.db")
        self._init_schema()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def get_meta(self, key: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM app_meta WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO app_meta (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def insert_task(
        self,
        title: str,
        due_date: date,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO tasks (title, due_date, completed, rollover_count)
                VALUES (?, ?, 0, 0)
                """,
                (title.strip(), due_date.isoformat()),
            )
            return int(cur.lastrowid)

    def update_task(
        self,
        task_id: int,
        title: Optional[str] = None,
        due_date: Optional[date] = None,
        completed: Optional[bool] = None,
    ) -> None:
        fields: List[str] = []
        values: List[object] = []
        if title is not None:
            fields.append("title = ?")
            values.append(title.strip())
        if due_date is not None:
            fields.append("due_date = ?")
            values.append(due_date.isoformat())
        if completed is not None:
            fields.append("completed = ?")
            values.append(1 if completed else 0)
            if completed:
                fields.append("completed_at = ?")
                values.append(datetime.now().isoformat(timespec="seconds"))
            else:
                fields.append("completed_at = NULL")
        if not fields:
            return
        values.append(task_id)
        sql = f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?"
        with self._connect() as conn:
            conn.execute(sql, values)

    def increment_rollover(self, task_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET rollover_count = rollover_count + 1 WHERE id = ?",
                (task_id,),
            )

    def delete_task(self, task_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    def fetch_task(self, task_id: int) -> Optional[TaskRow]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            return self._row_to_task(row) if row else None

    def fetch_tasks_for_list(self, view_day: date) -> List[TaskRow]:
        """
        Tasks due on view_day, plus incomplete tasks with due_date before view_day (overdue).
        """
        vd = view_day.isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE due_date = ?
                   OR (completed = 0 AND due_date < ?)
                ORDER BY completed ASC, due_date ASC, id ASC
                """,
                (vd, vd),
            ).fetchall()
            return [self._row_to_task(r) for r in rows]

    def all_tasks(self) -> List[TaskRow]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY due_date ASC, id ASC"
            ).fetchall()
            return [self._row_to_task(r) for r in rows]

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> TaskRow:
        return TaskRow(
            id=int(row["id"]),
            title=str(row["title"]),
            due_date=_parse_date(str(row["due_date"])),
            completed=bool(row["completed"]),
            created_at=_parse_dt(str(row["created_at"])) or datetime.now(),
            completed_at=_parse_dt(row["completed_at"]),
            rollover_count=int(row["rollover_count"] or 0),
        )
