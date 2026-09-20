"""Structure I/O helpers built on top of ASE.

Supported read/write formats: CIF, POSCAR/CONTCAR (VASP), Materials Studio
XSD and VASP XDATCAR.  All conversions inside the GUI go through ASE so that
the rest of the application only ever deals with :class:`ase.Atoms` objects.
"""

from __future__ import annotations

import os
import re
import tempfile
from typing import Iterable, List, Optional

import numpy as np
from ase import Atoms
from ase.io import read as ase_read
from ase.io import write as ase_write

# ---------------------------------------------------------------------------
# format detection
# ---------------------------------------------------------------------------

#: logical name -> (human label, file extensions)
FORMATS = {
    "cif": ("CIF 晶体文件", [".cif"]),
    "vasp": ("VASP POSCAR/CONTCAR", [".poscar", ".vasp", ".contcar"]),
    "xsd": ("Materials Studio XSD", [".xsd"]),
    "vasp-xdatcar": ("VASP XDATCAR 轨迹", [".xdatcar"]),
}

_EXT_TO_FORMAT = {}
for _fmt, (_label, _exts) in FORMATS.items():
    for _e in _exts:
        _EXT_TO_FORMAT[_e] = _fmt

#: file name (no extension) -> format
_NAME_TO_FORMAT = {
    "poscar": "vasp",
    "contcar": "vasp",
    "xdatcar": "vasp-xdatcar",
}

#: everything the LASPAI backend understands in ``struct_str``
API_STRUCTURE_FORMATS = {"cif", "arc", "car", "pdb", "poscar", "xyz", "mol", "xsd", "vasp-xdatcar"}


def detect_format(path: str) -> Optional[str]:
    """Best effort format detection from a path."""
    name = os.path.basename(path).strip()
    ext = os.path.splitext(name)[1].lower()
    if ext in _EXT_TO_FORMAT:
        return _EXT_TO_FORMAT[ext]
    stem = os.path.splitext(name)[0].lower()
    if stem in _NAME_TO_FORMAT:
        return _NAME_TO_FORMAT[stem]
    # tolerate ASE's ``POSCAR@index`` / ``CONTCAR@run`` naming
    head = stem.split("@", 1)[0]
    if head in _NAME_TO_FORMAT:
        return _NAME_TO_FORMAT[head]
    if name.split("@", 1)[0].upper() == "XDATCAR":
        return "vasp-xdatcar"
    return None


def file_filter() -> str:
    """Qt file dialog filter string."""
    parts = []
    all_exts = []
    for fmt, (label, exts) in FORMATS.items():
        pats = " ".join("*" + e for e in exts)
        parts.append(f"{label} ({pats})")
        all_exts.extend("*" + e for e in exts)
    parts.append("所有结构文件 (" + " ".join(all_exts) + ")")
    parts.append("所有文件 (*)")
    return ";;".join(parts)


# ---------------------------------------------------------------------------
# NEB image discovery
# ---------------------------------------------------------------------------

def collect_neb_images(path: str) -> List[str]:
    """Return the ``POSCAR`` files inside the numbered image folders.

    Only folders whose name is entirely digits (``00``, ``01``, ``02`` ...)
    are considered, and only the ``POSCAR`` inside each of them.  Every other
    file or folder - including CIF / CONTCAR / loose structure files - is
    ignored.  Images are returned in ascending folder order and later
    renumbered to ``00 .. NN`` in the job directory.
    """
    if not path or not os.path.isdir(path):
        return []
    try:
        entries = list(os.scandir(path))
    except OSError:
        return []

    images: List[tuple] = []
    for entry in entries:
        try:
            if not entry.is_dir() or not entry.name.isdigit():
                continue
            poscar = os.path.join(entry.path, "POSCAR")
            if os.path.isfile(poscar):
                images.append((int(entry.name), poscar))
        except OSError:
            continue

    images.sort(key=lambda item: item[0])
    return [poscar for _number, poscar in images]


# ---------------------------------------------------------------------------
# reading / writing through ASE
# ---------------------------------------------------------------------------

