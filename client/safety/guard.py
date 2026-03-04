"""Client-side safety guard — intercept actions before execution."""

import asyncio
import subprocess

from AppKit import NSWorkspace


SOUND_ALERT = "/System/Library/Sounds/Funk.aiff"

DANGEROUS_APPS = {"Terminal", "iTerm2", "iTerm"}
DANGEROUS_KEYWORDS = ["rm ", "sudo ", "delete", "password", "credit card", "rmdir", "mkfs"]

CAUTION_APPS = {"Mail", "Messages", "Slack", "System Settings", "System Preferences"}

CAUTION_DELAY = 3  # seconds to wait before auto-proceeding on caution


def _get_active_app() -> str:
    """Get the name of the currently active application."""
    ws = NSWorkspace.sharedWorkspace()
    app = ws.frontmostApplication()
    if app is None:
        return ""
    return app.localizedName() or ""


def _play_alert():
    """Play an alert sound."""
    subprocess.Popen(
        ["afplay", SOUND_ALERT],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def check_safety(action: dict, active_app: str) -> str:
    """Check if an action is safe to execute.

    Returns:
        'safe' — execute immediately
        'caution' — warn user, auto-proceed after delay
        'dangerous' — block execution, require confirmation
    """
    name = action.get("action", "")
    params = action.get("params", {})

    # Check dangerous: typing in Terminal with dangerous keywords
    if active_app in DANGEROUS_APPS and name == "type_text":
        text = params.get("text", "").lower()
        if any(kw in text for kw in DANGEROUS_KEYWORDS):
            return "dangerous"
        return "caution"

    # Check dangerous: pressing Enter in Terminal (could execute dangerous command)
    if active_app in DANGEROUS_APPS and name == "press_key":
        key = params.get("key", "").lower()
        if key in ("return", "enter"):
            return "caution"

    # Check caution: any action in sensitive apps
    if active_app in CAUTION_APPS:
        return "caution"

    return "safe"


async def enforce_safety(action: dict) -> tuple[bool, str]:
    """Enforce safety policy. Returns (proceed, level).

    proceed: True if action should proceed, False to block.
    level: 'safe', 'caution', or 'dangerous'.
    """
    active_app = _get_active_app()
    level = check_safety(action, active_app)

    if level == "safe":
        return True, level

    action_name = action.get("action", "")
    params = action.get("params", {})

    if level == "caution":
        _play_alert()
        print(f"  WARNING: {action_name} in {active_app}")
        print(f"    Params: {params}")
        print(f"    Auto-proceeding in {CAUTION_DELAY}s... (triple-Esc to abort)")
        await asyncio.sleep(CAUTION_DELAY)
        return True, level

    if level == "dangerous":
        _play_alert()
        print(f"  BLOCKED: {action_name} in {active_app}")
        print(f"    Params: {params}")
        print(f"    Reason: Potentially destructive action detected.")
        print(f"    Action was NOT executed.")
        return False, level

    return True, level
