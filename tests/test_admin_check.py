"""
Tests for src/admin_check.py
"""

import sys
import os
import platform
import unittest
from unittest.mock import patch, MagicMock

# Ensure repo root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.admin_check import is_admin, require_admin


class TestIsAdmin(unittest.TestCase):

    @unittest.skipUnless(platform.system() != "Windows", "Non-Windows test")
    def test_non_windows_root(self):
        with patch("os.geteuid", return_value=0):
            self.assertTrue(is_admin())

    @unittest.skipUnless(platform.system() != "Windows", "Non-Windows test")
    def test_non_windows_non_root(self):
        with patch("os.geteuid", return_value=1000):
            self.assertFalse(is_admin())

    @unittest.skipUnless(platform.system() == "Windows", "Windows-only test")
    def test_windows_admin_true(self):
        mock_ctypes = MagicMock()
        mock_ctypes.windll.shell32.IsUserAnAdmin.return_value = 1
        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            # Re-import to pick up the mock
            import importlib
            import src.admin_check as ac
            importlib.reload(ac)
            with patch.object(mock_ctypes.windll.shell32, "IsUserAnAdmin", return_value=1):
                result = ac.is_admin()
                self.assertTrue(result)

    def test_require_admin_raises_when_not_admin(self):
        with patch("src.admin_check.is_admin", return_value=False):
            with self.assertRaises(PermissionError):
                require_admin(auto_relaunch=False)

    def test_require_admin_passes_when_admin(self):
        with patch("src.admin_check.is_admin", return_value=True):
            # Should not raise
            require_admin(auto_relaunch=False)


if __name__ == "__main__":
    unittest.main()
