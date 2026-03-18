"""
Activity tracker – monitors the admin's daily PC activity and builds a
short context summary that can be injected into the AI prompt.

Tracks:
  • Active foreground window title / application name (Windows only)
  • Clipboard text changes (all platforms)

All data is stored locally in a JSON log.  No content is sent off-device.
"""

import json
import platform
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Deque, Dict, Optional

import config


def _get_active_window_title() -> Optional[str]:
    """Return the title of the current foreground window (Windows only)."""
    if platform.system() != "Windows":
        return None
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return None
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value or None
    except Exception:
        return None


def _get_clipboard_text() -> Optional[str]:
    """Return the current clipboard text content (best-effort)."""
    try:
        import pyperclip
        text = pyperclip.paste()
        return text if text else None
    except Exception:
        return None


class ActivityEntry:
    """A single snapshot of the user's desktop activity."""

    __slots__ = ("timestamp", "window_title", "clipboard_snippet")

    def __init__(
        self,
        timestamp: str,
        window_title: Optional[str],
        clipboard_snippet: Optional[str],
    ) -> None:
        self.timestamp = timestamp
        self.window_title = window_title
        # Store only the first 200 chars of clipboard content
        self.clipboard_snippet = (
            clipboard_snippet[:200] if clipboard_snippet else None
        )

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "window_title": self.window_title,
            "clipboard_snippet": self.clipboard_snippet,
        }

    def __repr__(self) -> str:
        return (
            f"ActivityEntry(ts={self.timestamp!r}, "
            f"window={self.window_title!r})"
        )


class ActivityTracker:
    """
    Background thread that periodically samples desktop activity and keeps
    a rolling in-memory log as well as an on-disk JSON log.

    Usage
    -----
    tracker = ActivityTracker()
    tracker.start()
    ...
    context = tracker.get_context_summary()  # inject into AI prompt
    tracker.stop()
    """

    def __init__(
        self,
        log_path: Path = config.ACTIVITY_LOG_PATH,
        poll_interval: float = config.ACTIVITY_POLL_INTERVAL,
        context_limit: int = config.ACTIVITY_CONTEXT_LIMIT,
    ) -> None:
        self._log_path = log_path
        self._poll_interval = poll_interval
        self._context_limit = context_limit

        self._entries: Deque[ActivityEntry] = deque(maxlen=500)
        self._last_clipboard: Optional[str] = None
        self._last_window: Optional[str] = None

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Load existing log from disk
        self._load_log()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background polling thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="ActivityTracker"
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the background polling thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def get_recent_entries(self, limit: Optional[int] = None) -> list:
        """Return the most recent activity entries as dicts."""
        limit = limit or self._context_limit
        with self._lock:
            entries = list(self._entries)
        return [e.to_dict() for e in entries[-limit:]]

    def get_context_summary(self, limit: Optional[int] = None) -> str:
        """
        Return a human-readable summary of recent activity suitable for
        injection into an AI prompt.
        """
        entries = self.get_recent_entries(limit)
        if not entries:
            return "No recent activity recorded."

        lines = ["Recent desktop activity (most recent last):"]
        for e in entries:
            ts = e.get("timestamp", "")
            win = e.get("window_title") or "—"
            clip = e.get("clipboard_snippet")
            line = f"  [{ts}] Active window: {win}"
            if clip:
                line += f"  |  Clipboard: {clip!r}"
            lines.append(line)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._sample()
            except Exception:
                pass
            self._stop_event.wait(self._poll_interval)

    def _sample(self) -> None:
        window = _get_active_window_title()
        clipboard = _get_clipboard_text()

        # Only record if something changed
        if window == self._last_window and clipboard == self._last_clipboard:
            return

        self._last_window = window
        self._last_clipboard = clipboard

        entry = ActivityEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            window_title=window,
            clipboard_snippet=clipboard,
        )
        with self._lock:
            self._entries.append(entry)

        self._append_to_log(entry)

    def _load_log(self) -> None:
        if not self._log_path.exists():
            return
        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data[-500:]:
                self._entries.append(
                    ActivityEntry(
                        timestamp=item.get("timestamp", ""),
                        window_title=item.get("window_title"),
                        clipboard_snippet=item.get("clipboard_snippet"),
                    )
                )
        except (json.JSONDecodeError, OSError):
            pass

    def _append_to_log(self, entry: ActivityEntry) -> None:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if self._log_path.exists():
                with open(self._log_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = []
        except (json.JSONDecodeError, OSError):
            data = []

        data.append(entry.to_dict())
        # Keep last 500 entries on disk
        data = data[-500:]

        with open(self._log_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
