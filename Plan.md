# MacOS Computer-Use Agent — Hackathon Plan

## Overview

A **voice-only** macOS desktop agent. Hold a key → speak a command → your Mac captures the screen and sends it to a cloud-hosted ADK agent → Gemini reasons about what to do → the action is returned and executed locally. No text input. No CLI. Just your voice.

**Framework:** Google Agent Development Kit (ADK) on Cloud Run
**LLM:** Gemini 2.5 Flash (multimodal — vision + text)
**STT:** Google Cloud Speech-to-Text (streaming)
**Language:** Python
**Target:** Hackathon demo-ready

---

## Architecture

```
┌───────────────────────────────────────────────────────┐
│                   LOCAL macOS CLIENT                   │
│                                                       │
│  ┌─────────┐    ┌──────────┐    ┌──────────────────┐ │
│  │ Hotkey   │───▶│ Google   │───▶│ Capture screen   │ │
│  │ Listener │    │ Cloud STT│    │ + AX tree        │ │
│  │ (hold ⌥) │    │          │    │                  │ │
│  └─────────┘    └──────────┘    └────────┬─────────┘ │
│                                          │            │
│                    POST /run             │            │
│              {transcript, screenshot,    │            │
│               ax_tree}                   │            │
│                                          ▼            │
│  ┌──────────────────────────────────────────────────┐ │
│  │              Execute returned action              │ │
│  │  click(x,y) / type("text") / press_key(...)     │ │
│  └──────────────────────────────────────────────────┘ │
└──────────────────────┬──────────────────┬─────────────┘
                       │                  ▲
                       │ HTTPS            │ action JSON
                       ▼                  │
┌──────────────────────────────────────────────────────┐
│              CLOUD RUN (Google Cloud)                  │
│                                                       │
│  ┌──────────────────────────────────────────────────┐ │
│  │  ADK Agent (Gemini 2.5 Flash)                     │ │
│  │                                                   │ │
│  │  Receives: transcript + screenshot + AX tree      │ │
│  │  Reasons:  what action to take                    │ │
│  │  Returns:  {action, params, thought}              │ │
│  │                                                   │ │
│  │  FastAPI via get_fast_api_app()                    │ │
│  │  Deployed with: adk deploy cloud_run              │ │
│  └──────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────┘
```

### Client-Server Protocol

The local client and cloud agent communicate via a simple request-response loop:

**Client → Server (POST /run):**
```json
{
  "appName": "mac_agent",
  "userId": "user_1",
  "sessionId": "session_1",
  "newMessage": {
    "role": "user",
    "parts": [
      {"text": "Open Safari and search for weather in Hanoi"},
      {"inlineData": {"mimeType": "image/png", "data": "<base64_screenshot>"}},
      {"text": "ACCESSIBILITY TREE:\n[AXApplication 'Finder' ...]\n..."}
    ]
  }
}
```

**Server → Client (response events):**
```json
{
  "action": "click",
  "params": {"x": 640, "y": 1050},
  "thought": "I see Safari in the dock. Clicking to open it.",
  "done": false
}
```

The client executes the action, captures a new screenshot, and sends it back for the next step. This continues until the agent returns `"done": true`.

---

## Directory Structure

```
macagent/
├── README.md
├── LICENSE                          # Apache 2.0
├── .env.example                     # API keys template
│
├── server/                          # → Deployed to Cloud Run
│   ├── mac_agent/                   # ADK agent package
│   │   ├── __init__.py              # from . import agent
│   │   └── agent.py                 # root_agent definition + prompts
│   ├── main.py                      # FastAPI app via get_fast_api_app()
│   ├── requirements.txt             # google-adk, etc.
│   └── Dockerfile                   # for gcloud run deploy
│
├── client/                          # → Runs locally on macOS
│   ├── __init__.py
│   ├── main.py                      # entry point: hotkey → STT → server loop
│   ├── voice/
│   │   ├── __init__.py
│   │   ├── hotkey.py                # hold-to-talk listener (pynput)
│   │   └── stt.py                   # Google Cloud STT streaming
│   ├── perception/
│   │   ├── __init__.py
│   │   ├── screenshot.py            # screen capture → base64 PNG
│   │   └── accessibility.py         # AX tree → compact text
│   ├── action/
│   │   ├── __init__.py
│   │   ├── executor.py              # dispatch action JSON → macOS APIs
│   │   ├── mouse.py                 # click, double_click, scroll
│   │   └── keyboard.py             # type_text, press_key
│   ├── safety/
│   │   ├── __init__.py
│   │   └── guard.py                 # client-side safety check before execution
│   └── utils/
│       ├── __init__.py
│       ├── coordinates.py           # Retina point↔pixel conversion
│       ├── permissions.py           # check Screen Recording + Accessibility
│       └── config.py                # load .env, server URL
│
└── logs/                            # session logs (gitignored)
    └── .gitkeep
```

