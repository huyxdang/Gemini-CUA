import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path)

SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8080")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
APP_NAME = "mac_agent"
USER_ID = "user_1"

# ElevenLabs TTS
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")

# Screenshot settings
SCREENSHOT_WIDTH = 1280

# Agent loop settings
MAX_STEPS = 15
STEP_DELAY = 0.5  # seconds to wait after each action for UI to settle

# Live API settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
LIVE_MODEL = os.getenv("LIVE_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025")
LIVE_VOICE = os.getenv("LIVE_VOICE", "Kore")
