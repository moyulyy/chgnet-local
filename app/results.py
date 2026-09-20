"""Parse the files produced by the ChgNetCalculater scripts.

Nothing in here imports torch/chgnet: only ASE/numpy, so the GUI thread stays
light.  Every parser is defensive - a missing or unexpected file simply yields
fewer summary lines instead of an exception.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

import numpy as np
from ase import Atoms

from .structure_io import (read_frames, read_relax_pkl, read_trajectory,
                           read_xdatcar_tolerant)

# ---------------------------------------------------------------------------
# tiny numeric helpers
# ---------------------------------------------------------------------------

_NUM = r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?"


def parse_vasp_energy(token: str) -> Optional[float]:
    """Parse a VASP style number such as ``-.12345678E+03``."""
    text = token.strip()
    if not text:
        return None
    sign = 1.0
    if text[0] in "+-":
        if text[0] == "-":
            sign = -1.0
        text = text[1:]
    if text.startswith("."):
        text = "0" + text
    elif text and text[0] not in "0123456789":
        return None
    try:
        return sign * float(text)
    except ValueError:
        return None


def _read_text(path: str, limit: Optional[int] = None) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            if limit is None:
                return fh.read()
            return fh.read(limit)
    except OSError:
        return ""


def _find(job_dir: str, *names: str) -> Optional[str]:
    for name in names:
        path = os.path.join(job_dir, name)
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            return path
    return None


def _energy_profile(path: Optional[str]) -> List[float]:
    """Extract the ``F=`` column from an OSZICAR file."""
    if not path:
        return []
    energies: List[float] = []
    for line in _read_text(path).splitlines():
        match = re.search(r"F=\s*(" + _NUM + ")", line)
        if match:
            value = parse_vasp_energy(match.group(1))
            if value is not None:
                energies.append(value)
    return energies


# ---------------------------------------------------------------------------
# per-task parsers
# ---------------------------------------------------------------------------

def _single_point(job_dir: str) -> Dict[str, Any]:
    outcar = _read_text(_find(job_dir, "OUTCAR") or "")
    lines: List[str] = []
    energy = _grab(outcar, r"Total energy\s*=\s*(" + _NUM + ")")
    fmax = _grab(outcar, r"Max \|force\|\s*=\s*(" + _NUM + ")")
    frms = _grab(outcar, r"RMS force\s*=\s*(" + _NUM + ")")
    if energy is not None:
        lines.append(f"单点总能 = {energy:.8f} eV")
    if fmax is not None:
        lines.append(f"最大受力 = {fmax:.6f} eV/Å")
    if frms is not None:
        lines.append(f"均方受力 = {frms:.6f} eV/Å")
    return {"summary": lines, "kind": "single"}


def _relax(job_dir: str) -> Dict[str, Any]:
    energies = _energy_profile(_find(job_dir, "OSZICAR"))
    lines: List[str] = []
    if energies:
        lines.append(f"初始能量 = {energies[0]:.6f} eV")
        lines.append(f"最终能量 = {energies[-1]:.6f} eV")
        lines.append(f"能量变化 = {energies[-1] - energies[0]:+.6f} eV")
        lines.append(f"优化步数 = {len(energies)}")
    return {"summary": lines, "kind": "traj"}


def _aimd(job_dir: str) -> Dict[str, Any]:
    lines: List[str] = []
    log_path = _find(job_dir, "log.dat")
    energies: List[float] = []
    temps: List[float] = []
    if log_path:
        for line in _read_text(log_path).splitlines():
            if line.startswith("#") or not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 4:
                try:
                    energies.append(float(parts[2]))
                    temps.append(float(parts[3]))
                except ValueError:
                    continue
    if energies:
        lines.append(f"模拟帧数 = {len(energies)}")
        lines.append(f"平均能量 = {np.mean(energies):.6f} eV")
        lines.append(f"能量波动 = {np.std(energies):.6f} eV")
    if temps:
        lines.append(f"平均温度 = {np.mean(temps):.2f} K")
        lines.append(f"温度波动 = {np.std(temps):.2f} K")
    return {"summary": lines, "kind": "traj"}


def _freq(job_dir: str) -> Dict[str, Any]:
    lines: List[str] = []
    zpe_path = _find(job_dir, "zpe-ts.dat")
    if zpe_path:
        for line in _read_text(zpe_path).splitlines():
            text = line.strip()
            if "=" in text:
                key, _, value = text.partition("=")
                lines.append(f"{key.strip()} = {value.strip()}")
    results = _read_text(_find(job_dir, "FREQ_RESULTS") or "")
    for label, value in (("E_pot", "势能 E_pot"), ("F_corr", "自由能修正 F_corr")):
        found = _grab(results, re.escape(label) + r"\s*=\s*(" + _NUM + ")")
        if found is not None:
            lines.append(f"{value} = {found:.6f} eV")
    real = _grab(results, r"实频数量[:：]?\s*(\d+)")
    imag = _grab(results, r"虚频数量[:：]?\s*(\d+)")
    if real is not None:
        lines.append(f"实频模式 = {int(real)}")
    if imag is not None:
        lines.append(f"虚频模式 = {int(imag)}")
    return {"summary": lines, "kind": "freq"}


def _neb(job_dir: str) -> Dict[str, Any]:
    lines: List[str] = []
    text = _read_text(_find(job_dir, "NEB_RESULTS") or "")
    forward = _grab(text, r"Forward Barrier[^:]*:\s*(" + _NUM + ")")
    reverse = _grab(text, r"Reverse Barrier[^:]*:\s*(" + _NUM + ")")
    reaction = _grab(text, r"Reaction Energy[^:]*:\s*(" + _NUM + ")")
    if forward is not None:
        lines.append(f"正向能垒 (IS→TS) = {forward:.4f} eV")
    if reverse is not None:
        lines.append(f"反向能垒 (FS→TS) = {reverse:.4f} eV")
    if reaction is not None:
        lines.append(f"反应能 (FS−IS) = {reaction:+.4f} eV")
    # per image relative energies from the profile table
    profile = re.findall(
        r"^\s*(\d+)\s+(" + _NUM + r")\s+(" + _NUM + r")\s+(\S+)\s*$",
        text, flags=re.MULTILINE)
    if profile:
        for _image, _energy, rel, mark in profile:
            tag = "  ← TS" if "*" in mark else ""
            lines.append(f"  图像 {_image}: {float(rel):+.4f} eV{tag}")
    return {"summary": lines, "kind": "traj"}


def _grab(text: str, pattern: str) -> Optional[float]:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except (ValueError, IndexError):
        return parse_vasp_energy(match.group(1))


_PARSERS = {
    "single_point": _single_point,
    "relax": _relax,
    "aimd": _aimd,
    "freq": _freq,
    "neb": _neb,
}


# ---------------------------------------------------------------------------
# live NEB progress (parsed straight from the script's stdout)
# ---------------------------------------------------------------------------

_NEB_STEP = re.compile(r"NEB\s*(?:初始状态|第\s*(\d+)\s*步)")
_NEB_FORCE = re.compile(r"当前最大力\s*[:：]\s*(" + _NUM + r")")
_NEB_TS = re.compile(r"当前过渡态\s*[:：]\s*([0-9A-Za-z_.@\-]+)")
_NEB_FWD = re.compile(r"正向能垒[^:：]*[:：]\s*(" + _NUM + r")")
_NEB_REV = re.compile(r"反向能垒[^:：]*[:：]\s*(" + _NUM + r")")
_NEB_REACT = re.compile(r"反应热[^:：]*[:：]\s*(" + _NUM + r")")


class NebProgress:
    """Collect the per-step NEB box the script prints while optimising.

    The calculator prints, once per optimisation step::

        当前最大力: 0.123456 eV/Å
        当前过渡态: 03
        正向能垒 (IS → TS): 0.4321 eV
        反向能垒 (FS → TS): 0.2100 eV
        反应热   (FS - IS): 0.2221 eV

    wrapped in a box.  Feed every stdout line to :meth:`feed`; it returns
    ``True`` whenever a field changed so the GUI can refresh its status line.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.step: Optional[int] = None
        self.force: Optional[float] = None
        self.ts: Optional[str] = None
        self.forward: Optional[float] = None
        self.reverse: Optional[float] = None
        self.reaction: Optional[float] = None

    def feed(self, line: str) -> bool:
        if not line:
            return False
        changed = False

        match = _NEB_STEP.search(line)
        if match:
            self.step = int(match.group(1)) if match.group(1) else 0
            # a fresh box: drop the values of the previous step
            self.force = self.ts = None
            self.forward = self.reverse = self.reaction = None
            changed = True

        for attr, pattern in (("force", _NEB_FORCE), ("forward", _NEB_FWD),
                              ("reverse", _NEB_REV), ("reaction", _NEB_REACT)):
            match = pattern.search(line)
            if match:
                value = parse_vasp_energy(match.group(1))
                if value is not None:
                    setattr(self, attr, value)
                    changed = True

        match = _NEB_TS.search(line)
        if match:
            self.ts = match.group(1)
            changed = True
        return changed

    def has_data(self) -> bool:
        return any(value is not None
                   for value in (self.force, self.ts, self.forward))

    def summary(self) -> str:
        parts: List[str] = []
        if self.step is not None:
            parts.append("NEB 初始状态" if self.step == 0 else f"NEB 第 {self.step} 步")
        if self.force is not None:
            parts.append(f"受力 maxF = {self.force:.4f} eV/Å")
        if self.ts is not None:
            parts.append(f"TS 帧 = {self.ts}")
        if self.forward is not None:
            parts.append(f"能垒 Ea = {self.forward:.4f} eV")
        return "   ·   ".join(parts)


