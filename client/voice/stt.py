"""Google Cloud Speech-to-Text streaming recognition with mic capture."""

import queue
import threading

import numpy as np
import sounddevice as sd
from google.cloud import speech


SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_DURATION_MS = 100  # send audio in 100ms chunks
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)


class StreamingSTT:
    """Streaming speech-to-text using Google Cloud Speech API.

    Usage:
        stt = StreamingSTT()
        stt.start()
        # ... user speaks ...
        transcript = stt.stop()
    """

    def __init__(self, language: str = "en-US"):
        self._language = language
        self._audio_queue: queue.Queue[bytes | None] = queue.Queue()
        self._stream: sd.InputStream | None = None
        self._is_recording = False
        self._client = speech.SpeechClient()
        # Diagnostics
        self._chunk_count = 0
        self._peak_rms = 0.0

    def start(self):
        """Start recording audio from the default microphone."""
        self._audio_queue = queue.Queue()
        self._is_recording = True
        self._chunk_count = 0
        self._peak_rms = 0.0

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self) -> str:
        """Stop recording and return the final transcript."""
        self._is_recording = False

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        # Log diagnostics
        print(f"  Audio: {self._chunk_count} chunks, peak RMS={self._peak_rms:.1f}")

        # Signal end of audio
        self._audio_queue.put(None)

        # Run STT on collected audio
        return self._transcribe()

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Called by sounddevice for each audio chunk."""
        if status:
            print(f"  Audio warning: {status}")
        if self._is_recording:
            self._chunk_count += 1
            rms = np.sqrt(np.mean(indata.astype(np.float32) ** 2))
            if rms > self._peak_rms:
                self._peak_rms = rms
            self._audio_queue.put(bytes(indata))

    def _audio_generator(self):
        """Yield audio chunks from the queue for the STT API."""
        while True:
            chunk = self._audio_queue.get()
            if chunk is None:
                return
            yield speech.StreamingRecognizeRequest(audio_content=chunk)

    def _transcribe(self) -> str:
        """Send recorded audio to Google Cloud STT and return transcript."""
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=SAMPLE_RATE,
            language_code=self._language,
            enable_automatic_punctuation=True,
        )
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=False,
        )

        try:
            responses = self._client.streaming_recognize(
                streaming_config, self._audio_generator()
            )

            transcript_parts = []
            for response in responses:
                for result in response.results:
                    if result.is_final:
                        transcript_parts.append(result.alternatives[0].transcript)

            return " ".join(transcript_parts).strip()

        except Exception as e:
            print(f"  STT error: {e}")
            return ""
