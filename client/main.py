"""macOS Computer-Use Agent — Client entry point."""

import argparse
import asyncio
import json
import sys
import threading
import time
from uuid import uuid4

import httpx

from client.action.executor import execute_action
from client.perception.screenshot import capture_screen
from client.perception.accessibility import read_accessibility_tree
from client.router import classify, needs_screen
from client.safety.guard import enforce_safety
from client.utils.config import (
    SERVER_URL, APP_NAME, USER_ID, MAX_STEPS, STEP_DELAY,
    ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID,
)
from client.utils.logger import SessionLogger
from client.utils.permissions import check_permissions

# Thread-safe kill switch
_kill_event = threading.Event()

# Maps our local session IDs to ADK server session IDs
_session_map: dict[str, str] = {}


def request_kill():
    """Signal the agent loop to stop."""
    _kill_event.set()


def _check_kill() -> bool:
    """Check and reset the kill switch."""
    if _kill_event.is_set():
        _kill_event.clear()
        return True
    return False


async def _ensure_session(client: httpx.AsyncClient, session_id: str) -> str:
    """Create a session on the ADK server and return the server-assigned session ID."""
    if session_id in _session_map:
        return _session_map[session_id]
    response = await client.post(
        f"{SERVER_URL}/apps/{APP_NAME}/users/{USER_ID}/sessions",
        json={},
        timeout=10.0,
    )
    response.raise_for_status()
    server_session_id = response.json()["id"]
    _session_map[session_id] = server_session_id
    return server_session_id


async def send_to_agent(
    client: httpx.AsyncClient,
    session_id: str,
    command: str,
    screenshot_b64: str,
    ax_tree: str,
) -> dict:
    """Send screenshot + AX tree + command to the cloud agent and return parsed action.

    This is the UI mode path — always includes a screenshot and AX tree so
    the agent is forced to reason about the screen and output an action.
    """
    server_session_id = await _ensure_session(client, session_id)

    message_parts = [
        {"text": command},
        {
            "inlineData": {
                "mimeType": "image/png",
                "data": screenshot_b64,
            }
        },
        {"text": ax_tree},
    ]

    payload = {
        "appName": APP_NAME,
        "userId": USER_ID,
        "sessionId": server_session_id,
        "newMessage": {
            "role": "user",
            "parts": message_parts,
        },
    }

    response = await client.post(
        f"{SERVER_URL}/run",
        json=payload,
        timeout=60.0,
    )
    response.raise_for_status()

    agent_text = _extract_agent_text(response.text)
    return _parse_action(agent_text)


async def send_chat(
    client: httpx.AsyncClient,
    session_id: str,
    command: str,
    screenshot_b64: str | None = None,
) -> str:
    """Send a question to the agent with an optional screenshot for context.

    The agent sees the screen and answers in natural language — no action execution.
    """
    server_session_id = await _ensure_session(client, session_id)

    chat_command = (
        "The user is asking a question or making conversation — NOT requesting a desktop action. "
        "Look at the screenshot of their screen and respond with a helpful, natural-language answer. "
        "Do NOT return JSON or an action object. Just answer the question directly.\n\n"
        f"User: {command}"
    )

    parts = [{"text": chat_command}]
    if screenshot_b64:
        parts.append({
            "inlineData": {
                "mimeType": "image/png",
                "data": screenshot_b64,
            }
        })

    payload = {
        "appName": APP_NAME,
        "userId": USER_ID,
        "sessionId": server_session_id,
        "newMessage": {
            "role": "user",
            "parts": parts,
        },
    }

    response = await client.post(
        f"{SERVER_URL}/run",
        json=payload,
        timeout=60.0,
    )
    response.raise_for_status()
    return _extract_agent_text(response.text)


def _extract_agent_text(response_body: str) -> str:
    """Extract the agent's text from the ADK /run response.

    ADK returns a JSON array of events. Each event may have
    content.parts[].text with the agent's response.
    """
    last_text = ""
    try:
        data = json.loads(response_body)
        # ADK returns a JSON array of events
        events = data if isinstance(data, list) else [data]
        for event in events:
            content = event.get("content", {})
            if not isinstance(content, dict):
                continue
            parts = content.get("parts", [])
            for part in parts:
                if isinstance(part, dict) and "text" in part:
                    last_text = part["text"]
    except (json.JSONDecodeError, AttributeError, TypeError, KeyError):
        # Fallback: try line-by-line parsing
        for line in response_body.strip().split("\n"):
            line = line.strip()
            if line.startswith("{") and "action" in line:
                last_text = line

    return last_text


