"""Settings store for ChgNet Studio.

Everything is persisted as JSON in the user's home directory so the GUI can
remember the interpreter / script directory / last used folders and the last
parameters entered for every task.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Optional

# The project root is the folder that contains ``app/`` (and ``ChgNetCalculater/``).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".chgnet_studio.json")

#: interpreter that ships with a working chgnet + torch + CUDA install
DEFAULT_PYTHON = r"D:\miniconda3\envs\chem_env\python.exe"

DEFAULTS: Dict[str, Any] = {
    "python_exe": DEFAULT_PYTHON,
    #: root of the ChgNetCalculater scripts (contains chgnet-opt / chgnet-aimd ...)
    "project_dir": os.path.join(PROJECT_ROOT, "ChgNetCalculater"),
    "last_dir": "",
    # ---- task defaults ---------------------------------------------------
    "relax_type": "bulk",
    "relax_max_steps": 2000,
    "relax_fmax": 0.02,
    "aimd_temperature": 300.0,
    "aimd_timestep": 1.0,
    "aimd_steps": 1000,
    "aimd_loginterval": 1,
    "aimd_ensemble": "nvt",
    "aimd_thermostat": "Nose-Hoover",
    "freq_delta": 0.015,
    "freq_nfree": 2,
    "freq_temperature": 298.15,
    "neb_fmax": 0.05,
    "neb_max_steps": 2000,
    "neb_spring": 0.1,
    "neb_climb": True,
}


def load_config() -> Dict[str, Any]:
    data = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            stored = json.load(fh)
        if isinstance(stored, dict):
            data.update(stored)
    except (OSError, ValueError):
        pass
    return data


def save_config(data: Dict[str, Any]) -> None:
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in data.items() if k in DEFAULTS})
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, ensure_ascii=False, indent=2)
    except OSError:
        pass


def resolve_python(config: Dict[str, Any]) -> str:
    """Return an existing interpreter, falling back to the current one."""
    candidates = [str(config.get("python_exe", "")).strip(), DEFAULT_PYTHON,
                  sys.executable]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    return sys.executable


def resolve_project_dir(config: Dict[str, Any]) -> Optional[str]:
    """Return the folder holding the ChgNetCalculater scripts (or ``None``)."""
    candidate = str(config.get("project_dir", "")).strip()
    if candidate and os.path.isdir(candidate):
        return candidate
    fallback = os.path.join(PROJECT_ROOT, "ChgNetCalculater")
    return fallback if os.path.isdir(fallback) else None


__all__ = ["load_config", "save_config", "resolve_python", "resolve_project_dir",
           "CONFIG_PATH", "DEFAULTS", "DEFAULT_PYTHON", "PROJECT_ROOT"]
