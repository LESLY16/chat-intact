"""
Main GUI for the Windows 11 AI Assistant.
Built with tkinter (bundled with Python) for zero extra dependencies.

Layout
------
Left sidebar  – session list + New / Delete / Rename buttons
Centre panel  – chat transcript (scrollable)
Bottom bar    – text input, Send, Mic (STT), Search toggle, Copy
Right panel   – settings (collapsible)
"""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, simpledialog, ttk
from typing import Callable, Optional

import config
from src.ai_engine import AIEngine
from src.activity_tracker import ActivityTracker
from src.conversation_db import ConversationDB
from src.tts_engine import TTSEngine
from src.stt_engine import STTEngine
from src.web_search import WebSearch


# ---------------------------------------------------------------------------
# Colour palette (dark theme, Windows-11-inspired)
# ---------------------------------------------------------------------------
BG_DARK = "#1c1c1e"
BG_PANEL = "#2c2c2e"
BG_INPUT = "#3a3a3c"
FG_PRIMARY = "#f5f5f7"
FG_SECONDARY = "#aeaeb2"
ACCENT = "#0a84ff"
ACCENT_HOVER = "#409cff"
USER_BUBBLE = "#0a84ff"
ASST_BUBBLE = "#3a3a3c"
DANGER = "#ff453a"


