"""Siri-like orb overlay using WKWebView in a transparent window."""

import time
from pathlib import Path

from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSBackingStoreBuffered,
    NSColor,
    NSScreen,
    NSWindow,
    NSWindowStyleMaskBorderless,
)
from Quartz import kCGFloatingWindowLevel
from WebKit import WKWebView, WKWebViewConfiguration

OVERLAY_SIZE = 250
BOTTOM_MARGIN = 50
VALID_STATES = {"idle", "activated", "listening", "thinking", "speaking"}
_AMP_MIN_INTERVAL = 0.05  # seconds between amplitude JS calls


class SiriOverlay:
    """Floating, click-through Siri-like orb overlay.

    States: idle, activated, listening, thinking, speaking.
    The orb is always rendered in a transparent window; visibility
    is controlled by JavaScript state transitions.
    """

    def __init__(self):
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

        screen = NSScreen.mainScreen()
        frame = screen.frame()
        x = frame.origin.x + (frame.size.width - OVERLAY_SIZE) / 2
        y = frame.origin.y + BOTTOM_MARGIN

        self._window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((x, y), (OVERLAY_SIZE, OVERLAY_SIZE)),
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False,
        )
        self._window.setLevel_(kCGFloatingWindowLevel)
        self._window.setOpaque_(False)
        self._window.setBackgroundColor_(NSColor.clearColor())
        self._window.setIgnoresMouseEvents_(True)
        self._window.setHasShadow_(False)

        config = WKWebViewConfiguration.alloc().init()
        self._webview = WKWebView.alloc().initWithFrame_configuration_(
            ((0, 0), (OVERLAY_SIZE, OVERLAY_SIZE)), config
        )
        # Transparent WKWebView background
        self._webview.setValue_forKey_(False, "drawsBackground")

        html_path = Path(__file__).parent / "overlay.html"
        self._webview.loadHTMLString_baseURL_(html_path.read_text(), None)

        self._window.setContentView_(self._webview)
        self._window.orderFront_(None)
        self._state = "idle"
        self._last_amp_time: float = 0.0

    def set_state(self, state: str):
        """Set orb state: idle, activated, listening, thinking, speaking."""
        if state not in VALID_STATES or state == self._state:
            return
        self._state = state
        self._js(f"setState('{state}')")

    def set_amplitude(self, value: float):
        """Set audio amplitude (0.0-1.0) for waveform animation. Throttled."""
        now = time.monotonic()
        if now - self._last_amp_time < _AMP_MIN_INTERVAL:
            return
        self._last_amp_time = now
        self._js(f"setAmplitude({value:.4f})")

    def teardown(self):
        """Remove the overlay window."""
        self._window.orderOut_(None)

    def _js(self, code: str):
        self._webview.evaluateJavaScript_completionHandler_(code, None)
