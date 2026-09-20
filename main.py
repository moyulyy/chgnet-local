"""ChgNet Studio - entry point.

A local desktop GUI (PySide6 + QtWebEngine + 3Dmol.js + ASE) that drives the
bundled ChgNetCalculater command line scripts through a separate Python
interpreter that has chgnet + torch installed.

Run with the bundled launcher (it auto-detects the compute environment)::

    run.bat

or with any Python that has the GUI dependencies installed::

    python main.py

The compute interpreter is resolved from ``CHGNET_PYTHON``, the saved setting,
or an auto-detected conda environment named ``CHGNET_ENV`` (default chem_env);
see ``app/config.py`` and the README's "安装与配置" section.
"""

from __future__ import annotations

import os
import shutil
import sys

# Let Chromium fall back to its software renderer when no usable GPU is
# available, so the 3D view never ends up blank.
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--enable-unsafe-swiftshader")

# QtWebEngine must be imported before the QApplication is created.
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401,E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QFont, QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.main_window import MainWindow  # noqa: E402
from app.styles import qss  # noqa: E402

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ICON = os.path.join(PROJECT_DIR, "assets", "app.ico")


def _ensure_3dmol() -> None:
    """Make sure ``3Dmol-min.js`` sits next to ``viewer/viewer.html``."""
    target = os.path.join(PROJECT_DIR, "3Dmol-min.js")
    if os.path.exists(target):
        return
    for folder in (os.getcwd(), PROJECT_DIR, os.path.dirname(PROJECT_DIR)):
        candidate = os.path.join(folder, "3Dmol-min.js")
        if os.path.exists(candidate):
            try:
                shutil.copyfile(candidate, target)
            except OSError:
                pass
            return


def _set_windows_app_id() -> None:
    """Use our own taskbar icon instead of python.exe's."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ChgNet.Studio")
    except Exception:  # pragma: no cover
        pass


def main() -> int:
    _ensure_3dmol()
    _set_windows_app_id()

    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    app.setApplicationName("ChgNet Studio")
    app.setApplicationDisplayName("ChgNet Studio")
    app.setOrganizationName("ChgNet")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 9))
    app.setStyleSheet(qss())

    if os.path.exists(ICON):
        app.setWindowIcon(QIcon(ICON))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
