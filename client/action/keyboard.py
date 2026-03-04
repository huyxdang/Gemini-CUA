"""Keyboard actions using macOS CoreGraphics events."""

import time

from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    CGEventSetFlags,
    kCGHIDEventTap,
    kCGEventFlagMaskCommand,
    kCGEventFlagMaskShift,
    kCGEventFlagMaskAlternate,
    kCGEventFlagMaskControl,
)

# macOS virtual key codes
# Reference: /System/Library/Frameworks/Carbon.framework/Versions/A/Frameworks/HIToolbox.framework/Headers/Events.h
KEY_CODES: dict[str, int] = {
    # Letters
    "a": 0x00, "s": 0x01, "d": 0x02, "f": 0x03, "h": 0x04,
    "g": 0x05, "z": 0x06, "x": 0x07, "c": 0x08, "v": 0x09,
    "b": 0x0B, "q": 0x0C, "w": 0x0D, "e": 0x0E, "r": 0x0F,
    "y": 0x10, "t": 0x11, "1": 0x12, "2": 0x13, "3": 0x14,
    "4": 0x15, "6": 0x16, "5": 0x17, "9": 0x19, "7": 0x1A,
    "8": 0x1C, "0": 0x1D, "o": 0x1F, "u": 0x20, "i": 0x22,
    "p": 0x23, "l": 0x25, "j": 0x26, "k": 0x28, "n": 0x2D,
    "m": 0x2E,
    # Special keys
    "return": 0x24, "enter": 0x24,
    "tab": 0x30,
    "space": 0x31,
    "delete": 0x33, "backspace": 0x33,
    "escape": 0x35, "esc": 0x35,
    "forwarddelete": 0x75,
    # Arrow keys
    "left": 0x7B, "right": 0x7C,
    "down": 0x7D, "up": 0x7E,
    # Function keys
    "f1": 0x7A, "f2": 0x78, "f3": 0x63, "f4": 0x76,
    "f5": 0x60, "f6": 0x61, "f7": 0x62, "f8": 0x64,
    "f9": 0x65, "f10": 0x6D, "f11": 0x67, "f12": 0x6F,
    # Symbols
    "-": 0x1B, "=": 0x18, "[": 0x21, "]": 0x1E,
    "\\": 0x2A, ";": 0x29, "'": 0x27, ",": 0x2B,
    ".": 0x2F, "/": 0x2C, "`": 0x32,
    # Home/End/PageUp/PageDown
    "home": 0x73, "end": 0x77,
    "pageup": 0x74, "pagedown": 0x79,
}

# Characters that require Shift + base key (US keyboard layout)
SHIFTED_CHARS: dict[str, tuple[str, list[str]]] = {
    "!": ("1", ["shift"]), "@": ("2", ["shift"]),
    "#": ("3", ["shift"]), "$": ("4", ["shift"]),
    "%": ("5", ["shift"]), "^": ("6", ["shift"]),
    "&": ("7", ["shift"]), "*": ("8", ["shift"]),
    "(": ("9", ["shift"]), ")": ("0", ["shift"]),
    "_": ("-", ["shift"]), "+": ("=", ["shift"]),
    "{": ("[", ["shift"]), "}": ("]", ["shift"]),
    "|": ("\\", ["shift"]), ":": (";", ["shift"]),
    '"': ("'", ["shift"]), "<": (",", ["shift"]),
    ">": (".", ["shift"]), "?": ("/", ["shift"]),
    "~": ("`", ["shift"]),
}

MODIFIER_FLAGS: dict[str, int] = {
    "command": kCGEventFlagMaskCommand,
    "cmd": kCGEventFlagMaskCommand,
    "shift": kCGEventFlagMaskShift,
    "option": kCGEventFlagMaskAlternate,
    "alt": kCGEventFlagMaskAlternate,
    "control": kCGEventFlagMaskControl,
    "ctrl": kCGEventFlagMaskControl,
}


def _get_key_code(key: str) -> int:
    """Get the virtual key code for a key name."""
    key_lower = key.lower()
    if key_lower in KEY_CODES:
        return KEY_CODES[key_lower]
    raise ValueError(f"Unknown key: {key!r}. Available: {sorted(KEY_CODES.keys())}")


def _get_modifier_flags(modifiers: list[str]) -> int:
    """Combine modifier names into a CGEvent flag mask."""
    flags = 0
    for mod in modifiers:
        mod_lower = mod.lower()
        if mod_lower in MODIFIER_FLAGS:
            flags |= MODIFIER_FLAGS[mod_lower]
        else:
            raise ValueError(
                f"Unknown modifier: {mod!r}. Available: {sorted(MODIFIER_FLAGS.keys())}"
            )
    return flags


def press_key(key: str, modifiers: list[str] | None = None):
    """Press a key with optional modifiers (e.g., Cmd+C)."""
    modifiers = modifiers or []
    key_code = _get_key_code(key)
    flags = _get_modifier_flags(modifiers)

    # Key down
    down = CGEventCreateKeyboardEvent(None, key_code, True)
    if flags:
        CGEventSetFlags(down, flags)
    CGEventPost(kCGHIDEventTap, down)

    time.sleep(0.02)

    # Key up
    up = CGEventCreateKeyboardEvent(None, key_code, False)
    if flags:
        CGEventSetFlags(up, flags)
    CGEventPost(kCGHIDEventTap, up)


def type_text(text: str):
    """Type a string of text character by character."""
    for char in text:
        if char == "\n":
            press_key("return")
        elif char == "\t":
            press_key("tab")
        elif char == " ":
            press_key("space")
        elif char.isupper():
            press_key(char.lower(), ["shift"])
        elif char in SHIFTED_CHARS:
            base_key, mods = SHIFTED_CHARS[char]
            press_key(base_key, mods)
        elif char in KEY_CODES:
            press_key(char)
        else:
            _type_unicode_char(char)
        time.sleep(0.02)


def _type_unicode_char(char: str):
    """Type a single unicode character using CGEvent key event with unicode string."""
    from Quartz import CGEventKeyboardSetUnicodeString

    # Create a dummy key event and set its unicode string
    down = CGEventCreateKeyboardEvent(None, 0, True)
    CGEventKeyboardSetUnicodeString(down, len(char), char)
    CGEventPost(kCGHIDEventTap, down)

    time.sleep(0.01)

    up = CGEventCreateKeyboardEvent(None, 0, False)
    CGEventKeyboardSetUnicodeString(up, len(char), char)
    CGEventPost(kCGHIDEventTap, up)
