"""Hold-to-talk hotkey listener using pynput."""

import asyncio
import subprocess
import threading
import time

from pynput import keyboard


# Sound files for audio feedback
SOUND_START = "/System/Library/Sounds/Tink.aiff"
SOUND_STOP = "/System/Library/Sounds/Pop.aiff"


def _play_sound(sound_path: str):
    """Play a system sound asynchronously."""
    subprocess.Popen(
        ["afplay", sound_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class HotkeyListener:
    """Listens for a hold-to-talk hotkey (Right Option by default).

    Usage:
        listener = HotkeyListener()
        listener.start()

        # Block until key is pressed and released
        await listener.wait_for_press()   # returns when key is pressed
        await listener.wait_for_release() # returns when key is released

        listener.stop()
    """

    def __init__(self, key=keyboard.Key.alt_r):
        self._target_key = key
        self._pressed_event = asyncio.Event()
        self._released_event = asyncio.Event()
        self._kill_event = asyncio.Event()
        self._listener: keyboard.Listener | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._is_held = False
        self._press_time: float = 0.0
        self._min_hold: float = 0.25  # ignore releases faster than 250ms
        # Kill switch: triple-press Escape
        self._esc_times: list[float] = []
        self._kill_window = 1.0  # 3 presses within 1 second

    def start(self, loop: asyncio.AbstractEventLoop):
        """Start listening for the hotkey. Must pass the running event loop."""
        self._loop = loop
        self._pressed_event.clear()
        self._released_event.clear()

        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        """Stop the hotkey listener."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def _on_press(self, key):
        """Called when any key is pressed."""
        # Kill switch: triple-press Escape
        if key == keyboard.Key.esc:
            now = time.monotonic()
            self._esc_times.append(now)
            # Keep only presses within the window
            self._esc_times = [t for t in self._esc_times if now - t <= self._kill_window]
            if len(self._esc_times) >= 3:
                self._esc_times.clear()
                if self._loop is not None:
                    self._loop.call_soon_threadsafe(self._kill_event.set)

        if key == self._target_key and not self._is_held:
            self._is_held = True
            self._press_time = time.monotonic()
            _play_sound(SOUND_START)
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._pressed_event.set)

    def _on_release(self, key):
        """Called when any key is released."""
        if key == self._target_key and self._is_held:
            # Debounce: ignore releases that happen too quickly (modifier key bounce)
            held_for = time.monotonic() - self._press_time
            if held_for < self._min_hold:
                return
            self._is_held = False
            _play_sound(SOUND_STOP)
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._released_event.set)

    async def wait_for_press(self):
        """Block until the hotkey is pressed."""
        self._pressed_event.clear()
        self._released_event.clear()  # clear release here to avoid race condition
        await self._pressed_event.wait()

    async def wait_for_release(self):
        """Block until the hotkey is released."""
        # Don't clear here — already cleared in wait_for_press.
        # This prevents a quick tap from hanging forever.
        await self._released_event.wait()

    @property
    def kill_requested(self) -> bool:
        """Check if kill switch (triple Escape) was triggered."""
        return self._kill_event.is_set()

    def clear_kill(self):
        """Reset the kill switch."""
        self._kill_event.clear()
