"""Rule-based intent router — classify commands as UI actions or chat."""

import re

# Keywords that indicate the user wants to interact with the UI
UI_KEYWORDS = [
    "click", "tap", "press", "type", "fill", "submit",
    "login", "log in", "sign in", "sign up",
    "scroll", "scroll down", "scroll up",
    "open", "close", "launch", "quit", "exit",
    "select", "choose", "pick", "check", "uncheck", "toggle",
    "find", "search", "go to", "navigate", "visit",
    "drag", "drop", "move", "resize", "minimize", "maximize",
    "copy", "paste", "cut", "undo", "redo",
    "save", "delete", "rename", "create",
    "switch to", "switch app", "alt tab",
    "write", "compose", "send",
    "download", "upload",
    "play", "pause", "stop", "mute", "unmute",
    "zoom in", "zoom out",
    "refresh", "reload",
    "bookmark", "pin",
    "take a screenshot",
]

# Compile patterns for efficient matching (word boundaries where possible)
_UI_PATTERNS = [re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE) for kw in UI_KEYWORDS]


def classify(command: str) -> str:
    """Classify a user command as 'ui' or 'chat'.

    'ui'   — user wants to interact with the desktop (click, type, open, etc.)
    'chat' — user wants information or conversation (no desktop action needed)

    Examples:
        "Open Safari"                          -> 'ui'
        "Click the submit button"              -> 'ui'
        "Search for weather in Hanoi"          -> 'ui'
        "What is the capital of France?"       -> 'chat'
        "Explain this error message"           -> 'chat'
        "Scroll down and find the login form"  -> 'ui'
    """
    for pattern in _UI_PATTERNS:
        if pattern.search(command):
            return "ui"

    return "chat"
