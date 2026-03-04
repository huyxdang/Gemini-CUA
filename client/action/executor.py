"""Action dispatcher — routes action JSON to the appropriate mouse/keyboard function."""

import subprocess
import time

from client.action import mouse, keyboard
from client.utils.coordinates import screenshot_to_points


def execute_action(action: dict, screenshot_width: int, screenshot_height: int):
    """Execute an action returned by the cloud agent.

    Coordinates in the action are in screenshot space (resized image).
    They are converted to macOS screen points before execution.
    """
    name = action["action"]
    params = action.get("params", {})

    match name:
        case "click":
            x, y = _convert_coords(
                params["x"], params["y"], screenshot_width, screenshot_height
            )
            mouse.click(x, y, params.get("button", "left"))

        case "double_click":
            x, y = _convert_coords(
                params["x"], params["y"], screenshot_width, screenshot_height
            )
            mouse.double_click(x, y)

        case "type_text":
            keyboard.type_text(params["text"])

        case "press_key":
            keyboard.press_key(params["key"], params.get("modifiers", []))
            # Extra delay after modifier combos to let the system process them
            if params.get("modifiers"):
                time.sleep(0.3)

        case "scroll":
            x, y = _convert_coords(
                params["x"], params["y"], screenshot_width, screenshot_height
            )
            mouse.scroll(x, y, params.get("direction", "down"), params.get("amount", 3))

        case "open_app":
            _open_app(params["app_name"])

        case "wait":
            time.sleep(params.get("seconds", 1.0))

        case _:
            raise ValueError(f"Unknown action: {name}")


def _open_app(app_name: str):
    """Open a macOS application by name using the `open` command.

    This is more reliable than simulating Cmd+Space → type name → Enter,
    because synthetic CGEvents don't always trigger system shortcuts.
    """
    result = subprocess.run(
        ["open", "-a", app_name],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to open '{app_name}': {result.stderr.strip()}")
    # Give the app time to launch and gain focus
    time.sleep(1.5)


def _convert_coords(
    x: int, y: int, screenshot_width: int, screenshot_height: int
) -> tuple[int, int]:
    """Convert screenshot-space coordinates to macOS screen points, clamped to screen bounds."""
    from AppKit import NSScreen

    px, py = screenshot_to_points(x, y, screenshot_width, screenshot_height)

    screen = NSScreen.mainScreen()
    if screen is not None:
        frame = screen.frame()
        px = max(0, min(px, int(frame.size.width) - 1))
        py = max(0, min(py, int(frame.size.height) - 1))

    return px, py
