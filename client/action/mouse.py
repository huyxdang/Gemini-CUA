"""Mouse actions using macOS CoreGraphics events."""

import time

from Quartz import (
    CGEventCreateMouseEvent,
    CGEventCreateScrollWheelEvent,
    CGEventPost,
    kCGEventLeftMouseDown,
    kCGEventLeftMouseUp,
    kCGEventRightMouseDown,
    kCGEventRightMouseUp,
    kCGEventMouseMoved,
    kCGHIDEventTap,
    kCGScrollEventUnitLine,
    CGEventSetIntegerValueField,
    kCGMouseEventClickState,
)
from Quartz import CGPointMake


def _move(x: int, y: int):
    """Move the mouse cursor to (x, y) in screen points."""
    point = CGPointMake(float(x), float(y))
    event = CGEventCreateMouseEvent(None, kCGEventMouseMoved, point, 0)
    CGEventPost(kCGHIDEventTap, event)
    time.sleep(0.05)


def click(x: int, y: int, button: str = "left"):
    """Click at (x, y) in screen points."""
    point = CGPointMake(float(x), float(y))

    if button == "right":
        down_type = kCGEventRightMouseDown
        up_type = kCGEventRightMouseUp
    else:
        down_type = kCGEventLeftMouseDown
        up_type = kCGEventLeftMouseUp

    _move(x, y)

    down = CGEventCreateMouseEvent(None, down_type, point, 0)
    up = CGEventCreateMouseEvent(None, up_type, point, 0)

    CGEventPost(kCGHIDEventTap, down)
    time.sleep(0.05)
    CGEventPost(kCGHIDEventTap, up)


def double_click(x: int, y: int):
    """Double-click at (x, y) in screen points."""
    point = CGPointMake(float(x), float(y))

    _move(x, y)

    # First click
    down1 = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, point, 0)
    CGEventSetIntegerValueField(down1, kCGMouseEventClickState, 1)
    up1 = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, point, 0)
    CGEventSetIntegerValueField(up1, kCGMouseEventClickState, 1)

    CGEventPost(kCGHIDEventTap, down1)
    time.sleep(0.02)
    CGEventPost(kCGHIDEventTap, up1)
    time.sleep(0.02)

    # Second click (click state = 2 for double-click)
    down2 = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, point, 0)
    CGEventSetIntegerValueField(down2, kCGMouseEventClickState, 2)
    up2 = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, point, 0)
    CGEventSetIntegerValueField(up2, kCGMouseEventClickState, 2)

    CGEventPost(kCGHIDEventTap, down2)
    time.sleep(0.02)
    CGEventPost(kCGHIDEventTap, up2)


def scroll(x: int, y: int, direction: str = "down", amount: int = 3):
    """Scroll at (x, y). direction is 'up' or 'down'. amount is number of lines."""
    _move(x, y)

    # Positive = scroll up, negative = scroll down
    delta = amount if direction == "up" else -amount

    event = CGEventCreateScrollWheelEvent(None, kCGScrollEventUnitLine, 1, delta)
    CGEventPost(kCGHIDEventTap, event)
