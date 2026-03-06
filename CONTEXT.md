# Product Vision

## The One-Liner

A consumer-friendly macOS assistant powered by Gemini Live API — say "Hey Gemini," and it sees your screen, talks to you, and does things for you.

## The Problem

Computer-use agents today are developer tools: CLIs, API keys, Docker containers. Normal people can't use them. But everyone could benefit from an AI that looks at their screen and helps — explain an error, fill out a form, send an email.

## The Vision

You download the app. You open it. You say "Hey Gemini" — and it's there, watching your screen, ready to talk.

No setup wizards. No API keys. No terminal. Just a native macOS app in your menu bar that activates when you need it.

## Why Gemini Live API

Live API is the foundation of this product. It's what makes a truly conversational CUA possible.

**What Live API gives us:**
- **Real-time screen understanding** — continuous screen streaming, not periodic screenshots. The model sees your screen as a live video feed, so it always has full context.
- **Native bidirectional voice** — the user speaks, Gemini responds with voice, in real-time. No separate STT service, no separate TTS service. Just a natural conversation.
- **Persistent session context** — the model remembers what it's seen and what you've discussed within a session. "Scroll down" / "No, go back" / "What was that thing I saw earlier?" all work naturally.
- **Low latency** — streaming architecture means the model starts responding as soon as it has enough context, not after a full request-response round trip.
- **Multimodal natively** — screen (video/images) + voice (audio) + text all flow through one API. No stitching together separate services.

**The current architecture vs. the target:**

```
Current (hackathon):
  Mic -> Google STT -> text -> Cloud Run Agent -> JSON action -> execute -> screenshot -> repeat
  (4+ services, request-response, ~3s per step)

Target (Live API):
  Mic + Screen -> Gemini Live API (streaming) -> Voice response + action decisions (streaming)
  (1 service, real-time, conversational)
```

Live API collapses the entire pipeline into a single streaming connection. That's the architectural bet.

## Core Experience

1. **"Hey Gemini"** (or hold a hotkey) — the assistant activates, Live API session opens
2. **It sees your screen continuously** — screen is streamed to Live API in real-time
3. **You talk naturally** — "What does this error mean?" / "Can you help me write this email?" / "Open Safari and look up flights to Tokyo"
4. **It responds conversationally** — Gemini speaks back via Live API's native voice, like a knowledgeable friend looking over your shoulder
5. **It can act** — when you ask it to do something, it drives your mouse and keyboard to carry out the task

The key insight: most of the time, you don't need the AI to *do* things on your computer — you need it to *see* what you're looking at and *talk* to you about it. Screen understanding + voice conversation covers 80% of use cases. Action execution is the 20% power feature built on top.

## What "Consumer-Friendly" Means

- **Download and run.** One `.dmg`, ideally a native macOS app.
- **No cloud deploy.** User never touches Google Cloud Console, Cloud Run, or Docker. Live API is called directly from the client.
- **No config files.** Sign in with Google, and everything works.
- **Works immediately.** Grant Screen Recording + Microphone, and you're live.
- **Stays out of your way.** Menu bar icon, activates on voice or hotkey, disappears when done.

## Current State (v0.1 — Hackathon Prototype)

A working but developer-oriented prototype with a client-server split:

- **Cloud Run server**: Gemini 2.5 Flash agent via Google ADK, receives screenshots + accessibility tree, returns JSON actions
- **Local client**: Captures screen, reads accessibility tree, executes actions (click, type, scroll) via macOS APIs
- **Voice mode**: Hold Right Option, Google Cloud STT transcribes, agent responds
- **Chat mode**: Ask questions, get text answers (+ optional ElevenLabs TTS)
- **Safety guards**: Blocks dangerous Terminal commands, warns on sensitive apps
- **Intent routing**: Classifies commands as "ui" (do something) or "chat" (answer something)

### Gaps to Close

| Vision | Current State | What Needs to Change |
|--------|--------------|----------------------|
| Gemini Live API (real-time screen + voice) | Periodic screenshots + separate STT/TTS | Replace entire pipeline with Live API streaming |
| "Hey Gemini" wake word | Hold Right Option hotkey | Always-on wake word detection, then hand off to Live API |
| Download and run | `pip install` + Cloud Run deploy + `.env` | Eliminate server, package as native app |
| Sign in with Google | Manual API keys and gcloud auth | OAuth flow |
| Conversational back-and-forth | One command -> execute -> done | Live API session stays open for follow-ups |
| Menu bar app | Terminal CLI | Native macOS UI |

## Roadmap

### Phase 1 — Live API Integration (Next)

Replace the entire hackathon pipeline with Gemini Live API. This is the single biggest change.

- Open a Live API streaming session with screen capture + audio input
- Gemini sees the screen continuously and responds with voice natively
- Eliminate Cloud Run server — call Live API directly from the client
- Eliminate separate STT (Google Cloud Speech) and TTS (ElevenLabs) — Live API handles both
- Keep the action execution layer (mouse/keyboard/accessibility) on the client side
- Define how action decisions flow back from Live API (structured output or function calling within the streaming session)

### Phase 2 — Consumer Packaging

- Native macOS app (Swift/SwiftUI shell, Python or Swift backend)
- Menu bar icon with status (idle / listening / thinking / acting)
- Floating overlay UI for responses (not terminal output)
- Sign in with Google (OAuth)
- First-run onboarding: grant permissions, sign in, done
- Auto-update

### Phase 3 — Task Execution

Once "see and talk" is solid via Live API, layer on action execution:

- **Email**: "Send an email to John about the meeting" — agent composes in Mail/Gmail, user confirms
- **Notes**: "Add this to my notes" — agent opens Notes, types content
- **Web browsing**: "Search for flights to Tokyo" — agent drives Safari/Chrome
- **File management**: "Move this to the Desktop" — agent uses Finder
- **Form filling**: "Fill out this form" — agent reads fields, types answers

Safety: dangerous actions blocked, sensitive actions require voice confirmation.

### Phase 4 — Intelligence

- Context memory across sessions
- Proactive suggestions ("It looks like you're trying to...")
- Multi-app workflows
- User preference learning

## Design Principles

1. **Voice-first, Live API-native.** The primary interaction is a real-time voice conversation with screen context. Everything else is secondary.
2. **See, then do.** Screen understanding is the core. Action execution is a power feature on top.
3. **Zero config.** Every setting the user has to touch is a failure.
4. **Trust through transparency.** Show what the AI sees, what it's about to do, let the user cancel.
5. **Native feel.** Should feel like a macOS feature, not a web app.
