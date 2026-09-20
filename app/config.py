"""Settings store for ChgNet Studio.

Everything is persisted as JSON in the user's home directory so the GUI can
remember the interpreter / script directory / last used folders and the last
parameters entered for every task.

The interpreter is never hard-wired to one machine: it is resolved from

1. the ``CHGNET_PYTHON`` environment variable,
2. the saved ``python_exe`` setting,
3. a conda environment named by ``CHGNET_ENV`` (default ``chem_env``) found in
   the common conda / anaconda install locations (or the active one),
4. the legacy path used during development,
5. the interpreter that is currently running the GUI.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional

# The project root is the folder that contains ``app/`` (and ``ChgNetCalculater/``).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".chgnet_studio.json")

#: environment variable that forces an exact interpreter (run.bat honours it too)
ENV_PYTHON_VAR = "CHGNET_PYTHON"
#: environment variable naming the conda environment that holds chgnet + torch
ENV_NAME_VAR = "CHGNET_ENV"
DEFAULT_ENV_NAME = "chem_env"

#: last-resort hint for machines that use the original development layout
DEFAULT_PYTHON = r"D:\miniconda3\envs\chem_env\python.exe"

DEFAULTS: Dict[str, Any] = {
    #: empty means "auto-detect"; set an explicit path to override detection
    "python_exe": "",
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


def _env_python_name() -> str:
    return "python.exe" if os.name == "nt" else "python"


def _conda_roots() -> List[str]:
    """Return likely conda / anaconda installation roots for this machine."""
    home = os.path.expanduser("~")
    roots = [
        os.environ.get("CONDA_PREFIX_1", ""),  # base env while another is active
        os.path.join(home, "miniconda3"),
        os.path.join(home, "Miniconda3"),
        os.path.join(home, "anaconda3"),
        os.path.join(home, "Anaconda3"),
    ]
    for var in ("LOCALAPPDATA", "ProgramData", "ProgramFiles"):
        base = os.environ.get(var, "")
        if base:
            roots += [
                os.path.join(base, "miniconda3"),
                os.path.join(base, "Miniconda3"),
                os.path.join(base, "anaconda3"),
                os.path.join(base, "Anaconda3"),
                os.path.join(base, "Continuum", "anaconda3"),
            ]
    roots += [
        r"C:\miniconda3",
        r"C:\anaconda3",
        r"D:\miniconda3",
        r"D:\anaconda3",
    ]
    return roots


def _detected_interpreters() -> List[str]:
    """Candidate interpreters discovered from the environment / known locations."""
    found: List[str] = []

    env_python = os.environ.get(ENV_PYTHON_VAR, "").strip()
    if env_python:
        found.append(env_python)

    conda_prefix = os.environ.get("CONDA_PREFIX", "").strip()
    if conda_prefix:
        found.append(os.path.join(conda_prefix, _env_python_name()))

    env_name = os.environ.get(ENV_NAME_VAR, "").strip() or DEFAULT_ENV_NAME
    for root in _conda_roots():
        if not root:
            continue
        if os.name == "nt":
            found.append(os.path.join(root, "envs", env_name, "python.exe"))
        else:
            found.append(os.path.join(root, "envs", env_name, "bin", "python"))
    return found


def resolve_python(config: Dict[str, Any]) -> str:
    """Return an existing interpreter, falling back to the current one."""
    candidates: List[str] = [
        os.environ.get(ENV_PYTHON_VAR, "").strip(),
        str(config.get("python_exe", "")).strip(),
    ]
    candidates.extend(_detected_interpreters())
    candidates.append(DEFAULT_PYTHON)
    candidates.append(sys.executable)
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
           "CONFIG_PATH", "DEFAULTS", "DEFAULT_PYTHON", "PROJECT_ROOT",
           "ENV_PYTHON_VAR", "ENV_NAME_VAR", "DEFAULT_ENV_NAME"]