---

## Build Order (Hackathon Sprint)

### Phase 1 — Cloud Agent + Screen Perception (Hours 0–8)

**Goal:** ADK agent running on Cloud Run that accepts a screenshot + AX tree and returns a reasoned action.

#### Server Side

- [ ] **ADK agent definition** — `server/mac_agent/agent.py`
  ```python
  from google.adk.agents import Agent

  SYSTEM_PROMPT = """..."""  # See System Prompt section below

  root_agent = Agent(
      model="gemini-2.5-flash",
      name="mac_agent",
      instruction=SYSTEM_PROMPT,
      description="A macOS desktop automation agent that interprets screenshots and accessibility trees to decide actions.",
  )
  ```
  - No custom tools needed on server — the agent's job is pure reasoning
  - Input: multimodal message (screenshot image + AX tree text + user command)
  - Output: structured JSON action (via prompt engineering + output instructions)

- [ ] **System prompt** — embedded in `agent.py`
  - Instruct Gemini to always respond with a JSON action object
  - Define the action schema: `{thought, action, params, done}`
  - Define available actions: click, double_click, type_text, press_key, scroll, wait, done, fail
  - Include coordinate system rules, safety rules, verification strategy
  - Few-shot examples for common tasks

- [ ] **FastAPI wrapper** — `server/main.py`
  ```python
  import os
  from fastapi import FastAPI
  from google.adk.cli.fast_api import get_fast_api_app

  AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
  app: FastAPI = get_fast_api_app(agents_dir=AGENT_DIR, web=False)

  @app.get("/health")
  def health():
      return {"status": "ok"}
  ```

- [ ] **Deploy to Cloud Run**
  ```bash
  adk deploy cloud_run \
    --project=$GOOGLE_CLOUD_PROJECT \
    --region=us-central1 \
    ./server/mac_agent
  ```
  - Or manual deploy with Dockerfile + `gcloud run deploy --source .`
  - Test with curl: send a mock screenshot + command, verify JSON action response

- [ ] **Test the deployed agent**
  ```bash
  curl -X POST https://<cloud-run-url>/run \
    -H "Content-Type: application/json" \
    -d '{
      "appName": "mac_agent",
      "userId": "test",
      "sessionId": "test_1",
      "newMessage": {
        "role": "user",
        "parts": [{"text": "What do you see on this screen? Click on Safari."}]
      }
    }'
  ```

#### Client Side

- [ ] **Permissions check** — `client/utils/permissions.py`
  - Verify Screen Recording + Accessibility are granted
  - Exit with clear instructions if not

- [ ] **Screenshot capture** — `client/perception/screenshot.py`
  - `CGWindowListCreateImage` → PIL → resize to 1280px wide → base64 PNG
  - Handle Retina scaling

- [ ] **Accessibility tree** — `client/perception/accessibility.py`
  - `AXUIElement` → recursive walk → compact text
  - Format: `[Button "Submit" (120,340 80x32) enabled]`
  - Filter hidden/decorative, max depth 6, truncate at 4000 chars

- [ ] **Basic client loop** — `client/main.py` (text input for now)
  ```python
  async def agent_loop(command: str):
      session_id = str(uuid4())
      done = False

      while not done:
          # 1. Capture current state
          screenshot_b64 = capture_screen()
          ax_tree = read_accessibility_tree()

          # 2. Send to cloud agent
          response = await send_to_agent(
              server_url=SERVER_URL,
              session_id=session_id,
              screenshot=screenshot_b64,
              ax_tree=ax_tree,
              command=command if first_step else "Here is the updated screen after the last action.",
          )

          # 3. Parse action from agent response
          action = parse_action(response)

          # 4. Execute action locally
          if action["action"] == "done":
              done = True
              print(f"✅ {action.get('summary', 'Task complete')}")
          elif action["action"] == "fail":
              done = True
              print(f"❌ {action.get('reason', 'Task failed')}")
          else:
              execute_action(action)
              await asyncio.sleep(0.5)  # wait for UI to settle
  ```

- [ ] **Send to agent** — HTTP client (httpx or aiohttp)
  - POST to Cloud Run `/run` endpoint
  - Send screenshot as inline image Part + AX tree as text Part
  - Parse response events, extract agent's text (which contains the action JSON)

**Checkpoint:** Type a command → client captures screen → sends to Cloud Run → agent reasons → returns action → client could execute it (wired in Phase 2).

