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
    list_recent_lyrics_catalog,
    lookup_lyrics_by_title,
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

# ── App color palette ─────────────────────────────────────────────────────
BG_APP      = "#D9E8FF"   # background — L=92.5%, clearly sky-blue
MAIN_CLR    = "#AAD5FA"   # primary (sky blue)
ACCENT_TEAL = "#89D5D9"   # teal (hover / secondary)
ACCENT_MINT = "#84D3B6"   # mint (pressed / positive)
ACCENT_LBUE = "#D9E2FF"   # lavender-blue (selection, row highlight)
ACCENT_LAVD = "#E2DAFF"   # soft lavender (secondary selection)
FG_APP      = "#0F1729"   # main text (near-black blue)
FG_MUTED    = "#5A6880"   # muted text

# Override constants imports with palette-matched values
MUTED_FG    = FG_MUTED
TEXT_FG     = FG_APP

# Brand button aliases
BRAND_COLOR = MAIN_CLR
BRAND_PRESS = ACCENT_MINT
BRAND_HOVER = ACCENT_TEAL
BRAND_ROSE  = BRAND_COLOR  # legacy alias

# ── Module-level dialog helpers ────────────────────────────────────────────
_APP_ICO: str | None = None   # set by LyricsApp._configure_icon


def _set_dialog_icon(win: tk.Toplevel) -> None:
    if _APP_ICO and sys.platform == "win32":
        try:
            win.iconbitmap(_APP_ICO)
        except Exception:
            pass


class _DialogBase(ttk.Toplevel):
    """All modal popups inherit this: hidden until centered, app icon set."""
    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.configure(background=BG_APP)
        self.withdraw()
        self.transient(parent)
        _set_dialog_icon(self)

    def _show(self):
        self.update_idletasks()
        pw = self.master.winfo_width()
        ph = self.master.winfo_height()
        px = self.master.winfo_rootx()
        py = self.master.winfo_rooty()
        w  = self.winfo_width()
        h  = self.winfo_height()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")
        self.deiconify()


# ─── Multiline dialog ──────────────────────────────────────────────────────
class MultilineDialog(_DialogBase):
    def __init__(self, parent, title: str, prompt: str, initial_text: str = ""):
        super().__init__(parent)
        self.title(title)
        self.geometry("520x400")
        self.grab_set()
        self.result: str | None = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        if prompt:
            tk.Label(self, text=prompt, wraplength=480,
                     fg=MUTED_FG).grid(row=0, column=0, sticky=EW, padx=16, pady=(14, 6))

        tf = tk.Frame(self)
        tf.grid(row=1, column=0, sticky=NSEW, padx=16, pady=(0, 8))
        tf.columnconfigure(0, weight=1)
        tf.rowconfigure(0, weight=1)
        self._text = tk.Text(tf, height=10, wrap=WORD, font=("맑은 고딕", 11),
                             bg=BG_APP, insertbackground=MAIN_CLR,
                             relief=FLAT, highlightthickness=1,
                             highlightbackground=ACCENT_LBUE, highlightcolor=MAIN_CLR)
        _ts = ttk.Scrollbar(tf, orient=VERTICAL, command=self._text.yview,
                            style="Slim.Vertical.TScrollbar")
        self._text.configure(yscrollcommand=_ts.set)
        self._text.grid(row=0, column=0, sticky=NSEW)
        _ts.grid(row=0, column=1, sticky=NS)
        if initial_text:
            self._text.insert(END, initial_text)

        btn_row = tk.Frame(self)
        btn_row.grid(row=2, column=0, sticky=EW, padx=16, pady=(0, 14))
        ttk.Button(btn_row, text="취소", command=self.destroy,
                   bootstyle=OUTLINE, padding=(10, 5)).pack(side=RIGHT, padx=(4, 0))
        ttk.Button(btn_row, text="확인", command=self._accept,
                   bootstyle=PRIMARY, padding=(10, 5)).pack(side=RIGHT)

        self.after(0, self._show)
        self.wait_window(self)

    def _accept(self):
        self.result = self._text.get("1.0", END)
        self.destroy()