# ---------------------------------------------------------------------------
# structure / trajectory loading
# ---------------------------------------------------------------------------

def _load_frames(kind: str, job_dir: str) -> tuple[Optional[List[Atoms]], str]:
    """Return (frames, label) best suited for the 3D viewer."""
    if kind == "neb":
        traj = _find(job_dir, "neb_final.traj")
        if traj:
            try:
                frames = read_trajectory(traj)
                if frames:
                    return frames, "NEB 收敛路径"
            except Exception:  # noqa: BLE001
                pass
        frames = _neb_images(job_dir)
        if frames:
            return frames, "NEB 图像路径"
        return None, ""

    # AIMD writes a real ASE trajectory - always prefer it
    md_traj = _find(job_dir, "md_out.traj")
    if md_traj:
        try:
            frames = read_trajectory(md_traj)
            if frames:
                return frames, "md_out.traj 轨迹"
        except Exception:  # noqa: BLE001
            pass

    # relaxation keeps the full path in relax.pkl
    relax_pkl = _find(job_dir, "relax.pkl")
    if relax_pkl:
        try:
            frames = read_relax_pkl(relax_pkl)
            if frames:
                return frames, "relax.pkl 轨迹"
        except Exception:  # noqa: BLE001
            pass

    # fall back to the (non-standard) XDATCAR, then to CONTCAR
    xdatcar = _find(job_dir, "XDATCAR")
    if xdatcar:
        try:
            frames = read_xdatcar_tolerant(xdatcar)
            if not frames:
                frames = read_trajectory(xdatcar)
            if frames:
                return frames, "XDATCAR 轨迹"
        except Exception:  # noqa: BLE001
            pass

    contcar = _find(job_dir, "CONTCAR")
    if contcar:
        try:
            frames = read_frames(contcar, "vasp")
            if frames:
                return frames, "CONTCAR"
        except Exception:  # noqa: BLE001
            pass
    return None, ""