class ChatMessage(tk.Frame):
    """A single chat bubble (user or assistant)."""

    def __init__(
        self,
        parent,
        role: str,
        content: str,
        timestamp: str = "",
        on_copy: Optional[Callable[[str], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, bg=BG_DARK, **kwargs)
        is_user = role == "user"

        bubble_bg = USER_BUBBLE if is_user else ASST_BUBBLE
        anchor = "e" if is_user else "w"
        padx = (80, 8) if is_user else (8, 80)

        outer = tk.Frame(self, bg=BG_DARK)
        outer.pack(fill="x", padx=padx, pady=(4, 0))

        bubble = tk.Frame(outer, bg=bubble_bg, padx=12, pady=8)
        bubble.pack(anchor=anchor)

        txt = tk.Text(
            bubble,
            wrap="word",
            bg=bubble_bg,
            fg=FG_PRIMARY,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=("Segoe UI", 11),
            cursor="arrow",
        )
        txt.insert("1.0", content)
        txt.config(state="disabled")
        txt.pack(fill="both")
        # Auto-resize height
        self._resize_text(txt, content)
        self._txt = txt

        # Timestamp + copy button row
        meta = tk.Frame(outer, bg=BG_DARK)
        meta.pack(anchor=anchor, pady=(2, 4))

        if timestamp:
            lbl = tk.Label(
                meta,
                text=timestamp[:16],
                bg=BG_DARK,
                fg=FG_SECONDARY,
                font=("Segoe UI", 8),
            )
            lbl.pack(side="left", padx=(0, 6))

        copy_btn = tk.Button(
            meta,
            text="⎘ Copy",
            bg=BG_DARK,
            fg=FG_SECONDARY,
            relief="flat",
            borderwidth=0,
            font=("Segoe UI", 8),
            cursor="hand2",
            command=lambda: on_copy(content) if on_copy else None,
            activebackground=BG_DARK,
            activeforeground=FG_PRIMARY,
        )
        copy_btn.pack(side="left")

    @staticmethod
    def _resize_text(txt: tk.Text, content: str) -> None:
        line_count = content.count("\n") + 1
        # Rough estimate: cap at 20 lines displayed, then scrollable
        display_lines = min(line_count, 20)
        txt.config(height=display_lines, width=60)


class SettingsPanel(tk.Frame):
    """Collapsible settings panel shown on the right side."""

    def __init__(self, parent, settings: dict, on_save: Callable[[dict], None], **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        self._settings = settings
        self._on_save = on_save
        self._vars: dict = {}
        self._build()

    def _build(self) -> None:
        tk.Label(
            self, text="⚙ Settings", bg=BG_PANEL, fg=FG_PRIMARY,
            font=("Segoe UI", 13, "bold"),
        ).pack(pady=(12, 8), padx=12, anchor="w")

        self._add_field("Ollama URL", "ollama_base_url", str)
        self._add_field("Ollama model", "ollama_model", str)
        self._add_field("OpenAI API key", "openai_api_key", str, show="*")
        self._add_field("OpenAI model", "openai_model", str)
        self._add_field("Search results", "search_max_results", int)
        self._add_toggle("TTS enabled", "tts_enabled")
        self._add_field("TTS rate (wpm)", "tts_rate", int)
        self._add_toggle("STT enabled", "stt_enabled")
        self._add_toggle("Activity tracking", "activity_tracking_enabled")

        save_btn = tk.Button(
            self,
            text="Save",
            bg=ACCENT,
            fg=FG_PRIMARY,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
            command=self._save,
            activebackground=ACCENT_HOVER,
            activeforeground=FG_PRIMARY,
        )
        save_btn.pack(padx=12, pady=12, fill="x")

    def _add_field(
        self, label: str, key: str, dtype: type, show: str = ""
    ) -> None:
        frame = tk.Frame(self, bg=BG_PANEL)
        frame.pack(fill="x", padx=12, pady=3)
        tk.Label(
            frame, text=label, bg=BG_PANEL, fg=FG_SECONDARY,
            font=("Segoe UI", 9), width=18, anchor="w",
        ).pack(side="left")
        var = tk.StringVar(value=str(self._settings.get(key, "")))
        self._vars[key] = (var, dtype)
        entry = tk.Entry(
            frame,
            textvariable=var,
            bg=BG_INPUT,
            fg=FG_PRIMARY,
            relief="flat",
            insertbackground=FG_PRIMARY,
            show=show,
        )
        entry.pack(side="left", fill="x", expand=True)

    def _add_toggle(self, label: str, key: str) -> None:
        frame = tk.Frame(self, bg=BG_PANEL)
        frame.pack(fill="x", padx=12, pady=3)
        tk.Label(
            frame, text=label, bg=BG_PANEL, fg=FG_SECONDARY,
            font=("Segoe UI", 9), width=18, anchor="w",
        ).pack(side="left")
        var = tk.BooleanVar(value=bool(self._settings.get(key, False)))
        self._vars[key] = (var, bool)
        cb = tk.Checkbutton(
            frame,
            variable=var,
            bg=BG_PANEL,
            fg=FG_PRIMARY,
            selectcolor=BG_INPUT,
            relief="flat",
            activebackground=BG_PANEL,
        )
        cb.pack(side="left")

    def _save(self) -> None:
        updated = dict(self._settings)
        for key, (var, dtype) in self._vars.items():
            raw = var.get()
            try:
                if dtype is bool:
                    updated[key] = bool(var.get())
                elif dtype is int:
                    updated[key] = int(raw)
                elif dtype is float:
                    updated[key] = float(raw)
                else:
                    updated[key] = raw
            except ValueError:
                pass
        self._on_save(updated)


class AssistantApp(tk.Tk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("AI Assistant")
        self.configure(bg=BG_DARK)
        self.minsize(900, 600)
        self.geometry("1200x750")

        self._settings = config.load_settings()

        # Core components
        self._db = ConversationDB()
        self._ai = AIEngine()
        self._tts = TTSEngine()
        self._stt = STTEngine(on_result=self._on_stt_result)
        self._search = WebSearch(
            max_results=self._settings.get("search_max_results", config.SEARCH_MAX_RESULTS)
        )
        self._tracker = ActivityTracker()
        if self._settings.get("activity_tracking_enabled", config.ACTIVITY_TRACKING_ENABLED):
            self._tracker.start()

        # State
        self._current_session_id: Optional[int] = None
        self._use_search = tk.BooleanVar(value=False)
        self._is_generating = False
        self._token_queue: queue.Queue = queue.Queue()

        self._build_ui()
        self._refresh_session_list()
        self._load_or_create_session()

        # Start the token-drain loop
        self.after(50, self._drain_token_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Top bar
        self._build_topbar()

        # Main content area (sidebar | chat | settings)
        main = tk.Frame(self, bg=BG_DARK)
        main.pack(fill="both", expand=True)

        # Session sidebar
        self._build_sidebar(main)

        # Chat area
        chat_frame = tk.Frame(main, bg=BG_DARK)
        chat_frame.pack(side="left", fill="both", expand=True)
        self._build_chat_area(chat_frame)
        self._build_input_area(chat_frame)

        # Settings panel (hidden by default)
        self._settings_panel_visible = False
        self._settings_panel = SettingsPanel(
            main,
            settings=self._settings,
            on_save=self._apply_settings,
            width=280,
        )
        # Don't pack yet – toggled by button

    def _build_topbar(self) -> None:
        bar = tk.Frame(self, bg=BG_PANEL, height=44)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        tk.Label(
            bar,
            text="🤖  AI Assistant",
            bg=BG_PANEL,
            fg=FG_PRIMARY,
            font=("Segoe UI", 13, "bold"),
        ).pack(side="left", padx=16)

        # Settings toggle
        self._settings_btn = tk.Button(
            bar,
            text="⚙",
            bg=BG_PANEL,
            fg=FG_SECONDARY,
            relief="flat",
            font=("Segoe UI", 14),
            cursor="hand2",
            command=self._toggle_settings,
            activebackground=BG_PANEL,
            activeforeground=FG_PRIMARY,
        )
        self._settings_btn.pack(side="right", padx=8)

        # TTS indicator
        self._tts_label = tk.Label(
            bar,
            text="🔊" if self._tts.enabled else "🔇",
            bg=BG_PANEL,
            fg=FG_SECONDARY,
            font=("Segoe UI", 13),
        )
        self._tts_label.pack(side="right", padx=4)

    def _build_sidebar(self, parent: tk.Frame) -> None:
        sidebar = tk.Frame(parent, bg=BG_PANEL, width=220)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(
            sidebar,
            text="Conversations",
            bg=BG_PANEL,
            fg=FG_PRIMARY,
            font=("Segoe UI", 10, "bold"),
        ).pack(pady=(12, 4), padx=8, anchor="w")

        btn_row = tk.Frame(sidebar, bg=BG_PANEL)
        btn_row.pack(fill="x", padx=8, pady=(0, 6))

        for text, cmd in [
            ("＋ New", self._new_session),
            ("✎ Rename", self._rename_session),
            ("🗑 Delete", self._delete_session),
        ]:
            btn = tk.Button(
                btn_row,
                text=text,
                bg=BG_INPUT,
                fg=FG_PRIMARY,
                relief="flat",
                font=("Segoe UI", 9),
                cursor="hand2",
                command=cmd,
                activebackground=ACCENT,
                activeforeground=FG_PRIMARY,
            )
            btn.pack(side="left", padx=2)

        self._session_listbox = tk.Listbox(
            sidebar,
            bg=BG_PANEL,
            fg=FG_PRIMARY,
            selectbackground=ACCENT,
            selectforeground=FG_PRIMARY,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=("Segoe UI", 10),
            activestyle="none",
        )
        self._session_listbox.pack(fill="both", expand=True, padx=8, pady=4)
        self._session_listbox.bind("<<ListboxSelect>>", self._on_session_select)

    def _build_chat_area(self, parent: tk.Frame) -> None:
        container = tk.Frame(parent, bg=BG_DARK)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, bg=BG_DARK, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            container, orient="vertical", command=canvas.yview
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._messages_frame = tk.Frame(canvas, bg=BG_DARK)
        self._canvas_window = canvas.create_window(
            (0, 0), window=self._messages_frame, anchor="nw"
        )

        self._messages_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            ),
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(
                self._canvas_window, width=e.width
            ),
        )
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(
            -1 * (e.delta // 120), "units"
        ))

        self._canvas = canvas

    def _build_input_area(self, parent: tk.Frame) -> None:
        bar = tk.Frame(parent, bg=BG_PANEL)
        bar.pack(fill="x", padx=8, pady=8)

        # Search toggle
        search_cb = tk.Checkbutton(
            bar,
            text="🌐 Web",
            variable=self._use_search,
            bg=BG_PANEL,
            fg=FG_SECONDARY,
            selectcolor=BG_INPUT,
            activebackground=BG_PANEL,
            relief="flat",
            font=("Segoe UI", 10),
            cursor="hand2",
        )
        search_cb.pack(side="left", padx=(4, 0))

        # Mic button (STT)
        self._mic_btn = tk.Button(
            bar,
            text="🎤",
            bg=BG_PANEL,
            fg=FG_SECONDARY,
            relief="flat",
            font=("Segoe UI", 14),
            cursor="hand2",
            command=self._toggle_stt,
            activebackground=BG_PANEL,
            activeforeground=FG_PRIMARY,
        )
        self._mic_btn.pack(side="left", padx=4)

        # Text input
        self._input_box = tk.Text(
            bar,
            height=3,
            bg=BG_INPUT,
            fg=FG_PRIMARY,
            insertbackground=FG_PRIMARY,
            relief="flat",
            font=("Segoe UI", 11),
            wrap="word",
            padx=8,
            pady=6,
        )
        self._input_box.pack(side="left", fill="both", expand=True, padx=6)
        self._input_box.bind("<Return>", self._on_enter)
        self._input_box.bind("<Shift-Return>", lambda e: None)

        # Send button
        self._send_btn = tk.Button(
            bar,
            text="Send ➤",
            bg=ACCENT,
            fg=FG_PRIMARY,
            relief="flat",
            font=("Segoe UI", 11, "bold"),
            cursor="hand2",
            command=self._send_message,
            activebackground=ACCENT_HOVER,
            activeforeground=FG_PRIMARY,
        )
        self._send_btn.pack(side="left", padx=4)

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def _refresh_session_list(self) -> None:
        sessions = self._db.list_sessions()
        self._sessions_data = sessions
        self._session_listbox.delete(0, "end")
        for s in sessions:
            self._session_listbox.insert("end", s["name"])

    def _load_or_create_session(self) -> None:
        sessions = self._db.list_sessions()
        if sessions:
            self._open_session(sessions[0]["id"])
            self._session_listbox.selection_set(0)
        else:
            self._new_session()

    def _open_session(self, session_id: int) -> None:
        self._current_session_id = session_id
        self._clear_chat_display()
        messages = self._db.get_messages(session_id)
        for msg in messages:
            if msg["role"] != "system":
                self._append_bubble(
                    msg["role"], msg["content"], msg["timestamp"]
                )

    def _new_session(self) -> None:
        sid = self._db.create_session()
        self._refresh_session_list()
        self._session_listbox.selection_clear(0, "end")
        # Select the newly created session (first in list since sorted by updated_at desc)
        self._session_listbox.selection_set(0)
        self._open_session(sid)

    def _rename_session(self) -> None:
        if self._current_session_id is None:
            return
        new_name = simpledialog.askstring(
            "Rename session", "New name:", parent=self
        )
        if new_name:
            self._db.rename_session(self._current_session_id, new_name)
            self._refresh_session_list()

    def _delete_session(self) -> None:
        if self._current_session_id is None:
            return
        confirm = messagebox.askyesno(
            "Delete session",
            "Delete this conversation? This cannot be undone.",
            parent=self,
        )
        if confirm:
            self._db.delete_session(self._current_session_id)
            self._current_session_id = None
            self._refresh_session_list()
            self._load_or_create_session()

    def _on_session_select(self, event) -> None:
        sel = self._session_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self._sessions_data):
            self._open_session(self._sessions_data[idx]["id"])

    # ------------------------------------------------------------------
    # Chat display helpers
    # ------------------------------------------------------------------

    def _clear_chat_display(self) -> None:
        for child in self._messages_frame.winfo_children():
            child.destroy()

    def _append_bubble(
        self, role: str, content: str, timestamp: str = ""
    ) -> ChatMessage:
        bubble = ChatMessage(
            self._messages_frame,
            role=role,
            content=content,
            timestamp=timestamp,
            on_copy=self._copy_to_clipboard,
        )
        bubble.pack(fill="x", pady=2)
        self._scroll_to_bottom()
        return bubble

    def _scroll_to_bottom(self) -> None:
        self._canvas.update_idletasks()
        self._canvas.yview_moveto(1.0)

    # ------------------------------------------------------------------
    # Message sending & AI reply
    # ------------------------------------------------------------------

    def _on_enter(self, event) -> str:
        if event.state & 0x1:  # Shift held → newline
            return
        self._send_message()
        return "break"

    def _send_message(self) -> None:
        if self._is_generating:
            return
        user_text = self._input_box.get("1.0", "end").strip()
        if not user_text:
            return

        self._input_box.delete("1.0", "end")

        if self._current_session_id is None:
            self._new_session()

        # Persist + display user message
        from datetime import datetime
        ts = datetime.now().isoformat()
        self._db.add_message(self._current_session_id, "user", user_text)
        self._append_bubble("user", user_text, ts)

        # Kick off AI reply in background
        self._is_generating = True
        self._send_btn.config(state="disabled")
        threading.Thread(
            target=self._generate_reply,
            args=(user_text,),
            daemon=True,
        ).start()

    def _generate_reply(self, user_text: str) -> None:
        try:
            # Optionally fetch web search results
            search_context = ""
            search_results = []
            if self._use_search.get() and self._search.available:
                search_results = self._search.search(user_text)
                search_context = self._search.format_results_for_prompt(
                    search_results, user_text
                )

            # Build activity context
            activity_context = ""
            if self._settings.get(
                "activity_tracking_enabled", config.ACTIVITY_TRACKING_ENABLED
            ):
                activity_context = self._tracker.get_context_summary()

            # Build system prompt
            system_prompt = self._ai.build_system_prompt(
                activity_context=activity_context,
                search_context=search_context,
            )

            # Build message history for the AI
            limit = self._settings.get(
                "conversation_context_limit", config.CONVERSATION_CONTEXT_LIMIT
            )
            history = self._db.get_messages(self._current_session_id, limit=limit)
            messages = [{"role": "system", "content": system_prompt}]
            for msg in history:
                if msg["role"] != "system":
                    messages.append(
                        {"role": msg["role"], "content": msg["content"]}
                    )

            # Stream tokens into the queue
            self._token_queue.put(("START", None))
            for chunk in self._ai.chat_stream(messages):
                self._token_queue.put(("TOKEN", chunk))

            self._token_queue.put(("END", None))
        except Exception as exc:
            self._token_queue.put(("ERROR", str(exc)))

    def _drain_token_queue(self) -> None:
        """Called every 50 ms on the main thread to pull tokens from the queue."""
        try:
            while True:
                msg_type, payload = self._token_queue.get_nowait()
                if msg_type == "START":
                    from datetime import datetime
                    self._streaming_bubble = self._append_bubble(
                        "assistant", "", datetime.now().isoformat()
                    )
                    self._streaming_content = []
                elif msg_type == "TOKEN":
                    self._streaming_content.append(payload)
                    full = "".join(self._streaming_content)
                    self._update_streaming_bubble(full)
                elif msg_type in ("END", "ERROR"):
                    full = "".join(
                        getattr(self, "_streaming_content", [])
                    )
                    if msg_type == "ERROR":
                        full = f"Error: {payload}"
                    self._update_streaming_bubble(full)
                    self._finalize_reply(full)
        except queue.Empty:
            pass
        self.after(50, self._drain_token_queue)

    def _update_streaming_bubble(self, text: str) -> None:
        bubble = getattr(self, "_streaming_bubble", None)
        if bubble is None:
            return
        for child in bubble.winfo_children():
            for subchild in child.winfo_children():
                if isinstance(subchild, tk.Frame):
                    for widget in subchild.winfo_children():
                        if isinstance(widget, tk.Text):
                            widget.config(state="normal")
                            widget.delete("1.0", "end")
                            widget.insert("1.0", text)
                            widget.config(state="disabled")
                            ChatMessage._resize_text(widget, text)
                            return

    def _finalize_reply(self, full_text: str) -> None:
        if self._current_session_id is not None and full_text.strip():
            from datetime import datetime
            self._db.add_message(
                self._current_session_id, "assistant", full_text
            )
            self._refresh_session_list()

        # TTS
        if self._tts.enabled and full_text.strip():
            # Speak only the first 500 chars to avoid very long TTS
            self._tts.speak(full_text[:500])

        self._is_generating = False
        self._send_btn.config(state="normal")
        self._scroll_to_bottom()

    # ------------------------------------------------------------------
    # STT
    # ------------------------------------------------------------------

    def _toggle_stt(self) -> None:
        if not self._stt.available:
            messagebox.showinfo(
                "STT Unavailable",
                "Speech recognition is not available.\n"
                "Install 'SpeechRecognition' and a microphone to use this feature.",
                parent=self,
            )
            return
        if self._stt._listening:
            self._stt.stop_listening()
            self._mic_btn.config(fg=FG_SECONDARY)
        else:
            self._stt.start_listening()
            self._mic_btn.config(fg=DANGER)

    def _on_stt_result(self, text: str) -> None:
        """Called from STT background thread with transcribed text."""
        self.after(0, lambda: self._insert_stt_text(text))

    def _insert_stt_text(self, text: str) -> None:
        self._input_box.insert("end", text)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _toggle_settings(self) -> None:
        if self._settings_panel_visible:
            self._settings_panel.pack_forget()
            self._settings_panel_visible = False
        else:
            self._settings_panel.pack(
                side="right", fill="y", padx=(0, 0)
            )
            self._settings_panel_visible = True

    def _apply_settings(self, new_settings: dict) -> None:
        self._settings = new_settings
        config.save_settings(new_settings)
        self._ai.reload_settings()
        # Update TTS
        self._tts.enabled = new_settings.get("tts_enabled", config.TTS_ENABLED)
        self._tts.set_rate(new_settings.get("tts_rate", config.TTS_RATE))
        self._tts.set_volume(new_settings.get("tts_volume", config.TTS_VOLUME))
        self._tts_label.config(text="🔊" if self._tts.enabled else "🔇")
        # Update activity tracking
        tracking = new_settings.get(
            "activity_tracking_enabled", config.ACTIVITY_TRACKING_ENABLED
        )
        if tracking and not self._tracker._thread:
            self._tracker.start()
        elif not tracking:
            self._tracker.stop()
        messagebox.showinfo("Settings", "Settings saved.", parent=self)

    # ------------------------------------------------------------------
    # Clipboard
    # ------------------------------------------------------------------

    def _copy_to_clipboard(self, text: str) -> None:
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        self._tracker.stop()
        self._tts.shutdown()
        self._stt.stop_listening()
        self._db.close()
        self.destroy()
