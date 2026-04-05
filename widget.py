"""
PyQt6 frameless todo widget and Windows desktop-layer parenting (WorkerW / Progman).

Desktop pinning overview (Windows 10/11):
- The visible desktop wallpaper lives under a hidden "WorkerW" window that owns
  the "SHELLDLL_DefView" folder view for desktop icons.
- We send message 0x052C to the Program Manager ("Progman") so the shell creates
  the expected WorkerW hierarchy, then find the visible WorkerW that hosts
  SHELLDLL_DefView and SetParent() our HWND under it.
- The widget then paints above the wallpaper, stays visible when other apps are
  minimized, and remains clickable (unlike a pure wallpaper draw).
"""

from __future__ import annotations

import sys
from datetime import date
from typing import Optional

from PyQt6.QtCore import QDate, QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QGuiApplication, QMouseEvent, QScreen
from PyQt6.QtWidgets import (
    QCalendarWidget,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .database import Database
from .styles import application_stylesheet
from .task_service import TaskService, TaskViewModel
from .utils import format_display_date, get_active_day


DEFAULT_WIDTH = 320
DEFAULT_HEIGHT = 500


def _get_workerw_behind_shell() -> Optional[int]:
    """
    Locate the WorkerW window that sits behind desktop icons.

    Returns HWND as int, or None if the shell layout cannot be resolved.
    """
    try:
        import win32con
        import win32gui
    except ImportError:
        return None

    progman = win32gui.FindWindow("Progman", None)
    if not progman:
        return None

    # 0x052C: undocumented message used by wallpaper engines; forces WorkerW setup.
    win32gui.SendMessageTimeout(
        progman, 0x052C, 0, 0, win32con.SMTO_NORMAL, 1000
    )

    candidates: list[int] = []

    def _enum(hwnd: int, _: object) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        shell_view = win32gui.FindWindowEx(hwnd, None, "SHELLDLL_DefView", None)
        if shell_view:
            candidates.append(hwnd)
        return True

    win32gui.EnumWindows(_enum, None)
    return candidates[0] if candidates else None


def pin_widget_to_desktop(widget: QWidget) -> bool:
    """
    Reparent the Qt window to the desktop WorkerW layer.

    Must run after the native window exists (e.g. after show()).
    """
    try:
        import win32gui
    except ImportError:
        return False

    parent_hwnd = _get_workerw_behind_shell()
    if not parent_hwnd:
        return False

    hwnd = int(widget.winId())
    win32gui.SetParent(hwnd, parent_hwnd)
    return True


class TaskEditDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], title: str, initial_due: date) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self._due = initial_due

        lay = QVBoxLayout(self)
        self._edit = QLineEdit(self)
        self._edit.setPlaceholderText("Task title")
        lay.addWidget(QLabel("Title"))
        lay.addWidget(self._edit)

        self._cal = QCalendarWidget(self)
        self._cal.setSelectedDate(
            QDate(initial_due.year, initial_due.month, initial_due.day)
        )
        self._cal.selectionChanged.connect(self._on_cal)
        lay.addWidget(QLabel("Due date"))
        lay.addWidget(self._cal)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _on_cal(self) -> None:
        qd = self._cal.selectedDate()
        self._due = date(qd.year(), qd.month(), qd.day())

    def set_task_title(self, text: str) -> None:
        self._edit.setText(text)

    def task_title(self) -> str:
        return self._edit.text().strip()

    def due_date(self) -> date:
        return self._due


class DatePickDialog(QDialog):
    """Pick which calendar day filters the task list."""

    def __init__(self, parent: Optional[QWidget], current: date) -> None:
        super().__init__(parent)
        self.setWindowTitle("View date")
        self.setModal(True)
        self._d = current
        lay = QVBoxLayout(self)
        self._cal = QCalendarWidget(self)
        self._cal.setSelectedDate(QDate(current.year, current.month, current.day))
        self._cal.selectionChanged.connect(self._sync)
        lay.addWidget(self._cal)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _sync(self) -> None:
        qd = self._cal.selectedDate()
        self._d = date(qd.year(), qd.month(), qd.day())

    def selected_date(self) -> date:
        return self._d


