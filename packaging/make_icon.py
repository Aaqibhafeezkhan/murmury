"""Build murmury.icns from the chosen sprite (packaging/sprites.py) on a green macOS tile and build murmury.icns with iconutil.

    uv run python packaging/make_icon.py            # the chosen palette
    uv run python packaging/make_icon.py --preview  # every palette side by side, for choosing
"""
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QRadialGradient

PALETTES = {  # tile top, tile bottom, figure tint
    "green": ("#3ad483", "#0f8a4c", "#f2fbf6"),
}
CHOSEN = "green"


def squircle(s: float) -> QPainterPath:
    """The macOS tile: straight sides joined by smooth corners (superellipse quarters), as in Apple's icon grid."""
    import math
    left, top, size, r, n = 100, 100, 824, 250, 4.2
    centres = [(left + size - r, top + r, 0), (left + r, top + r, 90), (left + r, top + size - r, 180),
               (left + size - r, top + size - r, 270)]
    path = QPainterPath()
    for k, (cx, cy, start) in enumerate(centres):
        for i in range(0, 91, 3):
            t = math.radians(start + i)
            c, d = math.cos(t), -math.sin(t)
            x = cx + r * math.copysign(abs(c) ** (2 / n), c)
            y = cy + r * math.copysign(abs(d) ** (2 / n), d)
            (path.moveTo if k == 0 and i == 0 else path.lineTo)(x * s, y * s)
    path.closeSubpath()
    return path


def sprite(s: float) -> QPainterPath:
    """A sound wave, seven rounded bars: a murmur. (No speech bubble: green and a white bubble is WhatsApp.)"""
    path = QPainterPath()
    for i, h in enumerate((150, 290, 440, 560, 440, 290, 150)):
        x = 512 + (i - 3) * 96
        path.addRoundedRect(QRectF((x - 30) * s, (512 - h / 2) * s, 60 * s, h * s), 30 * s, 30 * s)
    return path


def eyes(s: float) -> QPainterPath:
    return QPainterPath()


def draw(size: int, palette: str) -> QImage:
    top, bottom, tint = PALETTES[palette]
    s = size / 1024
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    tile = squircle(s)
    background = QLinearGradient(0, 100 * s, 0, 924 * s)
    background.setColorAt(0, QColor(top))
    background.setColorAt(1, QColor(bottom))
    p.setBrush(background)
    p.drawPath(tile)
    shine = QRadialGradient(QPointF(512 * s, 120 * s), 620 * s)  # soft light from above
    shine.setColorAt(0, QColor(255, 255, 255, 70))
    shine.setColorAt(1, QColor(255, 255, 255, 0))
    p.setBrush(shine)
    p.drawPath(tile)
    p.setClipPath(tile)
    figure = sprite(s).subtracted(eyes(s))
    for offset, alpha in ((6, 26), (12, 18), (20, 10)):   # a soft shadow below the outline, not in the eyes
        p.setBrush(QColor(0, 0, 0, alpha))
        p.drawPath(sprite(s).translated(0, offset * s).subtracted(sprite(s)))
    body = QLinearGradient(0, 200 * s, 0, 1000 * s)
    body.setColorAt(0, QColor("white"))
    body.setColorAt(1, QColor(tint))
    p.setBrush(body)
    p.drawPath(figure)
    p.end()
    return image


def main() -> None:
    QGuiApplication(sys.argv)
    here = Path(__file__).parent
    if "--preview" in sys.argv:
        sheet = QImage(3 * 560, 560, QImage.Format.Format_ARGB32_Premultiplied)
        sheet.fill(QColor("#1d1f24"))
        p = QPainter(sheet)
        for i, name in enumerate(PALETTES):
            p.drawImage(i * 560 + 24, 24, draw(512, name))
        p.end()
        sheet.save(str(here / "icon-preview.png"))
        print("preview written")
        return
    out = here / "murmury.iconset"
    out.mkdir(exist_ok=True)
    from sprites import draw as draw_sprite  # the chosen character: the sprite with the curl
    for size in (16, 32, 64, 128, 256, 512, 1024):
        image = draw_sprite(size, "tall")
        if size <= 512:
            image.save(str(out / f"icon_{size}x{size}.png"))
        if size >= 32:
            image.save(str(out / f"icon_{size // 2}x{size // 2}@2x.png"))
    subprocess.run(["iconutil", "-c", "icns", str(out), "-o", str(here / "murmury.icns")], check=True)
    print("icon written")


if __name__ == "__main__":
    main()
