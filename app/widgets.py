"""Small reusable UI pieces."""

from __future__ import annotations

import math
import os
from typing import List, Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDoubleSpinBox,
                               QFrame, QHBoxLayout, QLabel, QPushButton,
                               QSizePolicy, QSpinBox, QToolButton,
                               QVBoxLayout, QWidget)


def card() -> QFrame:
    frame = QFrame()
    frame.setObjectName("Card")
    return frame


def title(text: str, role: str = "H1") -> QLabel:
    label = QLabel(text)
    label.setObjectName(role)
    return label


def section(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Section")
    return label


def muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Muted")
    label.setWordWrap(True)
    return label


def labeled(text: str, widget: QWidget) -> QWidget:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(5)
    caption = QLabel(text)
    caption.setObjectName("Field")
    caption.setWordWrap(True)          # let long captions wrap instead of
    caption.setMinimumWidth(0)         # forcing the panel to grow
    lay.addWidget(caption)
    lay.addWidget(widget)
    return box


class NoWheelComboBox(QComboBox):
    """Combo box that ignores the mouse wheel unless its popup is open.

    Scrolling the parameter panel must never silently change a selection;
    the options only change after the user opens the drop-down (or uses the
    keyboard).
    """

    def wheelEvent(self, event):  # noqa: N802
        if self.view().isVisible():
            super().wheelEvent(event)
        else:
            event.ignore()


class NoWheelSpinBox(QSpinBox):
    """Spin box that only changes via its arrows / keyboard, never the wheel."""

    def wheelEvent(self, event):  # noqa: N802
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """Floating point spin box that ignores the mouse wheel."""

    def wheelEvent(self, event):  # noqa: N802
        event.ignore()


class SegmentedControl(QFrame):
    """iOS style segmented control with per-segment enabling."""

    changed = Signal(int)

    def __init__(self, items: List[str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("Segmented")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: List[QToolButton] = []
        self._segment_enabled: List[bool] = []
        for index, text in enumerate(items):
            button = QToolButton()
            button.setText(text)
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            button.clicked.connect(lambda _c=False, i=index: self.changed.emit(i))
            self._group.addButton(button, index)
            self._buttons.append(button)
            self._segment_enabled.append(True)
            lay.addWidget(button)
        if self._buttons:
            self._buttons[0].setChecked(True)

    def index(self) -> int:
        return self._group.checkedId()

    def set_index(self, index: int, emit: bool = False):
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)
            if emit:
                self.changed.emit(index)

    def set_segment_enabled(self, index: int, enabled: bool):
        if 0 <= index < len(self._buttons):
            self._segment_enabled[index] = enabled
            self._buttons[index].setEnabled(self.isEnabled() and enabled)

    def set_segment_tooltip(self, index: int, tip: str):
        if 0 <= index < len(self._buttons):
            self._buttons[index].setToolTip(tip)

    def setEnabled(self, enabled: bool):  # noqa: N802
        super().setEnabled(enabled)
        for i, button in enumerate(self._buttons):
            button.setEnabled(enabled and self._segment_enabled[i])


class FileRow(QWidget):
    """Tinted button + selected file name."""

    clicked = Signal()

    def __init__(self, button_text: str, empty_text: str, primary: bool = False,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._empty = empty_text
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.button = QPushButton(button_text)
        self.button.setObjectName("Primary" if primary else "Tint")
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.setMinimumWidth(88)
        self.button.clicked.connect(self.clicked)
        self.name = QLabel(empty_text)
        self.name.setObjectName("Field")
        self.name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay.addWidget(self.button)
        lay.addWidget(self.name, 1)

    def set_file(self, path: Optional[str]):
        if path:
            self.name.setText(os.path.basename(path))
            self.name.setToolTip(path)
        else:
            self.name.setText(self._empty)
            self.name.setToolTip("")


class TaskIcon(QWidget):
    """Small vector pictogram for a calculation task (drawn, not emoji)."""

    def __init__(self, kind: str, color: str, size: int = 30,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.kind = kind
        self._color = QColor(color)
        self.setFixedSize(size, size)

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        box = QPainterPath()
        box.addRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 8.5, 8.5)
        painter.fillPath(box, self._color)
        painter.save()
        painter.scale(self.width() / 24.0, self.height() / 24.0)
        pen = QPen(QColor(255, 255, 255, 245))
        pen.setWidthF(1.9)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        drawer = getattr(self, "_" + self.kind, None) or TaskIcon._single_point
        drawer(painter)
        painter.restore()

    @staticmethod
    def _fill(painter):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 250))

    @staticmethod
    def _single_point(painter):
        TaskIcon._fill(painter)
        painter.drawPolygon(QPolygonF([
            QPointF(13.4, 2.6), QPointF(5.8, 13.2), QPointF(11.0, 13.2),
            QPointF(8.8, 21.4), QPointF(18.2, 10.6), QPointF(12.6, 10.6)]))

    @staticmethod
    def _trajectory(painter):
        path = QPainterPath(QPointF(3.5, 5.0))
        for point in ((8.5, 5.0), (8.5, 10.5), (13.5, 10.5), (13.5, 16.0), (20.0, 16.0)):
            path.lineTo(*point)
        painter.drawPath(path)
        TaskIcon._fill(painter)
        painter.drawEllipse(QPointF(20.0, 16.0), 2.0, 2.0)

    @staticmethod
    def _surface_fixed(painter):
        TaskIcon._fill(painter)
        for y in (5.4, 10.6, 15.8):
            bar = QPainterPath()
            bar.addRoundedRect(QRectF(4.5, y, 15.0, 3.2), 1.6, 1.6)
            painter.drawPath(bar)

    @staticmethod
    def _adsorption_vibration(painter):
        path = QPainterPath(QPointF(3.0, 12.0))
        for i in range(1, 19):
            path.lineTo(3.0 + i, 12.0 - 4.4 * math.sin(i / 18.0 * 2.0 * math.pi))
        painter.drawPath(path)

    @staticmethod
    def _double_end_search(painter):
        path = QPainterPath(QPointF(3.5, 17.5))
        path.cubicTo(7.5, 17.5, 8.0, 6.0, 12.0, 6.0)
        path.cubicTo(16.0, 6.0, 16.5, 17.5, 20.5, 17.5)
        painter.drawPath(path)
        TaskIcon._fill(painter)
        for point in (QPointF(3.5, 17.5), QPointF(12.0, 6.0), QPointF(20.5, 17.5)):
            painter.drawEllipse(point, 1.9, 1.9)

    @staticmethod
    def _aimd(painter):
        # a particle with motion arcs: dynamics
        path = QPainterPath(QPointF(3.4, 12.0))
        path.arcMoveTo(3.4, 7.0, 17.2, 10.0, 0)
        path.arcTo(3.4, 7.0, 17.2, 10.0, 0, 180)
        painter.drawPath(path)
        path2 = QPainterPath(QPointF(6.6, 12.0))
        path2.arcMoveTo(6.6, 9.2, 10.8, 5.6, 0)
        path2.arcTo(6.6, 9.2, 10.8, 5.6, 0, 180)
        painter.drawPath(path2)
        TaskIcon._fill(painter)
        painter.drawEllipse(QPointF(17.6, 7.6), 2.4, 2.4)

    @staticmethod
    def _charge(painter):
        painter.drawEllipse(QPointF(12.0, 12.0), 7.2, 7.2)
        path = QPainterPath(QPointF(12.0, 8.2))
        path.lineTo(12.0, 15.8)
        path.moveTo(8.2, 12.0)
        path.lineTo(15.8, 12.0)
        painter.drawPath(path)


__all__ = ["card", "title", "section", "muted", "labeled",
           "SegmentedControl", "FileRow", "TaskIcon", "NoWheelComboBox",
           "NoWheelSpinBox", "NoWheelDoubleSpinBox"]
