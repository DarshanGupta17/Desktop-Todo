"""
Todo Desktop Widget — entry point.

Run from the parent folder (e.g. ``Todo Widget``)::

    python -m todo_widget.main

On uncaught startup/runtime Python exceptions, the process retries up to five
times with a short backoff, then exits with code 1.

Dependencies::

    pip install PyQt6 pywin32

Optional: install shortcuts (requires pywin32 ``WScript.Shell`` / ``CreateShortcut``).
For Desktop path resolution, install ``winshell`` (recommended with OneDrive Desktop)::

    pip install winshell

    python -m todo_widget.main --install-autostart
    python -m todo_widget.main --install-desktop-shortcut

---------------------------------------------------------------------------
Packaging to a single .exe with PyInstaller
---------------------------------------------------------------------------

From the project parent directory (the folder that contains the ``todo_widget``
package), install PyInstaller and build::

    pip install pyinstaller
    pyinstaller --onefile --windowed --name TodoWidget -m todo_widget.main

Minimal form (from inside ``todo_widget``, after fixing imports to match)::

    pyinstaller --onefile --windowed main.py

Or, if you prefer pointing at this file directly from the parent folder::

    pyinstaller --onefile --windowed todo_widget/main.py

For a one-file bundle, ensure ``--paths`` includes the parent of ``todo_widget``
so imports resolve, e.g.::

    pyinstaller --onefile --windowed --name TodoWidget ^
        --paths . ^
        -m todo_widget.main

After building, edit the Startup shortcut (or re-run with a small launcher) so
``Target`` is the generated ``TodoWidget.exe`` and ``Arguments`` are empty.

---------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import List, Optional

MAX_START_ATTEMPTS = 5

# OneDrive Desktop often rejects WshShortcut.Save in place; temp+move is more reliable.
DESKTOP_SHORTCUT_NAME = "TodoWidget.lnk"


def _project_parent() -> Path:
    return Path(__file__).resolve().parent.parent


def _desktop_folder_winshell() -> Optional[Path]:
    """Desktop folder via winshell (often matches Explorer; good with OneDrive)."""
    try:
        import winshell

        d = winshell.desktop()
        if d:
            return Path(d)
    except ImportError:
        pass
    except (OSError, RuntimeError):
        pass
    return None


def _desktop_folder() -> Optional[Path]:
    """Resolve the user's Desktop folder (handles OneDrive / localized names)."""
    ws = _desktop_folder_winshell()
    if ws is not None and ws.exists():
        return ws
    try:
        import win32com.client

        shell = win32com.client.Dispatch("WScript.Shell")
        desktop = shell.SpecialFolders("Desktop")
        if desktop:
            return Path(desktop)
    except ImportError:
        pass
    userprofile = os.environ.get("USERPROFILE", "")
    if userprofile:
        return Path(userprofile) / "Desktop"
    desktop = Path.home() / "Desktop"
    return desktop if desktop.exists() else None


def _desktop_candidate_folders() -> List[Path]:
    """Ordered list of folders to try for a visible Desktop shortcut."""
    folders: List[Path] = []
    seen: set[str] = set()

    def add(p: Optional[Path]) -> None:
        if p is None:
            return
        try:
            resolved = p.resolve()
        except OSError:
            resolved = p
        key = str(resolved).lower()
        if key in seen:
            return
        seen.add(key)
        if p.exists():
            folders.append(p)

    # Prefer winshell first (same API as Explorer uses for "Desktop" in many setups).
    add(_desktop_folder_winshell())
    add(_desktop_folder())
    up = os.environ.get("USERPROFILE", "")
    if up:
        add(Path(up) / "Desktop")
    pub = os.environ.get("PUBLIC", "")
    if pub:
        add(Path(pub) / "Desktop")
    return folders


