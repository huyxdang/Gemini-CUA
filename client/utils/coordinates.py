"""Coordinate conversion between macOS points and pixels (Retina)."""

from AppKit import NSScreen


def get_scale_factor() -> float:
    """Get the Retina scale factor for the main screen."""
    screen = NSScreen.mainScreen()
    if screen is None:
        return 2.0  # default assumption for Retina Macs
    return screen.backingScaleFactor()


def points_to_pixels(x: int, y: int) -> tuple[int, int]:
    """Convert macOS points to pixel coordinates."""
    scale = get_scale_factor()
    return int(x * scale), int(y * scale)


def pixels_to_points(x: int, y: int) -> tuple[int, int]:
    """Convert pixel coordinates to macOS points."""
    scale = get_scale_factor()
    return int(x / scale), int(y / scale)


def screenshot_to_points(
    sx: int, sy: int, screenshot_width: int, screenshot_height: int
) -> tuple[int, int]:
    """Convert coordinates from the resized screenshot back to macOS screen points.

    The screenshot is resized from native resolution to screenshot_width.
    We need to map back to the actual screen point coordinates.
    """
    screen = NSScreen.mainScreen()
    if screen is None:
        return sx, sy

    frame = screen.frame()
    screen_width = frame.size.width  # in points
    screen_height = frame.size.height  # in points

    scale_x = screen_width / screenshot_width
    scale_y = screen_height / screenshot_height

    return int(sx * scale_x), int(sy * scale_y)
