"""Left project list, right parameter forms and the result / log viewer."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import (QCheckBox, QDoubleSpinBox, QFrame,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPlainTextEdit, QProgressBar,
                               QPushButton, QScrollArea, QSpinBox,
                               QStackedWidget, QTabWidget, QTextBrowser,
                               QVBoxLayout, QWidget)

from . import styles
from .widgets import (FileRow, NoWheelComboBox, NoWheelDoubleSpinBox,
                     NoWheelSpinBox, TaskIcon, card, labeled, muted, section,
                     title)

# ---------------------------------------------------------------------------
# catalogue
# ---------------------------------------------------------------------------
CALCULATIONS: List[Dict[str, str]] = [
    {"key": "single_point", "title": "单点能计算", "sub": "Single point",
     "icon": "single_point", "color": styles.ORANGE,
     "desc": "固定结构，计算一次能量、受力与应力。"},
    {"key": "relax", "title": "结构弛豫优化", "sub": "Relaxation",
     "icon": "trajectory", "color": styles.BLUE,
     "desc": "变胞 (bulk) 或定胞 (relax) 的 CHGNet 结构优化，输出轨迹。"},
    {"key": "aimd", "title": "从头分子动力学", "sub": "AIMD",
     "icon": "aimd", "color": styles.PURPLE,
     "desc": "CHGNet 分子动力学，支持 nvt / nve / npt 系综。"},
    {"key": "freq", "title": "振动频率计算", "sub": "Vibrations",
     "icon": "adsorption_vibration", "color": styles.TEAL,
     "desc": "有限位移法计算频率，给出 ZPE / TS 自由能修正。"},
    {"key": "neb", "title": "NEB 过渡态搜索", "sub": "NEB barrier",
     "icon": "double_end_search", "color": styles.PINK,
     "desc": "读取初末态生成路径，CHGNet-NEB 搜索过渡态与能垒。"},
]
CALC_BY_KEY = {c["key"]: c for c in CALCULATIONS}

ENSEMBLES = ["nvt", "nve", "npt"]
THERMOSTATS = ["Nose-Hoover", "Andersen", "Berendsen", "Langevin"]


# ---------------------------------------------------------------------------
# project list
# ---------------------------------------------------------------------------
class _ProjectRow(QWidget):
    def __init__(self, calc: Dict[str, str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(9, 7, 9, 7)
        lay.setSpacing(11)
        self.icon = TaskIcon(calc["icon"], calc["color"], 30)
        lay.addWidget(self.icon)
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)
        self.name = QLabel(calc["title"])
        self.name.setObjectName("ItemTitle")
        self.sub = QLabel(calc["sub"])
        self.sub.setObjectName("ItemSub")
        col.addWidget(self.name)
        col.addWidget(self.sub)
        lay.addLayout(col, 1)

    def set_selected(self, selected: bool):
        self.name.setStyleSheet(
            f"font-size:13px;font-weight:600;"
            f"color:{styles.BLUE_DARK if selected else styles.TEXT};")


class ProjectList(QFrame):
    projectSelected = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setMinimumWidth(120)
        self.setMaximumWidth(300)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 14, 10, 10)
        lay.setSpacing(8)
        head = title("计算项目")
        head.setContentsMargins(4, 0, 0, 0)
        lay.addWidget(head)

        self.list = QListWidget()
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.setFrameShape(QFrame.NoFrame)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._rows: Dict[int, _ProjectRow] = {}
        for calc in CALCULATIONS:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 54))
            item.setData(Qt.UserRole, calc["key"])
            row = _ProjectRow(calc)
            self.list.addItem(item)
            self.list.setItemWidget(item, row)
            self._rows[self.list.count() - 1] = row
        self.list.currentRowChanged.connect(self._on_row)
        lay.addWidget(self.list, 1)
        self.list.setCurrentRow(0)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(200, 400)

    def _on_row(self, row: int):
        for index, widget in self._rows.items():
            widget.set_selected(index == row)
        if row >= 0:
            self.projectSelected.emit(self.current_key())

    def current_key(self) -> str:
        item = self.list.currentItem()
        return str(item.data(Qt.UserRole)) if item else "single_point"


# ---------------------------------------------------------------------------
# parameter forms
# ---------------------------------------------------------------------------
class BaseForm(QWidget):
    key = ""
    openRequested = Signal(str)
    directoryRequested = Signal(str)
    clearFixedRequested = Signal()

    def __init__(self, config: Optional[Dict[str, Any]] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config = config or {}
        self.fixed_count = 0
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)
        self._build()
        self._layout.addStretch(1)

    def _build(self):
        self.file_row = FileRow("打开结构", "未选择结构文件", primary=True)
        self.file_row.clicked.connect(lambda: self.openRequested.emit("current"))
        self._add_card("输入结构", [self.file_row])
        self.build_params()

    def build_params(self):  # pragma: no cover - overridden
        pass

    def _add_card(self, heading: str, widgets: List[QWidget]) -> QFrame:
        box = card()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(12, 11, 12, 12)
        lay.setSpacing(9)
        if heading:
            lay.addWidget(section(heading))
        for widget in widgets:
            lay.addWidget(widget)
        self._layout.addWidget(box)
        return box

    def set_structure(self, path: Optional[str]):
        row = getattr(self, "file_row", None)
        if row is not None:
            row.set_file(path)

    def _fixed_row(self) -> QWidget:
        """Caption chip with the fixed-atom count plus a clear-all button."""
        self.fixed_chip = QLabel("已固定 0 个原子")
        self.fixed_chip.setObjectName("Chip")
        self.clear_fixed_btn = QPushButton("取消全部固定")
        self.clear_fixed_btn.setObjectName("Tint")
        self.clear_fixed_btn.setCursor(Qt.PointingHandCursor)
        self.clear_fixed_btn.setEnabled(False)
        self.clear_fixed_btn.clicked.connect(
            lambda: self.clearFixedRequested.emit())
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(self.fixed_chip)
        lay.addStretch(1)
        lay.addWidget(self.clear_fixed_btn)
        return row

    def set_fixed_count(self, count: int):
        self.fixed_count = count
        chip = getattr(self, "fixed_chip", None)
        if chip is not None:
            chip.setText(f"已固定 {count} 个原子")
        button = getattr(self, "clear_fixed_btn", None)
        if button is not None:
            button.setEnabled(count > 0)

    def gather(self) -> Dict[str, object]:
        return {}


def _dspin(low: float, high: float, value: float, decimals: int = 3,
           step: float = 0.5, suffix: str = "") -> QDoubleSpinBox:
    box = NoWheelDoubleSpinBox()
    box.setRange(low, high)
    box.setDecimals(decimals)
    box.setValue(value)
    box.setSingleStep(step)
    if suffix:
        box.setSuffix(suffix)
    box.setMinimumWidth(96)
    return box


def _ispin(low: int, high: int, value: int) -> QSpinBox:
    box = NoWheelSpinBox()
    box.setRange(low, high)
    box.setValue(value)
    box.setMinimumWidth(96)
    return box


class SinglePointForm(BaseForm):
    key = "single_point"

    def build_params(self):
        self._add_card("计算选项", [
            muted("固定结构，使用 CUDA 设备计算 CHGNet 单点能量 / 受力 / 应力；"
                  "结构保持不动，结果写入 OSZICAR、OUTCAR。"),
        ])

    def gather(self):
        return {}


class RelaxForm(BaseForm):
    key = "relax"

    def build_params(self):
        self.relax_type = NoWheelComboBox()
        self.relax_type.addItem("变胞弛豫 (bulk)", "bulk")
        self.relax_type.addItem("定胞弛豫 (relax)", "relax")
        wanted = str(self.config.get("relax_type", "bulk"))
        index = self.relax_type.findData(wanted)
        self.relax_type.setCurrentIndex(index if index >= 0 else 0)
        self.max_steps = _ispin(1, 100000, int(self.config.get("relax_max_steps", 2000)))
        self.fmax = _dspin(0.001, 10.0, float(self.config.get("relax_fmax", 0.02)),
                           decimals=4, step=0.005, suffix="  eV/Å")
        self._add_card("优化设置", [
            labeled("弛豫方式 type", self.relax_type),
            labeled("最大步数 max-steps", self.max_steps),
            labeled("力收敛阈值 fmax", self.fmax),
            self._fixed_row(),
            muted("固定原子会以 Selective dynamics 写入 POSCAR 并在结果中保留。"
                  "优化脚本固定使用 CUDA 设备。"),
        ])

    def gather(self):
        return {
            "relax_type": self.relax_type.currentData(),
            "max_steps": self.max_steps.value(),
            "fmax": self.fmax.value(),
        }


class AIMDForm(BaseForm):
    key = "aimd"

    def build_params(self):
        self.temperature = _dspin(1.0, 5000.0,
                                  float(self.config.get("aimd_temperature", 300.0)),
                                  decimals=2, step=10.0, suffix="  K")
        self.timestep = _dspin(0.1, 10.0,
                               float(self.config.get("aimd_timestep", 1.0)),
                               decimals=3, step=0.5, suffix="  fs")
        self.steps = _ispin(1, 1000000, int(self.config.get("aimd_steps", 1000)))
        self.loginterval = _ispin(1, 10000, int(self.config.get("aimd_loginterval", 1)))
        self.ensemble = NoWheelComboBox()
        self.ensemble.addItems(ENSEMBLES)
        self.ensemble.setCurrentText(str(self.config.get("aimd_ensemble", "nvt")))
        self.thermostat = NoWheelComboBox()
        self.thermostat.setEditable(True)
        self.thermostat.addItems(THERMOSTATS)
        self.thermostat.setCurrentText(str(self.config.get("aimd_thermostat", "Nose-Hoover")))
        self._add_card("模拟参数", [
            labeled("温度 temperature", self.temperature),
            labeled("时间步长 timestep", self.timestep),
            labeled("总步数 steps", self.steps),
            labeled("日志间隔 loginterval", self.loginterval),
            labeled("系综 ensemble", self.ensemble),
            labeled("恒温器 thermostat", self.thermostat),
            muted("输出 CONTCAR / XDATCAR / OSZICAR / log.dat 等，"
                  "轨迹可在中间视图中逐帧播放。脚本固定使用 CUDA 设备。"),
        ])

    def gather(self):
        return {
            "temperature": self.temperature.value(),
            "timestep": self.timestep.value(),
            "steps": self.steps.value(),
            "loginterval": self.loginterval.value(),
            "ensemble": self.ensemble.currentText(),
            "thermostat": self.thermostat.currentText().strip() or "Nose-Hoover",
        }


class FreqForm(BaseForm):
    key = "freq"

    def build_params(self):
        self.delta = _dspin(0.001, 0.5, float(self.config.get("freq_delta", 0.015)),
                            decimals=4, step=0.005, suffix="  Å")
        self.nfree = NoWheelComboBox()
        self.nfree.addItems(["2", "4"])
        stored_nfree = str(int(self.config.get("freq_nfree", 2)))
        self.nfree.setCurrentText(stored_nfree if stored_nfree in ("2", "4") else "2")
        self.temperature = _dspin(1.0, 3000.0,
                                  float(self.config.get("freq_temperature", 298.15)),
                                  decimals=2, step=5.0, suffix="  K")
        self._add_card("频率参数", [
            labeled("有限位移 delta", self.delta),
            labeled("位移次数 nfree", self.nfree),
            labeled("热力学温度", self.temperature),
            self._fixed_row(),
            muted("固定原子会以 Selective dynamics 写入 POSCAR，"
                  "只有未固定原子参与振动；输出 ZPE / TS / FREQ_RESULTS。"),
        ])

    def gather(self):
        return {
            "delta": self.delta.value(),
            "nfree": int(self.nfree.currentText()),
            "temperature": self.temperature.value(),
        }


class NEBForm(BaseForm):
    key = "neb"

    def __init__(self, config: Optional[Dict[str, Any]] = None,
                 parent: Optional[QWidget] = None):
        self.neb_dir = ""
        self.neb_frames: List[Any] = []
        super().__init__(config, parent)

    def _build(self):
        self.dir_row = FileRow("选择插点路径", "未选择 00 / 01 / 02 … 目录", primary=True)
        self.dir_row.clicked.connect(lambda: self.directoryRequested.emit("neb"))
        self.image_chip = QLabel("尚未载入图像")
        self.image_chip.setObjectName("Chip")
        self._add_card("IS / 插点 / FS", [
            self.dir_row,
            self.image_chip,
            muted("选择包含连续编号子目录的路径（如 00、01、02 …）；"
                  "程序只读取每个子目录中的 POSCAR，其他格式与其他文件均忽略。"
                  "第 1 个目录为 IS、最后一个为 FS，载入后可用视图下方的"
                  "进度条逐帧预览。"),
        ])
        self.build_params()

    def build_params(self):
        self.fmax = _dspin(0.001, 10.0, float(self.config.get("neb_fmax", 0.05)),
                           decimals=4, step=0.005, suffix="  eV/Å")
        self.max_steps = _ispin(1, 100000, int(self.config.get("neb_max_steps", 2000)))
        self.spring = _dspin(0.001, 10.0, float(self.config.get("neb_spring", 0.1)),
                             decimals=3, step=0.05, suffix="  eV/Å²")
        self.climb = QCheckBox("启用 climbing image")
        self.climb.setChecked(bool(self.config.get("neb_climb", True)))
        self._add_card("搜索参数", [
            labeled("力收敛阈值 fmax", self.fmax),
            labeled("最大优化步数 max-steps", self.max_steps),
            labeled("弹簧常数 spring-constant", self.spring),
            self.climb,
            muted("图像数量由所选路径决定（IS + 插点 + FS），脚本固定使用"
                  "CUDA 设备。"),
        ])

    def set_neb_frames(self, frames, path: Optional[str]):
        self.neb_frames = list(frames)
        self.neb_dir = path or ""
        self.dir_row.set_file(path)
        count = len(self.neb_frames)
        if count:
            middle = max(0, count - 2)
            self.image_chip.setText(f"已载入 {count} 个图像（IS + {middle} 插点 + FS）")
        else:
            self.image_chip.setText("尚未载入图像")

    def gather(self):
        return {
            "neb_dir": self.neb_dir,
            "neb_frames": list(self.neb_frames),
            "fmax": self.fmax.value(),
            "max_steps": self.max_steps.value(),
            "spring": self.spring.value(),
            "climb": self.climb.isChecked(),
        }


# ---------------------------------------------------------------------------
# results
# ---------------------------------------------------------------------------
class ResultView(QFrame):
    MAX = 40

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._blocks: List[str] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 11, 12, 11)
        lay.setSpacing(6)
        head = QHBoxLayout()
        head.addWidget(section("计算结果"))
        self.count = QLabel("")
        self.count.setObjectName("Muted")
        head.addWidget(self.count)
        head.addStretch(1)
        clear = QPushButton("清空")
        clear.setObjectName("Ghost")
        clear.setCursor(Qt.PointingHandCursor)
        clear.clicked.connect(self.clear)
        head.addWidget(clear)
        lay.addLayout(head)
        self.view = QTextBrowser()
        self.view.setObjectName("Result")
        self.view.setOpenExternalLinks(False)
        self.view.setOpenLinks(False)
        self.view.document().setDefaultStyleSheet(
            ".t{font-size:12px;font-weight:600;color:#1c1c1e;}"
            ".e{font-size:12px;font-weight:600;color:#ff3b30;}"
            ".w{font-size:12px;font-weight:600;color:#ff9500;}"
            ".s{font-size:10px;color:#8e8e93;}"
            ".k{font-size:11px;color:#3c3c43;}"
            ".d{font-size:10px;color:#0a66d0;}"
        )
        lay.addWidget(self.view, 1)
        self._render()

    def clear(self):
        self._blocks = []
        self._render()

    def add(self, heading: str, status: str = "", lines: Optional[List[str]] = None,
            out_dir: Optional[str] = None, files: Optional[List[str]] = None,
            level: str = "ok"):
        cls = {"ok": "t", "warn": "w", "error": "e"}.get(level, "t")
        parts = [f'<div class="{cls}">{html.escape(heading)}</div>']
        meta = " · ".join(p for p in (datetime.now().strftime("%H:%M:%S"),
                                      html.escape(status)) if p)
        if meta:
            parts.append(f'<div class="s">{meta}</div>')
        if lines:
            parts.append('<div class="k">' +
                         "<br>".join(html.escape(str(x)) for x in lines) + '</div>')
        if files:
            parts.append('<div class="s">产物：' +
                         html.escape("、".join(files)) + '</div>')
        if out_dir:
            parts.append(f'<div class="d">目录：{html.escape(out_dir)}</div>')
        self._blocks.append("<div style='margin-bottom:9px;'>" + "".join(parts) + "</div>")
        if len(self._blocks) > self.MAX:
            self._blocks = self._blocks[-self.MAX:]
        self._render()

    def _render(self):
        body = "".join(self._blocks) or '<div class="s">暂无结果</div>'
        self.view.setHtml("<body>" + body + "</body>")
        bar = self.view.verticalScrollBar()
        bar.setValue(bar.maximum())
        self.count.setText(f"{len(self._blocks)} 条" if self._blocks else "")


class LogView(QPlainTextEdit):
    MAX_LINES = 2000

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("Log")
        self.setReadOnly(True)
        self.setMaximumBlockCount(self.MAX_LINES)
        self.setPlaceholderText("运行日志会实时显示在这里 …")

    def append_line(self, text: str):
        self.appendPlainText(text)


# ---------------------------------------------------------------------------
# right panel
# ---------------------------------------------------------------------------
class ParameterPanel(QFrame):
    runRequested = Signal(str, dict)
    cancelRequested = Signal()
    openRequested = Signal(str)
    directoryRequested = Signal(str)
    clearFixedRequested = Signal()

    def __init__(self, config: Optional[Dict[str, Any]] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setMinimumWidth(240)
        self.setMaximumWidth(470)
        self.config = config or {}

        self.forms: Dict[str, BaseForm] = {
            "single_point": SinglePointForm(self.config),
            "relax": RelaxForm(self.config),
            "aimd": AIMDForm(self.config),
            "freq": FreqForm(self.config),
            "neb": NEBForm(self.config),
        }
        for form in self.forms.values():
            form.openRequested.connect(self.openRequested)
            form.directoryRequested.connect(self.directoryRequested)
            form.clearFixedRequested.connect(self.clearFixedRequested)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        head = QVBoxLayout()
        head.setSpacing(2)
        self.heading = title("参数设置")
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("Muted")
        head.addWidget(self.heading)
        head.addWidget(self.subtitle)
        lay.addLayout(head)

        self.stack = QStackedWidget()
        for form in self.forms.values():
            self.stack.addWidget(form)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(self.stack)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.results = ResultView()
        self.log = LogView()

        self.tabs = QTabWidget()
        self.tabs.setObjectName("PanelTabs")
        self.tabs.addTab(self.results, "计算结果")
        self.tabs.addTab(self.log, "运行日志")

        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(8)
        body_lay.addWidget(scroll, 3)
        body_lay.addWidget(self.tabs, 2)
        lay.addWidget(body, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        lay.addWidget(self.progress)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.run_btn = QPushButton("开始计算")
        self.run_btn.setObjectName("Primary")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.clicked.connect(self._emit_run)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("Danger")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.cancelRequested)
        footer.addWidget(self.run_btn, 1)
        footer.addWidget(self.cancel_btn)
        lay.addLayout(footer)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(350, 640)

    # ---------------------------------------------------------------------
    def select(self, key: str):
        if key in self.forms:
            self.stack.setCurrentWidget(self.forms[key])
            self.subtitle.setText(CALC_BY_KEY[key]["sub"])

    def form(self, key: str) -> BaseForm:
        return self.forms[key]

    def current_key(self) -> str:
        return self.stack.currentWidget().key  # type: ignore[attr-defined]

    def set_busy(self, busy: bool):
        self.run_btn.setVisible(not busy)
        self.cancel_btn.setVisible(busy)
        self.progress.setVisible(busy)

    def set_structure(self, path: Optional[str]):
        for form in self.forms.values():
            form.set_structure(path)

    def set_fixed_count(self, count: int):
        for form in self.forms.values():
            form.set_fixed_count(count)

    def set_neb_frames(self, frames, path: Optional[str]):
        form = self.forms["neb"]
        if isinstance(form, NEBForm):
            form.set_neb_frames(frames, path)

    def _emit_run(self):
        form = self.stack.currentWidget()
        self.runRequested.emit(form.key, form.gather())  # type: ignore[attr-defined]


__all__ = ["CALCULATIONS", "CALC_BY_KEY", "ProjectList", "ParameterPanel",
           "BaseForm", "NEBForm", "ResultView", "LogView"]
