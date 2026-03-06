"""Audio I/O for Gemini Live API.

Input:  16kHz 16-bit PCM mono from microphone
Output: 24kHz 16-bit PCM mono from Live API responses
"""

import asyncio
import queue
import threading

import numpy as np
import sounddevice as sd

INPUT_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 24000
CHANNELS = 1
INPUT_CHUNK_SIZE = int(INPUT_SAMPLE_RATE * 0.1)  # 100ms chunks


def compute_rms(pcm_int16: np.ndarray, scale: float = 1.0) -> float:
    """Compute normalized RMS amplitude from int16 PCM samples.

    Returns a value in [0.0, 1.0] after applying the scale factor.
    Uses dot product on raw int16 to minimize allocations on audio threads.
    """
    samples = pcm_int16.ravel()
    # int16 dot may overflow, but float64 accumulator in np.dot handles it
    rms = float(np.sqrt(np.dot(samples.astype(np.float64), samples) / max(1, samples.size))) / 32768.0
    return min(1.0, rms * scale)


class AudioInput:
    """Captures microphone audio and yields PCM chunks for the Live API."""

    def __init__(self):
        self._queue: queue.Queue[bytes | None] = queue.Queue()
        self._stream: sd.InputStream | None = None
        self._running = False
        self.latest_amplitude: float = 0.0  # written from audio thread, read from asyncio

    def start(self):
        self._running = True
        self._queue = queue.Queue()
        self._stream = sd.InputStream(
            samplerate=INPUT_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=INPUT_CHUNK_SIZE,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self):
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._queue.put(None)

    def _callback(self, indata, frames, time_info, status):
        if self._running:
            self._queue.put(bytes(indata))
            self.latest_amplitude = compute_rms(indata, scale=5.0)

    async def chunks(self):
        """Async generator yielding raw PCM audio chunks."""
        while True:
            chunk = await asyncio.to_thread(self._queue.get)
            if chunk is None:
                return
            yield chunk


class AudioOutput:
    """Plays 24kHz PCM audio from Live API responses in a background thread."""

    def __init__(self):
        self._queue: queue.Queue[bytes | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._running = False
        self.latest_amplitude: float = 0.0  # written from playback thread, read from asyncio

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._queue.put(None)
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def play(self, pcm_data: bytes):
        """Queue PCM audio data for playback."""
        if pcm_data:
            self._queue.put(pcm_data)

    def clear(self):
        """Discard queued audio (called on interruption)."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _playback_loop(self):
        try:
            stream = sd.RawOutputStream(
                samplerate=OUTPUT_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
            )
            stream.start()
        except Exception as e:
            print(f"  Audio output error: {e}")
            return

        try:
            while self._running:
                data = self._queue.get()
                if data is None:
                    break
                try:
                    if len(data) >= 2:
                        self.latest_amplitude = compute_rms(
                            np.frombuffer(data, dtype=np.int16), scale=4.0
                        )
                    stream.write(data)
                except Exception as e:
                    print(f"  Audio playback error: {e}")
                    break
        finally:
            stream.stop()
            stream.close()
