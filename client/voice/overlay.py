"""Pulsing dot overlay — visual feedback while recording."""

from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSBackingStoreBuffered,
    NSBezierPath,
    NSColor,
    NSScreen,
    NSView,
    NSWindow,
    NSWindowStyleMaskBorderless,
)
from Quartz import kCGFloatingWindowLevel
from Quartz import QuartzCore  # noqa: F401 — needed to enable layer-backing


DOT_SIZE = 20
BOTTOM_MARGIN = 40


class DotView(NSView):
    """A simple NSView that draws a filled red circle."""

    def drawRect_(self, rect):
        NSColor.redColor().setFill()
        NSBezierPath.bezierPathWithOvalInRect_(self.bounds()).fill()


class ListeningOverlay:
    """Floating, click-through pulsing dot shown while recording.

    Uses Core Animation opacity pulse — runs on the CA render thread,
    no run-loop interaction needed.
    """

    def __init__(self):
        # Ensure NSApplication exists (needed for NSWindow)
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

        # Position: bottom center of main screen
        screen = NSScreen.mainScreen()
        frame = screen.frame()
        x = frame.origin.x + (frame.size.width - DOT_SIZE) / 2
        y = frame.origin.y + BOTTOM_MARGIN

        self._window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((x, y), (DOT_SIZE, DOT_SIZE)),
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False,
        )
        self._window.setLevel_(kCGFloatingWindowLevel)
        self._window.setOpaque_(False)
        self._window.setBackgroundColor_(NSColor.clearColor())
        self._window.setIgnoresMouseEvents_(True)
        self._window.setHasShadow_(False)

        dot = DotView.alloc().initWithFrame_(((0, 0), (DOT_SIZE, DOT_SIZE)))
        dot.setWantsLayer_(True)
        self._window.setContentView_(dot)
        self._dot = dot

    def show(self):
        """Display the pulsing dot."""
        self._window.orderFront_(None)
        self._start_pulse()

    def hide(self):
        """Hide the dot and stop animation."""
        self._stop_pulse()
        self._window.orderOut_(None)

    def _start_pulse(self):
        layer = self._dot.layer()
        if layer is None:
            return
        pulse = QuartzCore.CABasicAnimation.animationWithKeyPath_("opacity")
        pulse.setFromValue_(1.0)
        pulse.setToValue_(0.3)
        pulse.setDuration_(0.6)
        pulse.setAutoreverses_(True)
        pulse.setRepeatCount_(float("inf"))
        layer.addAnimation_forKey_(pulse, "pulse")

    def _stop_pulse(self):
        layer = self._dot.layer()
        if layer is not None:
            layer.removeAllAnimations()
