"""Gemini Live API session manager — real-time voice + screen CUA."""

import asyncio
import base64
import subprocess
import time

from google import genai
from google.genai import types

from client.action import mouse, keyboard
from client.live.audio import AudioInput, AudioOutput
from client.live.screen import capture_screen_jpeg
from client.live.tools import CUA_TOOLS, SYSTEM_PROMPT
from client.perception.accessibility import read_accessibility_tree
from client.safety.guard import enforce_safety
from client.utils.config import GEMINI_API_KEY, LIVE_MODEL, LIVE_VOICE, WAKE_PHRASE
from client.utils.coordinates import screenshot_to_points

# Sessions with images (send_client_content with inline_data) may be treated
# as audio+video by the API, giving a 2-minute limit. Audio-only is 15 minutes.
# We track session start time and warn the user before auto-reconnecting.
SESSION_WARN_SECS = 90  # warn at 90s into a session
SESSION_MAX_SECS = 110  # proactively reconnect at 110s (before 120s hard limit)

# How long after the last model output before the overlay fades
IDLE_TIMEOUT = 3.0

# Fuzzy variants of the wake phrase to match against transcription
_WAKE_VARIANTS = [
    WAKE_PHRASE.lower(),
    WAKE_PHRASE.lower().replace(" ", ", "),  # "hey, gemini"
]


def _contains_wake_phrase(text: str) -> bool:
    """Check if text contains the wake phrase (fuzzy)."""
    t = text.lower().strip()
    return any(v in t for v in _WAKE_VARIANTS)


