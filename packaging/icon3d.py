"""The app icon with the 3D elf: a cut-out render (site/assets/elf-*.webp) on Murmury's green macOS tile.

    uv run python packaging/icon3d.py --preview     # the three poses side by side, large and small
    uv run python packaging/icon3d.py whisper       # build murmury.icns from that pose
"""
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QRadialGradient

sys.path.insert(0, str(Path(__file__).parent))
from make_icon import squircle  # noqa: E402  the same macOS tile shape

HERE = Path(__file__).parent
ELVES = HERE.parent / "site" / "assets"
TOP, BOTTOM = "#43d98b", "#0e8a4b"
# how each render sits on the tile: height of the elf in tile units (1024 grid), horizontal nudge
FRAMING = {"whisper": (880, 10), "paper": (860, -36), "sly": (870, 0)}


def draw(size: int, pose: str) -> QImage:
    s = size / 1024
    elf = QImage(str(ELVES / f"elf-{pose}.webp"))
    height, nudge = FRAMING[pose]
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
    tile = squircle(s)
    background = QLinearGradient(0, 100 * s, 0, 924 * s)
    background.setColorAt(0, QColor(TOP))
    background.setColorAt(1, QColor(BOTTOM))
    p.fillPath(tile, background)
    glow = QRadialGradient(QPointF(512 * s, 420 * s), 420 * s)  # soft light behind the elf
    glow.setColorAt(0, QColor(255, 255, 255, 90))
    glow.setColorAt(1, QColor(255, 255, 255, 0))
    p.fillPath(tile, glow)
    p.setClipPath(tile)
    h = height * s
    w = h * elf.width() / elf.height()
    target = QRectF((1024 * s - w) / 2 + nudge * s, 924 * s - h * 0.88, w, h)  # ears inside, feet run off the bottom edge
    shadow = elf.copy()  # a soft dark copy below, so the white figure lifts off the tile
    sp = QPainter(shadow)
    sp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    sp.fillRect(shadow.rect(), QColor(0, 60, 30, 26))
    sp.end()
    for dx, dy in ((0, 8), (0, 14), (0, 22), (-4, 30), (4, 30)):
        p.drawImage(target.translated(dx * s, dy * s), shadow)
    p.drawImage(target, elf)
    sheen = QLinearGradient(0, 100 * s, 0, 520 * s)  # the glassy top-light macOS icons have
    sheen.setColorAt(0, QColor(255, 255, 255, 46))
    sheen.setColorAt(1, QColor(255, 255, 255, 0))
    p.setClipping(False)
    p.fillPath(tile, sheen)
    p.end()
    return image


def build(pose: str) -> None:
    out = HERE / "murmury.iconset"
    out.mkdir(exist_ok=True)
    for size in (16, 32, 64, 128, 256, 512, 1024):
        image = draw(size, pose)
        if size <= 512:
            image.save(str(out / f"icon_{size}x{size}.png"))
        if size >= 32:
            image.save(str(out / f"icon_{size // 2}x{size // 2}@2x.png"))
    subprocess.run(["iconutil", "-c", "icns", str(out), "-o", str(HERE / "murmury.icns")], check=True)
    draw(256, pose).save(str(HERE.parent / "copilot" / "assets" / "icon.png"))  # the setup screen's header
    print("icon written:", pose)


def preview() -> None:
    poses = list(FRAMING)
    sheet = QImage(len(poses) * 560, 640, QImage.Format.Format_ARGB32_Premultiplied)
    sheet.fill(QColor("#1d1f24"))
    p = QPainter(sheet)
    for i, pose in enumerate(poses):
        p.drawImage(i * 560 + 24, 24, draw(512, pose))
        p.drawImage(i * 560 + 180, 560, draw(64, pose))   # Dock size
        p.drawImage(i * 560 + 270, 576, draw(32, pose))   # Finder list size
    p.end()
    sheet.save(str(HERE / "icon-preview.png"))
    print("preview written")


if __name__ == "__main__":
    QGuiApplication(sys.argv)
    preview() if "--preview" in sys.argv else build(sys.argv[1] if len(sys.argv) > 1 else "whisper")