def _tmp_path(suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path


def _read_atoms(path: str, fmt: Optional[str] = None, index: str = ":"):
    """``ase.io.read`` wrapper that never splits the path on ``@``.

    ASE's ``parse_filename`` treats whatever follows the *last* ``@`` of a
    file name as an index expression (``struct.cif@0``).  Real file names
    such as ``Ni@Al2O3.cif`` are therefore truncated to ``.../Ni`` and fail
    to open, so the splitting must be switched off explicitly.
    """
    return ase_read(path, format=fmt, index=index, do_not_split_by_at_sign=True)


def read_frames(path: str, fmt: Optional[str] = None) -> List[Atoms]:
    """Read one or more frames from *path*.

    XDATCAR files contain a whole trajectory; every other supported format
    yields a single frame.
    """
    fmt = fmt or detect_format(path)
    if fmt is None:
        raise ValueError(f"无法识别的结构文件格式: {path}")

    frames = _read_atoms(path, fmt)
    if isinstance(frames, Atoms):
        frames = [frames]
    return [Atoms(f) for f in frames]


def read_text(text: str, fmt: str) -> List[Atoms]:
    """Parse structure text of the given format."""
    suffix = "." + fmt.split("-")[-1]
    path = _tmp_path(suffix)
    try:
        # CIF/xsd write with byte streams, reading from text is fine
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        frames = _read_atoms(path, fmt)
        if isinstance(frames, Atoms):
            frames = [frames]
        return [Atoms(f) for f in frames]
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def dump_text(frames: Iterable[Atoms], fmt: str) -> str:
    """Serialise frames to text in the requested format."""
    frames = list(frames)
    if not frames:
        raise ValueError("没有可写出的结构")
    suffix = "." + fmt.split("-")[-1]
    path = _tmp_path(suffix)
    try:
        if fmt == "vasp-xdatcar":
            ase_write(path, frames, format=fmt)
        else:
            ase_write(path, frames[0], format=fmt)
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def write_frames(frames: Iterable[Atoms], path: str, fmt: Optional[str] = None) -> None:
    """Write frames to *path* (format inferred from the extension if needed)."""
    fmt = fmt or detect_format(path)
    if fmt is None:
        raise ValueError(f"无法确定输出格式: {path}")
    frames = list(frames)
    if fmt == "vasp-xdatcar":
        ase_write(path, frames, format=fmt)
    else:
        ase_write(path, frames[0], format=fmt)


# ---------------------------------------------------------------------------
# convenience converters
# ---------------------------------------------------------------------------

def write_poscar(atoms: Atoms, path: str, fixed: Optional[Iterable[int]] = None) -> None:
    """Write a VASP POSCAR, optionally with selective-dynamics flags.

    The bundled ChgNet scripts read the structure with pymatgen's ``Poscar``
    which honours the ``Selective dynamics`` block; in particular the
    frequency calculator only vibrates the atoms flagged ``T T T``.  We
    therefore express the fixed atoms as an ASE ``FixAtoms`` constraint, which
    makes the VASP writer emit the per-atom flags.
    """
    out = Atoms(atoms)
    indices = sorted({int(i) for i in (fixed or []) if 0 <= int(i) < len(out)})
    if indices:
        from ase.constraints import FixAtoms
        out.set_constraint(FixAtoms(indices=indices))
    ase_write(path, out, format="vasp", vasp5=True, direct=True, sort=False)


def read_trajectory(path: str) -> List[Atoms]:
    """Read a trajectory file (``XDATCAR`` or ASE ``.traj``)."""
    name = os.path.basename(path).lower()
    if name.endswith(".xdatcar") or name == "xdatcar":
        frames = _read_atoms(path, "vasp-xdatcar")
    else:
        frames = _read_atoms(path)
    if isinstance(frames, Atoms):
        frames = [frames]
    return [Atoms(f) for f in frames]


def read_xdatcar_tolerant(path: str) -> List[Atoms]:
    """Parse the relaxed/AIMD XDATCAR written by ChgNetCalculater.

    Those scripts repeat the lattice / species header before *every*
    configuration, which the stock ASE reader mis-handles (it stops after the
    first frame).  This parser re-synchronises on each ``Direct configuration``
    marker and rebuilds the cell from the header that precedes it.
    """
    import re

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    chunks = re.split(r"(?m)^\s*Direct configuration\s*=.*$\n?", text)
    if len(chunks) < 2:
        return []

    def lines_of(chunk: str) -> List[str]:
        return [ln for ln in chunk.splitlines() if ln.strip()]

    header = lines_of(chunks[0])[-5:]
    if len(header) < 5:
        return []
    symbols: List[str] = []
    for symbol, count in zip(header[3].split(), header[4].split()):
        try:
            symbols.extend([symbol] * int(count))
        except ValueError:
            return []
    natoms = len(symbols)
    if natoms == 0:
        return []

    def cell_of(chunk: str):
        tail = lines_of(chunk)[-5:]
        if len(tail) >= 3:
            try:
                return [[float(x) for x in tail[i].split()[:3]] for i in range(3)]
            except (ValueError, IndexError):
                pass
        return None

    base_cell = cell_of(chunks[0])
    frames: List[Atoms] = []
    for index in range(len(chunks) - 1):
        cell = cell_of(chunks[index]) or base_cell
        pos_lines = lines_of(chunks[index + 1])[:natoms]
        if len(pos_lines) < natoms:
            continue
        try:
            scaled = [[float(x) for x in ln.split()[:3]] for ln in pos_lines]
        except (ValueError, IndexError):
            continue
        frames.append(Atoms(symbols=symbols, scaled_positions=scaled,
                            cell=cell, pbc=True))
    return frames


def read_relax_pkl(path: str) -> List[Atoms]:
    """Read the ``relax.pkl`` trajectory saved by the relaxation script."""
    import pickle

    from ase.data import chemical_symbols

    with open(path, "rb") as fh:
        data = pickle.load(fh)
    if not isinstance(data, dict) or "atom_positions" not in data:
        return []
    numbers = np.asarray(data.get("atomic_number", []), dtype=int)
    symbols = [chemical_symbols[int(z)] for z in numbers]
    positions = list(data["atom_positions"])
    cells = data.get("cell")
    frames: List[Atoms] = []
    for index, pos in enumerate(positions):
        cell = None
        if cells is not None and len(cells):
            cell = cells[min(index, len(cells) - 1)]
        frames.append(Atoms(symbols=symbols, positions=np.asarray(pos, dtype=float),
                            cell=cell, pbc=True))
    return frames


def to_cif(atoms: Atoms) -> str:
    """Return a P1 CIF string."""
    return dump_text([atoms], "cif")


def to_xdatcar(frames: Iterable[Atoms]) -> str:
    """Return an XDATCAR string for a trajectory."""
    return dump_text(list(frames), "vasp-xdatcar")


def fixed_indices(atoms: Atoms) -> List[int]:
    """Return the atom indices constrained by ``FixAtoms``.

    The VASP reader turns a POSCAR/CONTCAR ``Selective dynamics`` block into
    an ASE ``FixAtoms`` constraint, so this recovers the atoms the file asked
    to keep frozen.
    """
    from ase.constraints import FixAtoms

    indices: List[int] = []
    for constraint in getattr(atoms, "constraints", []) or []:
        if isinstance(constraint, FixAtoms):
            indices.extend(int(i) for i in constraint.get_indices())
    return sorted({i for i in indices if 0 <= i < len(atoms)})


def viewer_payload(frames: List[Atoms], fixed: Iterable[int]) -> dict:
    """Build the JSON payload consumed by ``viewer.html``."""
    payload_frames = []
    for atoms in frames:
        symbols = [str(s) for s in atoms.get_chemical_symbols()]
        positions = np.asarray(atoms.get_positions(), dtype=float).tolist()
        payload_frames.append({"symbols": symbols, "positions": positions})

    cell = None
    if frames:
        cell_arr = np.asarray(frames[0].get_cell(), dtype=float)
        if np.any(np.abs(cell_arr) > 1e-8):
            cell = cell_arr.tolist()

    return {
        "frames": payload_frames,
        "cell": cell,
        "fixed": sorted(int(i) for i in fixed),
    }


def formula(atoms: Atoms) -> str:
    try:
        return atoms.get_chemical_formula()
    except Exception:  # pragma: no cover - defensive
        return "?"


def frame_summary(atoms: Atoms, index: int = 0, total: int = 1) -> str:
    cell = atoms.get_cell()
    lengths = cell.lengths() if cell is not None else [0, 0, 0]
    return (
        f"帧 {index + 1}/{total} · {formula(atoms)} · {len(atoms)} 原子 · "
        f"a={lengths[0]:.3f} b={lengths[1]:.3f} c={lengths[2]:.3f} Å"
    )


__all__ = [
    "FORMATS",
    "API_STRUCTURE_FORMATS",
    "detect_format",
    "file_filter",
    "read_frames",
    "read_trajectory",
    "read_xdatcar_tolerant",
    "read_relax_pkl",
    "collect_neb_images",
    "read_text",
    "dump_text",
    "write_frames",
    "write_poscar",
    "to_cif",
    "to_xdatcar",
    "fixed_indices",
    "viewer_payload",
    "formula",
    "frame_summary",
]