# ─── Lyrics search dialog ──────────────────────────────────────────────────
class LyricsSearchDialog(_DialogBase):
    _DEBOUNCE_MS = 300

    def __init__(self, parent, server_url: str,
                 preloaded: list[dict] | None = None,
                 on_refreshed=None):
        """
        preloaded  — cached list from app startup; skips network call if provided.
        on_refreshed — callback(list[dict]) called after user presses refresh.
        """
        super().__init__(parent)
        self.title("가사 DB 검색")
        self.geometry("560x500")
        self.grab_set()
        self.result: dict | None = None
        self._server_url = server_url
        self._preloaded = preloaded
        self._on_refreshed = on_refreshed
        self._debounce_id = None
        self._results: list[dict] = []

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # ── Search bar + refresh button
        bar = tk.Frame(self)
        bar.grid(row=0, column=0, sticky=EW, padx=16, pady=(14, 6))
        bar.columnconfigure(0, weight=1)

        self._search_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self._search_var,
                  bootstyle=PRIMARY).grid(row=0, column=0, sticky=EW, padx=(0, 8))
        self._search_var.trace_add("write", self._on_query_changed)

        _ri = getattr(parent, "_get_icon", lambda _: None)("refresh")
        self._refresh_btn = ttk.Button(
            bar, image=_ri, text="" if _ri else "↻",
            width=0 if _ri else 3,
            bootstyle=OUTLINE,
            command=self._force_refresh)
        self._refresh_btn.grid(row=0, column=1)

        # ── Result list
        _lf_outer = tk.Frame(self)
        _lf_outer.grid(row=1, column=0, sticky=NSEW, padx=16, pady=(0, 8))
        _lf_outer.columnconfigure(0, weight=1)
        _lf_outer.rowconfigure(0, weight=1)
        _lf_canvas = tk.Canvas(_lf_outer, highlightthickness=0, bg=BG_APP)
        _lf_vs = ttk.Scrollbar(_lf_outer, orient=VERTICAL, command=_lf_canvas.yview,
                               style="Slim.Vertical.TScrollbar")
        self._list_frame = tk.Frame(_lf_canvas, bg=BG_APP)
        _lf_win = _lf_canvas.create_window((0, 0), window=self._list_frame, anchor=NW)
        self._list_frame.bind("<Configure>", lambda e: (
            _lf_canvas.configure(scrollregion=_lf_canvas.bbox("all")),
            _lf_canvas.itemconfigure(_lf_win, width=_lf_canvas.winfo_width()),
        ))
        _lf_canvas.configure(yscrollcommand=_lf_vs.set)
        _lf_canvas.grid(row=0, column=0, sticky=NSEW)
        _lf_vs.grid(row=0, column=1, sticky=NS)

        self._status_label = tk.Label(self._list_frame, text="불러오는 중…",
                                      bg=BG_APP, fg=MUTED_FG)
        self._status_label.pack(anchor=W, padx=8, pady=8)

        ttk.Button(self, text="닫기", command=self.destroy,
                   bootstyle=SECONDARY, padding=(10, 5)).grid(
            row=2, column=0, sticky=E, padx=16, pady=(0, 14))

        self.after(0, self._show)
        self.after(50, self.focus_set)
        # Use cache immediately if available, otherwise fetch from server
        if self._preloaded is not None:
            self.after(30, lambda: self._render_results(self._preloaded, header="최근 추가순"))
        else:
            self.after(60, self._load_recent)
        self.wait_window(self)

    def _force_refresh(self):
        """User clicked refresh — fetch fresh data and update app cache."""
        self._refresh_btn.configure(state=DISABLED)
        self._show_status("새로고침 중…")
        threading.Thread(target=self._fetch_and_refresh, daemon=True).start()

    def _fetch_and_refresh(self):
        try:
            items = list_recent_lyrics_catalog(self._server_url, limit=50)
        except (PptServerUnavailable, PptServerEndpointUnavailable):
            self.after(0, lambda: self._show_status("서버에 연결할 수 없습니다."))
        except Exception as e:
            self.after(0, lambda: self._show_status(f"오류: {e}"))
        else:
            if self._on_refreshed:
                self.after(0, lambda r=items: self._on_refreshed(r))
            self.after(0, lambda r=items: self._render_results(r, header="최근 추가순"))
        finally:
            self.after(0, lambda: self._refresh_btn.configure(state=NORMAL) if self._alive() else None)

    def _load_recent(self):
        self._show_status("불러오는 중…")
        threading.Thread(target=self._fetch_recent, daemon=True).start()

    def _fetch_recent(self):
        try:
            items = list_recent_lyrics_catalog(self._server_url, limit=50)
        except (PptServerUnavailable, PptServerEndpointUnavailable):
            self.after(0, lambda: self._show_status("서버에 연결할 수 없습니다."))
            return
        except Exception as e:
            self.after(0, lambda: self._show_status(f"목록 조회 오류: {e}"))
            return
        self.after(0, lambda r=items: self._render_results(r, header="최근 추가순"))

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
            self._load_recent()
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

    def _alive(self) -> bool:
        try:
            return self.winfo_exists() and self._list_frame.winfo_exists()
        except Exception:
            return False

    def _show_status(self, msg: str):
        if not self._alive():
            return
        for child in self._list_frame.winfo_children():
            child.destroy()
        ttk.Label(self._list_frame, text=msg, foreground=MUTED_FG).pack(anchor=W, padx=8, pady=8)

    def _render_results(self, items: list[dict], header: str | None = None):
        if not self._alive():
            return
        for child in self._list_frame.winfo_children():
            child.destroy()
        if not items:
            self._show_status("검색 결과가 없습니다.")
            return
        if header:
            ttk.Label(self._list_frame, text=header, foreground=MUTED_FG,
                      font=("Segoe UI", 9)).pack(anchor=W, padx=8, pady=(6, 2))
        for item in items:
            self._build_result_row(item)

    def _build_result_row(self, item: dict):
        title = str(item.get("title") or "")
        sequence = str(item.get("sequence") or "")

        row = ttk.Frame(self._list_frame, relief=SOLID, borderwidth=1)
        row.pack(fill=X, padx=6, pady=(0, 6))

        ttk.Label(row, text=title, font=("맑은 고딕", 11, "bold")).grid(
            row=0, column=0, sticky=EW, padx=10, pady=(8, 2))
        info = sequence if sequence else "(진행 순서 없음)"
        ttk.Label(row, text=info, foreground=MUTED_FG,
                  font=("맑은 고딕", 10)).grid(row=1, column=0, sticky=EW, padx=10, pady=(0, 8))
        ttk.Button(row, text="추가", bootstyle=PRIMARY,
                   command=lambda i=item: self._select(i)).grid(
            row=0, column=1, rowspan=2, sticky=NS, padx=(0, 8), pady=8)
        row.columnconfigure(0, weight=1)

    def _select(self, item: dict):
        self.result = item
        self.destroy()


