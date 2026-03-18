"""
Tests for src/conversation_db.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.conversation_db import ConversationDB


class TestConversationDB(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.db = ConversationDB(db_path=Path(self._tmp.name))

    def tearDown(self):
        self.db.close()
        os.unlink(self._tmp.name)

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def test_create_and_list_sessions(self):
        sid = self.db.create_session("My chat")
        sessions = self.db.list_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["id"], sid)
        self.assertEqual(sessions[0]["name"], "My chat")

    def test_create_session_default_name(self):
        sid = self.db.create_session()
        s = self.db.get_session(sid)
        self.assertIsNotNone(s)
        self.assertIn("Chat", s["name"])

    def test_rename_session(self):
        sid = self.db.create_session("Old name")
        self.db.rename_session(sid, "New name")
        s = self.db.get_session(sid)
        self.assertEqual(s["name"], "New name")

    def test_delete_session(self):
        sid = self.db.create_session("To delete")
        self.db.delete_session(sid)
        self.assertIsNone(self.db.get_session(sid))
        self.assertEqual(self.db.list_sessions(), [])

    def test_get_nonexistent_session(self):
        self.assertIsNone(self.db.get_session(9999))

    def test_sessions_ordered_by_updated(self):
        sid1 = self.db.create_session("First")
        sid2 = self.db.create_session("Second")
        # Add message to first session to bump its updated_at
        self.db.add_message(sid1, "user", "hello")
        sessions = self.db.list_sessions()
        self.assertEqual(sessions[0]["id"], sid1)

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def test_add_and_get_messages(self):
        sid = self.db.create_session()
        mid = self.db.add_message(sid, "user", "Hello!")
        msgs = self.db.get_messages(sid)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[0]["content"], "Hello!")

    def test_message_ordering(self):
        sid = self.db.create_session()
        self.db.add_message(sid, "user", "first")
        self.db.add_message(sid, "assistant", "second")
        self.db.add_message(sid, "user", "third")
        msgs = self.db.get_messages(sid)
        self.assertEqual([m["content"] for m in msgs], ["first", "second", "third"])

    def test_get_messages_with_limit(self):
        sid = self.db.create_session()
        for i in range(10):
            self.db.add_message(sid, "user", f"msg{i}")
        msgs = self.db.get_messages(sid, limit=3)
        self.assertEqual(len(msgs), 3)
        self.assertEqual(msgs[-1]["content"], "msg9")

    def test_delete_message(self):
        sid = self.db.create_session()
        mid = self.db.add_message(sid, "user", "delete me")
        self.db.delete_message(mid)
        msgs = self.db.get_messages(sid)
        self.assertEqual(msgs, [])

    def test_clear_session_messages(self):
        sid = self.db.create_session()
        self.db.add_message(sid, "user", "msg1")
        self.db.add_message(sid, "assistant", "msg2")
        self.db.clear_session_messages(sid)
        self.assertEqual(self.db.get_messages(sid), [])
        # Session itself still exists
        self.assertIsNotNone(self.db.get_session(sid))

    def test_messages_deleted_with_session(self):
        sid = self.db.create_session()
        self.db.add_message(sid, "user", "msg")
        self.db.delete_session(sid)
        # Should not raise; messages should be gone via cascade
        msgs = self.db.get_messages(sid)
        self.assertEqual(msgs, [])

    def test_invalid_role_raises(self):
        sid = self.db.create_session()
        with self.assertRaises(Exception):
            self.db.add_message(sid, "invalid_role", "hello")

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def test_context_manager(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = Path(f.name)
        try:
            with ConversationDB(db_path=path) as db:
                sid = db.create_session("ctx test")
                db.add_message(sid, "user", "hi")
            # Re-open and verify persistence
            with ConversationDB(db_path=path) as db2:
                sessions = db2.list_sessions()
                self.assertEqual(len(sessions), 1)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
