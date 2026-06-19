"""ttkbootstrap UI for PPT Gen.

Run (Python 3.10 venv):  .\venv310\Scripts\python.exe src/main_ttk.py
"""

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import traceback
from tkinter import messagebox, filedialog
import tkinter as tk
import tkinter.font as tkfont

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText, ScrolledFrame

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

from ppt_builder import parse_sequence_text
from ppt_server_client import (
    PptServerEndpointUnavailable,
    PptServerResponseError,
    PptServerUnavailable,
    download_history_db_via_server,
    fetch_weekly_history_via_server,
    generate_pptx_via_server,
    generate_songlist_card_via_server,
    search_lyrics_catalog,
)
from ppt_service import (
    LocalOfficeUnavailable,
    build_integrated_pptx_with_local_office,
)
from songlist_builder import build_songlist_card, export_pptx_to_png
from error_reporter import build_error_report, format_exception, report_error_async, send_error_report
from constants import (
    APP_DISPLAY_NAME, APP_WINDOW_TITLE,
    ASSETS_DIR_NAME, ICON_ICO_FILE_NAME, ICON_FILE_NAME, LOGO_FILE_NAME,
    LOGO_SIZE, LOGO_DISPLAY_SCALE,
    TEMPLATE_DIR_NAME, TEMPLATE_DOWNLOAD_URL,
    OUTPUT_FILE_NAME, SONGLIST_TEMPLATE_FILE_NAME, SONGLIST_OUTPUT_FILE_NAME,
    WEEKLY_HISTORY_CACHE_FILE_NAME, WEEKLY_HISTORY_DB_FILE_NAME,
    DEFAULT_SERVER_URL, DEFAULT_MAX_LINES_PER_SLIDE, DEFAULT_MAX_CHARS_PER_LINE,
    DEFAULT_LYRICS_FONT_SIZE,
    BRAND_FONT_CANDIDATES,
    MUTED_FG, TEXT_FG,
    SEQUENCE_GUIDE_TEXT, LYRICS_GUIDE_TEXT,
)

BRAND_ROSE = "#D63B6E"


# ─── Multiline dialog ──────────────────────────────────────────────────────
class MultilineDialog(ttk.Toplevel):
    def __init__(self, parent, title: str, prompt: str, initial_text: str = ""):
        super().__init__(parent)
        self.title(title)
        self.geometry("520x400")
        self.transient(parent)
        self.grab_set()
        self.result: str | None = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        if prompt:
            ttk.Label(self, text=prompt, wraplength=480,
                      foreground=MUTED_FG).grid(row=0, column=0, sticky=EW, padx=16, pady=(14, 6))

        self._text = ScrolledText(self, autohide=True, height=10)
        self._text.grid(row=1, column=0, sticky=NSEW, padx=16, pady=(0, 8))
        if initial_text:
            self._text.insert(END, initial_text)

        btn_row = ttk.Frame(self)
        btn_row.grid(row=2, column=0, sticky=EW, padx=16, pady=(0, 14))
        ttk.Button(btn_row, text="취소", command=self.destroy, bootstyle=SECONDARY).pack(side=RIGHT, padx=(4, 0))
        ttk.Button(btn_row, text="확인", command=self._accept, bootstyle=PRIMARY).pack(side=RIGHT)

        self.wait_window(self)

    def _accept(self):
        self.result = self._text.get("1.0", END)
        self.destroy()


# ─── Lyrics search dialog ──────────────────────────────────────────────────
class LyricsSearchDialog(ttk.Toplevel):
    _DEBOUNCE_MS = 300

    def __init__(self, parent, server_url: str):
        super().__init__(parent)
        self.title("가사 DB 검색")
        self.geometry("560x480")
        self.transient(parent)
        self.grab_set()
        self.result: dict | None = None
        self._server_url = server_url
        self._debounce_id = None
        self._results: list[dict] = []

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        bar = ttk.Frame(self)
        bar.grid(row=0, column=0, sticky=EW, padx=16, pady=(14, 6))
        bar.columnconfigure(0, weight=1)

        self._search_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self._search_var,
                  bootstyle=PRIMARY).grid(row=0, column=0, sticky=EW)
        self._search_var.trace_add("write", self._on_query_changed)

        self._list_frame = ScrolledFrame(self, autohide=True)
        self._list_frame.grid(row=1, column=0, sticky=NSEW, padx=16, pady=(0, 8))

        self._status_label = ttk.Label(self._list_frame, text="검색어를 입력하면 결과가 표시됩니다.",
                                       foreground=MUTED_FG)
        self._status_label.pack(anchor=W, padx=8, pady=8)

        ttk.Button(self, text="닫기", command=self.destroy,
                   bootstyle=SECONDARY).grid(row=2, column=0, sticky=E, padx=16, pady=(0, 14))

        self.after(100, lambda: self.focus_set())
        self.wait_window(self)

    def _on_query_changed(self, *_):
        if self._debounce_id:
            try:
                self.after_cancel(self._debounce_id)
            except Exception:
                pass
        self._debounce_id = self.after(self._DEBOUNCE_MS, self._do_search)

    def _do_search(self):
        query = self._search_var.get().strip()
        if not query:
            self._show_status("검색어를 입력하면 결과가 표시됩니다.")
            return
        self._show_status("검색 중…")
        threading.Thread(target=self._fetch_results, args=(query,), daemon=True).start()

    def _fetch_results(self, query: str):
        try:
            items = search_lyrics_catalog(self._server_url, query, limit=20)
        except (PptServerUnavailable, PptServerEndpointUnavailable):
            self.after(0, lambda: self._show_status("서버에 연결할 수 없습니다."))
            return
        except Exception as e:
            self.after(0, lambda: self._show_status(f"검색 오류: {e}"))
            return
        self.after(0, lambda r=items: self._render_results(r))

    def _show_status(self, msg: str):
        for child in self._list_frame.winfo_children():
            child.destroy()
        ttk.Label(self._list_frame, text=msg, foreground=MUTED_FG).pack(anchor=W, padx=8, pady=8)

    def _render_results(self, items: list[dict]):
        for child in self._list_frame.winfo_children():
            child.destroy()
        if not items:
            self._show_status("검색 결과가 없습니다.")
            return
        for item in items:
            self._build_result_row(item)

    def _build_result_row(self, item: dict):
        title = str(item.get("title") or "")
        sequence = str(item.get("sequence") or "")
        source = str(item.get("source") or "")
        badge = {"bugs": "🌐 Bugs", "manual": "✏️ 직접", "history": "📅 이력"}.get(source, source)

        row = ttk.Frame(self._list_frame, relief=SOLID, borderwidth=1)
        row.pack(fill=X, padx=6, pady=(0, 6))

        ttk.Label(row, text=title, font=("맑은 고딕", 11, "bold")).grid(
            row=0, column=0, sticky=EW, padx=10, pady=(8, 2))
        info = sequence if sequence else "(진행 순서 없음)"
        ttk.Label(row, text=f"{info}  [{badge}]", foreground=MUTED_FG,
                  font=("맑은 고딕", 10)).grid(row=1, column=0, sticky=EW, padx=10, pady=(0, 8))
        ttk.Button(row, text="추가", bootstyle=PRIMARY,
                   command=lambda i=item: self._select(i)).grid(
            row=0, column=1, rowspan=2, sticky=NS, padx=(0, 8), pady=8)
        row.columnconfigure(0, weight=1)

    def _select(self, item: dict):
        self.result = item
        self.destroy()


