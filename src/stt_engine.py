"""
Optional Speech-to-Text (STT) engine.
Uses the SpeechRecognition library backed by the CMU Sphinx offline
recogniser (no internet required) or Google's free Web Speech API as a
fallback.

The engine captures audio from the default microphone and converts it to
text, which is then forwarded to a callback.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

import config


class STTEngine:
    """
    Microphone speech-to-text.

    Usage
    -----
    stt = STTEngine(on_result=handle_text)
    stt.start_listening()   # non-blocking
    ...
    stt.stop_listening()
    """

    def __init__(
        self,
        on_result: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._on_result = on_result
        self._on_error = on_error
        self._enabled = config.STT_ENABLED
        self._listening = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._recognizer = None
        self._microphone = None

        if self._enabled:
            self._init()

    # ------------------------------------------------------------------
    # Engine lifecycle
    # ------------------------------------------------------------------

    def _init(self) -> None:
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._microphone = sr.Microphone()
            self._enabled = True
        except (ImportError, Exception):
            self._enabled = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return self._enabled and self._recognizer is not None

    def start_listening(self) -> None:
        """Begin listening in a background thread."""
        if not self.available or self._listening:
            return
        self._stop_event.clear()
        self._listening = True
        self._thread = threading.Thread(
            target=self._listen_loop, daemon=True, name="STT"
        )
        self._thread.start()

    def stop_listening(self) -> None:
        """Stop the background listening thread."""
        self._stop_event.set()
        self._listening = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def listen_once(self) -> Optional[str]:
        """
        Synchronous single-shot listen – blocks until audio is captured.
        Returns the transcribed text or None on failure.
        """
        if not self.available:
            return None
        import speech_recognition as sr
        try:
            with self._microphone as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self._recognizer.listen(source, timeout=10)
            return self._transcribe(audio)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _listen_loop(self) -> None:
        import speech_recognition as sr
        try:
            with self._microphone as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=1)
                while not self._stop_event.is_set():
                    try:
                        audio = self._recognizer.listen(
                            source, timeout=5, phrase_time_limit=15
                        )
                        text = self._transcribe(audio)
                        if text and self._on_result:
                            self._on_result(text)
                    except sr.WaitTimeoutError:
                        continue
                    except Exception as exc:
                        if self._on_error:
                            self._on_error(str(exc))
        except Exception as exc:
            if self._on_error:
                self._on_error(str(exc))
        finally:
            self._listening = False

    def _transcribe(self, audio) -> Optional[str]:
        """Attempt online (Google) then offline (Sphinx) transcription."""
        import speech_recognition as sr
        # Try Google Web Speech API first
        try:
            return self._recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            return ""
        except sr.RequestError:
            pass
        # Fallback: CMU Sphinx (offline)
        try:
            return self._recognizer.recognize_sphinx(audio)
        except Exception:
            return None