# ─── PPT settings dialog ───────────────────────────────────────────────────
class PPTSettingsDialog(_DialogBase):
    def __init__(self, parent, max_lines_var: tk.StringVar,
                 max_chars_var: tk.StringVar, font_size_var: tk.StringVar):
        super().__init__(parent)
        self.title("PPT 상세 설정")
        self.resizable(False, False)
        self.grab_set()
        self.confirmed = False

        self._out_max_lines = max_lines_var
        self._out_max_chars = max_chars_var
        self._out_font_size = font_size_var

        self._max_lines = tk.StringVar(value=max_lines_var.get())
        self._max_chars = tk.StringVar(value=max_chars_var.get())
        self._font_size = tk.StringVar(value=font_size_var.get())

        content = tk.Frame(self)
        content.pack(fill=BOTH, expand=True, padx=24, pady=20)
        content.columnconfigure(1, weight=1)

        def row(r, label, var):
            tk.Label(content, text=label, font=("Segoe UI", 11)).grid(
                row=r, column=0, sticky=E, padx=(0, 12), pady=6)
            ttk.Entry(content, textvariable=var, width=10,
                      bootstyle=SECONDARY, justify=CENTER).grid(
                row=r, column=1, sticky=W, pady=6)

        row(0, "슬라이드별 최대 줄 수", self._max_lines)
        row(1, "줄별 최대 글자 수", self._max_chars)
        row(2, "가사 크기 (기본: 비워두기)", self._font_size)

        btn_row = tk.Frame(self)
        btn_row.pack(fill=X, padx=24, pady=(0, 16))
        ttk.Button(btn_row, text="취소", bootstyle=OUTLINE, padding=(10, 5),
                   command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        ttk.Button(btn_row, text="확인", bootstyle=PRIMARY, padding=(10, 5),
                   command=self._accept).pack(side=RIGHT)

        self.after(0, self._show)
        self.wait_window(self)

    def _accept(self):
        self._out_max_lines.set(self._max_lines.get())
        self._out_max_chars.set(self._max_chars.get())
        self._out_font_size.set(self._font_size.get())
        self.confirmed = True
        self.destroy()


# ─── Server settings dialog ────────────────────────────────────────────────
class ServerSettingsDialog(_DialogBase):
    def __init__(self, parent, server_url_var: tk.StringVar):
        super().__init__(parent)
        self.title("서버 설정")
        self.resizable(False, False)
        self.grab_set()

        self._out = server_url_var
        self._var = tk.StringVar(value=server_url_var.get())

        content = tk.Frame(self)
        content.pack(fill=BOTH, expand=True, padx=24, pady=20)
        content.columnconfigure(1, weight=1)

        tk.Label(content, text="PPT 서버 URL", font=("Segoe UI", 11)).grid(
            row=0, column=0, sticky=E, padx=(0, 12), pady=6)
        ttk.Entry(content, textvariable=self._var, width=30,
                  bootstyle=SECONDARY).grid(row=0, column=1, sticky=EW, pady=6)

        btn_row = tk.Frame(self)
        btn_row.pack(fill=X, padx=24, pady=(0, 16))
        ttk.Button(btn_row, text="취소", bootstyle=OUTLINE, padding=(10, 5),
                   command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        ttk.Button(btn_row, text="확인", bootstyle=PRIMARY, padding=(10, 5),
                   command=self._accept).pack(side=RIGHT)

        self.after(0, self._show)
        self.wait_window(self)

    def _accept(self):
        self._out.set(self._var.get().strip())
        self.destroy()


# ─── Busy dialog ───────────────────────────────────────────────────────────
class BusyDialog(_DialogBase):
    def __init__(self, parent, title: str, message: str, on_cancel=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("360x150")
        self.resizable(False, False)
        self.grab_set()
        self._on_cancel = on_cancel
        self.protocol("WM_DELETE_WINDOW", self.on_cancel if on_cancel else lambda: None)

        content = tk.Frame(self)
        content.pack(fill=BOTH, expand=True, padx=14, pady=14)

        self._msg_label = tk.Label(content, text=message, wraplength=300, justify=CENTER,
                                   font=("맑은 고딕", 12, "bold"))
        self._msg_label.pack(pady=(4, 10))

        self._progress = ttk.Progressbar(content, mode=INDETERMINATE, bootstyle="info-striped")
        self._progress.pack(fill=X, padx=8, pady=(0, 8))
        self._progress.start(10)

        self._show()

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
        self._undo_stack: list = []   # list of (repertoire_entries snapshot, lyrics_store snapshot)
        self._redo_stack: list = []
        self._busy_dialog: BusyDialog | None = None
        self.song_buttons: list = []
        self.selected_song_index: int | None = None
        self._sequence_parse_after_id = None

        self.brand_font_family = self._resolve_font_family(BRAND_FONT_CANDIDATES)

        self._apply_styles()
        self._load_icons()
        self._create_widgets()
        self.configure(background=BG_APP)

        self.load_local_weekly_history()
        self.render_weekly_history_accordion()
        self.after(500, self.sync_weekly_history_from_server_async)
        self.refresh_template_options()
        self.after(300, self.ensure_templates_async)
        # Preload DB catalog cache once at startup
        self._db_catalog_cache: list[dict] = []
        self._db_cache_ready = False
        self.after(800, self._preload_db_cache)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind_all("<Control-z>", lambda e: self.undo_repertoire())
        self.bind_all("<Control-y>", lambda e: self.redo_repertoire())

    def _configure_icon(self):
        global _APP_ICO
        ico = self.find_asset_file(ICON_ICO_FILE_NAME)
        if ico and sys.platform == "win32":
            try:
                self.iconbitmap(ico)
                _APP_ICO = ico
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

    def _load_icons(self):
        from PIL import Image, ImageTk
        icon_dir = os.path.join(self.base_dir, "assets", "icons")
        self._icons: dict = {}
        for name in ("edit", "trash", "refresh", "download", "plus", "search"):
            path = os.path.join(icon_dir, f"{name}.png")
            if os.path.exists(path):
                img = Image.open(path).convert("RGBA").resize((16, 16), Image.LANCZOS)
                self._icons[name] = ImageTk.PhotoImage(img)

    def _get_icon(self, name: str):
        return self._icons.get(name)

    def _apply_styles(self):
        # ── Tk option database — native tk widgets inherit these without explicit bg=
        self.option_add("*Background",       BG_APP)
        self.option_add("*Foreground",       FG_APP)
        self.option_add("*activeBackground", ACCENT_LBUE)
        self.option_add("*activeForeground", FG_APP)
        self.option_add("*selectBackground", ACCENT_LBUE)
        self.option_add("*selectForeground", FG_APP)

        s = ttk.Style()

        # ── Global TTK background
        s.configure(".", background=BG_APP, foreground=FG_APP, font=("Segoe UI", 10))
        for w in ("TFrame", "TLabel", "TLabelframe", "TLabelframe.Label",
                  "TMenubutton", "TCheckbutton", "TRadiobutton"):
            try:
                s.configure(w, background=BG_APP, foreground=FG_APP)
            except Exception:
                pass

        # ── Unified widget height — all interactive widgets in same row share padding
        _BTN_PAD = (10, 5)   # standard button padding  (used everywhere)
        _BTN_PAD_PRI = (14, 7)  # primary action buttons (action bar)
        # Store as instance attrs so widget-creation methods can reference them
        self._btn_pad     = _BTN_PAD
        self._btn_pad_pri = _BTN_PAD_PRI
        # Force Combobox to the same height as a button with _BTN_PAD vertical
        s.configure("TCombobox", padding=(4, 4))

        # ── Brand action button
        s.configure("Brand.TButton",
                    background=MAIN_CLR, foreground=FG_APP,
                    font=("Segoe UI", 12, "bold"), relief=FLAT, borderwidth=0,
                    padding=_BTN_PAD_PRI)
        s.map("Brand.TButton",
              background=[("active", ACCENT_TEAL), ("pressed", ACCENT_MINT),
                          ("disabled", "#cce7fa")],
              foreground=[("disabled", FG_MUTED)])

        # ── Pressed flash style
        s.configure("BrandPress.TButton",
                    background=ACCENT_MINT, foreground=FG_APP,
                    font=("Segoe UI", 12, "bold"), relief=FLAT, borderwidth=0,
                    padding=_BTN_PAD_PRI)
        s.map("BrandPress.TButton",
              background=[("active", ACCENT_MINT)])

        # ── Ghost scrollbar — fully invisible idle, teal thumb on hover
        for orient in ("Vertical", "Horizontal"):
            name = f"Slim.{orient}.TScrollbar"
            s.configure(name, width=6, arrowsize=0, relief=FLAT,
                        borderwidth=0, bordercolor=BG_APP,
                        lightcolor=BG_APP, darkcolor=BG_APP,
                        troughcolor=BG_APP, background=BG_APP,
                        groovewidth=0)
            s.map(name,
                  background=[("active", ACCENT_TEAL), ("pressed", ACCENT_MINT)],
                  troughcolor=[("active", BG_APP)])

    def _finalize_outline_styles(self):
        """Re-apply BG_APP to Outline.TButton after ttkbootstrap widget-init overrides."""
        s = ttk.Style()
        for pfx in ("", "primary.", "secondary.", "info.",
                    "success.", "warning.", "danger.", "light.", "dark."):
            for sfx in ("Outline.TButton", "Outline.Toolbutton", "Outline.TMenubutton"):
                name = f"{pfx}{sfx}"
                try:
                    s.configure(name, background=BG_APP)
                    s.map(name, background=[
                        ("active",   ACCENT_LBUE),
                        ("pressed",  ACCENT_MINT),
                        ("disabled", BG_APP),
                    ])
                except Exception:
                    pass
        # Also fix plain TMenubutton (non-outline)
        try:
            s.configure("TMenubutton", background=BG_APP)
            s.map("TMenubutton", background=[("active", ACCENT_LBUE), ("pressed", ACCENT_MINT)])
        except Exception:
            pass

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

        # ttkbootstrap creates Outline.TButton styles at widget instantiation,
        # overriding _apply_styles(). Re-apply BG_APP after all widgets exist.
        self._finalize_outline_styles()

    def _create_top_bar(self):
        top = tk.Frame(self)
        top.grid(row=0, column=0, sticky=EW, padx=20, pady=(12, 6))
        top.columnconfigure(0, weight=1)

        brand = tk.Frame(top)
        brand.grid(row=0, column=0, sticky=W)
        self._create_logo_label(brand).pack(anchor=W)
        tk.Label(brand, text="레파토리와 가사를 정리해 파워포인트로 만듭니다.",
                 fg=MUTED_FG, font=("Segoe UI", 10)).pack(anchor=W, pady=(6, 0))

        right = tk.Frame(top)
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
        bar = tk.Frame(parent)
        bar.pack(anchor=E, fill=X)

        def menu_btn(title, items):
            mb = ttk.Menubutton(bar, text=title, bootstyle=OUTLINE, padding=(10, 5))
            mb.pack(side=RIGHT, padx=(4, 0))
            m = tk.Menu(mb, tearoff=0, bg=BG_APP, fg=FG_APP,
                        activebackground=ACCENT_LBUE, activeforeground=FG_APP,
                        relief=FLAT, borderwidth=1)
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
            ("레파토리 입력", self.open_repertoire_input_dialog),
            ("전체 가사 가져오기", lambda: self.refresh_song_list(trigger_download=True)),
            ("-", None),
            ("PPT 상세 설정", self.open_ppt_settings),
            ("서버 설정", self.open_server_settings),
            ("-", None),
            ("작업 뒤로가기  Ctrl+Z", self.undo_repertoire),
            ("작업 앞으로가기  Ctrl+Y", self.redo_repertoire),
        ])
        menu_btn("파일", [
            ("작업 로그 다운로드", self.download_work_log),
            ("-", None),
            ("종료", self.on_close),
        ])

    def _create_settings_area(self, parent):
        # StringVars initialized here so they're accessible throughout the app
        self.max_lines_var = tk.StringVar(value=str(DEFAULT_MAX_LINES_PER_SLIDE))
        self.max_chars_var = tk.StringVar(value=str(DEFAULT_MAX_CHARS_PER_LINE))
        self.lyrics_font_size_var = tk.StringVar(value=DEFAULT_LYRICS_FONT_SIZE or "기본")

        frame = tk.Frame(parent)
        frame.pack(anchor=E, fill=X, pady=(8, 0))
        frame.columnconfigure(0, weight=1)

        def lbl(f, text, r, c):
            tk.Label(f, text=text, font=("Segoe UI", 11, "bold")).grid(
                row=r, column=c, sticky=E, padx=(0, 6), pady=3)

        lbl(frame, "템플릿", 0, 3)
        self.template_var = tk.StringVar(value="")
        self.template_combo = ttk.Combobox(frame, textvariable=self.template_var,
                                            state="readonly", width=20, bootstyle=SECONDARY)
        self.template_combo.grid(row=0, column=4, padx=(0, 4), pady=2)
        self.template_combo.bind("<<ComboboxSelected>>", lambda e: self.update_template_preview())

        _ri = self._get_icon("refresh")
        self.template_refresh_btn = ttk.Button(
            frame, image=_ri, text="" if _ri else "↻", width=0 if _ri else 3,
            bootstyle=OUTLINE, padding=(6, 5),
            command=lambda: self.ensure_templates_async(force=True))
        self.template_refresh_btn.grid(row=0, column=5, padx=(0, 4), pady=2)

        self.server_url_var = tk.StringVar(value=DEFAULT_SERVER_URL)

    def _create_workspace(self):
        workspace = tk.Frame(self)
        workspace.grid(row=1, column=0, sticky=NSEW, padx=20, pady=(0, 6))
        workspace.columnconfigure(0, weight=4, minsize=280)
        workspace.columnconfigure(1, weight=5, minsize=360)
        workspace.rowconfigure(0, weight=1, minsize=300)

        self._create_sequence_panel(workspace)
        self._create_lyrics_panel(workspace)

    def _create_sequence_panel(self, parent):
        frame = tk.LabelFrame(parent, text="  레파토리 입력  ", padx=8, pady=8,
                              font=("Segoe UI", 11, "bold"),
                              bg=BG_APP, fg=FG_APP)
        frame.grid(row=0, column=0, sticky=NSEW, padx=(0, 6))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=0)   # button bar
        frame.rowconfigure(1, weight=0)   # hint text
        frame.rowconfigure(2, weight=1, minsize=150)  # scroll area
        frame.rowconfigure(3, weight=0)   # reset button

        # Row 0: buttons
        btn_row = tk.Frame(frame)
        btn_row.grid(row=0, column=0, sticky=EW, pady=(0, 2))
        _BTN = {"bootstyle": OUTLINE, "padding": (10, 5)}
        ttk.Button(btn_row, text="레파토리 입력", command=self.open_repertoire_input_dialog,
                   **_BTN).pack(side=LEFT, padx=(0, 6))
        _si = self._get_icon("search")
        ttk.Button(btn_row, image=_si, text="DB 검색", compound=LEFT if _si else "none",
                   command=self.open_lyrics_search_dialog, **_BTN).pack(side=LEFT, padx=(0, 6))
        self.repertoire_summary_var = tk.StringVar(value="")

        # Row 1: hint text (moved above scroll area)
        tk.Label(frame, text="드래그로 순서 변경 · 더블클릭으로 수정",
                 fg=MUTED_FG, font=("맑은 고딕", 9)).grid(
            row=1, column=0, sticky=W, pady=(2, 2))

        # Row 2: scroll area
        _rep_outer = tk.Frame(frame)
        _rep_outer.grid(row=2, column=0, sticky=NSEW)
        _rep_outer.columnconfigure(0, weight=1)
        _rep_outer.rowconfigure(0, weight=1)
        self._rep_canvas = tk.Canvas(_rep_outer, highlightthickness=0, bg=BG_APP)
        _rep_vs = ttk.Scrollbar(_rep_outer, orient=VERTICAL, command=self._rep_canvas.yview,
                                style="Slim.Vertical.TScrollbar")
        self.repertoire_sort_scroll = tk.Frame(self._rep_canvas, bg=BG_APP)
        _rep_win = self._rep_canvas.create_window((0, 0), window=self.repertoire_sort_scroll, anchor=NW)
        def _sync_rep_width(w):
            if w > 1:
                self._rep_canvas.itemconfigure(_rep_win, width=w)
        def _on_rep_inner_cfg(e):
            self._rep_canvas.configure(scrollregion=self._rep_canvas.bbox("all"))
            _sync_rep_width(self._rep_canvas.winfo_width())
        def _on_rep_canvas_cfg(e):
            _sync_rep_width(e.width)
            self._rep_canvas.configure(scrollregion=self._rep_canvas.bbox("all"))
        self.repertoire_sort_scroll.bind("<Configure>", _on_rep_inner_cfg)
        self._rep_canvas.bind("<Configure>", _on_rep_canvas_cfg)
        self._rep_canvas.configure(yscrollcommand=_rep_vs.set)
        self._rep_canvas.grid(row=0, column=0, sticky=NSEW)
        _rep_vs.grid(row=0, column=1, sticky=NS)
        self.repertoire_sort_scroll.columnconfigure(0, weight=1)
        self._drop_line = self._rep_canvas.create_line(
            0, 0, 9999, 0, fill=ACCENT_TEAL, width=3, state="hidden"
        )
        self._repertoire_row_frames: list = []
        self._repertoire_drag_from_index: int | None = None
        self._repertoire_drag_target_index: int | None = None
        self._repertoire_drag_start_x: int | None = None
        self._repertoire_drag_start_y: int | None = None
        self._repertoire_drag_active = False
        self._drag_ghost: tk.Toplevel | None = None
        self.refresh_repertoire_sort_list()

        # Row 3: reset button only (no competing text, so never clipped)
        bottom_bar = tk.Frame(frame)
        bottom_bar.grid(row=3, column=0, sticky=EW, pady=(2, 0))
        ttk.Button(bottom_bar, text="⟳ 리셋", bootstyle=OUTLINE,
                   padding=(10, 5),
                   command=self.reset_all_repertoire).pack(side=RIGHT)

    def _create_lyrics_panel(self, parent):
        frame = tk.LabelFrame(parent, text="  가사 편집  ", padx=8, pady=8,
                              font=("Segoe UI", 11, "bold"),
                              bg=BG_APP, fg=FG_APP)
        frame.grid(row=0, column=1, sticky=NSEW, padx=(6, 0))
        frame.columnconfigure(0, minsize=150)
        frame.columnconfigure(1, weight=1, minsize=180)
        frame.rowconfigure(1, weight=1, minsize=150)

        # Header
        hdr = tk.Frame(frame)
        hdr.grid(row=0, column=0, columnspan=3, sticky=EW, pady=(0, 8))
        hdr.columnconfigure(0, weight=1)
        self.current_song_var = tk.StringVar(value="곡을 선택하세요")
        tk.Label(hdr, textvariable=self.current_song_var,
                 fg=MUTED_FG, font=("맑은 고딕", 10),
                 anchor=W).grid(row=0, column=0, sticky=EW)
        _dl_icon = self._get_icon("download")
        ttk.Button(hdr, image=_dl_icon, text="" if _dl_icon else "📥",
                   width=0 if _dl_icon else 3, bootstyle=OUTLINE, padding=(6, 5),
                   command=self.reload_current_song_lyrics_from_history).grid(
            row=0, column=1, padx=(6, 0))

        # Song list (left)
        list_frame = tk.Frame(frame, width=160)
        list_frame.grid(row=1, column=0, sticky=NSEW, padx=(0, 6))
        list_frame.grid_propagate(False)
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.song_listbox = tk.Listbox(list_frame, selectmode=SINGLE, activestyle="none",
                                       width=18, relief=FLAT, highlightthickness=0,
                                       bg=BG_APP, fg=FG_APP,
                                       selectbackground=ACCENT_LBUE, selectforeground=FG_APP,
                                       font=("맑은 고딕", 11))
        scroll_y = ttk.Scrollbar(list_frame, orient=VERTICAL, command=self.song_listbox.yview,
                                 style="Slim.Vertical.TScrollbar")
        self.song_listbox.configure(yscrollcommand=scroll_y.set)
        self.song_listbox.grid(row=0, column=0, sticky=NSEW)
        scroll_y.grid(row=0, column=1, sticky=NS)
        list_frame.columnconfigure(0, weight=1)
        self.song_listbox.bind("<<ListboxSelect>>", self._on_song_listbox_select)
        self.song_buttons = []

        # Lyrics text area (right) — plain tk.Text + scrollbar
        lt_outer = tk.Frame(frame)
        lt_outer.grid(row=1, column=1, sticky=NSEW)
        lt_outer.columnconfigure(0, weight=1)
        lt_outer.rowconfigure(0, weight=1)
        self.lyrics_text = tk.Text(lt_outer, wrap=WORD, undo=True,
                                   font=("맑은 고딕", 12),
                                   bg=BG_APP, fg=FG_APP,
                                   insertbackground=MAIN_CLR,
                                   relief=FLAT, highlightthickness=1,
                                   highlightbackground=ACCENT_LBUE,
                                   highlightcolor=MAIN_CLR)
        _lt_vs = ttk.Scrollbar(lt_outer, orient=VERTICAL, command=self.lyrics_text.yview,
                               style="Slim.Vertical.TScrollbar")
        self.lyrics_text.configure(yscrollcommand=_lt_vs.set)
        self.lyrics_text.grid(row=0, column=0, sticky=NSEW)
        _lt_vs.grid(row=0, column=1, sticky=NS)
        self.lyrics_text.bind("<FocusIn>", self.on_lyrics_focus_in)
        self.lyrics_text.bind("<FocusOut>", self.on_lyrics_focus_out)
        self.lyrics_text.bind("<<Modified>>", self.on_lyrics_modified)
        self.show_lyrics_guide()

    def _create_action_bar(self):
        bar = tk.Frame(self, bg=BG_APP)
        bar.grid(row=2, column=0, sticky=EW, padx=20, pady=(0, 10))

        _STD = {"padding": (14, 7)}
        self.refresh_btn = ttk.Button(bar, text="전체 가사 가져오기", bootstyle=OUTLINE,
                                      command=lambda: self.refresh_song_list(trigger_download=True),
                                      **_STD)
        self.refresh_btn.pack(side=LEFT, padx=(0, 6), pady=8)

        self.generate_btn = ttk.Button(bar, text="파워포인트 생성", style="Brand.TButton",
                                       command=self._on_generate_click, **_STD)
        self.generate_btn.pack(side=RIGHT, padx=(6, 0), pady=8)

        self.songlist_btn = ttk.Button(bar, text="송리스트 카드 생성", bootstyle=OUTLINE,
                                       command=self.generate_songlist_card, **_STD)
        self.songlist_btn.pack(side=RIGHT, padx=6, pady=8)

    def _on_generate_click(self):
        self.generate_btn.configure(style="BrandPress.TButton")
        self.after(160, lambda: self.generate_btn.configure(style="Brand.TButton"))
        self.after(30, self.generate_ppt)

    # ── Lyrics guide (placeholder) ─────────────────────────────────────
    def show_lyrics_guide(self):
        self.loading_lyrics = True
        self.lyrics_text.configure(state=NORMAL)
        self.lyrics_text.delete("1.0", END)
        self.lyrics_text.insert("1.0", LYRICS_GUIDE_TEXT)
        self.lyrics_text.configure(foreground=FG_MUTED)
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

        for index, (title, sequence) in enumerate(self.repertoire_entries):
            row = tk.Frame(self.repertoire_sort_scroll,
                           bg=BG_APP, highlightbackground=ACCENT_LBUE, highlightthickness=1)
            row.grid(row=index, column=0, sticky=EW, padx=6, pady=(0, 5))
            row.columnconfigure(1, weight=1)

            tk.Label(row, text=f"{index + 1}", fg=FG_MUTED,
                     font=("Segoe UI", 10, "bold"), width=3).grid(
                row=0, column=0, rowspan=2, sticky=NS, padx=(8, 4), pady=8)

            tk.Label(row, text=title,
                     font=("맑은 고딕", 10, "bold"), anchor=W).grid(
                row=0, column=1, sticky=EW, padx=(0, 4), pady=(8, 2))
            tk.Label(row, text=sequence, fg=FG_MUTED,
                     font=("맑은 고딕", 9), wraplength=300, anchor=W).grid(
                row=1, column=1, sticky=EW, padx=(0, 4), pady=(0, 8))

            btn_col = tk.Frame(row)
            btn_col.grid(row=0, column=2, rowspan=2, sticky=NS, padx=(0, 6), pady=6)
            _ti = self._get_icon("trash")
            ttk.Button(btn_col, text="✏️", width=2, bootstyle=OUTLINE, padding=(4, 4),
                       command=lambda i=index: self.edit_repertoire_item(i)).pack(
                fill=X, pady=(0, 3))
            ttk.Button(btn_col, image=_ti, text="" if _ti else "✕",
                       width=2 if not _ti else 0,
                       bootstyle="danger-outline", padding=(4, 4),
                       command=lambda i=index: self.delete_repertoire_item(i)).pack(fill=X)

            for widget in (row, *row.winfo_children()):
                widget.bind("<ButtonPress-1>", lambda e, i=index: self._on_rep_press(i, e))
                widget.bind("<B1-Motion>", lambda e, i=index: self._on_rep_motion(i, e))
                widget.bind("<ButtonRelease-1>", lambda e, i=index: self._on_rep_release(i, e))
                widget.bind("<Double-Button-1>", lambda e, i=index: self.edit_repertoire_item(i))

            self._repertoire_row_frames.append(row)

        # "+" add button — small square, always visible (row 0 when empty)
        plus_row = len(self.repertoire_entries)
        plus_btn = tk.Button(
            self.repertoire_sort_scroll, text="+",
            relief=SOLID, bd=1,
            bg=BG_APP, activebackground=ACCENT_LBUE,
            fg=FG_MUTED, activeforeground=FG_APP,
            font=("Segoe UI", 13, "bold"),
            width=2, height=1,
            cursor="hand2",
            highlightbackground=ACCENT_LBUE, highlightthickness=1,
            command=self.open_lyrics_search_dialog,
        )
        plus_btn.grid(row=plus_row, column=0, pady=6)

        self.repertoire_sort_scroll.columnconfigure(0, weight=1)
        self._update_repertoire_summary()

    def delete_repertoire_item(self, index: int):
        if not (0 <= index < len(self.repertoire_entries)):
            return
        self._push_undo()
        title = self.repertoire_entries[index][0]
        self.repertoire_entries.pop(index)
        self.lyrics_store.pop(title, None)
        if self.current_song_title == title:
            self.current_song_title = None
            self._set_song_title_display("곡을 선택하세요")
            self.show_lyrics_guide()
        self.refresh_repertoire_sort_list()
        self.sync_sequence_text_from_repertoire()
        self.populate_song_list(self.repertoire_entries)

    def reset_all_repertoire(self):
        if not self.repertoire_entries:
            return
        if not messagebox.askyesno("전체 리셋", "모든 레파토리와 가사를 삭제합니다.\n계속할까요?"):
            return
        self._push_undo()
        self.repertoire_entries.clear()
        self.lyrics_store.clear()
        self.current_song_title = None
        self._set_song_title_display("곡을 선택하세요")
        self.show_lyrics_guide()
        self.refresh_repertoire_sort_list()
        self.sync_sequence_text_from_repertoire()
        self.populate_song_list([])

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
            self._create_drag_ghost(self._repertoire_drag_from_index, event)

        target = self._target_index_by_y(event.y_root)
        self._repertoire_drag_target_index = target
        self._update_drag_visuals()
        self._move_drag_ghost(event)

    def _on_rep_release(self, _index, event=None):
        self._destroy_drag_ghost()
        if self._repertoire_drag_from_index is None or not self._repertoire_drag_active:
            self._repertoire_drag_from_index = None
            self._repertoire_drag_target_index = None
            self._repertoire_drag_active = False
            return

        source = self._repertoire_drag_from_index
        insert_pos = self._target_index_by_y(event.y_root) if event else source
        self._repertoire_drag_from_index = None
        self._repertoire_drag_target_index = None
        self._repertoire_drag_active = False
        self._update_drag_visuals()

        # No-op: inserting immediately before or after source is the same position
        if insert_pos == source or insert_pos == source + 1:
            return
        if 0 <= source < len(self.repertoire_entries):
            self._push_undo()
            item = self.repertoire_entries.pop(source)
            effective = insert_pos if insert_pos <= source else insert_pos - 1
            self.repertoire_entries.insert(effective, item)
            self.refresh_repertoire_sort_list()
            self.sync_sequence_text_from_repertoire()
            self.populate_song_list(self.repertoire_entries)

    def _create_drag_ghost(self, index: int, event):
        if not (0 <= index < len(self.repertoire_entries)):
            return
        title = self.repertoire_entries[index][0]
        src_frame = self._repertoire_row_frames[index]
        w = max(src_frame.winfo_width(), 180)
        h = max(src_frame.winfo_height(), 40)
        ghost = tk.Toplevel(self)
        ghost.overrideredirect(True)
        ghost.attributes("-alpha", 0.75)
        ghost.attributes("-topmost", True)
        ghost.geometry(f"{w}x{h}+{event.x_root - w // 2}+{event.y_root - h // 2}")
        inner = tk.Frame(ghost, bg=ACCENT_LBUE, relief=SOLID, bd=1)
        inner.pack(fill=BOTH, expand=True)
        tk.Label(inner, text=title, font=("맑은 고딕", 10, "bold"),
                 bg=ACCENT_LBUE, fg=FG_APP).pack(expand=True)
        self._drag_ghost = ghost

    def _move_drag_ghost(self, event):
        if self._drag_ghost:
            w = self._drag_ghost.winfo_width()
            h = self._drag_ghost.winfo_height()
            self._drag_ghost.geometry(f"+{event.x_root - w // 2}+{event.y_root - h // 2}")

    def _destroy_drag_ghost(self):
        if self._drag_ghost:
            try:
                self._drag_ghost.destroy()
            except Exception:
                pass
            self._drag_ghost = None
        try:
            self._rep_canvas.itemconfigure(self._drop_line, state="hidden")
        except Exception:
            pass

    def _target_index_by_y(self, y_root: int) -> int:
        """Returns insertion index 0..N (between items, not on items)."""
        frames = self._repertoire_row_frames
        for i, frame in enumerate(frames):
            mid = frame.winfo_rooty() + frame.winfo_height() // 2
            if y_root < mid:
                return i
        return len(frames)

    def _update_drag_visuals(self):
        src = self._repertoire_drag_from_index
        tgt = self._repertoire_drag_target_index
        frames = self._repertoire_row_frames

        if not self._repertoire_drag_active or tgt is None or not frames:
            self._rep_canvas.itemconfigure(self._drop_line, state="hidden")
            return

        # Position drop indicator line at the insertion gap
        n = len(frames)
        if tgt == 0:
            y = frames[0].winfo_y()
        elif tgt >= n:
            last = frames[-1]
            y = last.winfo_y() + last.winfo_height()
        else:
            above = frames[tgt - 1]
            below = frames[tgt]
            y = (above.winfo_y() + above.winfo_height() + below.winfo_y()) // 2

        w = self._rep_canvas.winfo_width()
        self._rep_canvas.coords(self._drop_line, 4, y, w - 4, y)
        self._rep_canvas.itemconfigure(self._drop_line, state="normal")

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

    def _preload_db_cache(self):
        threading.Thread(target=self._fetch_db_cache, daemon=True).start()

    def _fetch_db_cache(self):
        try:
            items = list_recent_lyrics_catalog(self.get_server_url(), limit=50)
            self._db_catalog_cache = items
            self._db_cache_ready = True
        except Exception:
            self._db_catalog_cache = []
            self._db_cache_ready = False

    def open_lyrics_search_dialog(self):
        server_url = self.get_server_url()
        preloaded = self._db_catalog_cache if self._db_cache_ready else None
        dialog = LyricsSearchDialog(self, server_url,
                                    preloaded=preloaded,
                                    on_refreshed=self._on_db_refreshed)
        item = dialog.result
        if not item:
            return

        title = str(item.get("title") or "").strip()
        sequence = str(item.get("sequence") or "").strip()
        lyrics = str(item.get("lyrics") or "").strip()
        if not title:
            return

        # recent 목록은 lyrics를 포함하지 않으므로 by-title로 별도 조회
        if not lyrics:
            try:
                full = lookup_lyrics_by_title(server_url, title)
                if full:
                    lyrics = str(full.get("lyrics") or "").strip()
                    if not sequence:
                        sequence = str(full.get("sequence") or "").strip()
            except Exception:
                pass

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
        self._set_song_title_display("곡을 선택하세요")
        self.populate_song_list([], preserve_current=False)
        self.show_lyrics_guide()
        self.log("[안내] 불러온 작업 내용을 초기화했습니다.")

    # ── Undo / Redo ────────────────────────────────────────────────────
    def _push_undo(self):
        import copy
        self._undo_stack.append((
            list(self.repertoire_entries),
            copy.copy(self.lyrics_store),
        ))
        self._redo_stack.clear()
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)

    def undo_repertoire(self):
        if not self._undo_stack:
            return
        import copy
        self._redo_stack.append((list(self.repertoire_entries), copy.copy(self.lyrics_store)))
        entries, store = self._undo_stack.pop()
        self.repertoire_entries = entries
        self.lyrics_store = store
        self._apply_repertoire_state()

    def redo_repertoire(self):
        if not self._redo_stack:
            return
        import copy
        self._undo_stack.append((list(self.repertoire_entries), copy.copy(self.lyrics_store)))
        entries, store = self._redo_stack.pop()
        self.repertoire_entries = entries
        self.lyrics_store = store
        self._apply_repertoire_state()

    def _apply_repertoire_state(self):
        self.refresh_repertoire_sort_list()
        self.sync_sequence_text_from_repertoire()
        self.populate_song_list(self.repertoire_entries)
        if self.current_song_title and self.current_song_title in self.lyrics_store:
            self.set_lyrics_editor_text(self.lyrics_store[self.current_song_title])
        elif self.current_song_title not in (e[0] for e in self.repertoire_entries):
            self.current_song_title = None
            self._set_song_title_display("곡을 선택하세요")
            self.show_lyrics_guide()

    def _on_db_refreshed(self, items: list[dict]):
        self._db_catalog_cache = items
        self._db_cache_ready = True

    def open_server_settings(self):
        ServerSettingsDialog(self, self.server_url_var)

    def open_ppt_settings(self):
        PPTSettingsDialog(self, self.max_lines_var, self.max_chars_var,
                          self.lyrics_font_size_var)

    def _set_song_title_display(self, title: str, max_chars: int = 22):
        if len(title) > max_chars:
            title = title[:max_chars - 1] + "…"
        self.current_song_var.set(title)

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
            self._set_song_title_display("곡을 선택하세요")
            self.show_lyrics_guide()

        if show_message:
            self.log(f"[안내] 레파토리 {len(sequence_entries)}곡을 인식했습니다.")

        if trigger_download:
            self.after(100, lambda: self._run_download(auto=True))

        return True

    def load_lyrics_for_song(self, song_title: str):
        self.current_song_title = song_title
        self._set_song_title_display(song_title)
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
