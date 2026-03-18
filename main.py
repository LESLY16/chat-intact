#!/usr/bin/env python3
"""
AI Assistant – Windows 11 desktop application entry point.

Startup sequence
----------------
1. Verify administrator privileges (auto-elevates on Windows via UAC).
2. Initialise all subsystems (DB, AI engine, activity tracker, TTS, STT).
3. Launch the tkinter GUI.

Run with:
    python main.py
"""

import sys
import platform


def main() -> None:
    # ------------------------------------------------------------------
    # Admin privilege check (Windows only)
    # ------------------------------------------------------------------
    if platform.system() == "Windows":
        from src.admin_check import require_admin
        require_admin(auto_relaunch=True)

    # ------------------------------------------------------------------
    # Launch GUI
    # ------------------------------------------------------------------
    try:
        from src.gui import AssistantApp
        app = AssistantApp()
        app.mainloop()
    except ImportError as exc:
        print(
            f"Failed to start the application: {exc}\n"
            "Please install dependencies:\n\n"
            "    pip install -r requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
