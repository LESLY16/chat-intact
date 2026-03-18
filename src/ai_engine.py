"""
AI engine – sends prompts to a locally running Ollama instance or to an
OpenAI-compatible API endpoint and streams/returns the response.

Priority:
  1. Ollama   (http://localhost:11434)
  2. OpenAI-compatible API (if OPENAI_API_KEY is configured)
"""

from __future__ import annotations

import json
import threading
from typing import Callable, Generator, Iterator, List, Optional

import requests

import config


class AIEngine:
    """
    Facade over Ollama / OpenAI-compatible backends.

    Usage
    -----
    engine = AIEngine()
    for chunk in engine.chat_stream(messages):
        print(chunk, end="", flush=True)
    """

    def __init__(self) -> None:
        self._settings = config.load_settings()

    def reload_settings(self) -> None:
        self._settings = config.load_settings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: List[dict],
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Send a list of ``{role, content}`` messages and return the full
        assistant response as a string.

        Parameters
        ----------
        messages:
            List of ``{"role": "user"|"assistant"|"system", "content": str}``.
        on_token:
            Optional callback invoked with each streamed token chunk.
        """
        if self._is_ollama_available():
            return self._ollama_chat(messages, on_token)
        if self._settings.get("openai_api_key"):
            return self._openai_chat(messages, on_token)
        return (
            "⚠️ No AI backend is configured.\n\n"
            "Please start Ollama locally (https://ollama.ai) or set an "
            "OpenAI API key in Settings."
        )

    def chat_stream(self, messages: List[dict]) -> Generator[str, None, None]:
        """
        Yield token chunks from the assistant response.
        Useful for streaming output in the GUI.
        """
        if self._is_ollama_available():
            yield from self._ollama_stream(messages)
        elif self._settings.get("openai_api_key"):
            yield from self._openai_stream(messages)
        else:
            yield (
                "⚠️ No AI backend is configured.\n\n"
                "Please start Ollama locally or configure an OpenAI API key."
            )

    # ------------------------------------------------------------------
    # Ollama backend
    # ------------------------------------------------------------------

    def _is_ollama_available(self) -> bool:
        base_url = self._settings.get("ollama_base_url", config.OLLAMA_BASE_URL)
        try:
            r = requests.get(f"{base_url}/api/tags", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def _ollama_chat(
        self,
        messages: List[dict],
        on_token: Optional[Callable[[str], None]],
    ) -> str:
        chunks = []
        for chunk in self._ollama_stream(messages):
            chunks.append(chunk)
            if on_token:
                on_token(chunk)
        return "".join(chunks)

    def _ollama_stream(self, messages: List[dict]) -> Generator[str, None, None]:
        base_url = self._settings.get("ollama_base_url", config.OLLAMA_BASE_URL)
        model = self._settings.get("ollama_model", config.OLLAMA_MODEL)
        url = f"{base_url}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        try:
            with requests.post(url, json=payload, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            yield token
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
        except requests.RequestException as exc:
            yield f"\n[Ollama error: {exc}]"

    # ------------------------------------------------------------------
    # OpenAI-compatible backend
    # ------------------------------------------------------------------

    def _openai_chat(
        self,
        messages: List[dict],
        on_token: Optional[Callable[[str], None]],
    ) -> str:
        chunks = []
        for chunk in self._openai_stream(messages):
            chunks.append(chunk)
            if on_token:
                on_token(chunk)
        return "".join(chunks)

    def _openai_stream(self, messages: List[dict]) -> Generator[str, None, None]:
        api_key = self._settings.get("openai_api_key", "")
        base_url = self._settings.get("openai_base_url", config.OPENAI_BASE_URL)
        model = self._settings.get("openai_model", config.OPENAI_MODEL)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        url = f"{base_url.rstrip('/')}/chat/completions"
        try:
            with requests.post(
                url, headers=headers, json=payload, stream=True, timeout=120
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    decoded = line.decode("utf-8") if isinstance(line, bytes) else line
                    if decoded.startswith("data: "):
                        decoded = decoded[6:]
                    if decoded.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(decoded)
                        delta = (
                            data.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, IndexError):
                        continue
        except requests.RequestException as exc:
            yield f"\n[OpenAI error: {exc}]"

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def build_system_prompt(
        self,
        activity_context: str = "",
        search_context: str = "",
    ) -> str:
        """
        Build the system prompt that includes activity and search context.
        """
        parts = [
            "You are a helpful desktop AI assistant running locally on "
            "the user's Windows 11 PC. You have access to the user's recent "
            "desktop activity to provide contextually relevant assistance. "
            "Be concise, helpful, and cite sources when available."
        ]
        if activity_context and activity_context.strip():
            parts.append("\n--- Recent Desktop Activity ---\n" + activity_context)
        if search_context and search_context.strip():
            parts.append("\n--- Web Search Results ---\n" + search_context)
        return "\n\n".join(parts)
