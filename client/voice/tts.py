"""ElevenLabs Text-to-Speech using httpx (no SDK needed)."""

import asyncio
import subprocess
import tempfile

import httpx

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"


class ElevenLabsTTS:
    """Async TTS via ElevenLabs REST API.

    Usage:
        tts = ElevenLabsTTS(api_key="...", voice_id="...")
        await tts.speak("Hello, world!")
    """

    def __init__(self, api_key: str, voice_id: str = "JBFqnCBsd6RMkjVDRZzb"):
        self._api_key = api_key
        self._voice_id = voice_id

    async def speak(self, text: str):
        """Convert text to speech and play it. Blocks until playback finishes."""
        audio_bytes = await self._synthesize(text)
        if audio_bytes:
            await self._play(audio_bytes)

    async def _synthesize(self, text: str) -> bytes | None:
        """Call ElevenLabs API and return MP3 bytes."""
        url = f"{ELEVENLABS_API_URL}/{self._voice_id}"
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": "eleven_flash_v2_5",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, json=payload, headers=headers, timeout=30.0
                )
                response.raise_for_status()
                return response.content
        except httpx.HTTPError as e:
            print(f"  TTS error: {e}")
            return None

    async def _play(self, audio_bytes: bytes):
        """Write MP3 to temp file and play with afplay. Waits for completion."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=True) as f:
            f.write(audio_bytes)
            f.flush()
            await asyncio.to_thread(
                subprocess.run,
                ["afplay", f.name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