class LiveSession:
    """Manages a persistent Gemini Live API session with CUA tool calling.

    Audio streams continuously (VAD handles speech detection).
    Screen frames are sent on session open and after each tool call.
    The overlay activates on "hey Gemini" and tracks session state.
    """

    def __init__(self, overlay=None):
        self._overlay = overlay  # SiriOverlay or None
        self._client = genai.Client(api_key=GEMINI_API_KEY)
        self._audio_in = AudioInput()
        self._audio_out = AudioOutput()
        self._session = None
        self._running = False
        self._screen_width = 0
        self._screen_height = 0
        self._session_start: float = 0.0
        self._warned_duration = False
        # Wake word / overlay state
        self._engaged = False  # True after wake phrase detected
        self._last_output_time: float = 0.0

    # ------------------------------------------------------------------
    # Overlay helpers
    # ------------------------------------------------------------------

    def _set_overlay(self, state: str):
        if self._overlay:
            self._overlay.set_state(state)

    async def _amplitude_loop(self):
        """Poll audio amplitude and update overlay (~20fps). Thread-safe:
        reads simple floats written by audio threads, calls overlay from asyncio."""
        try:
            while self._running:
                await asyncio.sleep(0.05)
                if not (self._overlay and self._engaged):
                    continue
                amp = max(self._audio_in.latest_amplitude,
                          self._audio_out.latest_amplitude)
                if amp > 0.005:
                    self._overlay.set_amplitude(amp)
        except asyncio.CancelledError:
            return

    async def _idle_watcher(self):
        """Fade the overlay to idle after a period of no model output."""
        try:
            while self._running:
                await asyncio.sleep(1.0)
                if (
                    self._engaged
                    and self._last_output_time > 0
                    and time.monotonic() - self._last_output_time > IDLE_TIMEOUT
                ):
                    self._engaged = False
                    self._set_overlay("idle")
        except asyncio.CancelledError:
            return

    async def run(self):
        """Open the Live API session and run until stopped or disconnected."""
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=SYSTEM_PROMPT,
            tools=CUA_TOOLS,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=LIVE_VOICE
                    )
                )
            ),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )

        self._running = True

        while self._running:
            try:
                await self._run_session(config)
            except Exception as e:
                if not self._running:
                    return
                print(f"\n  Session ended: {e}")
                print("  Reconnecting in 2s...")
                await asyncio.sleep(2)

    async def _run_session(self, config: types.LiveConnectConfig):
        """Run a single Live API session."""
        print(f"  Connecting to {LIVE_MODEL}...")

        async with self._client.aio.live.connect(
            model=LIVE_MODEL, config=config
        ) as session:
            self._session = session

            self._audio_in.start()
            self._audio_out.start()
            self._session_start = time.monotonic()
            self._warned_duration = False

            print("  Connected! Speak naturally.\n")

            # Send initial screen context
            await self._send_screen_context("Session started. Here is the user's current screen.")

            try:
                await asyncio.gather(
                    self._send_audio_loop(),
                    self._receive_loop(),
                    self._session_timer(),
                    self._idle_watcher(),
                    self._amplitude_loop(),
                )
            finally:
                self._audio_in.stop()
                self._audio_out.stop()
                self._session = None

    def stop(self):
        """Signal the session to stop."""
        self._running = False
        self._audio_in.stop()

    async def _session_timer(self):
        """Monitor session duration and proactively reconnect before the API limit."""
        while self._running:
            await asyncio.sleep(5)
            elapsed = time.monotonic() - self._session_start

            if not self._warned_duration and elapsed >= SESSION_WARN_SECS:
                self._warned_duration = True
                print("  (Session approaching time limit, will reconnect soon)")

            if elapsed >= SESSION_MAX_SECS:
                print("  Reconnecting to refresh session...")
                # Break out of _run_session; the outer loop will reconnect
                self._audio_in.stop()
                return

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    async def _send_audio_loop(self):
        """Stream mic audio to Live API continuously."""
        async for chunk in self._audio_in.chunks():
            if not self._running:
                return
            await self._session.send_realtime_input(
                audio=types.Blob(data=chunk, mime_type="audio/pcm;rate=16000")
            )

    async def _send_screen_context(self, label: str = "Screen update"):
        """Capture screen + AX tree and send as context to the session."""
        jpeg_bytes, sw, sh = await asyncio.to_thread(capture_screen_jpeg)
        self._screen_width = sw
        self._screen_height = sh

        ax_tree = await asyncio.to_thread(read_accessibility_tree)

        b64 = base64.b64encode(jpeg_bytes).decode("ascii")

        await self._session.send_client_content(
            turns={
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
                    {"text": f"[{label}]\n{ax_tree}"},
                ],
            },
            turn_complete=False,
        )

    # ------------------------------------------------------------------
    # Receiving
    # ------------------------------------------------------------------

    async def _receive_loop(self):
        """Process all messages from the Live API session."""
        async for msg in self._session.receive():
            if not self._running:
                return

            # Audio / text responses
            if msg.server_content:
                sc = msg.server_content

                # --- Model audio output ---
                if sc.model_turn and sc.model_turn.parts:
                    for part in sc.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            # Model is speaking — update overlay
                            if self._engaged:
                                self._set_overlay("speaking")
                                self._last_output_time = time.monotonic()
                            self._audio_out.play(part.inline_data.data)

                # --- Model output transcription ---
                if sc.output_transcription and sc.output_transcription.text:
                    text = sc.output_transcription.text
                    if text.strip():
                        print(f"  Gemini: {text}")
                        self._last_output_time = time.monotonic()

                # --- User input transcription (wake word detection) ---
                if sc.input_transcription and sc.input_transcription.text:
                    text = sc.input_transcription.text
                    if text.strip():
                        print(f"  You: {text}")
                        if not self._engaged and _contains_wake_phrase(text):
                            self._engaged = True
                            # "activated" auto-transitions to "listening" on the JS side
                            self._set_overlay("activated")
                        elif self._engaged:
                            # User still talking after activation
                            self._set_overlay("listening")

                if sc.interrupted:
                    self._audio_out.clear()

            # Tool calls
            if msg.tool_call:
                if self._engaged:
                    self._set_overlay("thinking")
                await self._handle_tool_calls(msg.tool_call)

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def _handle_tool_calls(self, tool_call):
        """Execute tool calls from the model and send responses back."""
        responses = []

        for fc in tool_call.function_calls:
            name = fc.name
            args = dict(fc.args) if fc.args else {}

            print(f"  Action: {name}({args})")

            result = await self._execute_tool(name, args)
            print(f"  Result: {result}")

            responses.append(
                types.FunctionResponse(
                    name=name,
                    id=fc.id,
                    response={"result": result},
                )
            )

        await self._session.send_tool_response(function_responses=responses)

        # Send fresh screen after actions so the model sees the result
        await asyncio.sleep(0.5)
        await self._send_screen_context("Screen after action")

    async def _execute_tool(self, name: str, args: dict) -> str:
        """Execute a single CUA tool. Returns a result description."""
        try:
            action = {"action": name, "params": args}
            proceed, level = await enforce_safety(action)

            if not proceed:
                return f"BLOCKED by safety guard. Try a different approach."

            match name:
                case "click":
                    x, y = self._to_screen(args["x"], args["y"])
                    await asyncio.to_thread(mouse.click, x, y, args.get("button", "left"))
                    return f"Clicked at ({x}, {y})"

                case "double_click":
                    x, y = self._to_screen(args["x"], args["y"])
                    await asyncio.to_thread(mouse.double_click, x, y)
                    return f"Double-clicked at ({x}, {y})"

                case "type_text":
                    await asyncio.to_thread(keyboard.type_text, args["text"])
                    return f"Typed text"

                case "press_key":
                    await asyncio.to_thread(keyboard.press_key, args["key"], args.get("modifiers", []))
                    if args.get("modifiers"):
                        await asyncio.sleep(0.3)
                    combo = "+".join(args.get("modifiers", []) + [args["key"]])
                    return f"Pressed {combo}"

                case "scroll":
                    x, y = self._to_screen(args["x"], args["y"])
                    direction = args.get("direction", "down")
                    amount = args.get("amount", 3)
                    await asyncio.to_thread(mouse.scroll, x, y, direction, amount)
                    return f"Scrolled {direction} at ({x}, {y})"

                case "open_app":
                    app_name = args["app_name"]
                    result = await asyncio.to_thread(
                        subprocess.run,
                        ["open", "-a", app_name],
                        capture_output=True, text=True, timeout=10,
                    )
                    if result.returncode != 0:
                        return f"Failed to open {app_name}: {result.stderr.strip()}"
                    await asyncio.sleep(1.5)
                    return f"Opened {app_name}"

                case _:
                    return f"Unknown action: {name}"

        except Exception as e:
            return f"Error: {e}"

    def _to_screen(self, x: int, y: int) -> tuple[int, int]:
        """Convert screenshot coordinates to clamped screen points."""
        from AppKit import NSScreen

        if self._screen_width > 0 and self._screen_height > 0:
            px, py = screenshot_to_points(x, y, self._screen_width, self._screen_height)
        else:
            px, py = x, y

        screen = NSScreen.mainScreen()
        if screen is not None:
            frame = screen.frame()
            px = max(0, min(px, int(frame.size.width) - 1))
            py = max(0, min(py, int(frame.size.height) - 1))

        return px, py
