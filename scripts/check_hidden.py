"""Check that Murmury's window stays out of screen capture, on this Mac, now.

    uv run python scripts/check_hidden.py

Shows two boxes for a few seconds: magenta, set up exactly like Murmury's floating window, and green, an
ordinary window. Then captures the screen three ways: ScreenCaptureKit (what Zoom, Meet and Teams use),
`screencapture` (macOS screenshots) and CGWindowListCreateImage (older capture). PASS means the green box
is in every capture and the magenta one in none. Run it again after each macOS update. Nothing is saved
outside a temporary folder.
"""
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from copilot.app import configure_native_window  # noqa: E402

HERE = Path(__file__).parent


def count(path: Path, rgb: tuple[int, int, int]) -> int:
    a = np.asarray(Image.open(path).convert("RGB")).astype(int)
    return int(np.all(np.abs(a - np.array(rgb)) < 25, axis=-1).sum())


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="murmury-capture-"))
    tool = tmp / "sckshot"
    subprocess.run(["swiftc", "-O", str(HERE / "sckshot.swift"), "-o", str(tool), "-framework", "ScreenCaptureKit"],
                   check=True, capture_output=True)
    app = QApplication([])
    boxes = []
    for colour, x, hide in (("#ff00ff", 260, True), ("#00ff00", 700, False)):
        w = QWidget()
        w.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        w.setStyleSheet(f"background:{colour};")
        w.setGeometry(x, 250, 360, 260)
        w.show()
        app.processEvents()
        configure_native_window(w, hide_from_capture=hide)
        boxes.append(w)
    for _ in range(30):
        app.processEvents()
        time.sleep(0.03)
    shots = {"ScreenCaptureKit (Zoom, Meet, Teams)": tmp / "sck.png",
             "screencapture (macOS screenshots)": tmp / "screencapture.png"}
    subprocess.run([str(tool), str(shots["ScreenCaptureKit (Zoom, Meet, Teams)"])], capture_output=True, timeout=60)
    subprocess.run(["screencapture", "-x", str(shots["screencapture (macOS screenshots)"])], timeout=30)
    try:
        import Quartz
        img = Quartz.CGWindowListCreateImage(Quartz.CGRectInfinite, Quartz.kCGWindowListOptionOnScreenOnly,
                                             Quartz.kCGNullWindowID, Quartz.kCGWindowImageDefault)
        if img:
            path = tmp / "cgwindowlist.png"
            url = Quartz.CFURLCreateWithFileSystemPath(None, str(path), Quartz.kCFURLPOSIXPathStyle, False)
            dest = Quartz.CGImageDestinationCreateWithURL(url, "public.png", 1, None)
            Quartz.CGImageDestinationAddImage(dest, img, None)
            Quartz.CGImageDestinationFinalize(dest)
            shots["CGWindowListCreateImage (older capture)"] = path
    except Exception:
        pass
    for w in boxes:
        w.close()
    app.processEvents()
    ok = True
    for name, path in shots.items():
        if not path.exists():
            print(f"{name}: no capture (screen recording permission?)")
            ok = False
            continue
        hidden, control = count(path, (255, 0, 255)), count(path, (0, 255, 0))
        passed = hidden == 0 and control > 0
        ok &= passed
        print(f"{'PASS' if passed else 'FAIL'}  {name}: Murmury-style window {hidden} px, ordinary window {control} px")
    print("\nHidden from every capture." if ok else "\nNOT hidden everywhere: do not rely on it.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
