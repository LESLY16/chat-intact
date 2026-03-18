"""
Tests for src/activity_tracker.py
"""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.activity_tracker import ActivityTracker, ActivityEntry, _get_clipboard_text


class TestActivityEntry(unittest.TestCase):

    def test_to_dict(self):
        e = ActivityEntry("2024-01-01 10:00:00", "Notepad", "some text")
        d = e.to_dict()
        self.assertEqual(d["timestamp"], "2024-01-01 10:00:00")
        self.assertEqual(d["window_title"], "Notepad")
        self.assertEqual(d["clipboard_snippet"], "some text")

    def test_clipboard_truncated_at_200(self):
        long_text = "x" * 300
        e = ActivityEntry("ts", "win", long_text)
        self.assertEqual(len(e.clipboard_snippet), 200)

    def test_none_values(self):
        e = ActivityEntry("ts", None, None)
        d = e.to_dict()
        self.assertIsNone(d["window_title"])
        self.assertIsNone(d["clipboard_snippet"])

    def test_repr(self):
        e = ActivityEntry("ts", "My Window", None)
        self.assertIn("My Window", repr(e))


class TestActivityTracker(unittest.TestCase):

    def _make_tracker(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.close()
        os.unlink(tmp.name)  # Remove so tracker creates fresh
        return ActivityTracker(
            log_path=Path(tmp.name),
            poll_interval=0.1,
            context_limit=5,
        ), tmp.name

    def test_start_stop(self):
        tracker, log_path = self._make_tracker()
        try:
            tracker.start()
            self.assertTrue(tracker._thread.is_alive())
            tracker.stop()
            self.assertFalse(tracker._thread.is_alive())
        finally:
            if os.path.exists(log_path):
                os.unlink(log_path)

    def test_double_start_is_safe(self):
        tracker, log_path = self._make_tracker()
        try:
            tracker.start()
            thread1 = tracker._thread
            tracker.start()  # Should not create a new thread
            self.assertIs(tracker._thread, thread1)
            tracker.stop()
        finally:
            if os.path.exists(log_path):
                os.unlink(log_path)

    def test_get_recent_entries_empty(self):
        tracker, log_path = self._make_tracker()
        try:
            entries = tracker.get_recent_entries()
            self.assertEqual(entries, [])
        finally:
            if os.path.exists(log_path):
                os.unlink(log_path)

    def test_context_summary_empty(self):
        tracker, log_path = self._make_tracker()
        try:
            summary = tracker.get_context_summary()
            self.assertIn("No recent", summary)
        finally:
            if os.path.exists(log_path):
                os.unlink(log_path)

    def test_sampling_records_entry(self):
        tracker, log_path = self._make_tracker()
        try:
            with patch(
                "src.activity_tracker._get_active_window_title",
                return_value="Test Window",
            ), patch(
                "src.activity_tracker._get_clipboard_text",
                return_value="copied text",
            ):
                tracker._sample()

            entries = tracker.get_recent_entries()
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["window_title"], "Test Window")
            self.assertEqual(entries[0]["clipboard_snippet"], "copied text")
        finally:
            if os.path.exists(log_path):
                os.unlink(log_path)

    def test_no_duplicate_when_unchanged(self):
        tracker, log_path = self._make_tracker()
        try:
            with patch(
                "src.activity_tracker._get_active_window_title",
                return_value="Same Window",
            ), patch(
                "src.activity_tracker._get_clipboard_text",
                return_value=None,
            ):
                tracker._sample()
                tracker._sample()  # Same state – should not add duplicate

            entries = tracker.get_recent_entries()
            self.assertEqual(len(entries), 1)
        finally:
            if os.path.exists(log_path):
                os.unlink(log_path)

    def test_context_summary_format(self):
        tracker, log_path = self._make_tracker()
        try:
            with patch(
                "src.activity_tracker._get_active_window_title",
                return_value="Browser",
            ), patch(
                "src.activity_tracker._get_clipboard_text",
                return_value=None,
            ):
                tracker._sample()
            summary = tracker.get_context_summary()
            self.assertIn("Browser", summary)
            self.assertIn("Active window", summary)
        finally:
            if os.path.exists(log_path):
                os.unlink(log_path)

    def test_log_persisted_to_disk(self):
        tracker, log_path = self._make_tracker()
        try:
            with patch(
                "src.activity_tracker._get_active_window_title",
                return_value="Disk Test",
            ), patch(
                "src.activity_tracker._get_clipboard_text",
                return_value=None,
            ):
                tracker._sample()

            self.assertTrue(Path(log_path).exists())
            with open(log_path) as f:
                data = json.load(f)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["window_title"], "Disk Test")
        finally:
            if os.path.exists(log_path):
                os.unlink(log_path)

    def test_load_existing_log(self):
        tmp = tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        )
        entries = [
            {"timestamp": "2024-01-01 09:00:00", "window_title": "Loaded", "clipboard_snippet": None}
        ]
        json.dump(entries, tmp)
        tmp.close()

        try:
            tracker = ActivityTracker(
                log_path=Path(tmp.name), poll_interval=60, context_limit=10
            )
            recent = tracker.get_recent_entries()
            self.assertEqual(len(recent), 1)
            self.assertEqual(recent[0]["window_title"], "Loaded")
        finally:
            os.unlink(tmp.name)


if __name__ == "__main__":
    unittest.main()
