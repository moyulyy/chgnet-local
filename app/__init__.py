"""ChgNet Studio - a local PySide6 GUI for the bundled ChgNetCalculater.

The GUI never imports torch / chgnet itself: every calculation is delegated
to the existing command line scripts inside ``ChgNetCalculater/`` and runs in
the configured conda environment (``D:\\miniconda3\\envs\\chem_env``).
"""

__version__ = "1.0.0"
