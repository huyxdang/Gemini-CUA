# macagent

A voice-controlled macOS desktop agent powered by Gemini 2.5 Flash on Google Cloud.

Hold a key, speak a command, and watch your Mac execute it. The local client captures your screen and accessibility tree, sends them to a Gemini agent on Cloud Run, and executes the returned actions (click, type, scroll) on your machine.

## Architecture

```
LOCAL macOS CLIENT                          CLOUD RUN
+-----------------------+                  +---------------------------+
| Hold key -> Speak     |                  | ADK Agent (Gemini 2.5    |
| Google Cloud STT      |   POST /run      | Flash)                   |
| Capture screenshot    | ---------------> |                          |
| Read AX tree          |                  | Screenshot + AX tree in  |
|                       | <--------------- | Action JSON out          |
| Execute action        |   {action, ...}  |                          |
| click / type / scroll |                  | Pure reasoning, no tools |
+-----------------------+                  +---------------------------+
```

The agent loop repeats (capture -> send -> execute) until the task is done or the step limit is reached.

## Quick Start

### Prerequisites

- macOS 13+
- Python 3.11+
- A Google Cloud project with billing enabled
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud`)
- (Optional) [ElevenLabs](https://elevenlabs.io/) API key for spoken responses

### 1. Install Google Cloud SDK

```bash
# Install via the official installer
curl https://sdk.cloud.google.com | bash

# Restart your shell, then authenticate
gcloud auth login
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_PROJECT_ID

# Enable the Speech-to-Text API (required for voice mode)
gcloud services enable speech.googleapis.com --project=YOUR_PROJECT_ID
```

### 2. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/Gemini-CUA.git
cd Gemini-CUA
pip install -e .

# For voice mode:
pip install -e ".[voice]"
```

### 3. Grant macOS permissions

Go to **System Settings > Privacy & Security** and enable for your terminal app:
- **Screen Recording**
- **Accessibility**
- **Microphone** (voice mode only)

### 4. Deploy the agent to Cloud Run

```bash
# Install ADK
pip install google-adk

# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable APIs
gcloud services enable run.googleapis.com
gcloud services enable generativelanguage.googleapis.com

# Deploy
cd server
adk deploy cloud_run \
  --project=YOUR_PROJECT_ID \
  --region=us-central1 \
  --service_name=macagent \
  mac_agent
```

Or deploy manually with the Dockerfile:

```bash
cd server
gcloud run deploy macagent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

### 5. Configure the client

```bash
cp .env.example .env
```

Edit `.env`:
```
SERVER_URL=https://macagent-XXXXXXXX-uc.a.run.app
GOOGLE_CLOUD_PROJECT=your-project-id

# Optional: enable spoken responses in voice mode
ELEVENLABS_API_KEY=your-elevenlabs-api-key
ELEVENLABS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb
```

### 6. Run

**Text mode:**
```bash
python -m client
```

**Voice mode:**
```bash
python -m client --voice
```

If ElevenLabs is configured, chat-mode responses will be spoken aloud before returning to "Listening...".

## Usage

### Text Mode

```
macOS Computer-Use Agent (Text Mode)
==================================================
Server: https://macagent-XXXXXXXX-uc.a.run.app
Type a command (or 'quit' to exit):

> Open Safari and search for weather in Hanoi
```

### Voice Mode

```
macOS Computer-Use Agent (Voice Mode)
==================================================
Hold Right Option to speak. Triple-press Escape to abort. Ctrl+C to quit.

Listening... (hold Right Option to speak)
Recording... (release to stop)
"Open Safari and search for weather in Hanoi"
```

The agent will:
1. Capture your screen + accessibility tree
2. Send to Gemini on Cloud Run
3. Receive an action (e.g., click Safari in Dock)
4. Execute it locally
5. Repeat until the task is done

## Safety

Actions are checked client-side before execution:

| Context | Level | Behavior |
|---------|-------|----------|
| `rm`, `sudo`, `delete` in Terminal | Dangerous | Blocked |
| Any typing in Terminal | Caution | 3s delay, auto-proceed |
| Actions in Mail, Messages, Slack | Caution | 3s delay, auto-proceed |
| Normal apps | Safe | Immediate |

**Kill switch:** Triple-press Escape to abort the current agent loop.

All steps are logged to `logs/<session_id>.jsonl` with timestamps, actions, safety verdicts, and the agent's reasoning.

## Project Structure

```
macagent/
├── server/                          # Cloud Run (Gemini agent)
│   ├── mac_agent/
│   │   ├── __init__.py
│   │   └── agent.py                 # ADK agent + system prompt
│   ├── main.py                      # FastAPI wrapper
│   ├── requirements.txt
│   └── Dockerfile
│
├── client/                          # Local macOS client
│   ├── main.py                      # Entry point (text + voice modes)
│   ├── perception/
│   │   ├── screenshot.py            # Screen capture -> base64 PNG
│   │   └── accessibility.py         # AX tree -> compact text
│   ├── action/
│   │   ├── executor.py              # Action dispatcher
│   │   ├── mouse.py                 # Click, double-click, scroll
│   │   └── keyboard.py              # Type text, key combos
│   ├── voice/
│   │   ├── hotkey.py                # Hold-to-talk (Right Option)
│   │   ├── stt.py                   # Google Cloud STT streaming
│   │   └── tts.py                   # ElevenLabs TTS (spoken responses)
│   ├── safety/
│   │   └── guard.py                 # Pre-execution safety checks
│   └── utils/
│       ├── config.py                # .env loading, settings
│       ├── coordinates.py           # Screenshot <-> screen point mapping
│       ├── logger.py                # JSONL session logging
│       └── permissions.py           # macOS permission checks
│
├── logs/                            # Session logs (gitignored)
├── pyproject.toml
├── .env.example
└── .gitignore
```

## Action Schema

The agent returns one action per step:

| Action | Params | Description |
|--------|--------|-------------|
| `click` | x, y, button | Click at coordinates |
| `double_click` | x, y | Double-click |
| `type_text` | text | Type a string |
| `press_key` | key, modifiers | Key combo (e.g., Cmd+C) |
| `scroll` | x, y, direction, amount | Scroll at position |
| `open_app` | app_name | Open a macOS app by name |
| `wait` | seconds | Pause |
| `done` | summary | Task complete |
| `fail` | reason | Task failed |

## Tech Stack

- **Agent framework:** Google Agent Development Kit (ADK)
- **LLM:** Gemini 2.5 Flash (multimodal — vision + text)
- **Hosting:** Google Cloud Run
- **Speech-to-text:** Google Cloud Speech-to-Text (streaming)
- **Text-to-speech:** ElevenLabs (optional, for spoken responses)
- **macOS APIs:** CoreGraphics (screenshots, mouse/keyboard events), Accessibility (AX tree)
- **Client deps:** httpx, pyobjc, Pillow, pynput, sounddevice

## License

Apache 2.0