class TaskRowWidget(QFrame):
    toggled = pyqtSignal(int, bool)
    edit_clicked = pyqtSignal(int)
    delete_clicked = pyqtSignal(int)

    def __init__(self, vm: TaskViewModel, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._task_id = vm.row.id
        self._apply_style(vm)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(8)

        self._check = QCheckBox(self)
        self._check.setObjectName("TaskCheck")
        self._check.setChecked(vm.row.completed)
        self._check.toggled.connect(self._on_toggle)

        mid = QVBoxLayout()
        mid.setSpacing(2)

        self._title = QLabel(vm.row.title, self)
        # QLabel defaults to min width = full text width; that forces horizontal scroll.
        self._title.setWordWrap(True)
        self._title.setMinimumWidth(0)
        self._title.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self._meta = QLabel(self._format_meta(vm), self)
        self._meta.setObjectName("TaskMeta")
        self._meta.setWordWrap(True)
        self._meta.setMinimumWidth(0)
        self._meta.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self._badge = QLabel("OVERDUE", self)
        self._badge.setObjectName("OverdueBadge")
        self._badge.setVisible(bool(vm.overdue_label))
        self._badge.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self._badge.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        self._apply_title_style(vm)

        title_row = QHBoxLayout()
        title_row.setSpacing(0)
        title_row.addWidget(self._title, 1)

        # Badge on its own row so long titles wrap without competing for width.
        badge_row = QHBoxLayout()
        badge_row.setSpacing(0)
        badge_row.addStretch(1)
        badge_row.addWidget(self._badge, 0, Qt.AlignmentFlag.AlignRight)

        mid.addLayout(title_row)
        mid.addLayout(badge_row)
        mid.addWidget(self._meta)

        self.setMinimumWidth(0)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        btn_col = QVBoxLayout()
        btn_col.setSpacing(2)
        edit_btn = QPushButton("✎", self)
        edit_btn.setObjectName("IconButton")
        edit_btn.setToolTip("Edit task")
        edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self._task_id))
        del_btn = QPushButton("×", self)
        del_btn.setObjectName("IconButton")
        del_btn.setToolTip("Delete task")
        del_btn.clicked.connect(lambda: self.delete_clicked.emit(self._task_id))
        btn_col.addWidget(edit_btn)
        btn_col.addWidget(del_btn)

        outer.addWidget(self._check, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(mid, 1)
        outer.addLayout(btn_col)

    def _apply_style(self, vm: TaskViewModel) -> None:
        if vm.is_overdue:
            self.setObjectName("TaskRowFrameOverdue")
        else:
            self.setObjectName("TaskRowFrame")

    def _apply_title_style(self, vm: TaskViewModel) -> None:
        if vm.row.completed:
            self._title.setObjectName("TaskTitleDone")
        elif vm.is_overdue:
            self._title.setObjectName("TaskTitleOverdue")
        else:
            self._title.setObjectName("TaskTitle")

    @staticmethod
    def _format_meta(vm: TaskViewModel) -> str:
        d = vm.row.due_date.strftime("%Y-%m-%d")
        parts = [f"Due: {d}"]
        if vm.row.rollover_count > 0:
            parts.append(f"Rolled: {vm.row.rollover_count}")
        return "  ·  ".join(parts)

    def _on_toggle(self, checked: bool) -> None:
        self.toggled.emit(self._task_id, checked)


class TodoWidgetWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._db = Database()
        self._service = TaskService(self._db)
        self._view_date: Optional[date] = None  # None => follow active day
        self._drag_pos: Optional[QPoint] = None

        self.setObjectName("TodoGlassRoot")
        self.setWindowTitle("Today's Tasks")
        self.setFixedSize(DEFAULT_WIDTH, DEFAULT_HEIGHT)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Window
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._build_ui()
        self._place_top_right()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(60_000)
        self._refresh_timer.timeout.connect(self.refresh_all)
        self._refresh_timer.start()

        self.refresh_all()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        header = QVBoxLayout()
        header.setSpacing(2)
        self._hdr_title = QLabel("Today's Tasks", self)
        self._hdr_title.setObjectName("HeaderTitle")
        self._hdr_date = QLabel("", self)
        self._hdr_date.setObjectName("HeaderDate")
        header.addWidget(self._hdr_title)
        header.addWidget(self._hdr_date)
        root.addLayout(header)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._list_host = QWidget(self)
        self._list_host.setMinimumWidth(0)
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(0, 0, 4, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch(1)
        self._scroll.setWidget(self._list_host)
        self._scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self._scroll, 1)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self._btn_add = QPushButton("Add task", self)
        self._btn_add.setObjectName("ToolbarButton")
        self._btn_add.clicked.connect(self._on_add)
        self._btn_date = QPushButton("Date", self)
        self._btn_date.setObjectName("ToolbarButton")
        self._btn_date.setToolTip("Choose which day to view (defaults to active day)")
        self._btn_date.clicked.connect(self._on_pick_date)
        self._btn_refresh = QPushButton("Refresh", self)
        self._btn_refresh.setObjectName("ToolbarButton")
        self._btn_refresh.clicked.connect(self.refresh_all)
        bar.addWidget(self._btn_add, 1)
        bar.addWidget(self._btn_date, 1)
        bar.addWidget(self._btn_refresh, 1)
        root.addLayout(bar)

    def _place_top_right(self) -> None:
        screen = self.windowHandle().screen() if self.windowHandle() else None
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        assert screen is not None
        geo = screen.availableGeometry()
        margin = 12
        x = geo.right() - DEFAULT_WIDTH - margin + 1
        y = geo.top() + margin
        self.move(x, y)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if getattr(self, "_desktop_pin_handled", False):
            return
        self._desktop_pin_handled = True
        # Native HWND exists after show; attach once to desktop WorkerW / Progman chain.
        ok = pin_widget_to_desktop(self)
        if not ok:
            # Without pywin32 or if shell layout fails, stay usable as a bottom-most tool window.
            self.hide()
            self.setWindowFlags(
                self.windowFlags() | Qt.WindowType.WindowStaysOnBottomHint
            )
            self.show()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            # Drag from header area only (top 56 px).
            if event.position().y() <= 56:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def refresh_all(self) -> None:
        self._service.apply_day_rollover_if_needed()
        view = self._service.get_view_day(self._view_date)
        active = get_active_day()
        if self._view_date is None:
            self._hdr_date.setText(
                f"{format_display_date(active)}  ·  Active day (3:00 rollover)"
            )
        else:
            self._hdr_date.setText(
                f"{format_display_date(view)}  ·  Picked view (active: {active.isoformat()})"
            )

        # Layout keeps a trailing stretch; remove task rows from the front.
        while self._list_layout.count() > 1:
            it = self._list_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()

        models = self._service.list_for_view(view)
        for vm in models:
            row = TaskRowWidget(vm, self._list_host)
            row.toggled.connect(self._on_row_toggled)
            row.edit_clicked.connect(self._on_row_edit)
            row.delete_clicked.connect(self._on_row_delete)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)

    def _on_row_toggled(self, task_id: int, completed: bool) -> None:
        self._service.set_completed(task_id, completed)
        self.refresh_all()

    def _on_row_edit(self, task_id: int) -> None:
        row = self._service.get_task(task_id)
        if not row:
            return
        dlg = TaskEditDialog(self, "Edit task", row.due_date)
        dlg.set_task_title(row.title)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.refresh_all()
            return
        title = dlg.task_title()
        if not title:
            QMessageBox.warning(self, "Task", "Title cannot be empty.")
            self.refresh_all()
            return
        self._service.edit_task(task_id, title=title, due_date=dlg.due_date())
        self.refresh_all()

    def _on_row_delete(self, task_id: int) -> None:
        self._service.delete_task(task_id)
        self.refresh_all()

    def _on_add(self) -> None:
        view = self._service.get_view_day(self._view_date)
        dlg = TaskEditDialog(self, "Add task", view)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        title = dlg.task_title()
        if not title:
            QMessageBox.warning(self, "Task", "Title cannot be empty.")
            return
        self._service.add_task(title, dlg.due_date())
        self.refresh_all()

    def _on_pick_date(self) -> None:
        current = self._service.get_view_day(self._view_date)
        dlg = DatePickDialog(self, current)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        picked = dlg.selected_date()
        active = get_active_day()
        if picked == active:
            self._view_date = None
        else:
            self._view_date = picked
        self.refresh_all()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._refresh_timer.stop()
        super().closeEvent(event)


def run_widget() -> int:
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(application_stylesheet())

    w = TodoWidgetWindow()
    w.show()
    return app.exec()
