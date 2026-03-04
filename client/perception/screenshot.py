"""Capture the macOS screen, resize, and encode as base64 PNG."""

import base64
import io

from PIL import Image
from Quartz import (
    CGDisplayBounds,
    CGMainDisplayID,
    CGWindowListCreateImage,
    kCGWindowImageDefault,
    kCGWindowListOptionOnScreenOnly,
    kCGNullWindowID,
)
from Quartz import CGImageGetWidth, CGImageGetHeight, CGImageGetBytesPerRow
from Quartz import CGImageGetDataProvider, CGDataProviderCopyData

from client.utils.config import SCREENSHOT_WIDTH


def _cgimage_to_pil(cg_image) -> Image.Image:
    """Convert a CGImage to a PIL Image."""
    width = CGImageGetWidth(cg_image)
    height = CGImageGetHeight(cg_image)
    bytes_per_row = CGImageGetBytesPerRow(cg_image)

    data_provider = CGImageGetDataProvider(cg_image)
    raw_data = CGDataProviderCopyData(data_provider)

    # CGImage is BGRA format
    img = Image.frombytes("RGBA", (width, height), raw_data, "raw", "BGRA", bytes_per_row)
    return img


def capture_screen() -> tuple[str, int, int]:
    """Capture the main display, resize to target width, return (base64_png, width, height).

    Only captures the main display (not secondary monitors) so coordinate
    mapping between screenshot space and screen points is correct.
    """
    main_display_bounds = CGDisplayBounds(CGMainDisplayID())
    cg_image = CGWindowListCreateImage(
        main_display_bounds,
        kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID,
        kCGWindowImageDefault,
    )

    if cg_image is None:
        raise RuntimeError(
            "Failed to capture screen. Check Screen Recording permission."
        )

    img = _cgimage_to_pil(cg_image)

    # Resize to target width, maintaining aspect ratio
    original_width, original_height = img.size
    scale = SCREENSHOT_WIDTH / original_width
    new_height = int(original_height * scale)
    img = img.resize((SCREENSHOT_WIDTH, new_height), Image.LANCZOS)

    # Convert to RGB (drop alpha) and encode as PNG
    img = img.convert("RGB")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    b64 = base64.b64encode(buffer.getvalue()).decode("ascii")

    return b64, SCREENSHOT_WIDTH, new_height
