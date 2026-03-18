"""
Tests for src/ai_engine.py
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.ai_engine import AIEngine


class TestAIEngine(unittest.TestCase):

    def test_build_system_prompt_basic(self):
        engine = AIEngine()
        prompt = engine.build_system_prompt()
        self.assertIn("assistant", prompt.lower())

    def test_build_system_prompt_with_activity(self):
        engine = AIEngine()
        prompt = engine.build_system_prompt(activity_context="Browser: Python docs")
        self.assertIn("Browser: Python docs", prompt)
        self.assertIn("Desktop Activity", prompt)

    def test_build_system_prompt_with_search(self):
        engine = AIEngine()
        prompt = engine.build_system_prompt(search_context="Result: https://example.com")
        self.assertIn("https://example.com", prompt)
        self.assertIn("Web Search", prompt)

    def test_build_system_prompt_empty_strings_excluded(self):
        engine = AIEngine()
        prompt = engine.build_system_prompt(activity_context="", search_context="")
        self.assertNotIn("Desktop Activity", prompt)
        self.assertNotIn("Web Search", prompt)

    def test_chat_no_backend_configured(self):
        engine = AIEngine()
        engine._settings = {
            "ollama_base_url": "http://localhost:11434",
            "openai_api_key": "",
        }
        # Patch Ollama availability check to return False
        with patch.object(engine, "_is_ollama_available", return_value=False):
            result = engine.chat([{"role": "user", "content": "hello"}])
        self.assertIn("No AI backend", result)

    def test_chat_stream_no_backend_configured(self):
        engine = AIEngine()
        engine._settings = {
            "ollama_base_url": "http://localhost:11434",
            "openai_api_key": "",
        }
        with patch.object(engine, "_is_ollama_available", return_value=False):
            chunks = list(engine.chat_stream([{"role": "user", "content": "hi"}]))
        full = "".join(chunks)
        self.assertIn("No AI backend", full)

    def test_ollama_chat_streams_tokens(self):
        engine = AIEngine()
        engine._settings = {
            "ollama_base_url": "http://localhost:11434",
            "ollama_model": "llama3",
            "openai_api_key": "",
        }
        fake_lines = [
            b'{"message": {"content": "Hello"}, "done": false}',
            b'{"message": {"content": " world"}, "done": true}',
        ]
        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.iter_lines = MagicMock(return_value=iter(fake_lines))
        mock_response.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_response), \
             patch.object(engine, "_is_ollama_available", return_value=True):
            result = engine.chat([{"role": "user", "content": "hi"}])

        self.assertEqual(result, "Hello world")

    def test_openai_chat_streams_tokens(self):
        engine = AIEngine()
        engine._settings = {
            "ollama_base_url": "http://localhost:11434",
            "openai_api_key": "sk-test",
            "openai_base_url": "https://api.openai.com/v1",
            "openai_model": "gpt-4o-mini",
        }
        fake_lines = [
            b'data: {"choices": [{"delta": {"content": "Hi"}}]}',
            b'data: {"choices": [{"delta": {"content": " there"}}]}',
            b"data: [DONE]",
        ]
        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.iter_lines = MagicMock(return_value=iter(fake_lines))
        mock_response.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_response), \
             patch.object(engine, "_is_ollama_available", return_value=False):
            result = engine.chat([{"role": "user", "content": "hi"}])

        self.assertEqual(result, "Hi there")

    def test_reload_settings(self):
        engine = AIEngine()
        # Should not raise
        engine.reload_settings()
        self.assertIsInstance(engine._settings, dict)

    def test_on_token_callback(self):
        engine = AIEngine()
        engine._settings = {
            "ollama_base_url": "http://localhost:11434",
            "ollama_model": "llama3",
            "openai_api_key": "",
        }
        fake_lines = [
            b'{"message": {"content": "A"}, "done": false}',
            b'{"message": {"content": "B"}, "done": true}',
        ]
        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.iter_lines = MagicMock(return_value=iter(fake_lines))
        mock_response.raise_for_status = MagicMock()

        tokens_received = []
        with patch("requests.post", return_value=mock_response), \
             patch.object(engine, "_is_ollama_available", return_value=True):
            engine.chat(
                [{"role": "user", "content": "hi"}],
                on_token=tokens_received.append,
            )

        self.assertEqual(tokens_received, ["A", "B"])


if __name__ == "__main__":
    unittest.main()
