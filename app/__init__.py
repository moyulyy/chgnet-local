"""ChgNet Studio - a local PySide6 GUI for the bundled ChgNetCalculater.

The GUI never imports torch / chgnet itself: every calculation is delegated
to the existing command line scripts inside ``ChgNetCalculater/`` and runs in
a separately configured conda environment (auto-detected, or set through the
``CHGNET_PYTHON`` / ``CHGNET_ENV`` environment variables).
"""

__version__ = "1.0.0"
