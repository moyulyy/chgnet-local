"""Main window: frameless rounded shell driving the local ChgNet calculators."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QGuiApplication, QIcon, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QSizePolicy,
                               QVBoxLayout, QWidget)

from .config import (load_config, resolve_project_dir, resolve_python,
                     save_config)
from .panels import CALC_BY_KEY, ParameterPanel, ProjectList
from .results import NebProgress
from .structure_io import (collect_neb_images, detect_format, file_filter,
                           fixed_indices, formula, read_frames)
from .viewer import StructureViewer
from .window import FramelessWindow, TitleBar
from .workers import Worker

ICON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "assets", "app.ico")

#: characters used by the script's ``print_box`` decorations - the NEB
#: calculator draws its boxes with ASCII ``+ = |`` and sometimes Unicode
_BOX_CHARS = set("+=|-_")
_UNICODE_BOX = set("─│╭╮╰╯├┤┬┴┼═║╔╗╚╝╠╣┌┐└┘┏┓┗┛━┃")


def _is_box_junk(text: str) -> bool:
    """True for lines made only of box-drawing characters / whitespace."""
    return bool(text) and all(
        ch in _BOX_CHARS or ch in _UNICODE_BOX or ch.isspace() for ch in text)


# ---------------------------------------------------------------------------
# main window
# ---------------------------------------------------------------------------
class MainWindow(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChgNet Studio")
        self.setMinimumSize(640, 440)
        if os.path.exists(ICON):
            self.setWindowIcon(QIcon(ICON))

        self.config = load_config()
        self.frames: List[Any] = []
        self.fixed: List[int] = []
        self.current_frame = 0
        self.source_path: Optional[str] = None
        self.source_format: Optional[str] = None
        self.worker: Optional[Worker] = None
        self._req = 0
        self._key = ""
        self._neb: Optional[NebProgress] = None

        self._build()
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            width = max(640, min(1440, area.width() - 60))
            height = max(440, min(900, area.height() - 60))
            self.resize(width, height)
            self.move(area.x() + (area.width() - width) // 2,
                      area.y() + (area.height() - height) // 2)
        else:
            self.resize(1240, 800)

        shortcut = QAction(self)
        shortcut.setShortcut(QKeySequence.Open)
        shortcut.triggered.connect(lambda: self._on_open("current"))
        self.addAction(shortcut)
        self._welcome()

    # ---------------------------------------------------------------- build
    def _build(self):
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = TitleBar()
        outer.addWidget(self.title_bar)

        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(0)
        outer.addWidget(content, 1)

        self.projects = ProjectList()
        self.viewer = StructureViewer()
        self.params = ParameterPanel(self.config)

        # the status line lives directly under the 3D view
        center = QWidget()
        center_lay = QVBoxLayout(center)
        center_lay.setContentsMargins(0, 0, 0, 0)
        center_lay.setSpacing(6)
        center_lay.addWidget(self.viewer, 1)
        self.status = QLabel("")
        self.status.setObjectName("Muted")
        self.status.setContentsMargins(8, 0, 0, 0)
        # never let a long NEB progress line stretch the window
        self.status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        center_lay.addWidget(self.status)

        columns = QWidget()
        row = QHBoxLayout(columns)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        row.addWidget(self.projects, 0)
        row.addWidget(center, 1)              # only the 3D view stretches
        row.addWidget(self.params, 0)
        lay.addWidget(columns, 1)

        self.projects.projectSelected.connect(self.params.select)
        self.viewer.fixedChanged.connect(self._on_fixed)
        self.viewer.frameChanged.connect(self._on_frame)
        self.params.runRequested.connect(self.run_calculation)
        self.params.cancelRequested.connect(self._cancel)
        self.params.openRequested.connect(self._on_open)
        self.params.directoryRequested.connect(self._on_directory)
        self.params.clearFixedRequested.connect(self._clear_fixed)
        self.params.select("single_point")

    # -------------------------------------------------------------- helpers
    def set_status(self, text: str):
        self.status.setText(text)

    def _welcome(self):
        python_exe = resolve_python(self.config)
        project_dir = resolve_project_dir(self.config)
        missing = []
        if not os.path.isfile(python_exe):
            missing.append("Python 解释器")
        if not project_dir:
            missing.append("ChgNetCalculater 目录")
        if missing:
            self.params.results.add(
                "环境未就绪", "自动探测计算环境失败",
                [f"缺少：{'、'.join(missing)}"], level="warn")
            self.set_status("环境未就绪：" + "、".join(missing))
        else:
            self.set_status("就绪 · 在右侧「输入结构」中打开结构文件，"
                            "或在左侧选择计算项目")
        self.params.log.append_line("ChgNet Studio 已启动")
        self.params.log.append_line(f"Python  : {python_exe}")
        self.params.log.append_line(f"脚本目录: {project_dir or '(未配置)'}")

    def _notify(self, heading: str, status: str = "", lines: Optional[List[str]] = None,
                out_dir: Optional[str] = None, files: Optional[List[str]] = None,
                level: str = "ok"):
        self.params.results.add(heading, status, lines, out_dir, files, level)
        self.set_status(status or heading)

    def _remember_dir(self, path: str):
        self.config["last_dir"] = os.path.dirname(os.path.abspath(path))
        save_config(self.config)

    # ------------------------------------------------------------- file I/O
    def _on_open(self, slot: str):
        if slot == "dir":
            self._on_directory(slot)
            return
        start = self.config.get("last_dir", "")

        path, _ = QFileDialog.getOpenFileName(self, "打开结构文件", start, file_filter())
        if not path:
            return
        try:
            frames = read_frames(path)
        except Exception as exc:  # noqa: BLE001
            self._notify("结构读取失败", os.path.basename(path), [str(exc)], level="error")
            return
        if not frames:
            self._notify("结构读取失败", os.path.basename(path), ["文件中没有可用结构。"],
                         level="warn")
            return

        self._remember_dir(path)
        self.source_path = path
        self.source_format = detect_format(path)
        # POSCAR / CONTCAR may carry a "Selective dynamics" block; keep those
        # atoms fixed.  Other formats start with no constraint as before.
        self.fixed = fixed_indices(frames[0]) if self.source_format == "vasp" else []
        self.set_frames(frames)
        self.params.set_structure(path)
        status = (f"已载入 {os.path.basename(path)} · {formula(frames[0])} · "
                  f"{len(frames)} 帧")
        if self.fixed:
            status += f" · 固定 {len(self.fixed)} 个原子"
        self.set_status(status)

    def _on_directory(self, _slot: str):
        """Load the ``POSCAR`` of every numbered image folder for preview & run."""
        start = self.config.get("last_dir", "")
        path = QFileDialog.getExistingDirectory(
            self, "选择 NEB 图像路径（00、01、02 … 子目录）", start)
        if not path:
            return
        self._remember_dir(path)

        try:
            images = collect_neb_images(path)
        except Exception as exc:  # noqa: BLE001
            self._notify("NEB 路径读取失败", os.path.basename(path), [str(exc)],
                         level="error")
            return
        if len(images) < 2:
            self._notify(
                "NEB 路径图像不足", os.path.basename(path),
                ["需要至少两个编号子目录，且每个子目录内含 POSCAR。",
                 "例如：00/POSCAR（IS）、01/POSCAR（插点）… NN/POSCAR（FS）。"],
                level="warn")
            return

        frames: List[Any] = []
        for image in images:
            try:
                parsed = read_frames(image)
            except Exception as exc:  # noqa: BLE001
                self._notify("NEB 图像读取失败", os.path.basename(image),
                             [str(exc)], level="error")
                return
            if parsed:
                frames.append(parsed[0])
        if len(frames) < 2:
            self._notify("NEB 路径图像不足", os.path.basename(path),
                         ["可用的 POSCAR 少于 2 个。"], level="warn")
            return

        self.fixed = []
        self.source_path = None
        self.set_frames(frames)
        self.params.set_neb_frames(frames, path)
        self.set_status(f"NEB：已载入 {len(frames)} 个图像"
                        f"（第 1 张=IS，最后一张=FS，中间 {len(frames) - 2} 个插点），"
                        f"可拖动视图下方进度条逐帧预览")

    # ---------------------------------------------------------- viewer sync
    def set_frames(self, frames):
        self.frames = list(frames)
        self.current_frame = 0
        if self.frames:
            count = len(self.frames[0])
            self.fixed = [i for i in self.fixed if 0 <= i < count]
        self.viewer.set_frames(self.frames, self.fixed)
        self.params.set_fixed_count(len(self.fixed))

    def _on_fixed(self, indices: List[int]):
        self.fixed = list(indices)
        self.params.set_fixed_count(len(self.fixed))
        if self.fixed:
            preview = ", ".join(str(i) for i in self.fixed[:10])
            if len(self.fixed) > 10:
                preview += " …"
            self.set_status(f"已固定 {len(self.fixed)} 个原子：{preview}")
        else:
            self.set_status("已取消全部固定原子")

    def _on_frame(self, index: int):
        if not self.frames:
            return
        self.current_frame = max(0, min(index, len(self.frames) - 1))
        self.set_status(f"轨迹帧 {self.current_frame + 1}/{len(self.frames)}")

    def _clear_fixed(self):
        had = bool(self.fixed) or any(
            getattr(form, "fixed_count", 0) for form in self.params.forms.values())
        self.fixed = []
        self.viewer.set_fixed([])
        self.params.set_fixed_count(0)
        self.set_status("已取消全部固定原子" if had else "当前没有固定原子")

    # ------------------------------------------------------------- running
    def _atoms(self):
        if not self.frames:
            return None
        index = min(max(self.current_frame, 0), len(self.frames) - 1)
        return self.frames[index]

    def _output_dir(self) -> str:
        if self.source_path:
            return os.path.dirname(os.path.abspath(self.source_path))
        return self.config.get("last_dir") or os.getcwd()

    def run_calculation(self, key: str, params: Dict[str, Any]):
        if self.worker is not None:
            self._notify("请稍候", "已有任务正在运行", level="warn")
            return

        python_exe = resolve_python(self.config)
        project_dir = resolve_project_dir(self.config)
        if not project_dir:
            self._notify("无法开始计算", "缺少 ChgNetCalculater 目录",
                         ["请确认项目目录中存在 ChgNetCalculater 脚本文件夹。"],
                         level="error")
            return

        is_neb = key == "neb"
        atoms = self._atoms()

        if is_neb:
            if len(params.get("neb_frames") or []) < 2:
                self._notify("无法开始计算", "缺少 NEB 图像",
                             ["请先点击「IS / 插点 / FS」中的「选择插点路径」，"
                              "载入 IS、插点与 FS 结构。"], level="warn")
                return
        elif atoms is None:
            self._notify("无法开始计算", "缺少结构",
                         ["请先在「输入结构」中打开结构文件。"], level="warn")
            self._on_open("current")
            return

        base_dir = self._output_dir()
        if is_neb:
            neb_dir = str(params.get("neb_dir") or "")
            if os.path.isdir(neb_dir):
                base_dir = os.path.dirname(os.path.abspath(neb_dir)) or base_dir

        spec = {
            "key": key,
            "params": dict(params),
            "python_exe": python_exe,
            "project_dir": project_dir,
            "device": "cuda",
            "base_dir": base_dir,
            "atoms": atoms,
            "fixed": list(self.fixed),
            "neb_frames": list(params.get("neb_frames") or []) if is_neb else None,
        }
        self._remember_params(key, params)
        save_config(self.config)
        self._start(key, spec)

    def _remember_params(self, key: str, params: Dict[str, Any]):
        mapping = {
            "relax": {"relax_type": "relax_type", "max_steps": "relax_max_steps",
                      "fmax": "relax_fmax"},
            "aimd": {"temperature": "aimd_temperature", "timestep": "aimd_timestep",
                     "steps": "aimd_steps", "loginterval": "aimd_loginterval",
                     "ensemble": "aimd_ensemble", "thermostat": "aimd_thermostat"},
            "freq": {"delta": "freq_delta", "nfree": "freq_nfree",
                     "temperature": "freq_temperature"},
            "neb": {"fmax": "neb_fmax", "max_steps": "neb_max_steps",
                    "spring": "neb_spring", "climb": "neb_climb"},
        }.get(key, {})
        for src, dst in mapping.items():
            if src in params and params[src] is not None:
                self.config[dst] = params[src]

    def _start(self, key: str, spec: Dict[str, Any]):
        self._req += 1
        self._key = key
        self._neb = NebProgress() if key == "neb" else None
        heading = CALC_BY_KEY[key]["title"] if key in CALC_BY_KEY else key
        self.params.set_busy(True)
        self.params.log.append_line("")
        self.params.log.append_line(f"===== {heading} · 任务开始 =====")
        self.set_status("任务提交中…")
        self.worker = Worker(f"{key}-{self._req}", spec, self)
        self.worker.line.connect(self._on_line)
        self.worker.succeeded.connect(self._on_success)
        self.worker.failed.connect(self._on_failure)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_line(self, _rid: str, text: str):
        self.params.log.append_line(text)
        stripped = text.strip()

        # during a NEB run, show step / force / TS frame / barrier live
        if self._key == "neb" and self._neb is not None:
            if self._neb.feed(text):
                self.set_status(self._neb.summary())
            elif not self._neb.has_data() and stripped and not _is_box_junk(stripped):
                self.set_status(stripped[:140])
            return

        if stripped:
            self.set_status(stripped[:140])

    def _cancel(self):
        if self.worker is not None:
            self.worker.cancel()
            self.params.log.append_line("已请求取消，正在终止子进程 …")
            self.set_status("已请求取消")
            self._notify("已取消", "停止等待任务结果", level="warn")

    def _on_finished(self, _rid: str):
        self.params.set_busy(False)
        self.worker = None

    # -------------------------------------------------------------- results
    def _on_success(self, _rid: str, job_dir: str, result: Any):
        key = self._key
        heading = CALC_BY_KEY[key]["title"] if key in CALC_BY_KEY else key
        summary = list(result.get("summary", [])) if isinstance(result, dict) else []
        frames = result.get("frames") if isinstance(result, dict) else None
        files = result.get("artifacts") if isinstance(result, dict) else None

        if frames:
            try:
                self.set_frames(frames)
            except Exception:  # noqa: BLE001
                pass

        self._notify(heading, "运行完毕", summary, job_dir, files)
        self.params.log.append_line(f"----- {heading} 完成 -----")

    def _on_failure(self, _rid: str, job_dir: str, message: str):
        key = self._key
        heading = CALC_BY_KEY[key]["title"] if key in CALC_BY_KEY else "计算任务"
        lines = [ln for ln in str(message).splitlines() if ln.strip()]
        self._notify(f"{heading} · 运行失败", "任务失败", lines,
                     job_dir or None, level="error")
        self.params.log.append_line(f"!!!!! {heading} 失败: {message}")

    def closeEvent(self, event):  # noqa: N802
        if self.worker is not None:
            self.worker.cancel()
            self.worker.wait(2500)
        save_config(self.config)
        super().closeEvent(event)


__all__ = ["MainWindow"]