def _neb_images(job_dir: str) -> List[Atoms]:
    dirs = []
    try:
        for name in os.listdir(job_dir):
            full = os.path.join(job_dir, name)
            if os.path.isdir(full) and name.isdigit():
                dirs.append((int(name), name))
    except OSError:
        return []
    dirs.sort()
    frames: List[Atoms] = []
    for _num, name in dirs:
        for candidate in ("CONTCAR", "POSCAR"):
            path = os.path.join(job_dir, name, candidate)
            if os.path.isfile(path):
                try:
                    parsed = read_frames(path, "vasp")
                    if parsed:
                        frames.append(parsed[0])
                        break
                except Exception:  # noqa: BLE001
                    continue
    return frames


#: files that are interesting to report to the user
ARTIFACT_NAMES = (
    "POSCAR", "CONTCAR", "OSZICAR", "XDATCAR", "OUTCAR", "relax.pkl",
    "log.dat", "FREQ_RESULTS", "zpe-ts.dat", "vib_summary.txt",
    "NEB_RESULTS", "neb_profile.png", "neb_final.traj", "neb_final.xtd",
    "neb_initial.traj", "md_out.traj", "md_out.log",
)


def collect_artifacts(job_dir: str) -> List[str]:
    found = []
    for name in ARTIFACT_NAMES:
        if os.path.isfile(os.path.join(job_dir, name)):
            found.append(name)
    return found


# ---------------------------------------------------------------------------
# public entry point
# ---------------------------------------------------------------------------

def gather_result(key: str, job_dir: str) -> Dict[str, Any]:
    """Parse *job_dir* and return everything the GUI needs to show."""
    parser = _PARSERS.get(key)
    data: Dict[str, Any] = {"summary": [], "kind": "single"}
    if parser is not None:
        try:
            data = parser(job_dir)
        except Exception:  # noqa: BLE001 - never fail the whole run
            data = {"summary": [], "kind": "single"}

    frames: Optional[List[Atoms]] = None
    label = ""
    try:
        frames, label = _load_frames(data.get("kind", "single"), job_dir)
    except Exception:  # noqa: BLE001
        frames, label = None, ""

    summary: List[str] = list(data.get("summary", []))
    if frames:
        summary.insert(0, f"轨迹帧数 = {len(frames)}")
        if label:
            summary.insert(1, f"视图来源 = {label}")

    return {
        "summary": summary,
        "frames": frames,
        "frames_label": label,
        "artifacts": collect_artifacts(job_dir),
        "job_dir": job_dir,
    }


__all__ = ["gather_result", "collect_artifacts", "parse_vasp_energy",
           "NebProgress"]