def create_shortcut_at(shortcut_path: Path) -> bool:
    """
    Create a ``.lnk`` using Windows ``WScript.Shell`` ``CreateShortcut`` (pywin32).

    Sets Target to ``sys.executable``, Arguments to ``-m todo_widget.main``,
    and Working directory to the project parent (folder that contains
    ``todo_widget``).
    """
    try:
        import pywintypes
        import win32com.client
    except ImportError:
        return False

    root = _project_parent()
    shortcut_path = Path(shortcut_path)
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(suffix=".lnk")
    os.close(fd)
    tmp_path = Path(tmp_name)
    moved = False
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        sc = shell.CreateShortCut(str(tmp_path))
        sc.Targetpath = sys.executable
        sc.Arguments = "-m todo_widget.main"
        sc.WorkingDirectory = str(root)
        sc.IconLocation = sys.executable
        sc.WindowStyle = 1
        sc.Description = "Todo Desktop Widget"
        sc.save()
        # Move into final location (helps OneDrive / cloud Desktop folders).
        try:
            os.replace(str(tmp_path), str(shortcut_path))
        except OSError:
            shutil.move(str(tmp_path), str(shortcut_path))
        moved = True
        return True
    except pywintypes.com_error:
        return False
    except OSError:
        return False
    finally:
        if not moved and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def ensure_login_autostart_shortcut() -> bool:
    """
    Create ``TodoWidget.lnk`` in the per-user Startup folder
    (``shell:startup``).
    """
    appdata = Path(os.environ.get("APPDATA", ""))
    if not appdata:
        return False
    startup_dir = appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return create_shortcut_at(startup_dir / "TodoWidget.lnk")


def ensure_desktop_shortcut() -> Optional[Path]:
    """
    Create ``TodoWidget.lnk`` on the Desktop (first writable candidate folder).

    Tries shell Desktop, then ``%USERPROFILE%\\Desktop``, then ``%PUBLIC%\\Desktop``.
    """
    for desktop in _desktop_candidate_folders():
        path = desktop / DESKTOP_SHORTCUT_NAME
        if create_shortcut_at(path):
            return path
    return None


def _run_widget_with_retries() -> int:
    """Run the Qt event loop; on failure retry up to ``MAX_START_ATTEMPTS`` times."""
    from todo_widget.widget import run_widget

    last_exc: Optional[BaseException] = None
    for attempt in range(1, MAX_START_ATTEMPTS + 1):
        try:
            return run_widget()
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt >= MAX_START_ATTEMPTS:
                break
            time.sleep(0.5 * attempt)
    if last_exc is not None:
        traceback.print_exception(
            type(last_exc), last_exc, last_exc.__traceback__, file=sys.stderr
        )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Desktop Todo Widget")
    parser.add_argument(
        "--install-autostart",
        action="store_true",
        help="Create TodoWidget.lnk in the Startup folder (requires pywin32).",
    )
    parser.add_argument(
        "--install-desktop-shortcut",
        action="store_true",
        help=(
            f"Create {DESKTOP_SHORTCUT_NAME} on the Desktop (pywin32; "
            "optional: pip install winshell for Desktop path)."
        ),
    )
    args = parser.parse_args()

    parent = _project_parent()
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))

    if args.install_autostart or args.install_desktop_shortcut:
        failed = False
        if args.install_autostart:
            if ensure_login_autostart_shortcut():
                print(f"Startup shortcut created: {sys.executable} -m todo_widget.main")
            else:
                print(
                    "Could not create Startup shortcut (install pywin32: pip install pywin32).",
                    file=sys.stderr,
                )
                failed = True
        if args.install_desktop_shortcut:
            desk_path = ensure_desktop_shortcut()
            if desk_path is not None:
                print(f"Desktop shortcut created: {desk_path}")
            else:
                print(
                    "Could not create Desktop shortcut (install pywin32, or Desktop path missing).",
                    file=sys.stderr,
                )
                failed = True
        return 1 if failed else 0

    return _run_widget_with_retries()


if __name__ == "__main__":
    sys.exit(main())
