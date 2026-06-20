"""CustomTkinter UI — 작은 작업실 스타일.

Run: .\venv310\Scripts\python.exe src/main_ctk.py
"""
from __future__ import annotations

import copy
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from tkinter import messagebox, filedialog
import tkinter as tk
import tkinter.font as tkfont

import customtkinter as ctk

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

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
from ppt_service import build_integrated_pptx_with_local_office
from songlist_builder import build_songlist_card
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
    LYRICS_GUIDE_TEXT,
)

# ── Appearance ─────────────────────────────────────────────────────────────
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# ── Palette — "작은 작업실": 거의 흰 배경 + 포인트 블루/민트 ──────────────
BG_ROOT   = "#F7F8FA"   # 앱 루트 (쿨 화이트)
BG_CARD   = "#FFFFFF"   # 카드/패널
BG_SOFT   = "#F3F4F6"   # 입력창·사이드바 배경
BORDER    = "#E5E7EB"   # 카드 경계선
ACCENT    = "#5B9BD5"   # 메인 블루
ACCENT_HV = "#4A8BC4"   # 호버
ACCENT_PR = "#3A7AB3"   # 프레스
MINT      = "#3CB89A"   # 민트 (긍정 상태)
FG_PRI    = "#111827"   # 기본 텍스트
FG_MUT    = "#9CA3AF"   # 흐린 텍스트
FG_BTN    = "#FFFFFF"   # 버튼 위 텍스트
ST_OK     = "#10B981"   # 상태 녹색
ST_WARN   = "#F59E0B"   # 상태 주황

MUTED_FG = FG_MUT
TEXT_FG  = FG_PRI

_APP_ICO: str | None = None

# ── 공통 버튼 스타일 딕셔너리 ─────────────────────────────────────────────
_OUTLINE = dict(fg_color="transparent", text_color=FG_PRI,
                hover_color=BG_SOFT, border_width=1, border_color=BORDER,
                corner_radius=8)
_PRIMARY = dict(fg_color=ACCENT, text_color=FG_BTN,
                hover_color=ACCENT_HV, corner_radius=8)
_DANGER  = dict(fg_color="#FEF2F2", text_color="#EF4444",
                hover_color="#FEE2E2", border_width=1,
                border_color="#FECACA", corner_radius=6)


# ─── 다이얼로그 기반 클래스 ────────────────────────────────────────────────
class _BaseDialog(ctk.CTkToplevel):
    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.configure(fg_color=BG_CARD)
        self.withdraw()
        self.transient(parent)
        if _APP_ICO and sys.platform == "win32":
            self.after(200, lambda: self.iconbitmap(_APP_ICO))

    def _center_on_parent(self):
        self.update_idletasks()
        pw = self.master.winfo_width()
        ph = self.master.winfo_height()
        px = self.master.winfo_rootx()
        py = self.master.winfo_rooty()
        w  = self.winfo_width()
        h  = self.winfo_height()
        self.geometry(f"+{px+(pw-w)//2}+{py+(ph-h)//2}")
        self.deiconify()
        self.focus_set()


# ─── 여러 줄 입력 다이얼로그 ──────────────────────────────────────────────
class MultilineDialog(_BaseDialog):
    def __init__(self, parent, title: str, prompt: str, initial_text: str = ""):
        super().__init__(parent)
        self.title(title)
        self.geometry("540x420")
        self.grab_set()
        self.result: str | None = None

        if prompt:
            ctk.CTkLabel(self, text=prompt, wraplength=490,
                          text_color=FG_MUT, font=("Segoe UI", 10),
                          justify="left").pack(fill="x", padx=20, pady=(16, 8))

        self._text = ctk.CTkTextbox(self, wrap="word", font=("맑은 고딕", 11),
                                     fg_color=BG_SOFT, border_width=1,
                                     border_color=BORDER, corner_radius=8,
                                     text_color=FG_PRI)
        self._text.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        if initial_text:
            self._text.insert("end", initial_text)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 16))
        ctk.CTkButton(row, text="취소", height=36, command=self.destroy,
                       **_OUTLINE).pack(side="right", padx=(6, 0))
        ctk.CTkButton(row, text="확인", height=36, command=self._accept,
                       **_PRIMARY).pack(side="right")

        self.after(100, self._center_on_parent)
        self.wait_window(self)

    def _accept(self):
        self.result = self._text.get("1.0", "end")
        self.destroy()


# ─── 가사 DB 검색 다이얼로그 ──────────────────────────────────────────────
class LyricsSearchDialog(_BaseDialog):
    _DEBOUNCE_MS = 300

    def __init__(self, parent, server_url: str,
                 preloaded: list[dict] | None = None,
                 on_refreshed=None):
        super().__init__(parent)
        self.title("가사 DB 검색")
        self.geometry("580x520")
        self.grab_set()
        self.result: dict | None = None
        self._server_url = server_url
        self._preloaded  = preloaded
        self._on_refreshed = on_refreshed
        self._debounce_id  = None

        # 검색창
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=20, pady=(16, 10))
        bar.columnconfigure(0, weight=1)

        self._search_var = ctk.StringVar()
        entry = ctk.CTkEntry(bar, textvariable=self._search_var,
                              placeholder_text="곡 제목으로 검색…",
                              height=40, corner_radius=8,
                              border_color=BORDER, fg_color=BG_SOFT,
                              text_color=FG_PRI)
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._search_var.trace_add("write", self._on_query)

        self._refresh_btn = ctk.CTkButton(bar, text="↻", width=40, height=40,
                                           **_OUTLINE, command=self._force_refresh)
        self._refresh_btn.grid(row=0, column=1)

        # 결과 목록
        self._list = ctk.CTkScrollableFrame(self, fg_color=BG_SOFT, corner_radius=8)
        self._list.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        self._status_lbl = ctk.CTkLabel(self._list, text="불러오는 중…",
                                         text_color=FG_MUT, font=("Segoe UI", 11))
        self._status_lbl.pack(anchor="w", padx=8, pady=8)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 16))
        ctk.CTkButton(footer, text="+ 신곡 추가", height=36,
                       **_OUTLINE, command=self._open_new_song_dialog).pack(side="left")
        ctk.CTkButton(footer, text="닫기", height=36,
                       **_OUTLINE, command=self.destroy).pack(side="right")

        self.after(100, self._center_on_parent)
        self.after(120, lambda: entry.focus_set())

        if self._preloaded is not None:
            self.after(30, lambda: self._render(self._preloaded, "최근 추가순"))
        else:
            self.after(60, self._load_recent)

        self.wait_window(self)

    def _open_new_song_dialog(self):
        dialog = NewSongDialog(self)
        if dialog.result:
            self._select(dialog.result)

    def _force_refresh(self):
        self._refresh_btn.configure(state="disabled")
        self._show_status("새로고침 중…")
        threading.Thread(target=self._fetch_refresh, daemon=True).start()

    def _fetch_refresh(self):
        try:
            items = list_recent_lyrics_catalog(self._server_url, limit=50)
        except Exception as e:
            self.after(0, lambda: self._show_status(f"오류: {e}"))
        else:
            if self._on_refreshed:
                self.after(0, lambda r=items: self._on_refreshed(r))
            self.after(0, lambda r=items: self._render(r, "최근 추가순"))
        finally:
            self.after(0, lambda: self._refresh_btn.configure(state="normal")
                       if self._alive() else None)

    def _load_recent(self):
        self._show_status("불러오는 중…")
        threading.Thread(target=self._fetch_recent, daemon=True).start()

    def _fetch_recent(self):
        try:
            items = list_recent_lyrics_catalog(self._server_url, limit=50)
        except Exception as e:
            self.after(0, lambda: self._show_status(f"목록 조회 오류: {e}"))
            return
        self.after(0, lambda r=items: self._render(r, "최근 추가순"))

    def _on_query(self, *_):
        if self._debounce_id:
            try:
                self.after_cancel(self._debounce_id)
            except Exception:
                pass
        self._debounce_id = self.after(self._DEBOUNCE_MS, self._do_search)

    def _do_search(self):
        q = self._search_var.get().strip()
        if not q:
            self._load_recent()
            return
        self._show_status("검색 중…")
        threading.Thread(target=self._fetch_search, args=(q,), daemon=True).start()

    def _fetch_search(self, q: str):
        try:
            items = search_lyrics_catalog(self._server_url, q, limit=20)
        except Exception as e:
            self.after(0, lambda: self._show_status(f"검색 오류: {e}"))
            return
        self.after(0, lambda r=items: self._render(r))

    def _alive(self) -> bool:
        try:
            return self.winfo_exists()
        except Exception:
            return False

    def _show_status(self, msg: str):
        if not self._alive():
            return
        for w in self._list.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._list, text=msg, text_color=FG_MUT,
                      font=("Segoe UI", 11)).pack(anchor="w", padx=8, pady=8)

    def _render(self, items: list[dict], header: str | None = None):
        if not self._alive():
            return
        for w in self._list.winfo_children():
            w.destroy()
        if not items:
            self._show_status("검색 결과가 없습니다.")
            return
        if header:
            ctk.CTkLabel(self._list, text=header, text_color=FG_MUT,
                          font=("Segoe UI", 9)).pack(anchor="w", padx=8, pady=(6, 2))
        for item in items:
            self._build_row(item)

    def _build_row(self, item: dict):
        title = str(item.get("title") or "")
        seq   = str(item.get("sequence") or "")
        card  = ctk.CTkFrame(self._list, fg_color=BG_CARD, corner_radius=8,
                               border_width=1, border_color=BORDER)
        card.pack(fill="x", padx=0, pady=(0, 6))
        card.columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text=title, text_color=FG_PRI,
                      font=("맑은 고딕", 12, "bold"),
                      anchor="w").grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))
        ctk.CTkLabel(card, text=seq or "(진행 순서 없음)", text_color=FG_MUT,
                      font=("맑은 고딕", 10),
                      anchor="w").grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        ctk.CTkButton(card, text="추가", width=60, height=32,
                       **_PRIMARY,
                       command=lambda i=item: self._select(i)).grid(
            row=0, column=1, rowspan=2, sticky="ns", padx=(0, 10), pady=10)

    def _select(self, item: dict):
        self.result = item
        self.destroy()


