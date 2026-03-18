"""
Text-to-speech engine.
Uses pyttsx3 which wraps the native Windows SAPI 5 engine (SAPI on Windows,
espeak on Linux, NSSpeechSynthesizer on macOS).

All TTS calls are executed in a background thread so the GUI stays
responsive.
"""

from __future__ import annotations

import threading
from typing import Callable, List, Optional

import config


class TTSEngine:
    """
    Thread-safe TTS wrapper.

    Usage
    -----
    tts = TTSEngine()
    tts.speak("Hello, I am your AI assistant.")
    tts.stop()         # interrupt current speech
    tts.shutdown()     # clean up when the app exits
    """

    def __init__(self) -> None:
        self._enabled = config.TTS_ENABLED
        self._engine = None
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._voices: List = []

        if self._enabled:
            self._init_engine()

    # ------------------------------------------------------------------
    # Engine lifecycle
    # ------------------------------------------------------------------

    def _init_engine(self) -> None:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", config.TTS_RATE)
            engine.setProperty("volume", config.TTS_VOLUME)
            self._voices = engine.getProperty("voices") or []
            if self._voices and config.TTS_VOICE_INDEX < len(self._voices):
                engine.setProperty(
                    "voice", self._voices[config.TTS_VOICE_INDEX].id
                )
            self._engine = engine
        except Exception:
            self._engine = None
            self._enabled = False

    def shutdown(self) -> None:
        """Release engine resources."""
        self.stop()
        if self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Speech control
    # ------------------------------------------------------------------

    def speak(self, text: str, on_done: Optional[Callable] = None) -> None:
        """
        Speak *text* in a background thread.
        If speech is already in progress it is stopped first.

        Parameters
        ----------
        text:
            The text to speak.
        on_done:
            Optional callback invoked when speech finishes.
        """
        if not self._enabled or not self._engine:
            if on_done:
                on_done()
            return

        self.stop()

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_speech,
            args=(text, on_done),
            daemon=True,
            name="TTS",
        )
        self._thread.start()

    def stop(self) -> None:
        """Interrupt ongoing speech."""
        self._stop_event.set()
        if self._engine:
            try:
                with self._lock:
                    self._engine.stop()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_speech(self, text: str, on_done: Optional[Callable]) -> None:
        try:
            with self._lock:
                if not self._stop_event.is_set():
                    self._engine.say(text)
                    self._engine.runAndWait()
        except Exception:
            pass
        finally:
            if on_done:
                try:
                    on_done()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def set_rate(self, rate: int) -> None:
        if self._engine:
            self._engine.setProperty("rate", rate)

    def set_volume(self, volume: float) -> None:
        if self._engine:
            self._engine.setProperty("volume", volume)

    def set_voice(self, index: int) -> None:
        if self._engine and self._voices and index < len(self._voices):
            self._engine.setProperty("voice", self._voices[index].id)

    def list_voices(self) -> List[str]:
        """Return the names of available TTS voices."""
        return [v.name for v in self._voices]

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
        if value and self._engine is None:
            self._init_engine()
