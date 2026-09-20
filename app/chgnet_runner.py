"""Bridge between the GUI and the bundled ChgNetCalculater CLI scripts.

Every calculation is executed as a **separate process** using the configured
Python interpreter (by default ``D:\\miniconda3\\envs\\chem_env\\python.exe``).
That keeps the GUI process free of torch/chgnet imports (fast start-up) and
reuses the exact calculators that already ship with the project.

The scripts always work on a ``POSCAR`` file placed in a fresh job directory::

    <structure folder>/<timestamp>_<task>/
        POSCAR            (written by the GUI)
        CONTCAR / OSZICAR / XDATCAR / OUTCAR ...   (written by the script)
"""

from __future__ import annotations

import os
import subprocess
import threading
from datetime import datetime
from typing import Callable, Dict, List, Optional, Sequence, Tuple

#: task key -> (sub-folder inside ChgNetCalculater, script file)
TASK_SCRIPTS: Dict[str, Tuple[str, str]] = {
    "single_point": ("chgnet-opt", "singlepoint_runner.py"),
    "relax": ("chgnet-opt", "main.py"),
    "aimd": ("chgnet-aimd", "main.py"),
    "freq": ("chgnet-freq", "main.py"),
    "neb": ("chgnet-neb", "main.py"),
}


class RunnerError(RuntimeError):
    """Raised for configuration problems detected before launching a job."""


# ---------------------------------------------------------------------------
# paths / environment
# ---------------------------------------------------------------------------

def script_path(project_dir: str, key: str) -> str:
    sub, name = TASK_SCRIPTS[key]
    return os.path.join(project_dir, sub, name)


def new_job_dir(base_dir: str, key: str) -> str:
    """Create ``<base>/<timestamp>_<key>/`` and return its absolute path."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(base_dir, f"{stamp}_{key}")
    os.makedirs(path, exist_ok=True)
    return path


def _process_env() -> Dict[str, str]:
    env = os.environ.copy()
    # the scripts print Å / ✗ and unicode banners; force UTF-8 everywhere
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONUTF8"] = "1"
    return env


# ---------------------------------------------------------------------------
# command construction
# ---------------------------------------------------------------------------

def build_command(key: str, script: str, python_exe: str, device: str,
                  params: Dict[str, object]) -> List[str]:
    """Assemble the argv list for one task."""
    cmd = [python_exe, script]

    if key == "single_point":
        cmd += ["--input", "POSCAR", "--output", "CONTCAR",
                "--device", device or "auto"]
    elif key == "relax":
        cmd += ["--type", str(params.get("relax_type", "bulk")),
                "--input", "POSCAR", "--output", "CONTCAR",
                "--max-steps", str(int(params.get("max_steps", 2000))),
                "--fmax", _num(params.get("fmax", 0.02))]
    elif key == "aimd":
        cmd += ["--input", "POSCAR", "--output", "CONTCAR",
                "--temperature", _num(params.get("temperature", 300.0)),
                "--timestep", _num(params.get("timestep", 1.0)),
                "--steps", str(int(params.get("steps", 1000))),
                "--loginterval", str(int(params.get("loginterval", 1))),
                "--ensemble", str(params.get("ensemble", "nvt")),
                "--thermostat", str(params.get("thermostat", "Nose-Hoover"))]
    elif key == "freq":
        cmd += ["--input", "POSCAR",
                "--delta", _num(params.get("delta", 0.015)),
                "--nfree", str(int(params.get("nfree", 2))),
                "--temperature", _num(params.get("temperature", 298.15))]
    elif key == "neb":
        cmd += ["--work-dir", ".",
                "--fmax", _num(params.get("fmax", 0.05)),
                "--max-steps", str(int(params.get("max_steps", 2000))),
                "--spring-constant", _num(params.get("spring", 0.1)),
                "--climb", "True" if params.get("climb", True) else "False"]
        if params.get("dry_run"):
            cmd += ["--dry-run", "True"]
    else:  # pragma: no cover - guarded by the task catalogue
        raise RunnerError(f"未知的计算任务: {key}")
    return cmd


def _num(value: object) -> str:
    """Format a number the way the CLIs expect (no trailing noise)."""
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return str(value)


# ---------------------------------------------------------------------------
# process execution
# ---------------------------------------------------------------------------

def run_process(cmd: Sequence[str], cwd: str,
                on_line: Optional[Callable[[str], None]] = None,
                cancel: Optional[threading.Event] = None,
                timeout: Optional[float] = None) -> Tuple[int, List[str]]:
    """Run *cmd* in *cwd*, streaming stdout/stderr line by line.

    Returns ``(returncode, lines)``.  Cancellation terminates the child
    process group and returns ``-9``.
    """
    lines: List[str] = []
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    proc = subprocess.Popen(
        list(cmd),
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=_process_env(),
        creationflags=creationflags,
    )

    def _reader():
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            lines.append(line)
            if on_line is not None:
                try:
                    on_line(line)
                except Exception:  # noqa: BLE001 - never break reading
                    pass

    reader = threading.Thread(target=_reader, name="chgnet-stdout", daemon=True)
    reader.start()

    try:
        while True:
            try:
                code = proc.wait(timeout=0.4)
                break
            except subprocess.TimeoutExpired:
                if cancel is not None and cancel.is_set():
                    _terminate(proc)
                    code = proc.wait()
                    reader.join(timeout=2)
                    return -9, lines
    finally:
        reader.join(timeout=3)
        if proc.stdout is not None:
            proc.stdout.close()

    return int(code), lines


def _terminate(proc: subprocess.Popen) -> None:
    try:
        proc.terminate()
    except OSError:
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# environment probe (used by the settings sheet)
# ---------------------------------------------------------------------------

def probe_environment(python_exe: str, timeout: float = 180.0) -> Tuple[bool, str]:
    """Check that *python_exe* exists and can import chgnet + torch."""
    if not python_exe or not os.path.isfile(python_exe):
        return False, f"未找到 Python 解释器: {python_exe or '(空)'}"
    code = (
        "import chgnet, torch, pymatgen, ase, numpy\n"
        "print('chgnet', getattr(chgnet, '__version__', '?'))\n"
        "print('torch', torch.__version__, 'cuda', torch.cuda.is_available())\n"
    )
    try:
        proc = subprocess.run(
            [python_exe, "-c", code],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"探测环境失败: {exc}"
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        tail = " | ".join(detail[-3:]) if detail else "未知错误"
        return False, f"该环境缺少依赖: {tail}"
    info = " · ".join(line.strip() for line in proc.stdout.splitlines() if line.strip())
    return True, info or "环境可用"


__all__ = ["TASK_SCRIPTS", "RunnerError", "script_path", "new_job_dir",
           "build_command", "run_process", "probe_environment"]