# ─── 신곡 추가 다이얼로그 ────────────────────────────────────────────────
class NewSongDialog(_BaseDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("신곡 추가")
        self.geometry("420x220")
        self.resizable(False, False)
        self.grab_set()
        self.result: dict | None = None

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=(20, 8))
        content.columnconfigure(1, weight=1)

        ctk.CTkLabel(content, text="곡 제목 *", font=("Segoe UI", 11),
                      text_color=FG_PRI, anchor="e").grid(
            row=0, column=0, sticky="e", padx=(0, 12), pady=(0, 12))
        self._title_var = ctk.StringVar()
        self._title_entry = ctk.CTkEntry(
            content, textvariable=self._title_var,
            placeholder_text="곡 제목을 입력하세요",
            height=36, corner_radius=8,
            border_color=BORDER, fg_color=BG_SOFT, text_color=FG_PRI)
        self._title_entry.grid(row=0, column=1, sticky="ew", pady=(0, 12))

        ctk.CTkLabel(content, text="레파토리", font=("Segoe UI", 11),
                      text_color=FG_MUT, anchor="e").grid(
            row=1, column=0, sticky="e", padx=(0, 12))
        self._seq_var = ctk.StringVar()
        ctk.CTkEntry(
            content, textvariable=self._seq_var,
            placeholder_text="예) I-V1-V2-C-C  (선택 사항)",
            height=36, corner_radius=8,
            border_color=BORDER, fg_color=BG_SOFT, text_color=FG_PRI,
            placeholder_text_color=FG_MUT).grid(row=1, column=1, sticky="ew")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(12, 16))
        ctk.CTkButton(btn_row, text="취소", height=36, command=self.destroy,
                       **_OUTLINE).pack(side="right", padx=(6, 0))
        ctk.CTkButton(btn_row, text="추가하기", height=36, command=self._accept,
                       **_PRIMARY).pack(side="right")

        self.after(100, self._center_on_parent)
        self.after(120, lambda: self._title_entry.focus_set())
        self.bind("<Return>", lambda e: self._accept())
        self.wait_window(self)

    def _accept(self):
        title = self._title_var.get().strip()
        if not title:
            messagebox.showwarning("신곡 추가", "곡 제목을 입력해 주세요.", parent=self)
            return
        self.result = {
            "title": title,
            "sequence": self._seq_var.get().strip(),
            "lyrics": "",
            "_source": "new_song",
        }
        self.destroy()


# ─── PPT 설정 다이얼로그 ──────────────────────────────────────────────────
class PPTSettingsDialog(_BaseDialog):
    def __init__(self, parent, max_lines_var, max_chars_var, font_size_var):
        super().__init__(parent)
        self.title("PPT 상세 설정")
        self.resizable(False, False)
        self.grab_set()
        self.confirmed = False

        self._out_ml = max_lines_var
        self._out_mc = max_chars_var
        self._out_fs = font_size_var
        self._ml = ctk.StringVar(value=max_lines_var.get())
        self._mc = ctk.StringVar(value=max_chars_var.get())
        self._fs = ctk.StringVar(value=font_size_var.get())

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=20)
        content.columnconfigure(1, weight=1)

        def row(r, label, var):
            ctk.CTkLabel(content, text=label, font=("Segoe UI", 11),
                          text_color=FG_PRI, anchor="e").grid(
                row=r, column=0, sticky="e", padx=(0, 12), pady=6)
            ctk.CTkEntry(content, textvariable=var, width=120, height=34,
                          corner_radius=8, border_color=BORDER,
                          fg_color=BG_SOFT, justify="center").grid(
                row=r, column=1, sticky="w", pady=6)

        row(0, "슬라이드별 최대 줄 수", self._ml)
        row(1, "줄별 최대 글자 수",     self._mc)
        row(2, "가사 크기 (기본: 비워두기)", self._fs)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(0, 16))
        ctk.CTkButton(btn_row, text="취소", height=36, command=self.destroy,
                       **_OUTLINE).pack(side="right", padx=(6, 0))
        ctk.CTkButton(btn_row, text="확인", height=36, command=self._accept,
                       **_PRIMARY).pack(side="right")

        self.after(100, self._center_on_parent)
        self.wait_window(self)

    def _accept(self):
        self._out_ml.set(self._ml.get())
        self._out_mc.set(self._mc.get())
        self._out_fs.set(self._fs.get())
        self.confirmed = True
        self.destroy()


# ─── 서버 설정 다이얼로그 ─────────────────────────────────────────────────
class ServerSettingsDialog(_BaseDialog):
    def __init__(self, parent, server_url_var):
        super().__init__(parent)
        self.title("서버 설정")
        self.resizable(False, False)
        self.grab_set()

        self._out = server_url_var
        self._var = ctk.StringVar(value=server_url_var.get())

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=20)
        content.columnconfigure(1, weight=1)
        ctk.CTkLabel(content, text="PPT 서버 URL", font=("Segoe UI", 11),
                      text_color=FG_PRI, anchor="e").grid(
            row=0, column=0, sticky="e", padx=(0, 12), pady=6)
        ctk.CTkEntry(content, textvariable=self._var, width=260, height=34,
                      corner_radius=8, border_color=BORDER,
                      fg_color=BG_SOFT).grid(row=0, column=1, sticky="ew", pady=6)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(0, 16))
        ctk.CTkButton(btn_row, text="취소", height=36, command=self.destroy,
                       **_OUTLINE).pack(side="right", padx=(6, 0))
        ctk.CTkButton(btn_row, text="확인", height=36, command=self._accept,
                       **_PRIMARY).pack(side="right")

        self.after(100, self._center_on_parent)
        self.wait_window(self)

    def _accept(self):
        self._out.set(self._var.get().strip())
        self.destroy()


