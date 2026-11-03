// Captures the main display the way Zoom, Meet and Teams do on current macOS (ScreenCaptureKit), saves a PNG,
// and lists which on-screen windows ScreenCaptureKit can see for a given owner.
import Foundation
import ScreenCaptureKit
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let out = CommandLine.arguments[1]
let sem = DispatchSemaphore(value: 0)
Task {
    do {
        let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
        guard let display = content.displays.first else { print("no display"); sem.signal(); return }
        for w in content.windows where (w.owningApplication?.applicationName ?? "").lowercased().contains("python") {
            print("SCK sees window:", w.title ?? "(no title)", w.frame)
        }
        let filter = SCContentFilter(display: display, excludingWindows: [])
        let cfg = SCStreamConfiguration()
        cfg.width = display.width
        cfg.height = display.height
        let img = try await SCScreenshotManager.captureImage(contentFilter: filter, configuration: cfg)
        let url = URL(fileURLWithPath: out) as CFURL
        let dest = CGImageDestinationCreateWithURL(url, UTType.png.identifier as CFString, 1, nil)!
        CGImageDestinationAddImage(dest, img, nil)
        CGImageDestinationFinalize(dest)
        print("SCK captured \(img.width)x\(img.height) of display \(display.width)x\(display.height)")
    } catch { print("SCK error:", error) }
    sem.signal()
}
sem.wait()
