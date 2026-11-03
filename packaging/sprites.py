"""Three sprite variants for the Murmury icon, drawn on the macOS tile, side by side for choosing."""
import sys
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath,
                           QPainterPathStroker, QRadialGradient, QTransform)
sys.path.insert(0, "packaging")
from make_icon import squircle

TOP, BOTTOM, TINT = "#3ad483", "#0f8a4c", "#dff5e8"


def soften(path: QPainterPath, s: float, r: float = 10) -> QPainterPath:
    """Round the outer corners of a silhouette by a few pixels."""
    st = QPainterPathStroker()
    st.setWidth(r * s)
    st.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return path.united(st.createStroke(path)).simplified()


def base(s: float, ear_tip: tuple, ear_inner: float) -> QPainterPath:
    """Head (a soft rounded block), elf ears growing up and out, narrow shoulders."""
    P = lambda x, y: QPointF(x * s, y * s)
    head = QPainterPath()
    head.addRoundedRect(QRectF(262 * s, 360 * s, 500 * s, 360 * s), 170 * s, 170 * s)
    for side in (-1, 1):
        tx, ty = ear_tip
        ear = QPainterPath(P(512 + side * 120, 420))
        ear.cubicTo(P(512 + side * 200, 380), P(512 + side * (tx - 40), ty + 60), P(512 + side * tx, ty))   # outer edge up to the tip
        ear.cubicTo(P(512 + side * (tx - 20), ty + 120), P(512 + side * ear_inner, 470), P(512 + side * 240, 560))
        ear.closeSubpath()
        head = head.united(ear)
    body = QPainterPath(P(400, 690))
    body.cubicTo(P(380, 760), P(320, 820), P(300, 940))
    body.lineTo(P(724, 940))
    body.cubicTo(P(704, 820), P(644, 760), P(624, 690))
    body.closeSubpath()
    return head.united(body)


def eyes(s: float) -> QPainterPath:
    path = QPainterPath()
    for cx, angle in ((410, 8), (614, -8)):  # between the first flat ovals and round: a soft, slightly tilted oval
        e = QPainterPath()
        e.addEllipse(QPointF(0, 0), 67 * s, 59 * s)
        path = path.united(QTransform().translate(cx * s, 562 * s).rotate(angle).map(e))
    return path


def variant(name: str, s: float, holes: bool = True) -> QPainterPath:
    P = lambda x, y: QPointF(x * s, y * s)
    if name == "sprout":       # ears up and out, a two-leaf sprout
        fig = base(s, (300, 250), 190)
        stem = QPainterPath(P(504, 372)); stem.cubicTo(P(500, 330), P(506, 300), P(512, 282))
        stem.cubicTo(P(518, 300), P(524, 330), P(520, 372)); stem.closeSubpath()
        for side in (-1, 1):
            leaf = QPainterPath(P(512, 296))
            leaf.cubicTo(P(512 + side * 30, 236), P(512 + side * 90, 222), P(512 + side * 128, 240))
            leaf.cubicTo(P(512 + side * 100, 292), P(512 + side * 50, 312), P(512, 296))
            stem = stem.united(leaf)
        fig = fig.united(stem)
    elif name == "cap":        # ears out, a soft pointed cap flopping to the right
        fig = base(s, (330, 330), 200)
        cap = QPainterPath(P(300, 450))
        cap.cubicTo(P(300, 330), P(400, 250), P(520, 230))
        cap.cubicTo(P(640, 214), P(730, 250), P(790, 330))
        cap.cubicTo(P(806, 350), P(800, 372), P(778, 372))
        cap.cubicTo(P(744, 330), P(700, 316), P(680, 330))
        cap.cubicTo(P(720, 380), P(728, 420), P(724, 450))
        cap.closeSubpath()
        ball = QPainterPath(); ball.addEllipse(P(790, 380), 34 * s, 34 * s)
        fig = fig.united(cap).united(ball)
    else:                      # "tall": long ears straight up, a little curl of hair
        fig = base(s, (250, 200), 170)
        curl = QPainterPath(P(470, 372))
        curl.cubicTo(P(450, 300), P(500, 250), P(560, 262))
        curl.cubicTo(P(600, 270), P(604, 316), P(574, 326))
        curl.cubicTo(P(586, 300), P(566, 290), P(548, 300))
        curl.cubicTo(P(524, 314), P(526, 350), P(540, 372))
        curl.closeSubpath()
        fig = fig.united(curl)
    fig = soften(fig, s)
    return fig.subtracted(eyes(s)) if holes else fig


def draw(size: int, name: str) -> QImage:
    s = size / 1024
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied); img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setPen(Qt.PenStyle.NoPen)
    tile = squircle(s)
    g = QLinearGradient(0, 100 * s, 0, 924 * s); g.setColorAt(0, QColor(TOP)); g.setColorAt(1, QColor(BOTTOM))
    p.setBrush(g); p.drawPath(tile)
    shine = QRadialGradient(QPointF(512 * s, 100 * s), 640 * s)
    shine.setColorAt(0, QColor(255, 255, 255, 60)); shine.setColorAt(1, QColor(255, 255, 255, 0))
    p.setBrush(shine); p.drawPath(tile)
    p.setClipPath(tile)
    glossy = False  # glossy black eyes were tried on the app icon; the two-colour cut-out eyes read better
    fig = variant(name, s, holes=not glossy)
    for off, a in ((8, 30), (16, 18), (26, 9)):
        p.setBrush(QColor(0, 60, 30, a)); p.drawPath(fig.translated(0, off * s).subtracted(fig))
    body = QLinearGradient(0, 220 * s, 0, 940 * s); body.setColorAt(0, QColor("white")); body.setColorAt(1, QColor(TINT))
    p.setBrush(body); p.drawPath(fig)
    if glossy:
        for cx in (414, 610):  # big glossy eyes, a little taller than wide, each with two highlights
            iris = QRadialGradient(QPointF((cx - 14) * s, 540 * s), 90 * s)
            iris.setColorAt(0, QColor("#2b3a33")); iris.setColorAt(1, QColor("#08120d"))
            p.setBrush(iris); p.drawEllipse(QPointF(cx * s, 562 * s), 60 * s, 70 * s)
            p.setBrush(QColor(255, 255, 255, 235)); p.drawEllipse(QPointF((cx - 20) * s, 534 * s), 17 * s, 15 * s)
            p.setBrush(QColor(255, 255, 255, 150)); p.drawEllipse(QPointF((cx + 22) * s, 590 * s), 7 * s, 7 * s)
    p.end()
    return img


if __name__ == "__main__":
    QGuiApplication(sys.argv)
    names = ["sprout", "cap", "tall"]
    sheet = QImage(3 * 560, 600, QImage.Format.Format_ARGB32_Premultiplied); sheet.fill(QColor("#f1f4f2"))
    p = QPainter(sheet)
    for i, n in enumerate(names):
        p.drawImage(i * 560 + 24, 24, draw(512, n))
        p.drawImage(i * 560 + 24 + 200, 548, draw(48, n))  # small, as in the Dock or Finder
    p.end()
    sheet.save("packaging/icon-preview.png")
    print("ok")
