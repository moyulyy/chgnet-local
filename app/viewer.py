"""3D structure viewer widget (3Dmol.js inside a QWebEngineView)."""

from __future__ import annotations

import json
import os
from typing import Iterable, List, Optional

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QSizePolicy,
                               QVBoxLayout, QWidget)

from .structure_io import frame_summary, viewer_payload
from .widgets import SegmentedControl

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(os.path.dirname(HERE), "viewer", "viewer.html")


def file_url(path: str) -> QUrl:
    """Build a ``file:`` URL for *path* with ``@`` percent-encoded.

    :meth:`QUrl.fromLocalFile` leaves ``@`` raw.  Chromium happens to accept
    it inside a ``file:`` path, but ``@`` is a URL sub-delimiter (the userinfo
    separator), so a directory such as ``C:\\Users\\name@host\\...`` produces
    an ambiguous URL.  Encoding it keeps the address unambiguous.
    """
    return QUrl(QUrl.fromLocalFile(path).toString().replace("@", "%40"))


class _Bridge(QObject):
    pageReady = Signal()
    fixedChangedJs = Signal(list)
    frameChangedJs = Signal(int)

    @Slot(str)
    def ready(self, _payload: str = ""):
        self.pageReady.emit()

    @Slot(str)
    def fixedChanged(self, payload: str):
        try:
            data = json.loads(payload) if payload else []
        except ValueError:
            data = []
        self.fixedChangedJs.emit([int(i) for i in data])

    @Slot(str)
    def frameChanged(self, payload: str):
        try:
            self.frameChangedJs.emit(int(json.loads(payload)) if payload else 0)
        except (ValueError, TypeError):
            self.frameChangedJs.emit(0)


class StructureViewer(QFrame):
    fixedChanged = Signal(list)
    frameChanged = Signal(int)

    MODES = [("rotate", "旋转"), ("atom", "点选"), ("box", "框选")]
    TIPS = ["拖拽旋转 / 滚轮缩放", "点击原子固定或取消固定", "拖出矩形批量固定"]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._ready = False
        self._queue: List[str] = []
        self._frames = []
        self._fixed: List[int] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 11, 12, 12)
        root.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        head.addStretch(1)
        self.mode = SegmentedControl([label for _k, label in self.MODES])
        for index, tip in enumerate(self.TIPS):
            self.mode.set_segment_tooltip(index, tip)
        self.mode.changed.connect(self._on_mode)
        self.mode.setMinimumWidth(120)
        head.addWidget(self.mode)
        root.addLayout(head)

        self.info = QLabel("")
        self.info.setObjectName("Muted")
        root.addWidget(self.info)

        self.web = QWebEngineView(self)
        self.web.setMinimumSize(140, 120)
        self.web.setStyleSheet("border-radius:10px;background:#ffffff;")
        settings = self.web.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, False)
        root.addWidget(self.web, 1)

        self._channel = QWebChannel(self.web.page())
        self._bridge = _Bridge(self)
        self._bridge.pageReady.connect(self._on_page_ready)
        self._bridge.fixedChangedJs.connect(self._on_fixed)
        self._bridge.frameChangedJs.connect(self.frameChanged)
        self._channel.registerObject("bridge", self._bridge)
        self.web.page().setWebChannel(self._channel)

        if os.path.exists(HTML):
            self.web.load(file_url(HTML))
        else:
            self.info.setText("缺少 viewer/viewer.html")

    # ------------------------------------------------------------- plumbing
    def _run(self, script: str):
        if self._ready:
            self.web.page().runJavaScript(script)
        else:
            self._queue.append(script)

    def _on_page_ready(self):
        self._ready = True
        queued, self._queue = self._queue, []
        for script in queued:
            self.web.page().runJavaScript(script)
        if self._frames:
            self._push()

    def _push(self):
        payload = viewer_payload(self._frames, self._fixed)
        self._run("window.setData(%s);" % json.dumps(payload))

    # --------------------------------------------------------------- public
    def set_frames(self, frames, fixed: Optional[Iterable[int]] = None):
        self._frames = list(frames)
        if fixed is not None:
            self._fixed = sorted(int(i) for i in fixed)
        count = len(self._frames[0]) if self._frames else 0
        self._fixed = [i for i in self._fixed if 0 <= i < count]
        if not self._frames:
            self.info.setText("")
            self._run("window.setData({frames:[],cell:null,fixed:[]});")
            return
        self.info.setText(frame_summary(self._frames[0], 0, len(self._frames)))
        self._push()

    def set_fixed(self, fixed: Iterable[int]):
        self._fixed = sorted(int(i) for i in fixed)
        self._run("window.setFixed(%s);" % json.dumps(self._fixed))

    def set_mode(self, mode_key: str):
        for index, (key, _label) in enumerate(self.MODES):
            if key == mode_key:
                self.mode.set_index(index)
        self._run("window.setMode(%s);" % json.dumps(mode_key))

    def reset_view(self):
        self._run("window.resetView();")

    # ---------------------------------------------------------------- slots
    def _on_mode(self, index: int):
        if 0 <= index < len(self.MODES):
            self._run("window.setMode(%s);" % json.dumps(self.MODES[index][0]))

    def _on_fixed(self, indices: List[int]):
        self._fixed = indices
        self.fixedChanged.emit(indices)


__all__ = ["StructureViewer", "file_url"]
