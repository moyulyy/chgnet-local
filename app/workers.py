"""Background worker: prepare a job folder, run a ChgNet script, parse output.

Running the calculator in a :class:`QThread` keeps the interface responsive
and lets the user cancel a long relaxation / AIMD / NEB run.
"""

from __future__ import annotations

import os
import re
import threading
import traceback
from typing import Any, Dict, Optional

from PySide6.QtCore import QThread, Signal

from .chgnet_runner import (RunnerError, build_command, new_job_dir,
                            run_process, script_path)
from .results import gather_result
from .structure_io import write_poscar


_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def _clean_line(text: str) -> str:
    """Drop ANSI colour codes and carriage-return progress junk."""
    if not text:
        return ""
    cleaned = _ANSI.sub("", text).replace("\r", " ")
    return cleaned.strip()


class Worker(QThread):
    """Execute one ChgNet calculation in a child process."""

    line = Signal(str, str)         # (request_id, output line)
    succeeded = Signal(str, str, object)   # (request_id, job_dir, result)
    failed = Signal(str, str, str)         # (request_id, job_dir, message)
    finished = Signal(str)                 # (request_id)

    def __init__(self, request_id: str, spec: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.request_id = request_id
        self.spec = spec
        self._cancel = threading.Event()
        self.job_dir: Optional[str] = None

    # ------------------------------------------------------------------ api
    def cancel(self):
        self._cancel.set()

    def is_cancelled(self) -> bool:
        return self._cancel.is_set()

    # --------------------------------------------------------------- helpers
    def _emit(self, text: str):
        cleaned = _clean_line(text)
        if cleaned:
            self.line.emit(self.request_id, cleaned)

    # ------------------------------------------------------------------ run
    def run(self):  # noqa: D401 - QThread entry point
        key = self.spec["key"]
        try:
            if self._cancel.is_set():
                return
            self.job_dir = self._prepare(key)
            self._emit(f"工作目录: {self.job_dir}")

            script = script_path(self.spec["project_dir"], key)
            if not os.path.isfile(script):
                raise RunnerError(f"未找到计算脚本: {script}")

            # every bundled calculator runs on CUDA (the GUI offers no device
            # switch any more)
            cmd = build_command(key, script, self.spec["python_exe"],
                                "cuda", self.spec["params"])
            self._emit("命令: " + " ".join(f'"{c}"' if " " in c else c for c in cmd[1:]))

            code, _lines = run_process(cmd, self.job_dir,
                                       on_line=self._emit, cancel=self._cancel)

            if self._cancel.is_set():
                self.failed.emit(self.request_id, self.job_dir, "任务已取消")
                return
            if code != 0:
                tail = self._tail()
                self.failed.emit(self.request_id, self.job_dir,
                                 f"计算进程退出码 {code}。\n{tail}")
                return

            result = gather_result(key, self.job_dir)
            self.succeeded.emit(self.request_id, self.job_dir, result)
        except Exception as exc:  # noqa: BLE001 - report, never crash
            detail = f"{type(exc).__name__}: {exc}"
            self._emit(detail)
            self._emit(traceback.format_exc())
            self.failed.emit(self.request_id, self.job_dir or "", detail)
        finally:
            self.finished.emit(self.request_id)

    # ------------------------------------------------------------ job setup
    def _prepare(self, key: str) -> str:
        base_dir = self.spec["base_dir"]
        os.makedirs(base_dir, exist_ok=True)
        job_dir = new_job_dir(base_dir, key)

        if key == "neb":
            self._prepare_neb(job_dir)
        else:
            atoms = self.spec.get("atoms")
            if atoms is None:
                raise RunnerError("缺少输入结构")
            fixed = self.spec.get("fixed") or []
            write_poscar(atoms, os.path.join(job_dir, "POSCAR"), fixed=fixed)
            self._emit(f"已写入 POSCAR ({len(atoms)} 原子)"
                       + (f"，固定 {len(fixed)} 个原子" if fixed else ""))
        return job_dir

    def _prepare_neb(self, job_dir: str) -> None:
        frames = self.spec.get("neb_frames") or []
        if len(frames) < 2:
            raise RunnerError("NEB 需要至少两个图像（IS 与 FS），请先选择插点路径")
        for index, atoms in enumerate(frames):
            target_dir = os.path.join(job_dir, f"{index:02d}")
            os.makedirs(target_dir, exist_ok=True)
            write_poscar(atoms, os.path.join(target_dir, "POSCAR"))
        self._emit(f"已写入 {len(frames)} 个图像目录 (00 .. {len(frames) - 1:02d})")

    def _tail(self, limit: int = 12) -> str:
        # The last emitted lines are not stored here; read the OUTCAR the
        # scripts write so the user still sees why a run failed.
        if not self.job_dir:
            return ""
        path = os.path.join(self.job_dir, "OUTCAR")
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                lines = [ln.rstrip() for ln in fh.readlines() if ln.strip()]
            return "\n".join(lines[-limit:])
        except OSError:
            return ""


# ---------------------------------------------------------------------------
# NEB helpers
# ---------------------------------------------------------------------------

__all__ = ["Worker"]