def _parse_action(text: str) -> dict:
    """Parse the agent's JSON action from its text response."""
    text = text.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        return {
            "thought": f"Failed to parse agent response: {text[:200]}",
            "action": "fail",
            "params": {"reason": "Could not parse agent response as JSON"},
            "done": True,
        }


async def handle_command(command: str, session_id: str | None = None, tts=None):
    """Route a command to UI mode or chat mode, then execute."""
    if session_id is None:
        session_id = str(uuid4())

    mode = classify(command)
    print(f"  [{mode.upper()} mode]")

    if mode == "chat":
        await chat_loop(command, session_id, tts=tts)
    else:
        await ui_loop(command, session_id)


async def chat_loop(command: str, session_id: str, tts=None):
    """Chat mode — optionally capture screen, send question, get text answer."""
    print(f"\nSession: {session_id[:8]}...")
    print(f"Command: {command}\n")

    screenshot_b64 = None
    if await needs_screen(command):
        print("  Capturing screen (question references screen)...")
        screenshot_b64, sw, sh = capture_screen()
    else:
        print("  Skipping screenshot (general question)")

    async with httpx.AsyncClient() as client:
        try:
            response_text = await send_chat(client, session_id, command, screenshot_b64)
            print(f"  Agent: {response_text}\n")
            if tts and response_text:
                await tts.speak(response_text)
        except httpx.HTTPError as e:
            print(f"  HTTP error: {e}")


async def ui_loop(command: str, session_id: str):
    """UI mode — forced pipeline: capture screen -> send to agent -> execute action -> repeat."""
    logger = SessionLogger(session_id)
    print(f"\nSession: {session_id[:8]}... (log: {logger.path.name})")
    print(f"Command: {command}\n")

    async with httpx.AsyncClient() as client:
        current_command = command

        for step in range(1, MAX_STEPS + 1):
            # Check kill switch
            if _check_kill():
                print("\n  ABORTED (kill switch triggered).")
                break

            logger.start_step()
            print(f"--- Step {step}/{MAX_STEPS} ---")

            # 1. Always capture screen + AX tree (forced pipeline)
            print("  Capturing screen...")
            screenshot_b64, sw, sh = capture_screen()

            print("  Reading accessibility tree...")
            ax_tree = read_accessibility_tree()

            # 2. Always send to Gemini with vision context
            print("  Sending to agent...")
            try:
                action = await send_to_agent(
                    client=client,
                    session_id=session_id,
                    command=current_command,
                    screenshot_b64=screenshot_b64,
                    ax_tree=ax_tree,
                )
            except httpx.HTTPError as e:
                print(f"  HTTP error: {e}")
                break

            thought = action.get("thought", "")
            action_name = action.get("action", "unknown")
            params = action.get("params", {})
            done = action.get("done", False)

            print(f"  Thought: {thought}")
            print(f"  Action: {action_name} {params}")

            if action_name == "done":
                logger.log(current_command, action)
                print(f"\n  Task complete: {params.get('summary', '')}")
                break
            elif action_name == "fail":
                logger.log(current_command, action)
                print(f"\n  Task failed: {params.get('reason', '')}")
                break

            # 3. Safety check before execution
            proceed, safety_level = await enforce_safety(action)
            if not proceed:
                logger.log(current_command, action, safety_level=safety_level, blocked=True)
                current_command = (
                    f"The action '{action_name}' was BLOCKED by safety guard. "
                    "Do NOT retry this action. Try a different, safer approach or report done/fail."
                )
                await asyncio.sleep(STEP_DELAY)
                continue

            logger.log(current_command, action, safety_level=safety_level)

            # 4. Always execute the action
            print(f"  Executing: {action_name}({params})")
            try:
                execute_action(action, sw, sh)
            except Exception as e:
                print(f"  Execution error: {e}")
                current_command = (
                    f"The last action '{action_name}' failed with error: {e}. "
                    "Here is the current screen. Please try a different approach."
                )
                await asyncio.sleep(STEP_DELAY)
                continue

            if done:
                print("\n  Task marked done after final action.")
                break

            # 5. Repeat — next iteration will capture fresh screen
            current_command = "Here is the updated screen after the last action. Continue with the task."
            await asyncio.sleep(STEP_DELAY)

        else:
            print(f"\n  Reached max steps ({MAX_STEPS}). Stopping.")

    print(f"  Log saved: {logger.path}")