---

### Phase 2 — Action Execution (Hours 8–14)

**Goal:** Client can execute any action the cloud agent returns.

- [ ] **Coordinate utils** — `client/utils/coordinates.py`
  - `points_to_pixels(x, y)` and `pixels_to_points(x, y)`
  - Get scale factor from `NSScreen.mainScreen().backingScaleFactor()`

- [ ] **Mouse actions** — `client/action/mouse.py`
  - `click(x, y, button="left")` via `CGEventCreateMouseEvent`
  - `double_click(x, y)`
  - `scroll(x, y, direction, amount)` via `CGEventCreateScrollWheelEvent`

- [ ] **Keyboard actions** — `client/action/keyboard.py`
  - `type_text(text)` — iterate chars, create keyboard events
  - `press_key(key, modifiers=[])` — key code mapping + modifier flags
  - Key codes: return, tab, escape, space, delete, a-z, 0-9, arrows, F1-F12
  - Modifiers: command → `kCGEventFlagMaskCommand`, shift, option, control

- [ ] **Action executor/dispatcher** — `client/action/executor.py`
  ```python
  def execute_action(action: dict):
      name = action["action"]
      params = action.get("params", {})

      match name:
          case "click":       mouse.click(params["x"], params["y"], params.get("button", "left"))
          case "double_click": mouse.double_click(params["x"], params["y"])
          case "type_text":   keyboard.type_text(params["text"])
          case "press_key":   keyboard.press_key(params["key"], params.get("modifiers", []))
          case "scroll":      mouse.scroll(params["x"], params["y"], params["direction"], params.get("amount", 3))
          case "wait":        time.sleep(params.get("seconds", 1.0))
  ```

- [ ] **Wire executor into client loop**
  - After parsing action from cloud response, call `execute_action(action)`
  - After execution, wait briefly, then loop back (capture new screen, send to agent)

- [ ] **Max step limit** — 15 steps per command (prevent infinite loops)

- [ ] **End-to-end test** (still text input)
  - Type "Open Safari" → client captures screen → sends to Cloud Run → agent says click dock → client clicks → captures new screen → agent says "done"
  - Type "Open Notes and write hello world"

**Checkpoint:** Full text-input agent loop working across client ↔ Cloud Run.

---

### Phase 3 — Voice Input (Hours 14–20)

**Goal:** Hold-to-talk voice activation. This IS the product.

- [ ] **Hotkey listener** — `client/voice/hotkey.py`
  - Use `pynput` to monitor Right Option key (configurable)
  - On press: emit `START_RECORDING`
  - On release: emit `STOP_RECORDING`
  - Play system sound on start/stop (`afplay /System/Library/Sounds/Tink.aiff`)

- [ ] **Google Cloud STT** — `client/voice/stt.py`
  - Streaming recognition via `google-cloud-speech`
  - Audio capture from default mic via `sounddevice` (16kHz, mono, int16)
  - Flow:
    1. `start()` → begin audio capture + open STT stream
    2. Audio chunks fed to STT in real-time
    3. `stop()` → close stream, return final transcript
  - Config: language="en-US" (or "vi-VN" for Vietnamese)
  - Handle: no speech detected, timeout, low confidence

- [ ] **Main loop with voice** — `client/main.py`
  ```python
  async def main():
      check_permissions()
      print("🎤 macagent ready. Hold Right Option to speak.")

      while True:
          # Block until hotkey pressed, record until released
          transcript = await voice.listen()

          if not transcript:
              print("(no speech detected)")
              continue

          print(f'🗣️ "{transcript}"')

          # Run the agent loop with cloud backend
          await agent_loop(command=transcript)

          print("✅ Done. Hold Right Option for next command.\n")
  ```

- [ ] **Session persistence across commands**
  - Reuse the same `session_id` across voice commands
  - ADK session on Cloud Run maintains conversation history
  - Agent remembers previous actions within the same session

- [ ] **Test the full flow**
  - Hold key → "Open Safari" → release → agent opens Safari
  - Hold key → "Now go to youtube.com" → agent types in address bar
  - Hold key → "Scroll down" → agent scrolls

**Checkpoint:** Fully voice-controlled desktop agent talking to Cloud Run.

---

### Phase 4 — Safety + Polish (Hours 20–24)

**Goal:** Safety guardrails, logging, and demo polish.

