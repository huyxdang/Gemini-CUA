"""Screen capture for Live API — JPEG encoding for efficient streaming."""

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

CAPTURE_WIDTH = 1280


def capture_screen_jpeg(quality: int = 75) -> tuple[bytes, int, int]:
    """Capture the main display, resize, return (jpeg_bytes, width, height)."""
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

    width = CGImageGetWidth(cg_image)
    height = CGImageGetHeight(cg_image)
    bytes_per_row = CGImageGetBytesPerRow(cg_image)
    data_provider = CGImageGetDataProvider(cg_image)
    raw_data = CGDataProviderCopyData(data_provider)

    img = Image.frombytes("RGBA", (width, height), raw_data, "raw", "BGRA", bytes_per_row)

    scale = CAPTURE_WIDTH / width
    new_height = int(height * scale)
    img = img.resize((CAPTURE_WIDTH, new_height), Image.LANCZOS)
    img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue(), CAPTURE_WIDTH, new_height
