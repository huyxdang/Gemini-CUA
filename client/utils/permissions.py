"""Check that required macOS permissions (Screen Recording + Accessibility) are granted."""

import subprocess
import sys

from Quartz import CGWindowListCopyWindowInfo, kCGNullWindowID, kCGWindowListOptionAll

import ApplicationServices


def check_screen_recording() -> bool:
    """Check if Screen Recording permission is granted by attempting to list windows."""
    windows = CGWindowListCopyWindowInfo(kCGWindowListOptionAll, kCGNullWindowID)
    if windows is None:
        return False
    # If we can see window names, we have permission
    for w in windows:
        name = w.get("kCGWindowOwnerName", "")
        if name:
            return True
    return False


def check_accessibility() -> bool:
    """Check if Accessibility permission is granted."""
    return ApplicationServices.AXIsProcessTrusted()


def check_microphone() -> bool:
    """Check if microphone access works by briefly opening an audio stream."""
    try:
        import sounddevice as sd

        stream = sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=160)
        stream.start()
        stream.stop()
        stream.close()
        return True
    except Exception:
        return False


def check_permissions(voice: bool = False):
    """Verify all required permissions. Exit with instructions if missing."""
    missing = []

    if not check_screen_recording():
        missing.append(
            "Screen Recording: System Settings → Privacy & Security → Screen Recording → enable for Terminal/your IDE"
        )

    if not check_accessibility():
        missing.append(
            "Accessibility: System Settings → Privacy & Security → Accessibility → enable for Terminal/your IDE"
        )

    if voice and not check_microphone():
        missing.append(
            "Microphone: System Settings → Privacy & Security → Microphone → enable for Terminal/your IDE"
        )

    if missing:
        print("Missing required macOS permissions:\n")
        for m in missing:
            print(f"  - {m}")
        print("\nGrant the permissions and restart the app.")
        sys.exit(1)

    print("All permissions granted.")
