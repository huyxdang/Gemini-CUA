"""Read the macOS accessibility tree and produce a compact text representation."""

from ApplicationServices import (
    AXUIElementCreateSystemWide,
    AXUIElementCopyAttributeValue,
    AXValueGetType,
    kAXValueCGPointType,
    kAXValueCGSizeType,
)
from ApplicationServices import AXValueGetValue
import Quartz

MAX_DEPTH = 6
MAX_CHARS = 4000

# Roles to skip (decorative / container noise)
SKIP_ROLES = {
    "AXGroup",
    "AXSplitGroup",
    "AXScrollArea",
    "AXLayoutArea",
    "AXLayoutItem",
    "AXUnknown",
}


def _get_attr(element, attr):
    """Safely get an AX attribute, returning None on failure."""
    err, value = AXUIElementCopyAttributeValue(element, attr, None)
    if err == 0:
        return value
    return None


def _get_position(element) -> tuple[int, int] | None:
    """Get the (x, y) position of an AX element in screen points."""
    pos_value = _get_attr(element, "AXPosition")
    if pos_value is None:
        return None
    try:
        if AXValueGetType(pos_value) == kAXValueCGPointType:
            ok, point = AXValueGetValue(pos_value, kAXValueCGPointType, None)
            if ok:
                return (int(point.x), int(point.y))
    except Exception:
        pass
    return None


def _get_size(element) -> tuple[int, int] | None:
    """Get the (width, height) of an AX element."""
    size_value = _get_attr(element, "AXSize")
    if size_value is None:
        return None
    try:
        if AXValueGetType(size_value) == kAXValueCGSizeType:
            ok, size = AXValueGetValue(size_value, kAXValueCGSizeType, None)
            if ok:
                return (int(size.width), int(size.height))
    except Exception:
        pass
    return None


def _walk(element, depth: int, lines: list[str], char_count: list[int]):
    """Recursively walk the AX tree, appending compact descriptions."""
    if depth > MAX_DEPTH or char_count[0] >= MAX_CHARS:
        return

    role = _get_attr(element, "AXRole") or ""
    if role in SKIP_ROLES:
        # Still walk children of skipped containers
        children = _get_attr(element, "AXChildren")
        if children:
            for child in children:
                _walk(child, depth, lines, char_count)
        return

    # Build description
    title = _get_attr(element, "AXTitle") or ""
    value = _get_attr(element, "AXValue")
    description = _get_attr(element, "AXDescription") or ""
    role_desc = _get_attr(element, "AXRoleDescription") or ""
    enabled = _get_attr(element, "AXEnabled")
    focused = _get_attr(element, "AXFocused")

    # Determine label
    label = title or description or (str(value) if value and str(value).strip() else "")
    if not label and not role_desc:
        # Skip elements with no useful info
        children = _get_attr(element, "AXChildren")
        if children:
            for child in children:
                _walk(child, depth, lines, char_count)
        return

    # Position and size
    pos = _get_position(element)
    size = _get_size(element)

    # Short role name (strip "AX" prefix)
    short_role = role[2:] if role.startswith("AX") else role

    # Build the line
    indent = "  " * depth
    parts = [f"{indent}[{short_role}"]

    if label:
        # Truncate long labels
        if len(label) > 60:
            label = label[:57] + "..."
        parts.append(f' "{label}"')

    if pos and size:
        parts.append(f" ({pos[0]},{pos[1]} {size[0]}x{size[1]})")
    elif pos:
        parts.append(f" ({pos[0]},{pos[1]})")

    flags = []
    if enabled is False:
        flags.append("disabled")
    if focused is True:
        flags.append("focused")
    if flags:
        parts.append(f" {' '.join(flags)}")

    parts.append("]")
    line = "".join(parts)

    if char_count[0] + len(line) > MAX_CHARS:
        lines.append(f"{indent}[... truncated]")
        char_count[0] = MAX_CHARS
        return

    lines.append(line)
    char_count[0] += len(line) + 1  # +1 for newline

    # Recurse into children
    children = _get_attr(element, "AXChildren")
    if children:
        for child in children:
            _walk(child, depth + 1, lines, char_count)


def _get_frontmost_app():
    """Get the frontmost application's AX element, with fallback to NSWorkspace."""
    from ApplicationServices import AXUIElementCreateApplication

    # Try the system-wide focused application first
    system_wide = AXUIElementCreateSystemWide()
    focused_app = _get_attr(system_wide, "AXFocusedApplication")
    if focused_app is not None:
        return focused_app

    # Fallback: use NSWorkspace to find the frontmost app by PID
    from AppKit import NSWorkspace

    ws = NSWorkspace.sharedWorkspace()
    app = ws.frontmostApplication()
    if app is None:
        return None

    return AXUIElementCreateApplication(app.processIdentifier())


def read_accessibility_tree() -> str:
    """Read the accessibility tree for the frontmost application and return compact text."""
    ax_app = _get_frontmost_app()
    if ax_app is None:
        return "(no focused application)"

    app_title = _get_attr(ax_app, "AXTitle") or "Unknown"

    lines = [f"ACCESSIBILITY TREE (focused app: {app_title}):"]
    char_count = [len(lines[0]) + 1]

    _walk(ax_app, 0, lines, char_count)

    return "\n".join(lines)
