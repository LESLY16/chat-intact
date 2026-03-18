# AI Assistant for Windows 11

A **Windows 11 admin-only desktop AI assistant** that learns from your daily PC activity, supports web search with source links, provides chat and voice replies (TTS + optional STT), remembers past conversations, and allows easy copy/paste of outputs.

---

## Features

| Feature | Details |
|---|---|
| 🔒 Admin-only | Requires Windows administrator privileges; auto-elevates via UAC |
| 🧠 Local AI inference | Powered by [Ollama](https://ollama.ai) (runs locally, no data leaves your PC) |
| 🔌 OpenAI-compatible fallback | Configure any OpenAI-compatible API as a secondary backend |
| 🌐 Web search | DuckDuckGo search with numbered source citations injected into AI context |
| 🔊 Text-to-speech (TTS) | Windows SAPI via pyttsx3 — reads assistant replies aloud |
| 🎤 Speech-to-text (STT) | Optional microphone input (Google Web Speech or CMU Sphinx offline) |
| 📋 Copy/paste | One-click copy button on every message bubble |
| 💬 Conversation history | SQLite database; multiple named sessions; rename & delete |
| 🖥️ Activity awareness | Tracks active window & clipboard; injects recent context into AI prompts |
| ⚙️ Settings panel | Configurable model, TTS rate/voice, search limits, and more |

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | ≥ 3.10 |
| [Ollama](https://ollama.ai) | latest (recommended) |
| Windows 11 | Any edition (admin account required) |

> **Note:** The application also runs on Linux/macOS for development purposes; the admin check and Windows-specific activity tracking are gracefully skipped on non-Windows systems.

---

## Quick start

### 1. Clone the repository

```bash
git clone https://github.com/LESLY16/chat-intact.git
cd chat-intact
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Start Ollama (recommended)

```bash
# Install Ollama from https://ollama.ai, then:
ollama pull llama3
ollama serve
```

### 4. Launch the assistant

```bash
# On Windows – right-click and "Run as administrator", or:
python main.py
```

The app will automatically request UAC elevation if not already running as admin.

---

## Configuration

All settings can be changed via the **⚙ Settings** panel in the UI, or by editing `data/settings.json` / a `.env` file in the project root.

| Setting | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3` | Model name for Ollama |
| `OPENAI_API_KEY` | *(empty)* | Enable OpenAI-compatible backend |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible endpoint |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model for OpenAI backend |
| `SEARCH_MAX_RESULTS` | `5` | Max web search results per query |
| `TTS_ENABLED` | `true` | Enable text-to-speech |
| `TTS_RATE` | `175` | TTS speaking rate (words/min) |
| `STT_ENABLED` | `false` | Enable speech-to-text microphone input |
| `ACTIVITY_TRACKING_ENABLED` | `true` | Track active window & clipboard |
| `CONVERSATION_CONTEXT_LIMIT` | `20` | Recent messages included per prompt |

---

## Project structure

```
chat-intact/
├── main.py                  # Entry point (admin check → GUI)
├── config.py                # Configuration & settings helpers
├── requirements.txt         # Python dependencies
├── src/
│   ├── admin_check.py       # Windows UAC / privilege verification
│   ├── activity_tracker.py  # Background desktop activity monitor
│   ├── ai_engine.py         # Ollama / OpenAI streaming client
│   ├── conversation_db.py   # SQLite conversation persistence
│   ├── gui.py               # tkinter GUI (dark theme)
│   ├── stt_engine.py        # Optional speech-to-text
│   ├── tts_engine.py        # Text-to-speech (pyttsx3 / SAPI)
│   └── web_search.py        # DuckDuckGo web search
├── tests/
│   ├── test_activity_tracker.py
│   ├── test_admin_check.py
│   ├── test_ai_engine.py
│   ├── test_conversation_db.py
│   └── test_web_search.py
└── data/                    # Created at runtime
    ├── conversations.db     # SQLite database
    ├── settings.json        # Saved UI settings
    └── activity_log.json    # Rolling activity log (last 500 entries)
```

---

## Running tests

```bash
pip install pytest
python -m pytest tests/ -v
```

---

## Privacy & security

- **All data stays local.** Conversations, activity logs, and settings are stored in the `data/` folder on your PC.
- **No telemetry.** The app never phones home.
- **Web search** makes outbound requests to DuckDuckGo only when you toggle the 🌐 Web button.
- **Ollama** runs models entirely locally — no data is sent to any third-party AI provider unless you configure an OpenAI API key.
- **Admin privileges** are required so the assistant can read foreground window titles across all applications.

---

## License

See [LICENSE](LICENSE).