# ─── 작업 중 다이얼로그 ───────────────────────────────────────────────────
class BusyDialog(_BaseDialog):
    def __init__(self, parent, title: str, message: str, on_cancel=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("360x160")
        self.resizable(False, False)
        self.grab_set()
        self._on_cancel = on_cancel
        self.protocol("WM_DELETE_WINDOW", self._cancel if on_cancel else lambda: None)

        self._msg = ctk.CTkLabel(self, text=message, wraplength=300,
                                  font=("맑은 고딕", 13, "bold"),
                                  text_color=FG_PRI, justify="center")
        self._msg.pack(padx=20, pady=(24, 12))

        self._bar = ctk.CTkProgressBar(self, mode="indeterminate",
                                        fg_color=BG_SOFT, progress_color=ACCENT)
        self._bar.pack(fill="x", padx=20, pady=(0, 8))
        self._bar.start()

        if on_cancel:
            ctk.CTkButton(self, text="취소", height=32,
                           **_OUTLINE, command=self._cancel).pack(pady=(0, 16))

        self.after(100, self._center_on_parent)

    def set_message(self, msg: str):
        if self.winfo_exists():
            self._msg.configure(text=msg)
            self.update_idletasks()

    def _cancel(self):
        if self._on_cancel:
            self._on_cancel()

    def close(self):
        try:
            self._bar.stop()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass


class OperationCancelled(RuntimeError):
    pass


# ─── 메인 앱 ──────────────────────────────────────────────────────────────
class LyricsApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_WINDOW_TITLE)
        self.geometry("1160x740")
        self.minsize(900, 640)
        self.configure(fg_color=BG_ROOT)

        if getattr(sys, "frozen", False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self._configure_icon()

        # ── 앱 상태 ──────────────────────────────────────────────────────
        self.sequence_entries: list      = []
        self.current_song_title: str | None = None
        self.lyrics_placeholder_visible  = False
        self.loading_lyrics              = False
        self.lyrics_store: dict          = {}
        self.template_files: dict        = {}
        self._template_download_running  = False
        self._recent_log_lines: list     = []
        self.weekly_history_items: list  = []
        self._loaded_history_lyrics_by_title: dict = {}
        self.repertoire_entries: list    = []
        self._undo_stack: list           = []
        self._redo_stack: list           = []
        self._busy_dialog: BusyDialog | None = None
        self.song_buttons: list          = []
        self.selected_song_index: int | None = None
        self._db_catalog_cache: list[dict] = []
        self._db_cache_ready             = False

        # 드래그 상태
        self._rep_cards: list            = []
        self._drop_dividers: list        = []
        self._rep_drag_from: int | None  = None
        self._rep_drag_target: int | None = None
        self._rep_drag_start_x: int | None = None
        self._rep_drag_start_y: int | None = None
        self._rep_drag_active            = False
        self._drag_ghost: tk.Toplevel | None = None
        self._seq_debounce_id            = None

        self.brand_font = self._resolve_font_family(BRAND_FONT_CANDIDATES)
        self._load_icons()
        self._create_ui()
        self.configure(fg_color=BG_ROOT)

        self.load_local_weekly_history()
        self.after(500, self.sync_weekly_history_from_server_async)
        self.refresh_template_options()
        self.after(300, self.ensure_templates_async)
        self.after(800, self._preload_db_cache)

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind_all("<Control-z>", lambda e: self.undo_repertoire())
        self.bind_all("<Control-y>", lambda e: self.redo_repertoire())

    # ── 아이콘 / 폰트 ─────────────────────────────────────────────────
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
        self._icons: dict = {}
        if not Image:
            return
        icon_dir = os.path.join(self.base_dir, "assets", "icons")
        for name in ("edit", "trash", "refresh", "download", "plus", "search"):
            path = os.path.join(icon_dir, f"{name}.png")
            if os.path.exists(path):
                img = Image.open(path).convert("RGBA").resize((16, 16), Image.LANCZOS)
                self._icons[name] = ctk.CTkImage(light_image=img, size=(16, 16))

    def _get_icon(self, name: str):
        return self._icons.get(name)

    # ── UI 생성 ────────────────────────────────────────────────────────
    def _create_ui(self):
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self._create_header()
        self._create_body()

    def _create_header(self):
        hdr = ctk.CTkFrame(self, fg_color=BG_CARD,
                            corner_radius=0, border_width=0,
                            height=56)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.columnconfigure(1, weight=1)

        # 로고 — ctk.CTkLabel 로 CTkImage 렌더링 (tk.Label 은 CTkImage 미지원)
        logo_file = self.find_asset_file(LOGO_FILE_NAME)
        if logo_file and Image:
            try:
                img = Image.open(logo_file).convert("RGBA")
                scale = min(34 / img.width, 34 / img.height)
                dw, dh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
                img = img.resize((dw, dh), Image.LANCZOS)
                self._logo_ctk = ctk.CTkImage(light_image=img, size=(dw, dh))
                ctk.CTkLabel(hdr, image=self._logo_ctk, text="",
                              fg_color="transparent").grid(
                    row=0, column=0, padx=(16, 6), pady=11)
            except Exception:
                logo_file = None
        if not logo_file or not Image:
            ctk.CTkLabel(hdr, text=APP_DISPLAY_NAME,
                          font=(self.brand_font, 14, "bold"),
                          text_color=FG_PRI).grid(
                row=0, column=0, padx=(16, 8), pady=14)

        # 부제
        ctk.CTkLabel(hdr, text="레파토리와 가사를 정리해 파워포인트로 만듭니다.",
                      text_color=FG_MUT, font=("Segoe UI", 9),
                      anchor="w").grid(row=0, column=1, sticky="w", pady=14)

        # 우측 버튼 — pady=14 로 로고/부제와 동일 수직 정렬
        btn_area = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_area.grid(row=0, column=2, padx=(0, 16), pady=14)

        self._more_btn = ctk.CTkButton(btn_area, text="⋮", width=36, height=28,
                                        **_OUTLINE,
                                        command=self._show_more_menu)
        self._more_btn.pack(side="left")
        self._more_menu = self._build_more_menu()

        # 헤더 하단 구분선
        tk.Frame(self, height=1, bg=BORDER).grid(row=0, column=0, sticky="ews")

    def _build_more_menu(self) -> tk.Menu:
        m = tk.Menu(self, tearoff=0, bg=BG_CARD, fg=FG_PRI,
                    activebackground=ACCENT, activeforeground=FG_BTN,
                    relief="flat", borderwidth=1, font=("Segoe UI", 10))
        m.add_command(label="레파토리 직접 입력", command=self.open_repertoire_input_dialog)
        m.add_separator()
        m.add_command(label="PPT 상세 설정",    command=self.open_ppt_settings)
        m.add_command(label="서버 설정",         command=self.open_server_settings)
        m.add_separator()
        m.add_command(label="작업 로그 다운로드", command=self.download_work_log)
        m.add_command(label="로그 첨부 버그 리포트", command=self.report_bug_with_logs)
        m.add_separator()
        m.add_command(label="앱 정보", command=self.show_app_about)
        m.add_command(label="종료",   command=self.on_close)
        return m

    def _show_more_menu(self):
        x = self._more_btn.winfo_rootx()
        y = self._more_btn.winfo_rooty() + self._more_btn.winfo_height() + 2
        self._more_menu.post(x, y)

    def _create_body(self):
        body = ctk.CTkFrame(self, fg_color=BG_ROOT, corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=12)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=0, minsize=260)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(2, weight=0, minsize=248)

        self._create_setlist_panel(body)
        self._create_editor_panel(body)
        self._create_deck_panel(body)

    # ── 왼쪽: SETLIST ──────────────────────────────────────────────────
    def _create_setlist_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=BG_CARD,
                              corner_radius=12, border_width=1, border_color=BORDER)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        panel.rowconfigure(1, weight=1)
        panel.columnconfigure(0, weight=1)

        # 패널 헤더
        ph = ctk.CTkFrame(panel, fg_color="transparent")
        ph.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 6))
        ph.columnconfigure(0, weight=1)
        ctk.CTkLabel(ph, text="SETLIST", font=("Segoe UI", 11, "bold"),
                      text_color=FG_MUT, anchor="w").grid(row=0, column=0, sticky="w")
        self._count_lbl = ctk.CTkLabel(ph, text="", font=("Segoe UI", 10),
                                        text_color=FG_MUT)
        self._count_lbl.grid(row=0, column=1)

        # 스크롤 영역
        self._setlist_scroll = ctk.CTkScrollableFrame(
            panel, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=BORDER, scrollbar_button_hover_color=ACCENT)
        self._setlist_scroll.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

        # 푸터
        footer = ctk.CTkFrame(panel, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        footer.columnconfigure(0, weight=1)
        ctk.CTkButton(footer, text="⟳  리셋", height=30, **_OUTLINE,
                       font=("Segoe UI", 10),
                       command=self.reset_all_repertoire).grid(row=0, column=1)

        self.refresh_setlist()

    # ── 가운데: LYRICS EDITOR ──────────────────────────────────────────
    def _create_editor_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=BG_CARD,
                              corner_radius=12, border_width=1, border_color=BORDER)
        panel.grid(row=0, column=1, sticky="nsew", padx=8)
        panel.rowconfigure(2, weight=1)
        panel.columnconfigure(0, weight=1)

        # 헤더: 곡 제목 + 다운로드 버튼
        hdr = ctk.CTkFrame(panel, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        hdr.columnconfigure(0, weight=1)

        self._song_title_lbl = ctk.CTkLabel(
            hdr, text="곡을 선택하세요",
            font=("맑은 고딕", 15, "bold"),
            text_color=FG_MUT, anchor="w")
        self._song_title_lbl.grid(row=0, column=0, sticky="ew")

        dl_icon = self._get_icon("download")
        self._dl_btn = ctk.CTkButton(
            hdr, image=dl_icon, text="" if dl_icon else "📥",
            width=34, height=34, **_OUTLINE,
            command=self.fetch_current_song_lyrics_online)
        self._dl_btn.grid(row=0, column=1, padx=(8, 0))

        # 진행 순서 입력
        seq_row = ctk.CTkFrame(panel, fg_color="transparent")
        seq_row.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        ctk.CTkLabel(seq_row, text="진행 순서", text_color=FG_MUT,
                      font=("Segoe UI", 10), width=60).pack(side="left", padx=(0, 8))
        self._seq_var = ctk.StringVar()
        self._seq_entry = ctk.CTkEntry(seq_row, textvariable=self._seq_var,
                                        placeholder_text="I-V1-V2-C-C",
                                        height=34, corner_radius=8,
                                        border_color=BORDER, fg_color=BG_SOFT,
                                        text_color=FG_PRI,
                                        placeholder_text_color=FG_MUT)
        self._seq_entry.pack(side="left", fill="x", expand=True)
        self._seq_var.trace_add("write", self._on_sequence_var_changed)

        # 가사 텍스트 영역 (tk.Text - undo 지원)
        ly_outer = ctk.CTkFrame(panel, fg_color="transparent", corner_radius=0)
        ly_outer.grid(row=2, column=0, sticky="nsew", padx=16, pady=(4, 14))
        ly_outer.rowconfigure(0, weight=1)
        ly_outer.columnconfigure(0, weight=1)

        self.lyrics_text = tk.Text(
            ly_outer, wrap="word", undo=True,
            font=("맑은 고딕", 10),
            bg=BG_CARD, fg=FG_PRI,
            insertbackground=ACCENT,
            relief="flat", highlightthickness=0,
            borderwidth=0, padx=0, pady=4,
            selectbackground="#DBEAFE",
            selectforeground=FG_PRI)
        ly_vs = ctk.CTkScrollbar(ly_outer, command=self.lyrics_text.yview,
                                   button_color=BORDER,
                                   button_hover_color=ACCENT)
        self.lyrics_text.configure(yscrollcommand=ly_vs.set)
        self.lyrics_text.grid(row=0, column=0, sticky="nsew")
        ly_vs.grid(row=0, column=1, sticky="ns", padx=(4, 0))

        self.lyrics_text.bind("<FocusIn>",    self.on_lyrics_focus_in)
        self.lyrics_text.bind("<FocusOut>",   self.on_lyrics_focus_out)
        self.lyrics_text.bind("<<Modified>>", self.on_lyrics_modified)
        self.show_lyrics_guide()

    # ── 오른쪽: DECK PANEL ─────────────────────────────────────────────
    def _create_deck_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=BG_CARD,
                              corner_radius=12, border_width=1, border_color=BORDER)
        panel.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        panel.rowconfigure(1, weight=1)
        panel.columnconfigure(0, weight=1)

        # 템플릿 섹션
        tmpl = ctk.CTkFrame(panel, fg_color="transparent")
        tmpl.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 0))
        tmpl.columnconfigure(0, weight=1)

        ctk.CTkLabel(tmpl, text="TEMPLATE", font=("Segoe UI", 10, "bold"),
                      text_color=FG_MUT, anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

        self.template_option = ctk.CTkOptionMenu(
            tmpl, values=["템플릿 없음"],
            command=self._on_template_selected,
            fg_color=BG_SOFT, text_color=FG_PRI,
            button_color=BORDER, button_hover_color=ACCENT,
            dropdown_fg_color=BG_CARD, dropdown_text_color=FG_PRI,
            dropdown_hover_color=BG_SOFT,
            corner_radius=8, height=34, anchor="w",
            font=("맑은 고딕", 10))
        self.template_option.grid(row=1, column=0, sticky="ew", padx=(0, 6))

        ref_icon = self._get_icon("refresh")
        self.template_refresh_btn = ctk.CTkButton(
            tmpl, image=ref_icon, text="" if ref_icon else "↻",
            width=34, height=34, **_OUTLINE,
            command=lambda: self.ensure_templates_async(force=True))
        self.template_refresh_btn.grid(row=1, column=1)

        self.template_var = tk.StringVar(value="")
        self.server_url_var = tk.StringVar(value=DEFAULT_SERVER_URL)
        self.max_lines_var = tk.StringVar(value=str(DEFAULT_MAX_LINES_PER_SLIDE))
        self.max_chars_var = tk.StringVar(value=str(DEFAULT_MAX_CHARS_PER_LINE))
        self.lyrics_font_size_var = tk.StringVar(value=DEFAULT_LYRICS_FONT_SIZE or "기본")

        # 구분선
        tk.Frame(panel, height=1, bg=BORDER).grid(
            row=0, column=0, sticky="ews", padx=14, pady=(84, 0))

        # 체크리스트 섹션
        cl_outer = ctk.CTkFrame(panel, fg_color="transparent")
        cl_outer.grid(row=1, column=0, sticky="nsew", padx=14, pady=(12, 0))
        cl_outer.columnconfigure(0, weight=1)

        ctk.CTkLabel(cl_outer, text="CHECKLIST", font=("Segoe UI", 10, "bold"),
                      text_color=FG_MUT, anchor="w").pack(fill="x", pady=(0, 8))

        self._checklist_frame = ctk.CTkFrame(cl_outer, fg_color="transparent")
        self._checklist_frame.pack(fill="both", expand=True)

        # 하단 액션 버튼
        actions = ctk.CTkFrame(panel, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 14))
        actions.columnconfigure(0, weight=1)

        self.generate_btn = ctk.CTkButton(
            actions, text="파워포인트 생성하기", height=46,
            fg_color=ACCENT, text_color=FG_BTN, hover_color=ACCENT_HV,
            corner_radius=10, font=("Segoe UI", 13, "bold"),
            command=self._on_generate_click)
        self.generate_btn.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.songlist_btn = ctk.CTkButton(
            actions, text="송리스트 카드 생성", height=36, **_OUTLINE,
            font=("Segoe UI", 11),
            command=self.generate_songlist_card)
        self.songlist_btn.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        self.refresh_btn = ctk.CTkButton(
            actions, text="전체 가사 가져오기", height=36, **_OUTLINE,
            font=("Segoe UI", 11),
            command=lambda: self.refresh_song_list(trigger_download=True))
        self.refresh_btn.grid(row=2, column=0, sticky="ew")

        self._refresh_checklist()

    # ── 체크리스트 ────────────────────────────────────────────────────
    def _estimate_slide_count(self) -> int:
        """ppt_builder.append_lyrics_to_ppt 로직을 미러링해 예상 슬라이드 수를 계산한다.
        오프닝 2장 + 각 곡 제목 1장 + 가사 청크 합산 + 클로징 1장.
        마지막 연속 반복(skip_indices) 및 max_lines/max_chars chunking 반영."""
        from ppt_builder import (
            parse_lyrics_text, get_base_key,
            wrap_text_by_max_chars, chunk_text,
        )
        max_lines = self.get_max_lines_per_slide()
        max_chars = self.get_max_chars_per_line()

        total = 2  # 오프닝 슬라이드 2장 (홈 + 예배를 시작하며)
        for title, seq_str in self.repertoire_entries:
            if not seq_str.strip():
                total += 1  # 제목 슬라이드만
                continue

            lyrics_text = self.lyrics_store.get(title, "")
            lyrics_dict = parse_lyrics_text(lyrics_text) if lyrics_text.strip() else {}

            seq_parts = [p.strip() for p in seq_str.split("-") if p.strip()]

            # 마지막 연속 반복 그룹 skip (ppt_builder와 동일 로직)
            skip_indices: set[int] = set()
            if len(seq_parts) >= 2 and seq_parts[-1] == seq_parts[-2]:
                trail = seq_parts[-1]
                start = len(seq_parts) - 1
                while start > 0 and seq_parts[start - 1] == trail:
                    start -= 1
                skip_indices = set(range(start + 1, len(seq_parts)))

            total += 1  # 곡 제목 슬라이드

            for idx, part in enumerate(seq_parts):
                if idx in skip_indices:
                    continue
                base_part = get_base_key(part)

                if part in lyrics_dict:
                    text = lyrics_dict[part]
                elif base_part in lyrics_dict:
                    text = lyrics_dict[base_part]
                else:
                    if idx == 0 and base_part.upper() in ("I", "INTRO"):
                        continue
                    text = "-"

                text = wrap_text_by_max_chars(text, max_chars)
                chunks = chunk_text(text, max_lines) or [""]
                total += len(chunks)

        total += 1  # 클로징 슬라이드 (기도)
        return total

    def _refresh_checklist(self):
        if not hasattr(self, "_checklist_frame"):
            return
        for w in self._checklist_frame.winfo_children():
            w.destroy()

        n = len(self.repertoire_entries)
        missing_ly  = [t for t, _ in self.repertoire_entries
                        if not self.lyrics_store.get(t, "").strip()]
        missing_seq = [t for t, s in self.repertoire_entries if not s.strip()]
        has_tmpl    = bool(self.template_files)

        slides = self._estimate_slide_count()

        items = [
            (f"총 {n}곡",           n > 0,                 n > 0),
            ("가사 모두 준비됨" if not missing_ly
             else f"가사 누락 {len(missing_ly)}곡",
             not missing_ly,       n > 0),
            ("순서 모두 준비됨" if not missing_seq
             else f"순서 누락 {len(missing_seq)}곡",
             not missing_seq,      n > 0),
            ("템플릿 선택됨" if has_tmpl else "템플릿 없음",
             has_tmpl,             True),
            (f"예상 슬라이드 ~{slides}장", slides > 0,      n > 0),
        ]

        for text, ok, active in items:
            row = ctk.CTkFrame(self._checklist_frame, fg_color="transparent")
            row.pack(fill="x", pady=3)
            dot_color  = ST_OK if ok else (ST_WARN if active else FG_MUT)
            text_color = FG_PRI if active else FG_MUT
            ctk.CTkLabel(row, text="●" if ok else "○",
                          text_color=dot_color, font=("Segoe UI", 9),
                          width=16, anchor="e").pack(side="left", padx=(0, 8))
            ctk.CTkLabel(row, text=text, text_color=text_color,
                          font=("Segoe UI", 11), anchor="w").pack(
                side="left", fill="x", expand=True)

    # ── SETLIST 카드 관리 ──────────────────────────────────────────────
    def refresh_setlist(self):
        if not hasattr(self, "_setlist_scroll"):
            return
        for w in self._setlist_scroll.winfo_children():
            w.destroy()
        self._rep_cards     = []
        self._drop_dividers = []

        self._drop_dividers.append(self._make_divider())

        for i, (title, sequence) in enumerate(self.repertoire_entries):
            card = self._build_card(i, title, sequence)
            self._rep_cards.append(card)
            self._drop_dividers.append(self._make_divider())

        ctk.CTkButton(self._setlist_scroll, text="+ 곡 추가", height=38,
                       fg_color="transparent", text_color=FG_MUT,
                       hover_color=BG_SOFT, border_width=1, border_color=BORDER,
                       corner_radius=8, font=("Segoe UI", 11),
                       command=self.open_lyrics_search_dialog).pack(
            fill="x", padx=4, pady=(2, 8))

        n = len(self.repertoire_entries)
        if hasattr(self, "_count_lbl"):
            self._count_lbl.configure(text=f"{n}곡" if n else "")
        self._refresh_checklist()

    def _make_divider(self) -> ctk.CTkFrame:
        div = ctk.CTkFrame(self._setlist_scroll, height=4, corner_radius=2,
                            fg_color=BG_ROOT, border_width=0)
        div.pack(fill="x", padx=8, pady=0)
        div.pack_propagate(False)
        return div

    def _build_card(self, index: int, title: str, sequence: str) -> ctk.CTkFrame:
        is_sel  = (title == self.current_song_title)
        card_bg = "#EFF6FF" if is_sel else BG_CARD
        border  = ACCENT if is_sel else BORDER
        bw      = 2 if is_sel else 1

        # CTkFrame은 시각 테두리/배경용, 클릭 이벤트는 내부 tk 위젯으로 처리
        card = ctk.CTkFrame(self._setlist_scroll, fg_color=card_bg,
                             corner_radius=8, border_width=bw,
                             border_color=border)
        card.pack(fill="x", padx=4, pady=2)

        # tk.Frame inner — 마우스 이벤트 바인딩이 CTkFrame보다 안정적
        inner = tk.Frame(card, bg=card_bg, cursor="hand2")
        inner.pack(fill="both", expand=True, padx=2, pady=2)

        # 번호 배지 (tk.Label)
        badge_bg = "#DBEAFE" if is_sel else BG_SOFT
        num = tk.Label(inner, text=str(index + 1), width=2,
                       bg=badge_bg, fg=ACCENT if is_sel else FG_MUT,
                       font=("맑은 고딕", 10, "bold"), relief="flat", padx=4)
        num.pack(side="left", padx=(10, 10), pady=14)

        # 우측: 편집·삭제 버튼 세로 배치
        right = tk.Frame(inner, bg=card_bg)
        right.pack(side="right", padx=(0, 8), fill="y")

        btn_col = tk.Frame(right, bg=card_bg)
        btn_col.pack(side="bottom", pady=(0, 10))
        edit_icon = self._get_icon("edit")
        ctk.CTkButton(btn_col, image=edit_icon, text="" if edit_icon else "✏",
                       width=28, height=26, **_OUTLINE,
                       command=lambda i=index: self.edit_repertoire_item(i)).pack(
            pady=(0, 3))
        trash_icon = self._get_icon("trash")
        ctk.CTkButton(btn_col, image=trash_icon, text="" if trash_icon else "✕",
                       width=28, height=26, **_DANGER,
                       command=lambda i=index: self.delete_repertoire_item(i)).pack()

        # 가운데: 제목 + 순서
        content = tk.Frame(inner, bg=card_bg)
        content.pack(side="left", fill="both", expand=True, pady=12)

        title_disp = title if len(title) <= 16 else title[:15] + "…"
        title_lbl = tk.Label(content, text=title_disp, bg=card_bg, fg=FG_PRI,
                              font=("맑은 고딕", 10, "bold"), anchor="w")
        title_lbl.pack(fill="x")
        seq_disp = sequence if len(sequence) <= 22 else sequence[:21] + "…"
        seq_lbl = tk.Label(content, text=seq_disp or "순서 없음",
                            bg=card_bg, fg=FG_MUT,
                            font=("맑은 고딕", 8), anchor="w")
        seq_lbl.pack(fill="x")

        # 드래그/클릭 바인딩 — tk 위젯은 직접 바인딩 가능
        for w in (inner, num, content, title_lbl, seq_lbl, right):
            w.bind("<ButtonPress-1>",   lambda e, i=index: self._on_rep_press(i, e))
            w.bind("<B1-Motion>",       lambda e, i=index: self._on_rep_motion(i, e))
            w.bind("<ButtonRelease-1>", lambda e, i=index: self._on_rep_release(i, e))
            w.bind("<Double-Button-1>", lambda e, i=index: self.edit_repertoire_item(i))
        # CTkFrame 내부 canvas에도 바인딩 (테두리 영역 클릭 대응)
        try:
            card._canvas.bind("<ButtonPress-1>",   lambda e, i=index: self._on_rep_press(i, e))
            card._canvas.bind("<ButtonRelease-1>", lambda e, i=index: self._on_rep_release(i, e))
        except Exception:
            pass

        return card

    def _on_card_select(self, index: int):
        if not (0 <= index < len(self.repertoire_entries)):
            return
        title, sequence = self.repertoire_entries[index]
        if title == self.current_song_title:
            return
        if self.current_song_title and not self.lyrics_placeholder_visible:
            self._save_lyrics_to_catalog_async(
                self.current_song_title, self.get_lyrics_editor_text())
        self.selected_song_index = index
        self.load_lyrics_for_song(title)
        self.refresh_setlist()

    # ── 드래그 앤 드롭 ────────────────────────────────────────────────
    def _on_rep_press(self, index: int, event=None):
        self._rep_drag_from   = index
        self._rep_drag_target = index
        self._rep_drag_start_x = event.x_root if event else None
        self._rep_drag_start_y = event.y_root if event else None
        self._rep_drag_active  = False

    def _on_rep_motion(self, _index, event=None):
        if self._rep_drag_from is None or event is None:
            return
        if not self._rep_drag_active:
            if self._rep_drag_start_x is None:
                return
            if max(abs(event.x_root - self._rep_drag_start_x),
                   abs(event.y_root - self._rep_drag_start_y)) < 6:
                return
            self._rep_drag_active = True
            self._create_drag_ghost(self._rep_drag_from, event)

        self._rep_drag_target = self._target_index_by_y(event.y_root)
        self._update_drag_visuals()
        self._move_drag_ghost(event)

    def _on_rep_release(self, index: int, event=None):
        self._destroy_drag_ghost()
        if not self._rep_drag_active:
            self._rep_drag_from   = None
            self._rep_drag_target = None
            self._rep_drag_active = False
            self._on_card_select(index)
            return

        source     = self._rep_drag_from
        insert_pos = self._target_index_by_y(event.y_root) if event else source
        self._rep_drag_from   = None
        self._rep_drag_target = None
        self._rep_drag_active = False
        self._update_drag_visuals()

        if insert_pos == source or insert_pos == source + 1:
            return
        if 0 <= source < len(self.repertoire_entries):
            self._push_undo()
            item = self.repertoire_entries.pop(source)
            effective = insert_pos if insert_pos <= source else insert_pos - 1
            self.repertoire_entries.insert(effective, item)
            self.refresh_setlist()
            self.sync_sequence_text_from_repertoire()
            self.populate_song_list(self.repertoire_entries)

    def _target_index_by_y(self, y_root: int) -> int:
        for i, card in enumerate(self._rep_cards):
            mid = card.winfo_rooty() + card.winfo_height() // 2
            if y_root < mid:
                return i
        return len(self._rep_cards)

    def _update_drag_visuals(self):
        tgt = self._rep_drag_target
        for i, div in enumerate(self._drop_dividers):
            div.configure(fg_color=ACCENT if i == tgt and self._rep_drag_active
                          else BG_ROOT)

    def _create_drag_ghost(self, index: int, event):
        if not (0 <= index < len(self.repertoire_entries)):
            return
        title = self.repertoire_entries[index][0]
        ghost = tk.Toplevel(self)
        ghost.overrideredirect(True)
        ghost.attributes("-alpha", 0.80)
        ghost.attributes("-topmost", True)
        ghost.geometry(f"220x44+{event.x_root - 110}+{event.y_root - 22}")
        inner = tk.Frame(ghost, bg="#DBEAFE", relief="solid", bd=1)
        inner.pack(fill="both", expand=True)
        tk.Label(inner, text=title, font=("맑은 고딕", 10, "bold"),
                 bg="#DBEAFE", fg=FG_PRI).pack(expand=True)
        self._drag_ghost = ghost

    def _move_drag_ghost(self, event):
        if self._drag_ghost:
            self._drag_ghost.geometry(f"+{event.x_root - 110}+{event.y_root - 22}")

    def _destroy_drag_ghost(self):
        if self._drag_ghost:
            try:
                self._drag_ghost.destroy()
            except Exception:
                pass
            self._drag_ghost = None
        for div in self._drop_dividers:
            try:
                div.configure(fg_color=BG_ROOT)
            except Exception:
                pass

    # ── 진행 순서 편집 ────────────────────────────────────────────────
    def _on_sequence_var_changed(self, *_):
        if self._seq_debounce_id:
            try:
                self.after_cancel(self._seq_debounce_id)
            except Exception:
                pass
        self._seq_debounce_id = self.after(600, self._save_current_sequence)

    def _save_current_sequence(self, event=None):
        if self.current_song_title is None:
            return
        new_seq = self._seq_var.get().strip()
        for i, (t, s) in enumerate(self.repertoire_entries):
            if t == self.current_song_title:
                if s != new_seq:
                    self.repertoire_entries[i] = (t, new_seq)
                    self.refresh_setlist()
                    self._refresh_checklist()
                break

    # ── 가사 에디터 ───────────────────────────────────────────────────
    def show_lyrics_guide(self):
        self.loading_lyrics = True
        self.lyrics_text.configure(state="normal")
        self.lyrics_text.delete("1.0", "end")
        self.lyrics_text.insert("1.0", LYRICS_GUIDE_TEXT)
        self.lyrics_text.configure(fg=FG_MUT)
        self.lyrics_placeholder_visible = True
        self.lyrics_text.edit_modified(False)
        self.loading_lyrics = False

    def clear_lyrics_guide(self):
        if not self.lyrics_placeholder_visible:
            return
        self.loading_lyrics = True
        self.lyrics_text.configure(state="normal")
        self.lyrics_text.delete("1.0", "end")
        self.lyrics_text.configure(fg=FG_PRI)
        self.lyrics_placeholder_visible = False
        self.lyrics_text.edit_modified(False)
        self.loading_lyrics = False

    def set_lyrics_editor_text(self, text: str):
        self.loading_lyrics = True
        self.lyrics_text.configure(state="normal", fg=FG_PRI)
        self.lyrics_text.delete("1.0", "end")
        self.lyrics_text.insert("1.0", text)
        self.lyrics_placeholder_visible = False
        self.lyrics_text.edit_modified(False)
        self.loading_lyrics = False

    def get_lyrics_editor_text(self) -> str:
        if self.lyrics_placeholder_visible:
            return ""
        return self.lyrics_text.get("1.0", "end").strip()

    def on_lyrics_focus_in(self, _=None):
        self.clear_lyrics_guide()

    def on_lyrics_focus_out(self, _=None):
        if not self.get_lyrics_editor_text():
            self.show_lyrics_guide()

    def on_lyrics_modified(self, _=None):
        if self.loading_lyrics:
            self.lyrics_text.edit_modified(False)
            return
        if self.lyrics_text.edit_modified():
            if self.current_song_title and not self.lyrics_placeholder_visible:
                self.lyrics_store[self.current_song_title] = self.get_lyrics_editor_text()
                self._refresh_checklist()
            self.lyrics_text.edit_modified(False)

    # ── 곡 목록 (호환) ────────────────────────────────────────────────
    def populate_song_list(self, sequence_entries: list,
                            preserve_current: bool = True) -> int | None:
        previous = self.current_song_title if preserve_current else None
        selected_index = None
        self.song_buttons = []
        for i, (title, _) in enumerate(sequence_entries):
            self.song_buttons.append((title, None))
            if previous == title and selected_index is None:
                selected_index = i
        if selected_index is None and sequence_entries:
            selected_index = 0
        self.refresh_setlist()
        return selected_index

    def _set_song_title_display(self, title: str, max_chars: int = 26):
        if len(title) > max_chars:
            title = title[:max_chars - 1] + "…"
        if hasattr(self, "_song_title_lbl"):
            color = FG_PRI if title not in ("곡을 선택하세요",) else FG_MUT
            self._song_title_lbl.configure(text=title, text_color=color)

    def load_lyrics_for_song(self, song_title: str):
        self.current_song_title = song_title
        self._set_song_title_display(song_title)
        # 진행 순서 로드
        seq = next((s for t, s in self.repertoire_entries if t == song_title), "")
        self._seq_var.set(seq)
        # 가사 로드
        lyrics = self.lyrics_store.get(song_title, "")
        if lyrics.strip():
            self.set_lyrics_editor_text(lyrics)
        else:
            self.show_lyrics_guide()

    def reload_current_song_lyrics_from_history(self):
        if not self.current_song_title:
            messagebox.showinfo("가사 불러오기", "먼저 곡을 선택하세요.")
            return
        lyrics = self._loaded_history_lyrics_by_title.get(self.current_song_title, "")
        if not str(lyrics).strip():
            messagebox.showinfo("가사 불러오기",
                                f"'{self.current_song_title}'에 저장된 이력이 없습니다.")
            return
        self.lyrics_store[self.current_song_title] = str(lyrics)
        self.set_lyrics_editor_text(str(lyrics))
        self.log(f"[완료] '{self.current_song_title}' 가사를 다시 불러왔습니다.")

    def fetch_current_song_lyrics_online(self):
        """현재 곡의 가사를 온라인에서 가져옵니다 (기존 auto_lyrics_downloader 사용)."""
        if not self.current_song_title:
            messagebox.showinfo("가사 가져오기", "먼저 곡을 선택하세요.")
            return

        try:
            from auto_lyrics_downloader import download_missing_lyrics
        except Exception as e:
            messagebox.showerror("오류", f"가사 다운로드 모듈을 불러올 수 없습니다:\n{e}")
            return

        title      = self.current_song_title
        server_url = self.get_server_url()
        seq_map    = {t: s for t, s in self.repertoire_entries}

        self.set_editor_state("disabled")
        self.set_action_buttons_state("disabled")
        self._dl_btn.configure(state="disabled", text="…")

        def run():
            downloaded = {}
            try:
                downloaded = download_missing_lyrics(
                    song_titles=[title],
                    existing_lyrics={},          # 기존 가사 무시하고 강제 다운로드
                    log_func=lambda m: self.after(0, lambda msg=m: self.log(msg)),
                    server_url=server_url,
                    sequence_map={title: seq_map.get(title, "")},
                )
            except Exception as e:
                self.after(0, lambda: self.report_exception("fetch lyrics online", e))

            def on_done():
                dl_icon = self._get_icon("download")
                self._dl_btn.configure(
                    state="normal",
                    image=dl_icon if dl_icon else None,
                    text="" if dl_icon else "📥")
                self.set_editor_state("normal")
                self.set_action_buttons_state("normal")

                lyrics = downloaded.get(title, "").strip()
                if lyrics and self.current_song_title == title:
                    self.lyrics_store[title] = lyrics
                    self.set_lyrics_editor_text(lyrics)
                    self.refresh_setlist()
                    self.log(f"[완료] '{title}' 가사를 가져왔습니다.")
                else:
                    messagebox.showinfo("가사 가져오기",
                                        f"'{title}' 가사를 온라인에서 찾을 수 없었습니다.")

            self.after(0, on_done)

        threading.Thread(target=run, daemon=True).start()

    # ── 레파토리 목록 ─────────────────────────────────────────────────
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
        self.refresh_setlist()
        self.sync_sequence_text_from_repertoire()
        self.populate_song_list(self.repertoire_entries)

    def reset_all_repertoire(self):
        if not self.repertoire_entries:
            return
        if not messagebox.askyesno("전체 리셋",
                                   "모든 레파토리와 가사를 삭제합니다.\n계속할까요?"):
            return
        self._push_undo()
        self.repertoire_entries.clear()
        self.lyrics_store.clear()
        self.current_song_title = None
        self._set_song_title_display("곡을 선택하세요")
        self.show_lyrics_guide()
        self._seq_var.set("")
        self.refresh_setlist()
        self.sync_sequence_text_from_repertoire()

    def _update_repertoire_summary(self):
        pass  # count_lbl updated in refresh_setlist

    def sync_sequence_text_from_repertoire(self):
        self._refresh_checklist()

    def edit_repertoire_item(self, index: int):
        if not (0 <= index < len(self.repertoire_entries)):
            return
        title, sequence = self.repertoire_entries[index]
        dialog = MultilineDialog(self, "레파토리 수정",
                                 "첫 줄: 곡 제목\n둘째 줄: 진행 순서",
                                 initial_text=f"{title}\n{sequence}")
        edited = (dialog.result or "").strip()
        if not edited:
            return
        lines = [l.strip() for l in edited.splitlines() if l.strip()]
        if len(lines) < 2:
            messagebox.showwarning("레파토리 수정", "두 줄로 입력해 주세요.")
            return
        new_title = self._clean_repertoire_title(lines[0])
        new_seq   = lines[1]
        if not new_title or not new_seq:
            messagebox.showwarning("레파토리 수정", "곡 제목과 진행 순서를 모두 입력해 주세요.")
            return
        self.repertoire_entries[index] = (new_title, new_seq)
        if self.current_song_title == title:
            self.current_song_title = new_title
            self._set_song_title_display(new_title)
            self._seq_var.set(new_seq)
        self.refresh_setlist()
        self.sync_sequence_text_from_repertoire()

    # ── 레파토리 입력 ─────────────────────────────────────────────────
    def open_repertoire_input_dialog(self):
        initial = self._format_repertoire_entries(self.repertoire_entries)
        dialog  = MultilineDialog(self, "레파토리 입력",
                                  "한 곡당 2줄(제목/진행순서)로 입력하세요.\n예)\n한나의 노래\nI-V1-V2-C",
                                  initial_text=initial)
        raw = (dialog.result or "").strip()
        if not raw:
            return
        entries = self._normalize_repertoire_entries(raw)
        if not entries:
            messagebox.showwarning("레파토리 입력", "입력 형식을 확인해 주세요.")
            return
        self.repertoire_entries = entries
        self.refresh_setlist()
        self.refresh_song_list(show_message=False)

    # ── DB 캐시 ───────────────────────────────────────────────────────
    def _preload_db_cache(self):
        threading.Thread(target=self._fetch_db_cache, daemon=True).start()

    def _fetch_db_cache(self):
        try:
            items = list_recent_lyrics_catalog(self.get_server_url(), limit=50)
            self._db_catalog_cache = items
            self._db_cache_ready   = True
        except Exception:
            self._db_catalog_cache = []
            self._db_cache_ready   = False

    def open_lyrics_search_dialog(self):
        server_url = self.get_server_url()
        preloaded  = self._db_catalog_cache if self._db_cache_ready else None
        dialog = LyricsSearchDialog(self, server_url, preloaded=preloaded,
                                    on_refreshed=self._on_db_refreshed)
        item = dialog.result
        if not item:
            return

        title     = str(item.get("title") or "").strip()
        sequence  = str(item.get("sequence") or "").strip()
        lyrics    = str(item.get("lyrics") or "").strip()
        is_new    = item.get("_source") == "new_song"
        if not title:
            return

        # 신곡 추가가 아닌 경우에만 DB에서 가사/순서 보완 시도
        if not is_new and not lyrics:
            try:
                full = lookup_lyrics_by_title(server_url, title)
                if full:
                    lyrics = str(full.get("lyrics") or "").strip()
                    if not sequence:
                        sequence = str(full.get("sequence") or "").strip()
            except Exception:
                pass

        # 신곡 추가는 순서 없이도 허용; DB 검색 결과는 순서 필수
        if not sequence and not is_new:
            dialog2 = MultilineDialog(self, "진행 순서 입력",
                                      f"'{title}'의 진행 순서를 입력하세요.\n예) I-V1-V2-C-C")
            _raw = (dialog2.result or "").strip()
            sequence = _raw.splitlines()[0].strip() if _raw else ""

        if not sequence and not is_new:
            messagebox.showwarning("DB에서 추가", "진행 순서가 없어 추가하지 않았습니다.")
            return

        for idx, (t, _) in enumerate(self.repertoire_entries):
            if t == title:
                self.repertoire_entries[idx] = (title, sequence)
                if lyrics:
                    self.lyrics_store[title] = lyrics
                # 데이터 업데이트 후 직접 로드 (동일 제목이면 _on_card_select 가 early-return 하므로)
                self.refresh_setlist()
                self.load_lyrics_for_song(title)
                self.refresh_setlist()
                return

        self.repertoire_entries.append((title, sequence))
        if lyrics:
            self.lyrics_store[title] = lyrics
        # 새 곡 추가 → _on_card_select 가 저장·로드·갱신 모두 처리
        self._on_card_select(len(self.repertoire_entries) - 1)

    def _on_db_refreshed(self, items: list[dict]):
        self._db_catalog_cache = items
        self._db_cache_ready   = True

    # ── 주간 이력 ─────────────────────────────────────────────────────
    def load_local_weekly_history(self):
        cache = self.get_history_cache_file()
        if not os.path.exists(cache):
            self.weekly_history_items = []
            return
        try:
            with open(cache, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.weekly_history_items = data if isinstance(data, list) else []
        except Exception as e:
            self.weekly_history_items = []
            self.report_exception("weekly history load", e)

    def save_local_weekly_history(self, items: list):
        with open(self.get_history_cache_file(), "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

    def sync_weekly_history_from_server(self, log_result: bool = False):
        server_url = self.get_server_url()
        items = fetch_weekly_history_via_server(server_url, year_from=2026)
        self.save_local_weekly_history(items)
        self.weekly_history_items = items
        download_history_db_via_server(server_url, self.get_history_db_file())
        if log_result:
            self.log(f"[완료] 주간 이력 {len(items)}개 동기화")

    def sync_weekly_history_from_server_async(self):
        def run():
            error = None
            try:
                self.sync_weekly_history_from_server()
            except Exception as e:
                error = e
            if error:
                self.after(0, lambda: self.report_exception("weekly history sync", error))
        threading.Thread(target=run, daemon=True).start()

    def apply_weekly_history_item(self, item: dict):
        seq_entries  = item.get("sequence_entries")
        lyrics_by_title = item.get("lyrics_by_title")
        if not isinstance(seq_entries, list) or not isinstance(lyrics_by_title, dict):
            messagebox.showerror("DB 이력 불러오기", "형식이 올바르지 않습니다.")
            return
        seq_text = self._sequence_text_from_entries(seq_entries)
        if not seq_text:
            messagebox.showwarning("DB 이력 불러오기", "레파토리가 없습니다.")
            return
        self.repertoire_entries = self._normalize_repertoire_entries(seq_text)
        self.refresh_setlist()
        self.lyrics_store = {str(k): str(v) for k, v in lyrics_by_title.items()}
        self._loaded_history_lyrics_by_title = dict(self.lyrics_store)
        self.refresh_song_list(show_message=False, trigger_download=False)

    # ── Undo / Redo ────────────────────────────────────────────────────
    def _push_undo(self):
        self._undo_stack.append((list(self.repertoire_entries),
                                  copy.copy(self.lyrics_store)))
        self._redo_stack.clear()
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)

    def undo_repertoire(self):
        if not self._undo_stack:
            return
        self._redo_stack.append((list(self.repertoire_entries),
                                  copy.copy(self.lyrics_store)))
        entries, store = self._undo_stack.pop()
        self.repertoire_entries = entries
        self.lyrics_store = store
        self._apply_repertoire_state()

    def redo_repertoire(self):
        if not self._redo_stack:
            return
        self._undo_stack.append((list(self.repertoire_entries),
                                  copy.copy(self.lyrics_store)))
        entries, store = self._redo_stack.pop()
        self.repertoire_entries = entries
        self.lyrics_store = store
        self._apply_repertoire_state()

    def _apply_repertoire_state(self):
        self.refresh_setlist()
        self.sync_sequence_text_from_repertoire()
        self.populate_song_list(self.repertoire_entries)
        if self.current_song_title and self.current_song_title in self.lyrics_store:
            self.set_lyrics_editor_text(self.lyrics_store[self.current_song_title])
        elif self.current_song_title not in (e[0] for e in self.repertoire_entries):
            self.current_song_title = None
            self._set_song_title_display("곡을 선택하세요")
            self.show_lyrics_guide()

    # ── 레파토리 헬퍼 ─────────────────────────────────────────────────
    def _clean_repertoire_title(self, value: str) -> str:
        text = str(value or "").strip()
        text = re.sub(r"^\s*\d+\s*[\.)]\s*", "", text)
        return text.strip()

    def _normalize_repertoire_entries(self, raw_text: str) -> list:
        lines = [l.strip() for l in str(raw_text or "").splitlines() if l.strip()]
        entries, idx = [], 0
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

    def _sequence_text_from_entries(self, seq_entries: list) -> str:
        chunks = []
        for entry in seq_entries:
            if not isinstance(entry, dict):
                continue
            title = str(entry.get("title", "")).strip()
            seq   = str(entry.get("sequence", "")).strip()
            if title and seq:
                chunks.append(f"{title}\n{seq}")
        return "\n\n".join(chunks).strip()

    # ── 템플릿 ────────────────────────────────────────────────────────
    def _on_template_selected(self, choice: str):
        self.template_var.set(choice)

    def list_template_files(self) -> list:
        templates, seen = [], set()
        for template_dir in self.get_template_search_dirs():
            for root, _, files in os.walk(template_dir):
                for fname in sorted(files, key=str.casefold):
                    if not fname.lower().endswith(".pptx"):
                        continue
                    if fname.casefold() == os.path.basename(
                            SONGLIST_TEMPLATE_FILE_NAME).casefold():
                        continue
                    path    = os.path.join(root, fname)
                    display = os.path.relpath(path, template_dir).replace(os.sep, " / ")
                    if display in seen:
                        continue
                    seen.add(display)
                    templates.append((display, path))
        return sorted(templates, key=lambda x: x[0].casefold(), reverse=True)

    def refresh_template_options(self):
        templates = self.list_template_files()
        self.template_files = {dn: path for dn, path in templates}
        values = list(self.template_files) or ["템플릿 없음"]
        if hasattr(self, "template_option"):
            self.template_option.configure(values=values)
            current = self.template_option.get()
            if current not in self.template_files:
                self.template_option.set(values[0])
                self.template_var.set(values[0])
        self._refresh_checklist()

    def update_template_preview(self, *_):
        pass

    def get_selected_template_file(self) -> str | None:
        sel = self.template_files.get(self.template_var.get()
                                      or (self.template_option.get()
                                          if hasattr(self, "template_option") else ""))
        if sel and os.path.exists(sel):
            return sel
        templates = self.list_template_files()
        return templates[0][1] if templates else None

    def set_template_loading_state(self, loading: bool, status_text: str = ""):
        self._template_download_running = loading
        if hasattr(self, "template_refresh_btn"):
            self.template_refresh_btn.configure(
                state="disabled" if loading else "normal")
            if not loading and status_text and status_text != "✓":
                self.template_refresh_btn.configure(text=f"↻ {status_text}")
            elif not loading:
                ref_icon = self._get_icon("refresh")
                self.template_refresh_btn.configure(
                    image=ref_icon if ref_icon else None,
                    text="" if ref_icon else "↻")

    def animate_template_loading(self, index: int = 0):
        if not self._template_download_running:
            return
        frames = ("◐", "◓", "◑", "◒")
        if hasattr(self, "template_refresh_btn"):
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
                                          quiet=True, use_cookies=False, resume=True,
                                          remaining_ok=True)
                except TypeError:
                    gdown.download_folder(TEMPLATE_DOWNLOAD_URL, output=target_dir,
                                          quiet=True, use_cookies=False, resume=True)
                after = {p for _, p in self.list_template_files()
                         if os.path.abspath(p).startswith(os.path.abspath(target_dir))}
                added = sorted(os.path.basename(p) for p in after - before)

                def on_done():
                    self.refresh_template_options()
                    if added:
                        self.log(f"[완료] 새 템플릿 {len(added)}개: {', '.join(added)}")
                    elif force:
                        self.log("[안내] 템플릿 목록 최신화.")
                    else:
                        self.log("[안내] 템플릿 목록 확인 완료.")
                self.after(0, on_done)
            except Exception as e:
                status = "!"
                self.report_exception("template download", e)
                self.after(0, lambda: self.log(f"[오류] 템플릿 다운로드 실패: {e}"))
            finally:
                self.after(0, lambda s=status: self.set_template_loading_state(False, s))

        threading.Thread(target=run, daemon=True).start()

    # ── 설정 접근자 ───────────────────────────────────────────────────
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
        val = self.lyrics_font_size_var.get().strip()
        if not val or val == "기본":
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    def open_server_settings(self):
        ServerSettingsDialog(self, self.server_url_var)

    def open_ppt_settings(self):
        PPTSettingsDialog(self, self.max_lines_var, self.max_chars_var,
                          self.lyrics_font_size_var)

    # ── Busy 다이얼로그 ───────────────────────────────────────────────
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

    # ── 액션 상태 ─────────────────────────────────────────────────────
    def set_action_buttons_state(self, state: str):
        # CTk uses "normal"/"disabled"
        s = "disabled" if state == "disabled" else "normal"
        for btn in (self.generate_btn, self.songlist_btn, self.refresh_btn):
            try:
                btn.configure(state=s)
            except Exception:
                pass

    def set_editor_state(self, state: str):
        tk_state = "disabled" if state == "disabled" else "normal"
        self.lyrics_text.configure(state=tk_state)

    # ── 로그 / 에러 ───────────────────────────────────────────────────
    def log(self, message: str):
        self._recent_log_lines.append(str(message))
        self._recent_log_lines = self._recent_log_lines[-50:]

    def report_exception(self, context: str, exc, tb=None, extra=None):
        try:
            server_url = self.get_server_url()
            report_error_async(server_url, context=context, message=str(exc),
                               traceback_text=format_exception(exc, tb),
                               extra={}, log_tail=self._recent_log_lines)
        except Exception:
            pass

    # ── 곡 목록 리프레시 ──────────────────────────────────────────────
    def get_sequence_entries(self) -> list:
        if self.repertoire_entries:
            return list(self.repertoire_entries)
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

    # ── 가사 다운로드 ─────────────────────────────────────────────────
    def _run_download(self, auto: bool = False):
        try:
            from auto_lyrics_downloader import download_missing_lyrics
        except Exception as e:
            self.report_exception("lyrics downloader import", e)
            if not auto:
                messagebox.showerror("오류", f"가사 다운로드 모듈 불러오기 실패:\n{e}")
            return

        song_titles  = [t for t, _ in self.sequence_entries]
        current_song = self.current_song_title
        server_url   = self.get_server_url()
        sequence_map = {t: s for t, s in self.sequence_entries}

        self.set_action_buttons_state("disabled")
        self.set_editor_state("disabled")

        def run():
            try:
                downloaded = download_missing_lyrics(
                    song_titles=song_titles, existing_lyrics=self.lyrics_store,
                    log_func=lambda msg: self.after(0, lambda m=msg: self.log(m)),
                    server_url=server_url, sequence_map=sequence_map)
                def on_done():
                    self.lyrics_store.update(downloaded)
                    self.set_editor_state("normal")
                    if current_song:
                        self.load_lyrics_for_song(current_song)
                    if not auto:
                        messagebox.showinfo("완료", "가사 다운로드 작업이 완료되었습니다.")
                    self.set_action_buttons_state("normal")
                    self.refresh_setlist()
                self.after(0, on_done)
            except Exception as e:
                err = e
                def on_error():
                    self.report_exception("lyrics download", err)
                    if not auto:
                        messagebox.showerror("오류", f"가사 다운로드 실패:\n{err}")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_error)

        threading.Thread(target=run, daemon=True).start()

    def _save_lyrics_to_catalog_async(self, song_title: str, lyrics: str):
        if not song_title or not lyrics.strip():
            return
        server_url   = self.get_server_url()
        seq_map      = {t: s for t, s in self.sequence_entries}
        sequence     = seq_map.get(song_title, "")

        def run():
            try:
                from ppt_server_client import save_lyrics_to_catalog
                save_lyrics_to_catalog(server_url, song_title, lyrics,
                                       source="manual", sequence=sequence)
            except Exception:
                pass

        threading.Thread(target=run, daemon=True).start()

    def _sync_all_lyrics_to_catalog_async(self):
        """세트리스트 전 곡의 가사를 DB에 일괄 업서트 (백그라운드)."""
        server_url = self.get_server_url()
        seq_map    = {t: s for t, s in self.repertoire_entries}
        items = [
            (t, self.lyrics_store.get(t, ""), seq_map.get(t, ""))
            for t, _ in self.repertoire_entries
            if self.lyrics_store.get(t, "").strip()
        ]
        if not items:
            return

        def run():
            from ppt_server_client import save_lyrics_to_catalog
            for title, lyrics, sequence in items:
                try:
                    save_lyrics_to_catalog(server_url, title, lyrics,
                                           source="manual", sequence=sequence)
                except Exception:
                    pass

        threading.Thread(target=run, daemon=True).start()

    # ── 송리스트 카드 ─────────────────────────────────────────────────
    def generate_songlist_card(self):
        if not self.refresh_song_list(show_message=False):
            return
        song_titles   = [t for t, _ in self.sequence_entries]
        template_file = self.find_asset_file(SONGLIST_TEMPLATE_FILE_NAME)
        if not template_file:
            messagebox.showerror("오류", f"템플릿 파일을 찾을 수 없습니다.")
            return

        output_file = os.path.join(self.get_output_dir(), SONGLIST_OUTPUT_FILE_NAME)
        output_dir  = os.path.dirname(os.path.abspath(output_file))
        fd, tmp = tempfile.mkstemp(prefix=".songlist_", suffix=".png", dir=output_dir)
        os.close(fd)
        try:
            os.remove(tmp)
        except OSError:
            pass

        cancel_event = threading.Event()

        def raise_if_cancelled():
            if cancel_event.is_set():
                raise OperationCancelled()

        def request_cancel():
            if not cancel_event.is_set():
                cancel_event.set()
                self.update_busy_dialog("취소 요청을 처리하고 있습니다.")

        self.set_action_buttons_state("disabled")
        self.set_editor_state("disabled")
        self.show_busy_dialog("송리스트 생성 중", "송리스트 카드를 생성하고 있습니다.",
                               on_cancel=request_cancel)

        def run():
            try:
                source = "서버"
                server_url = self.get_server_url()
                raise_if_cancelled()
                try:
                    week_num = generate_songlist_card_via_server(
                        server_url, template_file, song_titles, tmp)
                    raise_if_cancelled()
                except PptServerUnavailable:
                    raise_if_cancelled()
                    source = "로컬"
                    week_num = build_songlist_card(template_file, song_titles, tmp)
                    raise_if_cancelled()
                except PptServerResponseError as e:
                    raise_if_cancelled()
                    if e.status_code and e.status_code >= 500:
                        self.report_exception("songlist server fallback", e)
                        source = "로컬"
                        week_num = build_songlist_card(template_file, song_titles, tmp)
                        raise_if_cancelled()
                    else:
                        raise

                os.replace(tmp, output_file)

                def on_done():
                    if cancel_event.is_set():
                        return
                    self.hide_busy_dialog()
                    self.log(f"[완료] 송리스트 카드: '{output_file}' [{source}]")
                    opened = self.open_output_file(output_file)
                    messagebox.showinfo("완료",
                                        "송리스트 카드를 생성했습니다.\n저장: out/"
                                        + SONGLIST_OUTPUT_FILE_NAME
                                        + ("\n생성된 파일을 엽니다." if opened else ""))
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_done)

            except OperationCancelled:
                def on_cancel():
                    self.hide_busy_dialog()
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_cancel)
            except Exception as e:
                err = e
                def on_error():
                    if cancel_event.is_set():
                        return
                    self.report_exception("songlist", err)
                    self.hide_busy_dialog()
                    messagebox.showerror("오류", f"송리스트 카드 생성 실패:\n{err}")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_error)
            finally:
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except OSError:
                    pass

        threading.Thread(target=run, daemon=True).start()

    # ── PPT 생성 ──────────────────────────────────────────────────────
    def _on_generate_click(self):
        self.generate_btn.configure(fg_color=ACCENT_PR)
        self.after(150, lambda: self.generate_btn.configure(fg_color=ACCENT))
        self.after(30, self.generate_ppt)

    def generate_ppt(self):
        self.log("====================================")
        self.log("파워포인트 생성을 시작합니다.")

        if not self.refresh_song_list(show_message=False):
            return

        sequence_entries    = self.sequence_entries
        max_lines_per_slide = self.get_max_lines_per_slide()
        max_chars_per_line  = self.get_max_chars_per_line()
        lyrics_font_size    = self.get_lyrics_font_size()
        template_file       = self.get_selected_template_file()

        if not template_file:
            messagebox.showerror("오류", "템플릿 파일을 찾을 수 없습니다.")
            return

        lyrics_by_title = dict(self.lyrics_store)
        ready_count = 0
        for song_title, _ in sequence_entries:
            raw = lyrics_by_title.get(song_title, "")
            if not raw.strip():
                dialog = MultilineDialog(self, "가사 직접 입력",
                                         f"'{song_title}' 가사를 입력하세요.")
                raw = dialog.result or ""
                if raw:
                    self.lyrics_store[song_title] = raw
                    lyrics_by_title[song_title]   = raw
            if raw.strip():
                ready_count += 1
            else:
                self.log(f"[안내] '{song_title}' 가사가 없어 건너뜁니다.")

        if ready_count == 0:
            messagebox.showwarning("파워포인트 생성", "생성할 가사가 없습니다.")
            return

        output_file = os.path.join(self.get_output_dir(), OUTPUT_FILE_NAME)
        server_url  = self.get_server_url()

        # 출력 파일이 다른 프로세스에 열려있으면 미리 경고
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r+b'):
                    pass
            except (IOError, PermissionError):
                ans = messagebox.askyesno(
                    "파일 사용 중",
                    f"'{os.path.basename(output_file)}' 파일이 다른 프로그램(PowerPoint 등)에서\n"
                    "열려 있습니다.\n\n"
                    "파일을 닫은 후 계속하려면 [예]를 누르세요.\n"
                    "그냥 계속 시도하려면 [아니오]를 누르세요.",
                    parent=self,
                )
                if ans:
                    return

        self.set_action_buttons_state("disabled")
        self.set_editor_state("disabled")
        self.show_busy_dialog("파워포인트 생성 중", "파워포인트 파일을 생성하고 있습니다.")

        def run():
            try:
                source = "서버"
                self.after(0, lambda: self.update_busy_dialog(
                    "서버에 파워포인트 생성을 요청하고 있습니다."))
                try:
                    generated = generate_pptx_via_server(
                        server_url, template_file, sequence_entries, lyrics_by_title,
                        max_lines_per_slide, output_file,
                        max_chars_per_line=max_chars_per_line,
                        lyrics_font_size=lyrics_font_size)
                    if generated is None:
                        generated = ready_count
                except PptServerUnavailable:
                    source = "로컬"
                    self.after(0, lambda: self.update_busy_dialog("로컬에서 생성하고 있습니다."))
                    result = build_integrated_pptx_with_local_office(
                        template_file, sequence_entries, lyrics_by_title, output_file,
                        max_lines_per_slide, max_chars_per_line=max_chars_per_line,
                        lyrics_font_size=lyrics_font_size)
                    generated = result["appended_count"]
                    source    = f"로컬 {result.get('method', 'Office')}"
                except PptServerResponseError as e:
                    if e.status_code and e.status_code >= 500:
                        self.report_exception("ppt server fallback", e)
                        source = "로컬"
                        self.after(0, lambda: self.update_busy_dialog(
                            "로컬에서 생성하고 있습니다."))
                        result = build_integrated_pptx_with_local_office(
                            template_file, sequence_entries, lyrics_by_title, output_file,
                            max_lines_per_slide, max_chars_per_line=max_chars_per_line,
                            lyrics_font_size=lyrics_font_size)
                        generated = result["appended_count"]
                        source    = f"로컬 {result.get('method', 'Office')}"
                    else:
                        raise

                def on_done():
                    self.hide_busy_dialog()
                    self.log(f"[완료] PPT: '{output_file}' [{source}, {generated}곡]")
                    self._sync_all_lyrics_to_catalog_async()
                    opened = self.open_output_file(output_file)
                    messagebox.showinfo("완료",
                                        "파워포인트 파일을 생성했습니다.\n저장: out/integrated_lyrics.pptx"
                                        + ("\n생성된 파일을 엽니다." if opened else ""))
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_done)

            except Exception as e:
                err = e
                def on_error():
                    self.report_exception("ppt", err)
                    self.hide_busy_dialog()
                    messagebox.showerror("오류", f"파워포인트 생성 실패:\n{err}")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_error)

        threading.Thread(target=run, daemon=True).start()

    # ── 파일 출력 ─────────────────────────────────────────────────────
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
            self.report_exception("open output", e)
            return False

    # ── 작업 로그 / 버그 리포트 ───────────────────────────────────────
    def build_work_log_text(self) -> str:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [f"[{now}] PPT Gen 작업 로그",
                 f"서버 URL: {self.get_server_url()}",
                 f"현재 선택 곡: {self.current_song_title or '-'}", "",
                 "[최근 로그]"]
        lines.extend(self._recent_log_lines)
        return "\n".join(lines).strip() + "\n"

    def download_work_log(self, show_message: bool = True) -> str | None:
        default_name = f"work-log-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        try:
            initial_dir = self.get_output_dir()
        except Exception:
            initial_dir = os.getcwd()
        save_path = filedialog.asksaveasfilename(
            title="작업 로그 저장", defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialdir=initial_dir, initialfile=default_name)
        if not save_path:
            return None
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(self.build_work_log_text())
        if show_message:
            messagebox.showinfo("작업 로그", f"저장했습니다.\n{save_path}")
        return save_path

    def report_bug_with_logs(self):
        log_path = self.download_work_log(show_message=False)
        if not log_path:
            return
        dialog = MultilineDialog(self, "서버 버그 리포트",
                                 "증상과 재현 방법을 입력하세요.\n(작업 로그가 함께 첨부됩니다)")
        message = (dialog.result or "").strip()
        if not message:
            messagebox.showwarning("서버 버그 리포트", "버그 설명을 입력해 주세요.")
            return
        report = build_error_report(
            context="manual bug report", message=message,
            traceback_text="", extra={"log_file": os.path.abspath(log_path)},
            log_tail=self._recent_log_lines)
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
                    messagebox.showerror("버그 리포트", f"전송 실패.\n{error}")
                else:
                    messagebox.showinfo("버그 리포트", "버그 리포트를 전송했습니다.")
            self.after(0, on_done)
        threading.Thread(target=run, daemon=True).start()

    def show_app_about(self):
        messagebox.showinfo("앱 정보",
                            "PO,RR by a tempo\n레파토리와 가사를 정리해 파워포인트를 생성합니다.")

    # ── 파일 경로 헬퍼 ───────────────────────────────────────────────
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

    # ── 종료 ──────────────────────────────────────────────────────────
    def on_close(self):
        # 현재 편집 중인 곡 가사를 lyrics_store에 반영 후 DB 일괄 저장
        if self.current_song_title and not self.lyrics_placeholder_visible:
            lyrics = self.get_lyrics_editor_text()
            if lyrics.strip():
                self.lyrics_store[self.current_song_title] = lyrics
        self._sync_all_lyrics_to_catalog_async()
        try:
            self.sync_weekly_history_from_server()
        except Exception as e:
            self.report_exception("weekly history sync on close", e)
        self.destroy()


# ─── 진입점 ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = LyricsApp()
    app.mainloop()
