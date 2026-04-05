# Todo Desktop Widget

A Windows desktop todo widget (Python, PyQt6, SQLite, pywin32): frameless, translucent panel pinned to the desktop layer, tasks with due dates and 3:00 AM “business day” rollover.

---

## Requirements

- **Windows** 10 or 11  
- **Python 3.10+** recommended  
- Packages:

```bash
pip install PyQt6 pywin32
```

Optional (recommended for **Desktop** shortcut path / OneDrive):

```bash
pip install winshell
```

The installer uses **`winshell.desktop()`** when `winshell` is installed, then falls back to `WScript.Shell.SpecialFolders("Desktop")` and other paths.

---

## How to run the widget

The app must be started with the **project root** on Python’s import path. The project root is the folder that **contains** the `todo_widget` package (the parent of `todo_widget/`), e.g. `D:\Scripts\Todo Widget`.

### From the project root (recommended)

```bash
cd "D:\Scripts\Todo Widget"
python -m todo_widget.main
```

### From inside `todo_widget` (if you use `main.py` there)

Ensure the parent directory is on `PYTHONPATH`, or `cd` to the project root and use `-m` as above.

### Crash retries

If an uncaught Python exception occurs during startup or while `run_widget()` runs, the process **retries up to 5 times** with a short delay, then exits with code **1** and prints a traceback to stderr (visible if you run from a console).

---

## Shortcuts with `CreateShortcut` (pywin32)

Shortcuts are created with **Windows Script Host**: `WScript.Shell` → **`CreateShortcut`**. The code lives in `todo_widget/main.py` as **`create_shortcut_at(shortcut_path)`**, which sets:

| Property | Value |
|----------|--------|
| **Target** | `sys.executable` (your `python.exe` or frozen `.exe`) |
| **Arguments** | `-m todo_widget.main` (not `main.py` — keeps imports correct) |
| **Start in** | Project root (parent of `todo_widget`) |
| **Icon** | `IconLocation` = same as Target (Python icon) |

You need **pywin32** installed (`pip install pywin32`).

### Desktop shortcut (double-click to open)

Run **once** from the **project root**:

```bash
cd "D:\Scripts\Todo Widget"
python -m todo_widget.main --install-desktop-shortcut
```

This creates **`TodoWidget.lnk`** on your **Desktop**. The implementation writes the shortcut under **`%TEMP%`** first, then moves it into place, which avoids a common **OneDrive Desktop** error (`Unable to save shortcut` when saving directly to the cloud-backed folder).

If the first location fails, the installer tries **`%USERPROFILE%\Desktop`** and **`%PUBLIC%\Desktop`** in order.

Double-click **`TodoWidget.lnk`** anytime to launch the widget (shortcut description in Properties still shows “Todo Desktop Widget”).

### Startup folder (run at login)

```bash
python -m todo_widget.main --install-autostart
```

Creates **`TodoWidget.lnk`** in:

`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`

So the widget starts when you sign in.

Install **both** at once:

```bash
python -m todo_widget.main --install-desktop-shortcut --install-autostart
```

### Manual shortcut (GUI)

1. Right-click Desktop → **New** → **Shortcut**  
2. Target: `"C:\Path\To\Python\python.exe" -m todo_widget.main`  
3. **Start in:** your project root (folder containing `todo_widget`)

### After PyInstaller (`.exe`)

Build your one-file app, then edit any `.lnk`:

- **Target:** full path to `TodoWidget.exe`  
- **Arguments:** *(empty)*  
- **Start in:** folder containing the `.exe` (if needed)

---

## Optional: autostart flags summary

| Command | Effect |
|---------|--------|
| `python -m todo_widget.main` | Run the widget |
| `python -m todo_widget.main --install-desktop-shortcut` | Create Desktop `TodoWidget.lnk` |
| `python -m todo_widget.main --install-autostart` | Create Startup `TodoWidget.lnk` |
| Both flags in one command | Creates both shortcuts in a single run |

---

## Packaging (PyInstaller)

From the **project root**:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name TodoWidget --paths . -m todo_widget.main
```

See the docstring at the top of `todo_widget/main.py` for more variants.

---

## Data storage

SQLite database: `%USERPROFILE%\.todo_widget\tasks.db`

---

## Project layout

```text
Todo Widget/                 ← project root (run -m from here)
    README.md
    todo_widget/
        main.py              ← entry point, shortcuts, retries
        widget.py
        database.py
        task_service.py
        utils.py
        styles.py
```
