"""macOS-style window buttons (close, minimise, zoom) for Murmury's frameless windows."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QPushButton, QWidget

COLOURS = ("#ff5f57", "#febc2e", "#28c840")  # Apple's traffic-light colours
EDGES = ("#e0443e", "#dea123", "#1aab29")
D, GAP = 12, 8  # diameter and spacing, as on macOS


class TrafficLights(QWidget):
    """Three buttons; their symbols show while the pointer is over the group, as on macOS."""
    close_clicked = Signal()
    minimize_clicked = Signal()
    zoom_clicked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(3 * D + 2 * GAP + 2, D + 2)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.hovered = False

    def enterEvent(self, event):
        self.hovered = True
        self.update()

    def leaveEvent(self, event):
        self.hovered = False
        self.update()

    def _which(self, x: float) -> int | None:
        for i in range(3):
            left = 1 + i * (D + GAP)
            if left - GAP / 2 <= x <= left + D + GAP / 2:
                return i
        return None

    def mouseReleaseEvent(self, event):
        i = self._which(event.position().x())
        if i is not None:
            (self.close_clicked, self.minimize_clicked, self.zoom_clicked)[i].emit()

    def mousePressEvent(self, event):
        event.accept()  # keep the window from starting a drag

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for i, (fill, edge) in enumerate(zip(COLOURS, EDGES)):
            r = QRectF(1 + i * (D + GAP), 1, D, D)
            p.setPen(QPen(QColor(edge), 0.6))
            p.setBrush(QColor(fill))
            p.drawEllipse(r)
            if not self.hovered:
                continue
            c = r.center()
            p.setPen(QPen(QColor(0, 0, 0, 150), 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            k = 2.6
            if i == 0:    # ×
                p.drawLine(QPointF(c.x() - k, c.y() - k), QPointF(c.x() + k, c.y() + k))
                p.drawLine(QPointF(c.x() - k, c.y() + k), QPointF(c.x() + k, c.y() - k))
            elif i == 1:  # −
                p.drawLine(QPointF(c.x() - k - 0.5, c.y()), QPointF(c.x() + k + 0.5, c.y()))
            else:         # zoom: two small triangles
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(0, 0, 0, 150))
                p.drawPolygon([QPointF(c.x() - 3, c.y() + 0.6), QPointF(c.x() - 3, c.y() - 3), QPointF(c.x() + 0.6, c.y() - 3)])
                p.drawPolygon([QPointF(c.x() + 3, c.y() - 0.6), QPointF(c.x() + 3, c.y() + 3), QPointF(c.x() - 0.6, c.y() + 3)])


class AppearanceButton(QPushButton):
    """Sun in dark mode (go light), moon in light mode (go dark); switches the whole app."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        from . import theme
        self.setFixedSize(22, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setStyleSheet("background: transparent; border: none;")
        self.clicked.connect(theme.toggle)
        theme.watch(self.update)
        self._theme = theme

    def paintEvent(self, event):
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        colour = QColor(self._theme.palette()["secondary" if not self.underMouse() else "text"])
        c = QPointF(11, 11)
        if self._theme.is_dark():  # sun
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(colour)
            p.drawEllipse(c, 4, 4)
            p.setPen(QPen(colour, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for k in range(8):
                a = k * math.pi / 4
                p.drawLine(QPointF(11 + 6.5 * math.cos(a), 11 + 6.5 * math.sin(a)),
                           QPointF(11 + 8.5 * math.cos(a), 11 + 8.5 * math.sin(a)))
        else:                      # moon: a disc with a bite taken out
            from PySide6.QtGui import QPainterPath
            moon = QPainterPath()
            moon.addEllipse(c, 7, 7)
            bite = QPainterPath()
            bite.addEllipse(QPointF(15, 7.5), 6, 6)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(colour)
            p.drawPath(moon.subtracted(bite))

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()