async def voice_main():
    """Voice-controlled main loop: hold Right Option to speak."""
    from client.voice.hotkey import HotkeyListener
    from client.voice.overlay import ListeningOverlay
    from client.voice.stt import StreamingSTT

    check_permissions(voice=True)

    try:
        stt = StreamingSTT()
    except Exception as e:
        print(f"Failed to initialize Speech-to-Text: {e}")
        print("Set GOOGLE_APPLICATION_CREDENTIALS or run: gcloud auth application-default login")
        sys.exit(1)

    # Initialize TTS if API key is configured
    tts = None
    if ELEVENLABS_API_KEY:
        from client.voice.tts import ElevenLabsTTS
        tts = ElevenLabsTTS(api_key=ELEVENLABS_API_KEY, voice_id=ELEVENLABS_VOICE_ID)
        print("TTS: ElevenLabs enabled")
    else:
        print("TTS: disabled (set ELEVENLABS_API_KEY to enable)")

    print("macOS Computer-Use Agent (Voice Mode)")
    print("=" * 50)
    print(f"Server: {SERVER_URL}")
    print("Hold Right Option to speak. Triple-press Escape to abort. Ctrl+C to quit.\n")

    overlay = ListeningOverlay()

    loop = asyncio.get_running_loop()
    hotkey = HotkeyListener()
    hotkey.start(loop)

    session_id = str(uuid4())

    # Single watcher thread that bridges hotkey kill events to the agent loop
    def _kill_watcher():
        while True:
            if hotkey.kill_requested:
                request_kill()
                print("\n  KILL SWITCH: Triple-Escape detected!")
                hotkey.clear_kill()
            time.sleep(0.1)

    watcher = threading.Thread(target=_kill_watcher, daemon=True)
    watcher.start()

    try:
        while True:
            hotkey.clear_kill()
            print("Listening... (hold Right Option to speak)")
            await hotkey.wait_for_press()

            print("Recording... (release to stop)")
            overlay.show()
            stt.start()
            rec_start = time.monotonic()

            await hotkey.wait_for_release()
            rec_elapsed = time.monotonic() - rec_start
            overlay.hide()

            print(f"Processing speech... (recorded {rec_elapsed:.1f}s)")
            transcript = await asyncio.to_thread(stt.stop)

            if not transcript:
                print("(no speech detected)\n")
                continue

            print(f'"{transcript}"\n')
            await handle_command(command=transcript, session_id=session_id, tts=tts)
            print()

    except KeyboardInterrupt:
        print("\nBye!")
    finally:
        overlay.hide()
        hotkey.stop()


def text_main():
    """Text-input main loop."""
    check_permissions()

    print("macOS Computer-Use Agent (Text Mode)")
    print("=" * 50)
    print(f"Server: {SERVER_URL}")
    print("Type a command (or 'quit' to exit):\n")

    session_id = str(uuid4())

    while True:
        try:
            command = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break

        if not command:
            continue
        if command.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break

        asyncio.run(handle_command(command, session_id=session_id))
        print()


async def live_main():
    """Live API mode: real-time bidirectional voice + screen via Gemini Live API."""
    from client.live.session import LiveSession
    from client.ui.overlay import SiriOverlay
    from client.utils.config import GEMINI_API_KEY, WAKE_PHRASE
    from client.voice.hotkey import HotkeyListener

    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY is not set.")
        print("Set it in .env or as an environment variable.")
        sys.exit(1)

    check_permissions(voice=True)

    print("macOS Computer-Use Agent (Live API Mode)")
    print("=" * 50)
    print("Real-time voice + screen via Gemini Live API")
    print(f'Say "{WAKE_PHRASE}" to activate. Triple-press Escape to quit.\n')

    overlay = SiriOverlay()
    session = LiveSession(overlay=overlay)

    loop = asyncio.get_running_loop()
    hotkey = HotkeyListener()
    hotkey.start(loop)

    async def kill_watcher():
        """Poll for triple-Escape kill switch and stop the session."""
        try:
            while True:
                if hotkey.kill_requested:
                    print("\n  KILL SWITCH: Triple-Escape detected!")
                    session.stop()
                    hotkey.clear_kill()
                    return
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            return

    try:
        # Run session and kill watcher; when session ends, cancel the watcher
        session_task = asyncio.create_task(session.run())
        watcher_task = asyncio.create_task(kill_watcher())

        done, pending = await asyncio.wait(
            [session_task, watcher_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except KeyboardInterrupt:
        print("\nBye!")
    finally:
        session.stop()
        hotkey.stop()
        overlay.teardown()


def main():
    parser = argparse.ArgumentParser(description="macOS Computer-Use Agent")
    parser.add_argument(
        "--voice", action="store_true",
        help="Enable voice mode (hold Right Option to speak)",
    )
    parser.add_argument(
        "--live", action="store_true",
        help="Enable Live API mode (real-time voice + screen streaming)",
    )
    args = parser.parse_args()

    if args.live:
        asyncio.run(live_main())
    elif args.voice:
        asyncio.run(voice_main())
    else:
        text_main()


if __name__ == "__main__":
    main()