- [ ] **Client-side safety guard** — `client/safety/guard.py`
  - Intercept every action BEFORE execution
  ```python
  def check_safety(action: dict, active_app: str) -> str:
      """Returns 'safe', 'caution', or 'dangerous'."""
      name = action["action"]
      params = action.get("params", {})

      # Dangerous: typing in Terminal
      if active_app in ["Terminal", "iTerm2"] and name == "type_text":
          text = params.get("text", "")
          if any(kw in text for kw in ["rm ", "sudo ", "delete"]):
              return "dangerous"
          return "caution"

      # Dangerous: clicking Send in messaging apps
      if active_app in ["Mail", "Messages", "Slack"]:
          return "caution"

      # Dangerous: System Settings
      if active_app == "System Settings":
          return "caution"

      return "safe"
  ```
  - For `caution`: play alert sound, show warning, 3-second auto-proceed
  - For `dangerous`: require voice confirmation ("say 'yes' to proceed")

- [ ] **Kill switch**
  - Triple-press Escape → abort current agent loop immediately
  - Caught in the hotkey listener

- [ ] **Basic logging**
  - Log each step to `logs/<session_id>.jsonl`
  - Fields: timestamp, step, command, action, params, thought, duration_ms

- [ ] **System prompt polish**
  - Refine to minimize hallucinated coordinates
  - Emphasize: always use AX tree positions for clicks (center of bounding box)
  - Emphasize: verify after important actions
  - Add few-shot examples for common tasks
  - Test edge cases: what if app doesn't open, element not found, etc.

- [ ] **Demo scenarios** — rehearse:
  1. "Open Safari and search for the weather in Ho Chi Minh City"
  2. "Open Notes and write a grocery list: eggs, milk, bread"
  3. "Take a screenshot and save it to the desktop"
  4. "Open Terminal and run ls" → safety guard triggers

- [ ] **README.md**
  - Overview + demo GIF
  - Architecture diagram
  - Setup: GCP project, Cloud Run deploy, local client install, permissions
  - Run: `python -m client`

**Checkpoint:** Demo-ready with safety, logging, and polished UX.

---

## Cloud Run Deployment

### Option A: One-command deploy (recommended)
```bash
cd server/
adk deploy cloud_run \
  --project=$GOOGLE_CLOUD_PROJECT \
  --region=us-central1 \
  --service_name=macagent \
  mac_agent
```

### Option B: Manual deploy with Dockerfile
```dockerfile
# server/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

```bash
cd server/
gcloud run deploy macagent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

### Requirements (server)
```
google-adk
google-genai
```

---

## Action Schema

The cloud agent returns structured JSON for each step. The system prompt enforces this format:

```json
{
  "thought": "I see the Safari icon in the dock at approximately (640, 1050). I'll click it.",
  "action": "click",
  "params": {
    "x": 640,
    "y": 1050,
    "button": "left"
  },
  "done": false
}
```

| Action         | Params                           | Description                     |
|---------------|----------------------------------|---------------------------------|
| `click`       | x, y, button (left/right)       | Click at coordinates            |
| `double_click`| x, y                            | Double click                    |
| `type_text`   | text                             | Type string at cursor           |
| `press_key`   | key, modifiers[]                 | Key combo (e.g., Cmd+C)        |
| `scroll`      | x, y, direction, amount         | Scroll at position              |
| `wait`        | seconds                          | Pause between actions           |
| `done`        | summary                          | Task complete                   |
| `fail`        | reason                           | Task cannot be completed        |

---

## System Prompt (Core)

```
You are a macOS desktop automation agent. You receive screenshots and
accessibility tree data from a user's Mac. Your job is to decide what
action to take next to fulfill the user's voice command.

You MUST respond with a single JSON object (no markdown, no backticks):
{
  "thought": "your reasoning about what you see and what to do next",
  "action": "click | double_click | type_text | press_key | scroll | wait | done | fail",
  "params": { ... },
  "done": true/false
}

AVAILABLE ACTIONS:
- click: {"x": int, "y": int, "button": "left"|"right"}
- double_click: {"x": int, "y": int}
- type_text: {"text": "string to type"}
- press_key: {"key": "return"|"tab"|"escape"|..., "modifiers": ["command","shift",...]}
- scroll: {"x": int, "y": int, "direction": "up"|"down", "amount": int}
- wait: {"seconds": float}
- done: {"summary": "what was accomplished"}
- fail: {"reason": "why it failed"}

RULES:
1. Analyze the screenshot and accessibility tree carefully before acting.
2. Use accessibility tree coordinates for precise clicks: click at (x + width/2, y + height/2).
3. Coordinates are in macOS points (not pixels). (0,0) is top-left.
4. Only perform ONE action per response.
5. After the action is executed, you will receive an updated screenshot.
6. Never type passwords, credentials, or financial information.
7. If asked to do something destructive, include a warning in your thought.
8. Be concise in thoughts — the user hears status updates via terminal.
9. If you cannot find what you're looking for, try scrolling or switching apps.
10. When the task is complete, return action "done" with a summary.
```

