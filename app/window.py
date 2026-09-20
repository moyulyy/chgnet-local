"""Frameless rounded window with iOS style traffic-light controls.

The window has a **fixed, non-draggable size** (no splitters, no edge-resize
hit-testing, no size grip) so nothing in the content area can accidentally
resize or move it.  Only the maximise button changes the geometry.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QAbstractButton, QDialog, QFrame, QHBoxLayout,
                               QMainWindow, QWidget)


class TrafficLightButton(QAbstractButton):
    COLORS = {"close": "#FF5F57", "min": "#FEBC2E", "max": "#28C840"}

    def __init__(self, kind: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(13, 13)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip({"close": "关闭", "min": "最小化", "max": "最大化"}[kind])
        self._hover = False
        self._color = QColor(self.COLORS[kind])

    def enterEvent(self, event):  # noqa: N802
        self._hover = True
        self.update()

    def leaveEvent(self, event):  # noqa: N802
        self._hover = False
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(0, 0, -1, -1)
        p.setPen(Qt.NoPen)
        p.setBrush(self._color)
        p.drawEllipse(rect)
        if not self._hover:
            return
        pen = QPen(QColor(120, 0, 0, 220) if self.kind == "close" else QColor(100, 45, 0, 210))
        pen.setWidthF(1.5)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        inner = rect.adjusted(3, 3, -3, -3)
        if self.kind == "close":
            p.drawLine(inner.topLeft(), inner.bottomRight())
            p.drawLine(inner.topRight(), inner.bottomLeft())
        elif self.kind == "min":
            y = rect.center().y()
            p.drawLine(inner.left(), y, inner.right(), y)
        else:
            cx, cy = rect.center().x(), rect.center().y()
            p.drawLine(inner.left(), cy, inner.right(), cy)
            p.drawLine(cx, inner.top(), cx, inner.bottom())


class TitleBar(QFrame):
    """Slim draggable bar that only holds the window controls."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(44)
        self._offset: Optional[QPoint] = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(8)

        self.close_btn = TrafficLightButton("close")
        self.min_btn = TrafficLightButton("min")
        self.max_btn = TrafficLightButton("max")
        self.close_btn.clicked.connect(lambda: self.window().close())
        self.min_btn.clicked.connect(lambda: self.window().showMinimized())
        self.max_btn.clicked.connect(lambda: self.window().toggle_maximize())
        for button in (self.close_btn, self.min_btn, self.max_btn):
            lay.addWidget(button)
        lay.addStretch(1)

    # dragging is deliberately limited to this bar only -------------------
    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._offset = (event.globalPosition().toPoint()
                            - self.window().frameGeometry().topLeft())
            event.accept()

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._offset is None or not (event.buttons() & Qt.LeftButton):
            return
        window = self.window()
        if window.is_maximized():
            window.restore()
            self._offset = QPoint(int(window.width() * 0.5), self._offset.y())
        window.move(event.globalPosition().toPoint() - self._offset)
        event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802
        self._offset = None

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.window().toggle_maximize()


class FramelessWindow(QMainWindow):
    """Translucent frameless window; the rounded surface comes from QSS."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._maximized = False
        self._normal_geometry = None
        self.title_bar: Optional[TitleBar] = None

    # ------------------------------------------------------------------ api
    def is_maximized(self) -> bool:
        return self._maximized

    def toggle_maximize(self):
        self.restore() if self._maximized else self.maximize()

    def maximize(self):
        screen = self.screen()
        if screen is None:
            return
        self._normal_geometry = self.geometry()
        self._maximized = True
        self.setGeometry(screen.availableGeometry())

    def restore(self):
        if not self._maximized:
            return
        self._maximized = False
        if self._normal_geometry is not None:
            self.setGeometry(self._normal_geometry)


class FramelessDialog(QDialog):
    """Rounded frameless dialog used for the settings sheet."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setMinimumWidth(420)
        self._offset: Optional[QPoint] = None

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._offset = (event.globalPosition().toPoint()
                            - self.frameGeometry().topLeft())
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._offset is not None and (event.buttons() & Qt.LeftButton):
            self.move(event.globalPosition().toPoint() - self._offset)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        self._offset = None
        super().mouseReleaseEvent(event)


__all__ = ["FramelessWindow", "FramelessDialog", "TitleBar", "TrafficLightButton"]
