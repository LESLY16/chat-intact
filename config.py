"""
Configuration management for the AI Assistant.
Settings are stored in a .env file and can be overridden via the GUI settings panel.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
_ENV_FILE = Path(__file__).parent / ".env"
load_dotenv(_ENV_FILE)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "conversations.db"
SETTINGS_PATH = DATA_DIR / "settings.json"
ACTIVITY_LOG_PATH = DATA_DIR / "activity_log.json"

# ---------------------------------------------------------------------------
# AI / Ollama settings
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

# OpenAI-compatible fallback (leave empty to disable)
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ---------------------------------------------------------------------------
# Web search settings
# ---------------------------------------------------------------------------
# Number of search results to include as context
SEARCH_MAX_RESULTS: int = int(os.getenv("SEARCH_MAX_RESULTS", "5"))

# ---------------------------------------------------------------------------
# TTS settings
# ---------------------------------------------------------------------------
TTS_ENABLED: bool = os.getenv("TTS_ENABLED", "true").lower() == "true"
TTS_RATE: int = int(os.getenv("TTS_RATE", "175"))   # words per minute
TTS_VOLUME: float = float(os.getenv("TTS_VOLUME", "1.0"))
TTS_VOICE_INDEX: int = int(os.getenv("TTS_VOICE_INDEX", "0"))

# ---------------------------------------------------------------------------
# STT settings
# ---------------------------------------------------------------------------
STT_ENABLED: bool = os.getenv("STT_ENABLED", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Activity tracking settings
# ---------------------------------------------------------------------------
ACTIVITY_TRACKING_ENABLED: bool = (
    os.getenv("ACTIVITY_TRACKING_ENABLED", "true").lower() == "true"
)
# How many recent activities to inject into the AI context
ACTIVITY_CONTEXT_LIMIT: int = int(os.getenv("ACTIVITY_CONTEXT_LIMIT", "10"))
# Interval (seconds) between activity snapshots
ACTIVITY_POLL_INTERVAL: float = float(os.getenv("ACTIVITY_POLL_INTERVAL", "5.0"))

# ---------------------------------------------------------------------------
# Conversation settings
# ---------------------------------------------------------------------------
# Maximum number of recent messages to include in each AI prompt
CONVERSATION_CONTEXT_LIMIT: int = int(os.getenv("CONVERSATION_CONTEXT_LIMIT", "20"))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULTS: dict = {
    "ollama_base_url": OLLAMA_BASE_URL,
    "ollama_model": OLLAMA_MODEL,
    "openai_api_key": OPENAI_API_KEY,
    "openai_base_url": OPENAI_BASE_URL,
    "openai_model": OPENAI_MODEL,
    "search_max_results": SEARCH_MAX_RESULTS,
    "tts_enabled": TTS_ENABLED,
    "tts_rate": TTS_RATE,
    "tts_volume": TTS_VOLUME,
    "tts_voice_index": TTS_VOICE_INDEX,
    "stt_enabled": STT_ENABLED,
    "activity_tracking_enabled": ACTIVITY_TRACKING_ENABLED,
    "activity_context_limit": ACTIVITY_CONTEXT_LIMIT,
    "activity_poll_interval": ACTIVITY_POLL_INTERVAL,
    "conversation_context_limit": CONVERSATION_CONTEXT_LIMIT,
}


def load_settings() -> dict:
    """Load settings from the JSON settings file, falling back to defaults."""
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            merged = {**_DEFAULTS, **saved}
            return merged
        except (json.JSONDecodeError, OSError):
            pass
    return dict(_DEFAULTS)


def save_settings(settings: dict) -> None:
    """Persist settings to the JSON settings file."""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
