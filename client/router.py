"""Intent router — classify commands as UI actions or chat, and determine screen context need."""

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

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

_SCREEN_CLASSIFY_PROMPT = """\
Classify the user's intent into exactly one category. Reply with ONLY the category name, nothing else.

Categories:
- screen: The user is asking about something visible on their screen, referencing an app, window, error, or UI element they can currently see.
- general: The user is asking a general knowledge question, making conversation, or requesting information that does not require seeing their screen.

Examples:
- "What does this error mean?" → screen
- "What app is open right now?" → screen
- "Can you read what's on my screen?" → screen
- "What's the capital of France?" → general
- "Tell me a joke" → general
- "How do I make pasta?" → general
- "Summarize what I'm looking at" → screen
- "What's 2 + 2?" → general
"""

_genai_client: genai.Client | None = None


def _get_genai_client() -> genai.Client:
    """Lazy-init the Gemini client to avoid import-time crashes."""
    global _genai_client
    if _genai_client is None:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        _genai_client = genai.Client(api_key=api_key)
    return _genai_client


def classify(command: str) -> str:
    """Classify a user command as 'ui' or 'chat'.

    'ui'   — user wants to interact with the desktop (click, type, open, etc.)
    'chat' — user wants information or conversation (no desktop action needed)
    """
    for pattern in _UI_PATTERNS:
        if pattern.search(command):
            return "ui"
    return "chat"


async def needs_screen(command: str) -> bool:
    """Use Gemini Flash to determine if a chat question needs screen context."""
    import asyncio

    def _classify() -> bool:
        try:
            client = _get_genai_client()
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=f"{_SCREEN_CLASSIFY_PROMPT}\nUser: {command}",
            )
            label = response.text.strip().lower()
            print(f"  [Router] intent={label}")
            return label == "screen"
        except Exception as e:
            print(f"  [Router] classification failed ({e}), defaulting to screen")
            return True

    return await asyncio.to_thread(_classify)