# ─── Busy dialog ───────────────────────────────────────────────────────────
class BusyDialog(ttk.Toplevel):
    def __init__(self, parent, title: str, message: str, on_cancel=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("360x150")
        self.resizable(False, False)
        self.transient(parent)
        self._on_cancel = on_cancel
        self.protocol("WM_DELETE_WINDOW", self.on_cancel if on_cancel else lambda: None)

        content = ttk.Frame(self)
        content.pack(fill=BOTH, expand=True, padx=14, pady=14)

        self._msg_label = ttk.Label(content, text=message, wraplength=300, justify=CENTER,
                                    font=("맑은 고딕", 12, "bold"))
        self._msg_label.pack(pady=(4, 10))

        self._progress = ttk.Progressbar(content, mode=INDETERMINATE, bootstyle="danger-striped")
        self._progress.pack(fill=X, padx=8, pady=(0, 8))
        self._progress.start(10)

        self.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        x = px + (pw - self.winfo_width()) // 2
        y = py + (ph - self.winfo_height()) // 2
        self.geometry(f"+{max(0,x)}+{max(0,y)}")

    def set_message(self, message: str):
        self._msg_label.configure(text=message)
        self.update_idletasks()

    def on_cancel(self):
        if self._on_cancel:
            self._on_cancel()

    def close(self):
        try:
            self._progress.stop()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass


class OperationCancelled(RuntimeError):
    pass


# ─── Main Application ──────────────────────────────────────────────────────
class LyricsApp(ttk.Window):
    def __init__(self):
        super().__init__(title=APP_WINDOW_TITLE, themename="flatly",
                         size=(1080, 760), minsize=(900, 640))

        if getattr(sys, "frozen", False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self._configure_icon()

        # ── State ───────────────────────────────────────────────────────
        self.sequence_entries: list = []
        self.current_song_title: str | None = None
        self.sequence_placeholder_visible = False
        self.lyrics_placeholder_visible = False
        self.loading_lyrics = False
        self.suppress_song_select = False
        self.lyrics_store: dict = {}
        self.template_files: dict = {}
        self._template_download_running = False
        self._template_refresh_complete = False
        self._recent_log_lines: list = []
        self.weekly_history_items: list = []
        self._loaded_history_lyrics_by_title: dict = {}
        self.repertoire_entries: list = []
        self._busy_dialog: BusyDialog | None = None
        self.song_buttons: list = []
        self.selected_song_index: int | None = None
        self._sequence_parse_after_id = None

        self.brand_font_family = self._resolve_font_family(BRAND_FONT_CANDIDATES)

        self._create_widgets()
        self._apply_styles()

        self.load_local_weekly_history()
        self.render_weekly_history_accordion()
        self.after(500, self.sync_weekly_history_from_server_async)
        self.refresh_template_options()
        self.after(300, self.ensure_templates_async)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _configure_icon(self):
        ico = self.find_asset_file(ICON_ICO_FILE_NAME)
        if ico and sys.platform == "win32":
            try:
                self.iconbitmap(ico)
                return
            except Exception:
                pass
        png = self.find_asset_file(ICON_FILE_NAME)
        if png and Image and ImageTk:
            try:
                self._icon_img = ImageTk.PhotoImage(Image.open(png))
                self.iconphoto(True, self._icon_img)
            except Exception:
                pass

    def _resolve_font_family(self, candidates: tuple) -> str:
        available = set(tkfont.families(self))
        for c in candidates:
            if c in available:
                return c
        return "맑은 고딕"

    def _apply_styles(self):
        s = ttk.Style()
        # Make primary/danger buttons use Brand Rose
        s.configure("Brand.TButton",
                     background=BRAND_ROSE, foreground="white",
                     font=("Segoe UI", 12, "bold"))
        s.map("Brand.TButton",
              background=[("active", "#b82d5a"), ("disabled", "#d68fa6")],
              foreground=[("disabled", "white")])

    # ── Widget creation ────────────────────────────────────────────────
    def _create_widgets(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # ── Top bar
        self._create_top_bar()

        # ── Workspace (PanedWindow)
        self._create_workspace()

        # ── Action bar
        self._create_action_bar()

    def _create_top_bar(self):
        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky=EW, padx=40, pady=(18, 10))
        top.columnconfigure(0, weight=1)

        # Brand (left)
        brand = ttk.Frame(top)
        brand.grid(row=0, column=0, sticky=W)
        self._create_logo_label(brand).pack(anchor=W)
        ttk.Label(brand, text="레파토리와 가사를 정리해 파워포인트로 만듭니다.",
                  foreground=MUTED_FG, font=("Segoe UI", 10)).pack(anchor=W, pady=(6, 0))

        # Right panel (menus + settings)
        right = ttk.Frame(top)
        right.grid(row=0, column=1, sticky=NE)

        self._create_menu_bar(right)
        self._create_settings_area(right)

    def _create_logo_label(self, parent) -> ttk.Label | tk.Label:
        logo_file = self.find_asset_file(LOGO_FILE_NAME)
        if logo_file and Image and ImageTk:
            try:
                img = Image.open(logo_file).convert("RGBA")
                max_w = LOGO_SIZE[0] * LOGO_DISPLAY_SCALE
                max_h = LOGO_SIZE[1] * LOGO_DISPLAY_SCALE
                scale = min(max_w / img.width, max_h / img.height, 1.0)
                dw, dh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
                img = img.resize((dw, dh), Image.LANCZOS)
                self._logo_image = ImageTk.PhotoImage(img)
                lbl = ttk.Label(parent, image=self._logo_image)
                return lbl
            except Exception:
                pass
        return ttk.Label(parent, text=APP_DISPLAY_NAME,
                         font=(self.brand_font_family, 24, "bold"))

    def _create_menu_bar(self, parent):
        bar = ttk.Frame(parent)
        bar.pack(anchor=E, fill=X)

        def menu_btn(title, items):
            mb = ttk.Menubutton(bar, text=f"{title} ▾", bootstyle=OUTLINE)
            mb.pack(side=RIGHT, padx=(4, 0))
            m = tk.Menu(mb, tearoff=0)
            mb.configure(menu=m)
            for label, cmd in items:
                if label == "-":
                    m.add_separator()
                else:
                    m.add_command(label=label, command=cmd)

        menu_btn("도움말", [("앱 정보", self.show_app_about)])
        menu_btn("로그", [
            ("작업 로그 다운로드", self.download_work_log),
            ("로그 첨부 버그 리포트", self.report_bug_with_logs),
        ])
        menu_btn("도구", [
            ("레파토리 입력하기", self.open_repertoire_input_dialog),
            ("레파토리 인식", lambda: self.refresh_song_list(trigger_download=True)),
        ])
        menu_btn("파일", [
            ("작업 로그 다운로드", self.download_work_log),
            ("-", None),
            ("종료", self.on_close),
        ])

    def _create_settings_area(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(anchor=E, fill=X, pady=(8, 0))

        def lbl(f, text, r, c):
            ttk.Label(f, text=text, font=("Segoe UI", 11, "bold")).grid(
                row=r, column=c, sticky=E, padx=(0, 6), pady=3)

        lbl(frame, "설정", 0, 0)
        lbl(frame, "슬라이드별 최대 줄 수", 0, 1)
        self.max_lines_var = tk.StringVar(value=str(DEFAULT_MAX_LINES_PER_SLIDE))
        ttk.Entry(frame, textvariable=self.max_lines_var, width=8,
                  bootstyle=SECONDARY, justify=CENTER).grid(row=0, column=2, padx=(0, 12), pady=3)

        lbl(frame, "줄별 최대 글자 수", 1, 1)
        self.max_chars_var = tk.StringVar(value=str(DEFAULT_MAX_CHARS_PER_LINE))
        ttk.Entry(frame, textvariable=self.max_chars_var, width=8,
                  bootstyle=SECONDARY, justify=CENTER).grid(row=1, column=2, padx=(0, 12), pady=3)

        lbl(frame, "가사 크기", 2, 1)
        self.lyrics_font_size_var = tk.StringVar(value=DEFAULT_LYRICS_FONT_SIZE or "기본")
        ttk.Entry(frame, textvariable=self.lyrics_font_size_var, width=8,
                  bootstyle=SECONDARY, justify=CENTER).grid(row=2, column=2, padx=(0, 12), pady=3)

        lbl(frame, "템플릿", 0, 3)
        self.template_var = tk.StringVar(value="")
        self.template_combo = ttk.Combobox(frame, textvariable=self.template_var,
                                            state="readonly", width=22, bootstyle=SECONDARY)
        self.template_combo.grid(row=0, column=4, padx=(0, 4), pady=3)
        self.template_combo.bind("<<ComboboxSelected>>", lambda e: self.update_template_preview())

        self.template_refresh_btn = ttk.Button(frame, text="↻", width=3,
                                               bootstyle=OUTLINE,
                                               command=lambda: self.ensure_templates_async(force=True))
        self.template_refresh_btn.grid(row=0, column=5, padx=(0, 8), pady=3)

        lbl(frame, "PPT 서버", 1, 3)
        self.server_url_var = tk.StringVar(value=DEFAULT_SERVER_URL)
        ttk.Entry(frame, textvariable=self.server_url_var, width=24,
                  bootstyle=SECONDARY).grid(row=1, column=4, columnspan=2, padx=(0, 8), pady=3)

    def _create_workspace(self):
        workspace = ttk.Frame(self)
        workspace.grid(row=1, column=0, sticky=NSEW, padx=28, pady=(0, 8))
        workspace.columnconfigure(0, weight=4)
        workspace.columnconfigure(1, weight=5)
        workspace.rowconfigure(0, weight=1)

        self._create_sequence_panel(workspace)
        self._create_lyrics_panel(workspace)

    def _create_sequence_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="  레파토리 입력  ", bootstyle=PRIMARY,
                               padding=10)
        frame.grid(row=0, column=0, sticky=NSEW, padx=(0, 8))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)

        # Buttons
        btn_row = ttk.Frame(frame)
        btn_row.grid(row=0, column=0, sticky=EW, pady=(0, 6))
        ttk.Button(btn_row, text="레파토리 입력하기", bootstyle=OUTLINE,
                   command=self.open_repertoire_input_dialog).pack(side=LEFT, padx=(0, 6))
        ttk.Button(btn_row, text="🔍 DB에서 추가", bootstyle=OUTLINE,
                   command=self.open_lyrics_search_dialog).pack(side=LEFT, padx=(0, 6))
        self.repertoire_summary_var = tk.StringVar(value="입력된 레파토리 없음")
        ttk.Label(btn_row, textvariable=self.repertoire_summary_var,
                  foreground=MUTED_FG, font=("맑은 고딕", 10)).pack(side=LEFT, padx=4)

        ttk.Label(frame, text="드래그로 순서 변경 · 더블클릭으로 수정",
                  foreground=MUTED_FG, font=("맑은 고딕", 9)).grid(
            row=1, column=0, sticky=W, pady=(0, 4))

        # Repertoire scroll frame
        self.repertoire_sort_scroll = ScrolledFrame(frame, autohide=True, height=180)
        self.repertoire_sort_scroll.grid(row=3, column=0, sticky=NSEW)
        self.repertoire_sort_scroll.columnconfigure(0, weight=1)
        self._repertoire_row_frames: list = []
        self._repertoire_drag_from_index: int | None = None
        self._repertoire_drag_target_index: int | None = None
        self._repertoire_drag_start_x: int | None = None
        self._repertoire_drag_start_y: int | None = None
        self._repertoire_drag_active = False
        self.refresh_repertoire_sort_list()

    def _create_lyrics_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="  가사 편집  ", bootstyle=PRIMARY, padding=10)
        frame.grid(row=0, column=1, sticky=NSEW, padx=(8, 0))
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(1, weight=1)

        # Header
        hdr = ttk.Frame(frame)
        hdr.grid(row=0, column=0, columnspan=3, sticky=EW, pady=(0, 8))
        self.current_song_var = tk.StringVar(value="곡을 선택하세요")
        ttk.Label(hdr, textvariable=self.current_song_var,
                  foreground=MUTED_FG, font=("맑은 고딕", 11)).pack(side=LEFT, padx=(0, 8))
        ttk.Button(hdr, text="⟳", width=3, bootstyle=OUTLINE,
                   command=self.reload_current_song_lyrics_from_history).pack(side=LEFT)

        # Song list (left)
        list_frame = ttk.Frame(frame, width=175)
        list_frame.grid(row=1, column=0, sticky=NS, padx=(0, 8))
        list_frame.grid_propagate(False)
        list_frame.rowconfigure(0, weight=1)

        self.song_listbox = tk.Listbox(list_frame, selectmode=SINGLE, activestyle="none",
                                       width=18, relief=FLAT, highlightthickness=0,
                                       selectbackground="#FADCE5", selectforeground="#3d4756",
                                       font=("맑은 고딕", 11))
        scroll_y = ttk.Scrollbar(list_frame, orient=VERTICAL, command=self.song_listbox.yview)
        self.song_listbox.configure(yscrollcommand=scroll_y.set)
        self.song_listbox.grid(row=0, column=0, sticky=NSEW)
        scroll_y.grid(row=0, column=1, sticky=NS)
        list_frame.columnconfigure(0, weight=1)
        self.song_listbox.bind("<<ListboxSelect>>", self._on_song_listbox_select)
        self.song_buttons = []

        # Lyrics text area (right)
        self.lyrics_text = ScrolledText(frame, autohide=True, wrap=WORD,
                                        font=("맑은 고딕", 12), height=10)
        self.lyrics_text.grid(row=1, column=1, sticky=NSEW)
        self.lyrics_text.bind("<FocusIn>", self.on_lyrics_focus_in)
        self.lyrics_text.bind("<FocusOut>", self.on_lyrics_focus_out)
        self.lyrics_text.bind("<<Modified>>", self.on_lyrics_modified)
        self.lyrics_text.configure(undo=True)
        self.show_lyrics_guide()

    def _create_action_bar(self):
        bar = ttk.Frame(self, relief=RIDGE, borderwidth=1)
        bar.grid(row=2, column=0, sticky=EW, padx=28, pady=(0, 8))

        self.refresh_btn = ttk.Button(bar, text="레파토리 인식", bootstyle=OUTLINE,
                                      command=lambda: self.refresh_song_list(trigger_download=True))
        self.refresh_btn.pack(side=LEFT, padx=(10, 6), pady=10)

        self.generate_btn = ttk.Button(bar, text="파워포인트 생성", style="Brand.TButton",
                                       command=self.generate_ppt)
        self.generate_btn.pack(side=RIGHT, padx=(6, 10), pady=10)

        self.songlist_btn = ttk.Button(bar, text="송리스트 카드 생성", bootstyle=OUTLINE,
                                       command=self.generate_songlist_card)
        self.songlist_btn.pack(side=RIGHT, padx=6, pady=10)

    # ── Lyrics guide (placeholder) ─────────────────────────────────────
    def show_lyrics_guide(self):
        self.loading_lyrics = True
        self.lyrics_text.configure(state=NORMAL)
        self.lyrics_text.delete("1.0", END)
        self.lyrics_text.insert("1.0", LYRICS_GUIDE_TEXT)
        self.lyrics_text.configure(foreground="#9aa3af")
        self.lyrics_placeholder_visible = True
        self.lyrics_text.edit_modified(False)
        self.loading_lyrics = False

    def clear_lyrics_guide(self):
        if not self.lyrics_placeholder_visible:
            return
        self.loading_lyrics = True
        self.lyrics_text.configure(state=NORMAL)
        self.lyrics_text.delete("1.0", END)
        self.lyrics_text.configure(foreground=TEXT_FG)
        self.lyrics_placeholder_visible = False
        self.lyrics_text.edit_modified(False)
        self.loading_lyrics = False

    def set_lyrics_editor_text(self, text: str):
        self.loading_lyrics = True
        self.lyrics_text.configure(state=NORMAL, foreground=TEXT_FG)
        self.lyrics_text.delete("1.0", END)
        self.lyrics_text.insert("1.0", text)
        self.lyrics_placeholder_visible = False
        self.lyrics_text.edit_modified(False)
        self.loading_lyrics = False

    def get_lyrics_editor_text(self) -> str:
        if self.lyrics_placeholder_visible:
            return ""
        return self.lyrics_text.get("1.0", END).strip()

    def on_lyrics_focus_in(self, event=None):
        self.clear_lyrics_guide()

    def on_lyrics_focus_out(self, event=None):
        if not self.get_lyrics_editor_text():
            self.show_lyrics_guide()

    def on_lyrics_modified(self, event=None):
        if self.loading_lyrics:
            self.lyrics_text.edit_modified(False)
            return
        if self.lyrics_text.edit_modified():
            if self.current_song_title and not self.lyrics_placeholder_visible:
                self.lyrics_store[self.current_song_title] = self.get_lyrics_editor_text()
            self.lyrics_text.edit_modified(False)

    # ── Song list ──────────────────────────────────────────────────────
    def _on_song_listbox_select(self, event=None):
        if self.suppress_song_select:
            return
        sel = self.song_listbox.curselection()
        if not sel:
            return
        index = sel[0]
        if index >= len(self.song_buttons):
            return
        song_title = self.song_buttons[index][0]
        if song_title == self.current_song_title:
            return
        if self.current_song_title and not self.lyrics_placeholder_visible:
            lyrics = self.get_lyrics_editor_text()
            self.lyrics_store[self.current_song_title] = lyrics
            self._save_lyrics_to_catalog_async(self.current_song_title, lyrics)
        self.selected_song_index = index
        self.load_lyrics_for_song(song_title)

    def _set_song_selection(self, index: int | None):
        self.selected_song_index = index
        self.suppress_song_select = True
        self.song_listbox.selection_clear(0, END)
        if index is not None:
            self.song_listbox.selection_set(index)
            self.song_listbox.see(index)
        self.suppress_song_select = False

    def populate_song_list(self, sequence_entries: list, preserve_current: bool = True):
        previous_song = self.current_song_title if preserve_current else None
        selected_index = None

        self.suppress_song_select = True
        self.song_listbox.delete(0, END)
        self.song_buttons = []
        self.selected_song_index = None

        for index, (song_title, _) in enumerate(sequence_entries):
            self.song_listbox.insert(END, song_title)
            self.song_buttons.append((song_title, None))
            if previous_song == song_title and selected_index is None:
                selected_index = index

        if selected_index is None and sequence_entries:
            selected_index = 0

        if selected_index is not None:
            self._set_song_selection(selected_index)

        self.suppress_song_select = False
        return selected_index

    # ── Repertoire sort list ───────────────────────────────────────────
    def refresh_repertoire_sort_list(self):
        if not hasattr(self, "repertoire_sort_scroll"):
            return
        for child in self.repertoire_sort_scroll.winfo_children():
            child.destroy()
        self._repertoire_row_frames = []

        if not self.repertoire_entries:
            ttk.Label(self.repertoire_sort_scroll, text="인식된 레파토리가 없습니다.",
                      foreground=MUTED_FG, font=("맑은 고딕", 10)).grid(
                row=0, column=0, sticky=W, padx=8, pady=6)
            self._update_repertoire_summary()
            return

        for index, (title, sequence) in enumerate(self.repertoire_entries):
            row = ttk.Frame(self.repertoire_sort_scroll, relief=SOLID, borderwidth=1)
            row.grid(row=index, column=0, sticky=EW, padx=6, pady=(0, 6))
            row.columnconfigure(1, weight=1)

            ttk.Label(row, text=f"{index + 1}", foreground=MUTED_FG,
                      font=("Segoe UI", 10, "bold"), width=3).grid(
                row=0, column=0, rowspan=2, sticky=NS, padx=(8, 4), pady=8)

            ttk.Label(row, text=title, font=("맑은 고딕", 10, "bold")).grid(
                row=0, column=1, sticky=EW, padx=(0, 4), pady=(8, 2))
            ttk.Label(row, text=sequence, foreground=MUTED_FG,
                      font=("맑은 고딕", 9), wraplength=300).grid(
                row=1, column=1, sticky=EW, padx=(0, 4), pady=(0, 8))

            ttk.Button(row, text="✎", width=3, bootstyle=OUTLINE,
                       command=lambda i=index: self.edit_repertoire_item(i)).grid(
                row=0, column=2, rowspan=2, sticky=NS, padx=(0, 6), pady=8)

            for widget in (row, *row.winfo_children()):
                widget.bind("<ButtonPress-1>", lambda e, i=index: self._on_rep_press(i, e))
                widget.bind("<B1-Motion>", lambda e, i=index: self._on_rep_motion(i, e))
                widget.bind("<ButtonRelease-1>", lambda e, i=index: self._on_rep_release(i, e))
                widget.bind("<Double-Button-1>", lambda e, i=index: self.edit_repertoire_item(i))

            self._repertoire_row_frames.append(row)

        self.repertoire_sort_scroll.columnconfigure(0, weight=1)
        self._update_repertoire_summary()

    def _update_repertoire_summary(self):
        count = len(self.repertoire_entries)
        if not hasattr(self, "repertoire_summary_var"):
            return
        if count <= 0:
            self.repertoire_summary_var.set("입력된 레파토리 없음")
        else:
            self.repertoire_summary_var.set(f"총 {count}곡")

    def sync_sequence_text_from_repertoire(self):
        self._update_repertoire_summary()

    def _on_rep_press(self, index, event=None):
        self._repertoire_drag_from_index = index
        self._repertoire_drag_target_index = index
        self._repertoire_drag_start_x = event.x_root if event else None
        self._repertoire_drag_start_y = event.y_root if event else None
        self._repertoire_drag_active = False

    def _on_rep_motion(self, _index, event=None):
        if self._repertoire_drag_from_index is None or event is None:
            return
        if not self._repertoire_drag_active:
            if self._repertoire_drag_start_x is None:
                return
            if max(abs(event.x_root - self._repertoire_drag_start_x),
                   abs(event.y_root - self._repertoire_drag_start_y)) < 6:
                return
            self._repertoire_drag_active = True

        target = self._target_index_by_y(event.y_root)
        self._repertoire_drag_target_index = target
        self._update_drag_visuals()

    def _on_rep_release(self, _index, event=None):
        if self._repertoire_drag_from_index is None or not self._repertoire_drag_active:
            self._repertoire_drag_from_index = None
            self._repertoire_drag_target_index = None
            self._repertoire_drag_active = False
            return

        source = self._repertoire_drag_from_index
        target = self._target_index_by_y(event.y_root) if event else source
        self._repertoire_drag_from_index = None
        self._repertoire_drag_target_index = None
        self._repertoire_drag_active = False

        if (source != target and
                0 <= source < len(self.repertoire_entries) and
                0 <= target < len(self.repertoire_entries)):
            moved = self.repertoire_entries.pop(source)
            self.repertoire_entries.insert(target, moved)
            self.refresh_repertoire_sort_list()
            self.sync_sequence_text_from_repertoire()

    def _target_index_by_y(self, y_root: int) -> int:
        for i, frame in enumerate(self._repertoire_row_frames):
            mid = frame.winfo_rooty() + frame.winfo_height() // 2
            if y_root < mid:
                return i
        return max(0, len(self._repertoire_row_frames) - 1)

    def _update_drag_visuals(self):
        src = self._repertoire_drag_from_index
        tgt = self._repertoire_drag_target_index
        for i, frame in enumerate(self._repertoire_row_frames):
            try:
                if i == src:
                    frame.configure(relief=SOLID)
                elif i == tgt:
                    frame.configure(relief=RIDGE)
                else:
                    frame.configure(relief=SOLID)
            except Exception:
                pass

    # ── Asset helpers ──────────────────────────────────────────────────
    def find_asset_file(self, file_name: str) -> str | None:
        base_dirs = [self.base_dir]
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            base_dirs.append(bundle_dir)
        for base in base_dirs:
            for rel in [os.path.join(ASSETS_DIR_NAME, file_name), file_name]:
                p = os.path.join(base, rel)
                if os.path.exists(p):
                    return p
        return None

    def get_output_dir(self) -> str:
        d = os.path.join(self.base_dir, "out")
        os.makedirs(d, exist_ok=True)
        return d

    def get_history_cache_file(self) -> str:
        return os.path.join(self.get_output_dir(), WEEKLY_HISTORY_CACHE_FILE_NAME)

    def get_history_db_file(self) -> str:
        return os.path.join(self.get_output_dir(), WEEKLY_HISTORY_DB_FILE_NAME)

    def get_template_download_dir(self) -> str:
        d = os.path.join(self.base_dir, ASSETS_DIR_NAME, TEMPLATE_DIR_NAME)
        os.makedirs(d, exist_ok=True)
        return d

    def get_template_search_dirs(self) -> list:
        dirs = [self.get_template_download_dir()]
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            dirs.append(os.path.join(bundle_dir, ASSETS_DIR_NAME, TEMPLATE_DIR_NAME))
        result, seen = [], set()
        for d in dirs:
            d = os.path.abspath(d)
            if d in seen or not os.path.isdir(d):
                continue
            seen.add(d)
            result.append(d)
        return result

    def list_template_files(self) -> list:
        templates, seen_names = [], set()
        for template_dir in self.get_template_search_dirs():
            for root, _, files in os.walk(template_dir):
                for file_name in sorted(files, key=str.casefold):
                    if not file_name.lower().endswith(".pptx"):
                        continue
                    if file_name.casefold() == os.path.basename(SONGLIST_TEMPLATE_FILE_NAME).casefold():
                        continue
                    path = os.path.join(root, file_name)
                    display = os.path.relpath(path, template_dir).replace(os.sep, " / ")
                    if display in seen_names:
                        continue
                    seen_names.add(display)
                    templates.append((display, path))
        return sorted(templates, key=lambda x: x[0].casefold(), reverse=True)

    def refresh_template_options(self):
        templates = self.list_template_files()
        self.template_files = {dn: path for dn, path in templates}
        values = list(self.template_files)
        if not values:
            self.template_combo.configure(values=["템플릿 없음"], state=DISABLED)
            self.template_var.set("템플릿 없음")
        else:
            self.template_combo.configure(values=values, state="readonly")
            current = self.template_var.get()
            if current not in self.template_files:
                self.template_var.set(values[0])

    def update_template_preview(self, *_):
        pass  # simplified: no preview in ttkbootstrap version

    def get_selected_template_file(self) -> str | None:
        sel = self.template_files.get(self.template_var.get())
        if sel and os.path.exists(sel):
            return sel
        templates = self.list_template_files()
        return templates[0][1] if templates else None

    def set_template_loading_state(self, loading: bool, status_text: str = ""):
        self._template_download_running = loading
        self._template_refresh_complete = status_text == "✓"
        if hasattr(self, "template_refresh_btn"):
            state = DISABLED if loading else NORMAL
            self.template_refresh_btn.configure(state=state)
            if not loading and status_text:
                self.template_refresh_btn.configure(text=status_text)
            elif not loading:
                self.template_refresh_btn.configure(text="↻")

    def animate_template_loading(self, index=0):
        if not self._template_download_running:
            return
        frames = ("◐", "◓", "◑", "◒")
        self.template_refresh_btn.configure(text=frames[index % len(frames)])
        self.after(160, lambda: self.animate_template_loading(index + 1))

    def ensure_templates_async(self, force: bool = False):
        if self._template_download_running:
            return
        self.set_template_loading_state(True)
        self.animate_template_loading()

        def run():
            status = "✓"
            try:
                target_dir = self.get_template_download_dir()
                before = {p for _, p in self.list_template_files()
                          if os.path.abspath(p).startswith(os.path.abspath(target_dir))}
                self.after(0, lambda: self.log("[안내] 템플릿 저장소를 확인합니다."))
                try:
                    import gdown
                except ImportError:
                    status = "!"
                    self.after(0, lambda: self.log("[오류] gdown 패키지가 없습니다."))
                    return
                try:
                    gdown.download_folder(TEMPLATE_DOWNLOAD_URL, output=target_dir,
                                          quiet=True, use_cookies=False, resume=True, remaining_ok=True)
                except TypeError:
                    gdown.download_folder(TEMPLATE_DOWNLOAD_URL, output=target_dir,
                                          quiet=True, use_cookies=False, resume=True)
                after = {p for _, p in self.list_template_files()
                         if os.path.abspath(p).startswith(os.path.abspath(target_dir))}
                added = sorted(os.path.basename(p) for p in after - before)

                def on_done():
                    self.refresh_template_options()
                    if added:
                        self.log(f"[완료] 새 템플릿 {len(added)}개 다운로드: {', '.join(added)}")
                    elif force:
                        self.log("[안내] 템플릿 목록을 최신 상태로 갱신했습니다.")
                    else:
                        self.log("[안내] 템플릿 목록을 확인했습니다.")
                self.after(0, on_done)
            except Exception as e:
                status = "!"
                err = e
                self.report_exception("template download", err)
                self.after(0, lambda: self.log(f"[오류] 템플릿 다운로드 실패: {err}"))
            finally:
                self.after(0, lambda s=status: self.set_template_loading_state(False, s))

        threading.Thread(target=run, daemon=True).start()

    # ── Settings accessors ─────────────────────────────────────────────
    def get_server_url(self) -> str:
        return self.server_url_var.get().strip() or DEFAULT_SERVER_URL

    def get_max_lines_per_slide(self) -> int:
        try:
            return int(self.max_lines_var.get())
        except (TypeError, ValueError):
            return DEFAULT_MAX_LINES_PER_SLIDE

    def get_max_chars_per_line(self) -> int:
        try:
            return int(self.max_chars_var.get())
        except (TypeError, ValueError):
            return DEFAULT_MAX_CHARS_PER_LINE

    def get_lyrics_font_size(self) -> float | None:
        value = self.lyrics_font_size_var.get().strip()
        if not value or value == "기본":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    # ── Busy dialog ────────────────────────────────────────────────────
    def show_busy_dialog(self, title: str, message: str, on_cancel=None):
        self.hide_busy_dialog()
        self._busy_dialog = BusyDialog(self, title, message, on_cancel=on_cancel)
        self._busy_dialog.lift()

    def update_busy_dialog(self, message: str):
        if self._busy_dialog:
            self._busy_dialog.set_message(message)

    def hide_busy_dialog(self):
        if self._busy_dialog is None:
            return
        try:
            self._busy_dialog.close()
        except Exception:
            pass
        self._busy_dialog = None

    # ── Action state ───────────────────────────────────────────────────
    def set_action_buttons_state(self, state: str):
        self.refresh_btn.configure(state=state)
        self.generate_btn.configure(state=state)
        self.songlist_btn.configure(state=state)

    def set_editor_state(self, state: str):
        self.lyrics_text.configure(state=state)
        self.song_listbox.configure(state=state)

    # ── Logging ────────────────────────────────────────────────────────
    def log(self, message: str):
        self._recent_log_lines.append(str(message))
        self._recent_log_lines = self._recent_log_lines[-50:]

    # ── Error reporting ────────────────────────────────────────────────
    def report_exception(self, context: str, exc, tb=None, extra=None):
        try:
            server_url = self.get_server_url() if hasattr(self, "server_url_var") else DEFAULT_SERVER_URL
            report_error_async(
                server_url,
                context=context,
                message=str(exc),
                traceback_text=format_exception(exc, tb),
                extra={},
                log_tail=self._recent_log_lines,
            )
        except Exception:
            pass

    # ── Repertoire helpers ─────────────────────────────────────────────
    def _clean_repertoire_title(self, value: str) -> str:
        text = str(value or "").strip()
        text = re.sub(r"^\s*\d+\s*[\.)]\s*", "", text)
        return text.strip()

    def _normalize_repertoire_entries(self, raw_text: str) -> list:
        lines = [l.strip() for l in str(raw_text or "").splitlines() if l.strip()]
        entries = []
        idx = 0
        while idx + 1 < len(lines):
            title = self._clean_repertoire_title(lines[idx])
            sequence = lines[idx + 1].strip()
            if title and sequence:
                entries.append((title, sequence))
            idx += 2
        return entries

    def _format_repertoire_entries(self, entries: list) -> str:
        rows = []
        for title, sequence in entries:
            rows.append(str(title).strip())
            rows.append(str(sequence).strip())
        return "\n".join(rows).strip()

    def _sequence_text_from_entries(self, sequence_entries: list) -> str:
        chunks = []
        for entry in sequence_entries:
            if not isinstance(entry, dict):
                continue
            title = str(entry.get("title", "")).strip()
            sequence = str(entry.get("sequence", "")).strip()
            if title and sequence:
                chunks.append(f"{title}\n{sequence}")
        return "\n\n".join(chunks).strip()

    def _history_option_label(self, item: dict) -> str:
        week_start = str(item.get("week_start_date", "?"))
        week_end = str(item.get("week_end_date", "?"))
        seq = item.get("sequence_entries") if isinstance(item, dict) else []
        count = len(seq) if isinstance(seq, list) else 0
        return f"{week_start} ~ {week_end} ({count}곡)"

    # ── Repertoire dialogs ─────────────────────────────────────────────
    def open_repertoire_input_dialog(self):
        initial = self._format_repertoire_entries(self.repertoire_entries)
        dialog = MultilineDialog(
            self, "레파토리 입력",
            "한 곡당 2줄(제목/진행순서)로 입력하세요.\n예)\n한나의 노래\nI-V1-V2-C",
            initial_text=initial,
        )
        raw = (dialog.result or "").strip()
        if not raw:
            return
        entries = self._normalize_repertoire_entries(raw)
        if not entries:
            messagebox.showwarning("레파토리 입력", "입력 형식을 확인해 주세요. (제목/진행순서 2줄 구성)")
            return
        self.repertoire_entries = entries
        self.sequence_placeholder_visible = False
        self.refresh_repertoire_sort_list()
        self.refresh_song_list(show_message=False)

    def open_lyrics_search_dialog(self):
        server_url = self.get_server_url()
        dialog = LyricsSearchDialog(self, server_url)
        item = dialog.result
        if not item:
            return

        title = str(item.get("title") or "").strip()
        sequence = str(item.get("sequence") or "").strip()
        lyrics = str(item.get("lyrics") or "").strip()
        if not title:
            return

        if not sequence:
            dialog2 = MultilineDialog(
                self, "진행 순서 입력",
                f"'{title}'의 진행 순서를 입력하세요.\n예) I-V1-V2-C-C",
            )
            sequence = ((dialog2.result or "").strip().splitlines()[0].strip()
                        if dialog2.result else "")

        if not sequence:
            messagebox.showwarning("DB에서 추가", "진행 순서가 없어 추가하지 않았습니다.")
            return

        for idx, (t, _) in enumerate(self.repertoire_entries):
            if t == title:
                self.repertoire_entries[idx] = (title, sequence)
                if lyrics:
                    self.lyrics_store[title] = lyrics
                self.refresh_repertoire_sort_list()
                self.sync_sequence_text_from_repertoire()
                self.refresh_song_list(show_message=False)
                self.log(f"[DB] '{title}' 레파토리를 업데이트했습니다.")
                return

        self.repertoire_entries.append((title, sequence))
        if lyrics:
            self.lyrics_store[title] = lyrics
        self.sequence_placeholder_visible = False
        self.refresh_repertoire_sort_list()
        self.sync_sequence_text_from_repertoire()
        self.refresh_song_list(show_message=False)
        self.log(f"[DB] '{title}' 을(를) 레파토리에 추가했습니다.")

    def edit_repertoire_item(self, index: int):
        if index < 0 or index >= len(self.repertoire_entries):
            return
        title, sequence = self.repertoire_entries[index]
        dialog = MultilineDialog(
            self, "레파토리 수정",
            "첫 줄: 곡 제목\n둘째 줄: 진행 순서",
            initial_text=f"{title}\n{sequence}",
        )
        edited = (dialog.result or "").strip()
        if not edited:
            return
        lines = [l.strip() for l in edited.splitlines() if l.strip()]
        if len(lines) < 2:
            messagebox.showwarning("레파토리 수정", "두 줄(곡 제목/진행 순서)로 입력해 주세요.")
            return
        new_title = self._clean_repertoire_title(lines[0])
        new_seq = lines[1]
        if not new_title or not new_seq:
            messagebox.showwarning("레파토리 수정", "곡 제목과 진행 순서를 모두 입력해 주세요.")
            return
        self.repertoire_entries[index] = (new_title, new_seq)
        self.refresh_repertoire_sort_list()
        self.sync_sequence_text_from_repertoire()

    # ── Weekly history ─────────────────────────────────────────────────
    def load_local_weekly_history(self):
        cache_file = self.get_history_cache_file()
        if not os.path.exists(cache_file):
            self.weekly_history_items = []
            return
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.weekly_history_items = data if isinstance(data, list) else []
        except Exception as e:
            self.weekly_history_items = []
            self.report_exception("weekly history load", e)

    def save_local_weekly_history(self, items: list):
        cache_file = self.get_history_cache_file()
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

    def render_weekly_history_accordion(self):
        pass  # not displayed in this simplified UI

    def sync_weekly_history_from_server(self, log_result: bool = False):
        server_url = self.get_server_url()
        items = fetch_weekly_history_via_server(server_url, year_from=2026)
        self.save_local_weekly_history(items)
        self.weekly_history_items = items
        db_file = self.get_history_db_file()
        download_history_db_via_server(server_url, db_file)
        if log_result:
            self.log(f"[완료] 주간 작업 이력 {len(items)}개를 서버에서 동기화했습니다.")

    def sync_weekly_history_from_server_async(self):
        def run():
            error = None
            try:
                self.sync_weekly_history_from_server(log_result=False)
            except Exception as e:
                error = e
            def on_done():
                if error:
                    self.report_exception("weekly history auto sync", error)
            self.after(0, on_done)
        threading.Thread(target=run, daemon=True).start()

    def apply_weekly_history_item(self, item: dict):
        sequence_entries = item.get("sequence_entries") if isinstance(item, dict) else None
        lyrics_by_title = item.get("lyrics_by_title") if isinstance(item, dict) else None
        if not isinstance(sequence_entries, list) or not isinstance(lyrics_by_title, dict):
            messagebox.showerror("DB 이력 불러오기", "선택한 주간 작업 이력 형식이 올바르지 않습니다.")
            return
        sequence_text = self._sequence_text_from_entries(sequence_entries)
        if not sequence_text:
            messagebox.showwarning("DB 이력 불러오기", "선택한 주간 작업 이력에 레파토리가 없습니다.")
            return
        self.repertoire_entries = self._normalize_repertoire_entries(sequence_text)
        self.refresh_repertoire_sort_list()
        self.lyrics_store = {str(k): str(v) for k, v in lyrics_by_title.items()}
        self._loaded_history_lyrics_by_title = dict(self.lyrics_store)
        self.refresh_song_list(show_message=False, trigger_download=False)
        self.log(f"[완료] 주간 작업 이력을 불러왔습니다: {item.get('week_start_date','?')} ~ {item.get('week_end_date','?')}")

    def reset_loaded_history(self):
        self.repertoire_entries = []
        self.refresh_repertoire_sort_list()
        self.lyrics_store = {}
        self._loaded_history_lyrics_by_title = {}
        self.current_song_title = None
        self.current_song_var.set("곡을 선택하세요")
        self.populate_song_list([], preserve_current=False)
        self.show_lyrics_guide()
        self.log("[안내] 불러온 작업 내용을 초기화했습니다.")

    def reload_current_song_lyrics_from_history(self):
        if not self.current_song_title:
            messagebox.showinfo("가사 불러오기", "먼저 곡을 선택하세요.")
            return
        lyrics = self._loaded_history_lyrics_by_title.get(self.current_song_title, "")
        if not str(lyrics).strip():
            messagebox.showinfo("가사 불러오기", f"'{self.current_song_title}'에 저장된 이력이 없습니다.")
            return
        self.lyrics_store[self.current_song_title] = str(lyrics)
        self.set_lyrics_editor_text(str(lyrics))
        self.log(f"[완료] '{self.current_song_title}' 가사를 다시 불러왔습니다.")

    # ── Song list refresh ──────────────────────────────────────────────
    def get_sequence_entries(self) -> list:
        if self.repertoire_entries:
            return [(title, seq) for title, seq in self.repertoire_entries]
        if self.sequence_placeholder_visible:
            raise ValueError("레파토리 입력창이 비어 있습니다.")
        raise ValueError("레파토리 입력창이 비어 있습니다.")

    def refresh_song_list(self, show_message: bool = True,
                           trigger_download: bool = False) -> bool:
        try:
            sequence_entries = self.get_sequence_entries()
        except ValueError as e:
            self.log(f"[오류] {e}")
            messagebox.showerror("레파토리 입력 오류", str(e))
            return False

        self.sequence_entries = sequence_entries
        selected_index = self.populate_song_list(sequence_entries)

        if selected_index is not None:
            song_title = sequence_entries[selected_index][0]
            if song_title != self.current_song_title:
                self.load_lyrics_for_song(song_title)
        else:
            self.current_song_title = None
            self.current_song_var.set("곡을 선택하세요")
            self.show_lyrics_guide()

        if show_message:
            self.log(f"[안내] 레파토리 {len(sequence_entries)}곡을 인식했습니다.")

        if trigger_download:
            self.after(100, lambda: self._run_download(auto=True))

        return True

    def load_lyrics_for_song(self, song_title: str):
        self.current_song_title = song_title
        self.current_song_var.set(song_title)
        lyrics = self.lyrics_store.get(song_title, "")
        if lyrics.strip():
            self.set_lyrics_editor_text(lyrics)
        else:
            self.show_lyrics_guide()

    # ── Lyrics download ────────────────────────────────────────────────
    def _run_download(self, auto: bool = False):
        try:
            from auto_lyrics_downloader import download_missing_lyrics
        except Exception as e:
            self.report_exception("lyrics downloader import", e)
            self.log(f"[오류] 가사 다운로드 모듈 불러오기 실패: {e}")
            if not auto:
                messagebox.showerror("오류", f"가사 다운로드 모듈을 불러오지 못했습니다:\n{e}")
            return

        song_titles = [t for t, _ in self.sequence_entries]
        current_song = self.current_song_title
        server_url = self.get_server_url()
        sequence_map = {t: s for t, s in self.sequence_entries}

        self.set_action_buttons_state(DISABLED)
        self.set_editor_state(DISABLED)
        self.log("====================================")
        self.log("가사 다운로드를 시작합니다.")

        def run():
            try:
                downloaded = download_missing_lyrics(
                    song_titles=song_titles,
                    existing_lyrics=self.lyrics_store,
                    log_func=lambda msg: self.after(0, lambda m=msg: self.log(m)),
                    server_url=server_url,
                    sequence_map=sequence_map,
                )
                def on_done():
                    self.lyrics_store.update(downloaded)
                    self.set_editor_state(NORMAL)
                    if current_song:
                        self.load_lyrics_for_song(current_song)
                    if not auto:
                        messagebox.showinfo("완료", "가사 다운로드 작업이 완료되었습니다.")
                    self.set_action_buttons_state(NORMAL)
                self.after(0, on_done)
            except Exception as e:
                err = e
                def on_error():
                    self.report_exception("lyrics download", err)
                    self.log(f"[오류] 가사 다운로드 실패: {err}")
                    if not auto:
                        messagebox.showerror("오류", f"가사 다운로드에 실패했습니다:\n{err}")
                    self.set_editor_state(NORMAL)
                    self.set_action_buttons_state(NORMAL)
                self.after(0, on_error)

        threading.Thread(target=run, daemon=True).start()

    def _save_lyrics_to_catalog_async(self, song_title: str, lyrics: str):
        if not song_title or not lyrics.strip():
            return
        server_url = self.get_server_url()
        seq_map = {t: s for t, s in self.sequence_entries}
        sequence = seq_map.get(song_title, "")

        def run():
            try:
                from ppt_server_client import save_lyrics_to_catalog
                save_lyrics_to_catalog(server_url, song_title, lyrics, source="manual", sequence=sequence)
            except Exception:
                pass

        threading.Thread(target=run, daemon=True).start()

    # ── Songlist card ──────────────────────────────────────────────────
    def generate_songlist_card(self):
        if not self.refresh_song_list(show_message=False):
            return

        song_titles = [t for t, _ in self.sequence_entries]
        template_file = self.find_asset_file(SONGLIST_TEMPLATE_FILE_NAME)
        if not template_file:
            messagebox.showerror("오류", f"템플릿 파일을 찾을 수 없습니다:\nassets/{SONGLIST_TEMPLATE_FILE_NAME}")
            return

        output_file = os.path.join(self.get_output_dir(), SONGLIST_OUTPUT_FILE_NAME)
        output_dir = os.path.dirname(os.path.abspath(output_file))
        fd, temp_output_file = tempfile.mkstemp(prefix=".songlist_", suffix=".png", dir=output_dir)
        os.close(fd)
        try:
            os.remove(temp_output_file)
        except OSError:
            pass

        cancel_event = threading.Event()

        def raise_if_cancelled():
            if cancel_event.is_set():
                raise OperationCancelled()

        def request_cancel():
            if not cancel_event.is_set():
                cancel_event.set()
                self.log("[취소] 송리스트 카드 생성 취소 요청")
                self.update_busy_dialog("취소 요청을 처리하고 있습니다.")

        self.set_action_buttons_state(DISABLED)
        self.set_editor_state(DISABLED)
        self.log("====================================")
        self.log("송리스트 카드를 생성합니다.")
        self.show_busy_dialog("송리스트 생성 중", "송리스트 카드를 생성하고 있습니다.", on_cancel=request_cancel)

        def run():
            try:
                source = "서버"
                server_url = self.get_server_url()
                raise_if_cancelled()
                self.after(0, lambda: self.update_busy_dialog("서버에 송리스트 생성을 요청하고 있습니다."))
                try:
                    week_num = generate_songlist_card_via_server(
                        server_url, template_file, song_titles, temp_output_file)
                    raise_if_cancelled()
                except PptServerUnavailable as e:
                    raise_if_cancelled()
                    source = "로컬"
                    self.after(0, lambda: self.update_busy_dialog("로컬에서 변환하고 있습니다."))
                    week_num = build_songlist_card(template_file, song_titles, temp_output_file)
                    raise_if_cancelled()
                except PptServerResponseError as e:
                    raise_if_cancelled()
                    if e.status_code and e.status_code >= 500:
                        self.report_exception("songlist server processing fallback", e)
                        source = "로컬"
                        self.after(0, lambda: self.update_busy_dialog("로컬에서 변환하고 있습니다."))
                        week_num = build_songlist_card(template_file, song_titles, temp_output_file)
                        raise_if_cancelled()
                    else:
                        raise

                os.replace(temp_output_file, output_file)

                def on_done():
                    if cancel_event.is_set():
                        return
                    self.hide_busy_dialog()
                    self.log(f"[완료] 송리스트 카드 생성: '{output_file}' [{source}]")
                    opened = self.open_output_file(output_file)
                    open_msg = "\n생성된 파일을 엽니다." if opened else ""
                    messagebox.showinfo("완료", f"송리스트 카드를 생성했습니다.\n저장: out/{SONGLIST_OUTPUT_FILE_NAME}" + open_msg)
                    self.set_editor_state(NORMAL)
                    self.set_action_buttons_state(NORMAL)
                self.after(0, on_done)

            except OperationCancelled:
                def on_cancelled():
                    self.hide_busy_dialog()
                    self.log("[취소] 송리스트 카드 생성 중단")
                    self.set_editor_state(NORMAL)
                    self.set_action_buttons_state(NORMAL)
                self.after(0, on_cancelled)

            except Exception as e:
                err = e
                def on_error():
                    if cancel_event.is_set():
                        return
                    self.report_exception("songlist", err)
                    self.hide_busy_dialog()
                    self.log(f"[오류][송리스트]: {err}")
                    messagebox.showerror("오류", f"송리스트 카드 생성에 실패했습니다:\n{err}")
                    self.set_editor_state(NORMAL)
                    self.set_action_buttons_state(NORMAL)
                self.after(0, on_error)

            finally:
                try:
                    if os.path.exists(temp_output_file):
                        os.remove(temp_output_file)
                except OSError:
                    pass

        threading.Thread(target=run, daemon=True).start()

    # ── PPT generation ─────────────────────────────────────────────────
    def generate_ppt(self):
        self.log("====================================")
        self.log("파워포인트 생성을 시작합니다.")

        if not self.refresh_song_list(show_message=False):
            return

        sequence_entries = self.sequence_entries
        max_lines_per_slide = self.get_max_lines_per_slide()
        max_chars_per_line = self.get_max_chars_per_line()
        lyrics_font_size = self.get_lyrics_font_size()
        template_file = self.get_selected_template_file()

        if not template_file:
            messagebox.showerror("오류", f"템플릿 파일을 찾을 수 없습니다.")
            return

        lyrics_by_title = dict(self.lyrics_store)
        ready_count = 0
        for song_title, sequence_str in sequence_entries:
            raw_lyrics = lyrics_by_title.get(song_title, "")
            if not raw_lyrics.strip():
                self.log(f"[안내] '{song_title}' 가사가 없어 직접 입력 창을 엽니다.")
                dialog = MultilineDialog(self, "가사 직접 입력", f"'{song_title}' 가사를 입력하세요.")
                raw_lyrics = dialog.result or ""
                if raw_lyrics:
                    self.lyrics_store[song_title] = raw_lyrics
                    lyrics_by_title[song_title] = raw_lyrics
            else:
                self.log(f"[진행] '{song_title}' 처리 중")
            if raw_lyrics.strip():
                ready_count += 1
            else:
                self.log(f"[안내] '{song_title}' 가사가 없어 건너뜁니다.")

        if ready_count == 0:
            messagebox.showwarning("파워포인트 생성", "생성할 가사가 없습니다.")
            return

        output_file = os.path.join(self.get_output_dir(), OUTPUT_FILE_NAME)
        server_url = self.get_server_url()

        self.set_action_buttons_state(DISABLED)
        self.set_editor_state(DISABLED)
        self.show_busy_dialog("파워포인트 생성 중", "파워포인트 파일을 생성하고 있습니다.")

        def run():
            try:
                source = "서버"
                self.after(0, lambda: self.log(f"[정보][PPT][서버요청] 서버={server_url}"))
                self.after(0, lambda: self.update_busy_dialog("서버에 파워포인트 생성을 요청하고 있습니다."))
                try:
                    generated_count = generate_pptx_via_server(
                        server_url, template_file, sequence_entries, lyrics_by_title,
                        max_lines_per_slide, output_file,
                        max_chars_per_line=max_chars_per_line, lyrics_font_size=lyrics_font_size,
                    )
                    if generated_count is None:
                        generated_count = ready_count
                except PptServerUnavailable as e:
                    source = "로컬"
                    self.after(0, lambda: self.update_busy_dialog("로컬에서 생성하고 있습니다."))
                    result = build_integrated_pptx_with_local_office(
                        template_file, sequence_entries, lyrics_by_title, output_file,
                        max_lines_per_slide, max_chars_per_line=max_chars_per_line,
                        lyrics_font_size=lyrics_font_size,
                    )
                    generated_count = result["appended_count"]
                    source = f"로컬 {result.get('method', 'Office')}"
                except PptServerResponseError as e:
                    if e.status_code and e.status_code >= 500:
                        self.report_exception("ppt server processing fallback", e)
                        source = "로컬"
                        self.after(0, lambda: self.update_busy_dialog("로컬에서 생성하고 있습니다."))
                        result = build_integrated_pptx_with_local_office(
                            template_file, sequence_entries, lyrics_by_title, output_file,
                            max_lines_per_slide, max_chars_per_line=max_chars_per_line,
                            lyrics_font_size=lyrics_font_size,
                        )
                        generated_count = result["appended_count"]
                        source = f"로컬 {result.get('method', 'Office')}"
                    else:
                        raise

                def on_done():
                    self.hide_busy_dialog()
                    self.log(f"\n[완료] 파워포인트 파일: '{output_file}' [{source}, {generated_count}곡]\n")
                    opened = self.open_output_file(output_file)
                    open_msg = "\n생성된 파일을 엽니다." if opened else ""
                    messagebox.showinfo("완료", "파워포인트 파일을 생성했습니다.\n저장: out/integrated_lyrics.pptx" + open_msg)
                    self.set_editor_state(NORMAL)
                    self.set_action_buttons_state(NORMAL)
                self.after(0, on_done)

            except Exception as e:
                err = e
                def on_error():
                    self.report_exception("ppt", err)
                    self.hide_busy_dialog()
                    self.log(f"[오류][PPT]: {err}")
                    messagebox.showerror("오류", f"파워포인트 파일을 생성하지 못했습니다:\n{err}")
                    self.set_editor_state(NORMAL)
                    self.set_action_buttons_state(NORMAL)
                self.after(0, on_error)

        threading.Thread(target=run, daemon=True).start()

    # ── File output ────────────────────────────────────────────────────
    def open_output_file(self, file_path: str) -> bool:
        try:
            if sys.platform == "win32":
                os.startfile(os.path.abspath(file_path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", file_path])
            else:
                subprocess.Popen(["xdg-open", file_path])
            return True
        except Exception as e:
            self.report_exception("open output file", e)
            return False

    # ── Work log & bug report ──────────────────────────────────────────
    def build_work_log_text(self) -> str:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"[{now}] PPT Gen 작업 로그",
            f"서버 URL: {self.get_server_url()}",
            f"현재 선택 곡: {self.current_song_title or '-'}",
            "",
            "[최근 로그]",
        ]
        lines.extend(self._recent_log_lines)
        return "\n".join(lines).strip() + "\n"

    def download_work_log(self, show_message: bool = True) -> str | None:
        default_name = f"work-log-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        try:
            initial_dir = self.get_output_dir()
        except Exception:
            initial_dir = os.getcwd()
        save_path = filedialog.asksaveasfilename(
            title="작업 로그 저장",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialdir=initial_dir,
            initialfile=default_name,
        )
        if not save_path:
            return None
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(self.build_work_log_text())
        self.log(f"[완료] 작업 로그를 저장했습니다: {save_path}")
        if show_message:
            messagebox.showinfo("작업 로그", f"작업 로그를 저장했습니다.\n{save_path}")
        return save_path

    def report_bug_with_logs(self):
        log_path = self.download_work_log(show_message=False)
        if not log_path:
            return
        dialog = MultilineDialog(
            self, "서버 버그 리포트",
            "증상과 재현 방법을 입력하세요.\n(저장한 작업 로그가 함께 첨부됩니다)",
        )
        message = (dialog.result or "").strip()
        if not message:
            messagebox.showwarning("서버 버그 리포트", "버그 설명을 입력해 주세요.")
            return
        report = build_error_report(
            context="manual bug report", message=message,
            traceback_text="", extra={"log_file": os.path.abspath(log_path)},
            log_tail=self._recent_log_lines,
        )
        server_url = self.get_server_url()
        self.show_busy_dialog("버그 리포트 전송", "서버로 버그 리포트를 전송하고 있습니다.")

        def run():
            error = None
            try:
                send_error_report(server_url, report)
            except Exception as e:
                error = e
            def on_done():
                self.hide_busy_dialog()
                if error:
                    messagebox.showerror("버그 리포트", f"전송에 실패했습니다.\n{error}")
                    return
                self.log("[완료] 서버에 버그 리포트를 전송했습니다.")
                messagebox.showinfo("버그 리포트", "버그 리포트를 전송했습니다.")
            self.after(0, on_done)
        threading.Thread(target=run, daemon=True).start()

    def show_app_about(self):
        messagebox.showinfo("앱 정보", "PPT Gen\n레파토리와 가사를 정리해 파워포인트를 생성합니다.")

    # ── Window close ───────────────────────────────────────────────────
    def on_close(self):
        try:
            self.sync_weekly_history_from_server(log_result=False)
        except Exception as e:
            self.report_exception("weekly history sync on close", e)
        self.destroy()


# ─── Entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = LyricsApp()
    app.mainloop()