---

## Safety Rules

Implemented client-side (since the client executes actions):

```yaml
dangerous_contexts:
  apps: ["Terminal", "iTerm2"]
  keywords_in_type: ["rm ", "sudo ", "delete", "password", "credit card"]

caution_contexts:
  apps: ["Mail", "Messages", "Slack", "System Settings"]

on_caution:
  - play alert sound
  - print warning to terminal
  - auto-proceed after 3 seconds

on_dangerous:
  - play alert sound
  - require voice confirmation ("say 'yes' to proceed")
  - log the blocked action

kill_switch: triple_escape
max_steps_per_command: 15
```

---

## Key Dependencies

### Server (Cloud Run)
```
google-adk
google-genai
```

### Client (local macOS)
```toml
dependencies = [
    # Cloud communication
    "httpx",                             # async HTTP client for Cloud Run
    "google-cloud-speech",               # STT

    # Voice
    "sounddevice",                       # mic capture
    "numpy",                             # audio buffers

    # macOS APIs
    "pyobjc-framework-Cocoa",            # NSScreen, NSWorkspace
    "pyobjc-framework-Quartz",           # CoreGraphics, CGEvents
    "pyobjc-framework-ApplicationServices",  # Accessibility (AXUIElement)
    "pynput",                            # hotkey listener

    # Utils
    "Pillow",                            # screenshot processing
    "rich",                              # terminal output
]
```

---

## Key Technical Decisions

**Why client-server split:**
The hackathon requires the agent to be "hosted on Google Cloud." By deploying the ADK agent to Cloud Run, the reasoning brain is clearly cloud-hosted. The local client is just eyes (screenshot) and hands (click/type) — a thin execution layer.

**Why ADK on Cloud Run over raw FastAPI:**
`adk deploy cloud_run` handles Dockerfile generation, FastAPI wrapping, and session management. One command to deploy. ADK's `/run` endpoint accepts multimodal messages natively, so screenshots go directly into Gemini's vision pipeline.

**Why the agent has no custom tools on the server:**
In this split architecture, the agent doesn't execute actions — it only decides them. The tools (click, type, etc.) live client-side. The agent is a pure reasoning engine: screenshot in → action JSON out. This is simpler and avoids the complexity of remote tool execution.

**Why client-side safety instead of server-side:**
The client is the one executing actions, so it's the natural enforcement point. It also means safety works even if the server is compromised or returns unexpected actions.

**Why Gemini 2.5 Flash:**
Sub-2s multimodal inference. Critical for real-time desktop control. The latency budget is: STT (~1s) + network (~0.2s) + Gemini reasoning (~1.5s) + action execution (~0.3s) = ~3s per step. Acceptable for demo.

---

## Risk Mitigations

| Risk | Mitigation |
|------|-----------|
| Cloud Run cold start adds latency | Set `--min-instances=1` to keep one warm instance |
| Gemini hallucinates coordinates | Always prefer AX tree positions; prompt heavily for this |
| Screenshot too large for API | Resize to 1280px wide, JPEG if needed (smaller than PNG) |
| STT misrecognizes speech | Print transcript, let user re-speak |
| AX tree empty for some apps | Fall back to vision-only (Gemini guesses from screenshot) |
| Network failure during agent loop | Timeout + retry once, then abort gracefully |
| Agent gets stuck looping | Max 15 steps per command; kill switch |
| Demo day: audio doesn't work | Test mic 30 min before; have backup laptop |

---

## Demo Script (Suggested)

**"Let me show you macagent — a voice-controlled desktop agent powered by Gemini on Google Cloud."**

1. Show terminal: `python -m client` → "🎤 Ready. Hold Right Option to speak."
2. Briefly show Cloud Run dashboard: "The brain runs here, on Google Cloud."
3. **Demo 1:** Hold key → "Open Safari" → agent captures screen, sends to Cloud Run, gets back "click Safari in dock", executes
4. **Demo 2:** Hold key → "Search for latest AI news" → agent clicks address bar, types, presses Enter
5. **Demo 3:** Hold key → "Scroll down" → agent scrolls
6. **Demo 4:** Hold key → "Open Terminal and delete my files" → safety guard: "⚠️ Say 'yes' to proceed" → "No" → blocked
7. Show logs: "Every step is logged with the agent's reasoning."

**Closing:** "The local Mac is just the eyes and hands. All reasoning happens on Google Cloud via Gemini 2.5 Flash and Google ADK. Voice in, actions out."