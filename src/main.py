import os
import json
import re
import subprocess
import sys
import threading
import tempfile
import datetime
import tkinter as tk
import tkinter.font as tkfont
import hashlib
import io
import traceback
import zipfile
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
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
    build_songlist_card_png,
)
from songlist_builder import build_songlist_card, export_pptx_to_png
from error_reporter import build_error_report, format_exception, report_error_async, send_error_report
from constants import *


def hex_to_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[index:index + 2], 16) for index in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % rgb


def blend_hex(start_color, end_color, ratio):
    start_rgb = hex_to_rgb(start_color)
    end_rgb = hex_to_rgb(end_color)
    return rgb_to_hex(
        tuple(
            int(start_rgb[index] + (end_rgb[index] - start_rgb[index]) * ratio)
            for index in range(3)
        )
    )


class MultilineDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, prompt, initial_text=""):
        super().__init__(parent)
        self.title(title)
        self.geometry("460x380")
        self.transient(parent)
        self.result = None

        content_frame = ctk.CTkFrame(self, fg_color=APP_BG, corner_radius=0)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)
        content_frame.rowconfigure(1, weight=1)
        content_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            content_frame,
            text=prompt,
            text_color=MUTED_FG,
            font=("Segoe UI", 10),
        ).grid(row=0, column=0, sticky=tk.W, pady=(0, 8))

        self.text_area = ctk.CTkTextbox(
            content_frame,
            fg_color=TEXT_BG,
            bg_color="transparent",
            text_color=TEXT_FG,
            border_color=PANEL_BORDER,
            border_width=1,
            corner_radius=8,
            wrap=tk.WORD,
            font=("맑은 고딕", 10),
        )
        self.text_area.grid(row=1, column=0, sticky=tk.NSEW)
        if initial_text:
            self.text_area.insert("1.0", initial_text)

        btn_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky=tk.E, pady=(12, 0))

        ctk.CTkButton(
            btn_frame,
            text="확인",
            command=self.on_ok,
            width=80,
            height=34,
            corner_radius=10,
            fg_color=ACCENT,
            hover_color=ACCENT_DARK,
            text_color=TEXT_FG,
            font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 6))

        ctk.CTkButton(
            btn_frame,
            text="취소",
            command=self.on_cancel,
            width=80,
            height=34,
            corner_radius=10,
            fg_color="#ffffff",
            hover_color=ACCENT_SOFT,
            text_color=TEXT_FG,
            border_width=1,
            border_color=PANEL_BORDER,
            font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.LEFT)

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.grab_set()
        self.wait_window(self)

    def on_ok(self):
        self.result = self.text_area.get("1.0", "end").strip()
        self.destroy()

    def on_cancel(self):
        self.destroy()


class LyricsSearchDialog(ctk.CTkToplevel):
    """가사 카탈로그 검색 다이얼로그.

    선택 시 self.result = {"title": ..., "sequence": ..., "lyrics": ...} 또는 None.
    """

    _DEBOUNCE_MS = 300

    def __init__(self, parent, server_url: str):
        super().__init__(parent)
        self.title("가사 DB 검색")
        self.geometry("540x460")
        self.minsize(420, 320)
        self.resizable(True, True)
        self.configure(fg_color=APP_BG)

        self._server_url = server_url
        self._debounce_id = None
        self._results: list[dict] = []
        self.result: dict | None = None

        self._build_ui()
        self.grab_set()
        self.focus_force()
        self._search_entry.focus_set()
        self.wait_window(self)

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # ── Search bar ──────────────────────────────────────────────
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        bar.columnconfigure(0, weight=1)

        self._search_var = tk.StringVar()
        self._search_entry = ctk.CTkEntry(
            bar,
            textvariable=self._search_var,
            placeholder_text="곡명을 입력하세요…",
            height=36,
            corner_radius=10,
            font=("맑은 고딕", 12),
            fg_color=TEXT_BG,
            text_color=TEXT_FG,
            border_color=ACCENT,
            border_width=1,
        )
        self._search_entry.grid(row=0, column=0, sticky="ew")
        self._search_var.trace_add("write", self._on_query_changed)

        # ── Results list ────────────────────────────────────────────
        list_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=PANEL_SOFT_BG,
            corner_radius=12,
            scrollbar_button_color=ACCENT,
            scrollbar_button_hover_color=ACCENT_DARK,
        )
        list_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 8))
        list_frame.columnconfigure(0, weight=1)
        self._list_frame = list_frame

        self._status_label = ctk.CTkLabel(
            list_frame,
            text="검색어를 입력하면 결과가 표시됩니다.",
            text_color=MUTED_FG,
            font=("맑은 고딕", 11),
            anchor="w",
        )
        self._status_label.grid(row=0, column=0, sticky="ew", padx=8, pady=8)

        # ── Bottom buttons ───────────────────────────────────────────
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 14))
        btn_row.columnconfigure(0, weight=1)

        ctk.CTkButton(
            btn_row,
            text="닫기",
            width=80,
            height=32,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=ACCENT,
            hover_color=ACCENT_SOFT,
            text_color=TEXT_FG,
            font=("맑은 고딕", 11),
            command=self.destroy,
        ).grid(row=0, column=0, sticky="e")

    def _on_query_changed(self, *_):
        if self._debounce_id is not None:
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
        self._status_label = ctk.CTkLabel(
            self._list_frame,
            text=msg,
            text_color=MUTED_FG,
            font=("맑은 고딕", 11),
            anchor="w",
        )
        self._status_label.grid(row=0, column=0, sticky="ew", padx=8, pady=8)

    def _render_results(self, items: list[dict]):
        for child in self._list_frame.winfo_children():
            child.destroy()

        if not items:
            self._show_status("검색 결과가 없습니다.")
            return

        for idx, item in enumerate(items):
            self._build_result_row(idx, item)

    def _build_result_row(self, idx: int, item: dict):
        title = str(item.get("title") or "")
        sequence = str(item.get("sequence") or "")
        source = str(item.get("source") or "")
        source_badge = {"bugs": "🌐 Bugs", "manual": "✏️ 직접", "history": "📅 이력"}.get(source, source)

        row = ctk.CTkFrame(
            self._list_frame,
            fg_color=TEXT_BG,
            corner_radius=10,
            border_width=1,
            border_color=PANEL_BORDER,
        )
        row.grid(row=idx, column=0, sticky="ew", padx=6, pady=(0, 6))
        row.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            row,
            text=title,
            text_color=TEXT_FG,
            font=("맑은 고딕", 12, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))

        info_text = sequence if sequence else "(진행 순서 없음)"
        ctk.CTkLabel(
            row,
            text=f"{info_text}  [{source_badge}]",
            text_color=MUTED_FG,
            font=("맑은 고딕", 10),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))

        ctk.CTkButton(
            row,
            text="추가",
            width=56,
            height=28,
            corner_radius=8,
            fg_color=ACCENT,
            hover_color=ACCENT_DARK,
            text_color=TEXT_FG,
            font=("맑은 고딕", 11, "bold"),
            command=lambda i=item: self._select(i),
        ).grid(row=0, column=1, rowspan=2, sticky="e", padx=(0, 8), pady=8)

    def _select(self, item: dict):
        self.result = item
        self.destroy()


    def __init__(self, parent, title, message, on_cancel=None):
        super().__init__(parent)
        self._on_cancel = on_cancel
        self.title(title)
        self.geometry("360x150")
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel if on_cancel else lambda: None)

        content = ctk.CTkFrame(self, fg_color=PANEL_BG, corner_radius=16)
        content.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)
        content.columnconfigure(0, weight=1)

        self.message_label = ctk.CTkLabel(
            content,
            text=message,
            text_color=TEXT_FG,
            font=("맑은 고딕", 13, "bold"),
            wraplength=300,
            justify=tk.CENTER,
        )
        self.message_label.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 14))

        self.progress = ctk.CTkProgressBar(
            content,
            mode="indeterminate",
            height=10,
            progress_color=ACCENT,
            fg_color=PANEL_SOFT_BG,
        )
        self.progress.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 18))
        self.progress.start()

        self.update_idletasks()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - self.winfo_width()) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - self.winfo_height()) // 2)
        self.geometry(f"+{x}+{y}")

    def set_message(self, message):
        self.message_label.configure(text=message)
        self.update_idletasks()

    def on_cancel(self):
        if self._on_cancel:
            self._on_cancel()

    def close(self):
        try:
            self.progress.stop()
        except Exception:
            pass
        self.destroy()


class OperationCancelled(RuntimeError):
    pass


class LyricsApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_WINDOW_TITLE)
        self.geometry("1040x760")
        self.minsize(900, 640)

        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.configure_window_icon()

        self.sequence_entries = []
        self.current_song_title = None
        self.sequence_placeholder_visible = False
        self.lyrics_placeholder_visible = False
        self.loading_lyrics = False
        self.suppress_song_select = False
        self.lyrics_store = {}
        self.current_song_var = tk.StringVar(value="곡을 선택하세요")
        self.template_files = {}
        self._template_download_running = False
        self._template_refresh_complete = False

        self._background_image = None
        self._background_cache_key = None
        self._logo_image = None
        self._busy_dialog = None
        self._template_preview_request_id = 0
        self._template_preview_rendering = set()
        self._template_preview_failed = set()
        self._recent_log_lines = []
        self.weekly_history_items = []
        self._weekly_history_buttons = []
        self._weekly_history_expanded = {}
        self._loaded_history_lyrics_by_title = {}
        self.history_search_var = tk.StringVar(value="")
        self.history_select_var = tk.StringVar(value="")
        self.history_option_items = {}
        self.history_filtered_items = []
        self.repertoire_entries = []
        self._sequence_syncing = False
        self._sequence_parse_after_id = None
        self._repertoire_drag_from_index = None
        self._repertoire_drag_target_index = None
        self._repertoire_drag_start_x = None
        self._repertoire_drag_start_y = None
        self._repertoire_drag_active = False
        self._repertoire_row_frames = []
        self._repertoire_row_no_labels = []
        self._repertoire_drag_ghost = None
        self.brand_font_family = self.resolve_font_family(BRAND_FONT_CANDIDATES)
        self.install_error_reporting_hooks()
        self.setup_style()
        self.create_widgets()
        self.load_local_weekly_history()
        self.render_weekly_history_accordion()
        self.after(500, self.sync_weekly_history_from_server_async)
        self.refresh_template_options()
        self.after(300, self.ensure_templates_async)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def configure_window_icon(self):
        ico_file = self.find_asset_file(ICON_ICO_FILE_NAME)
        if ico_file and sys.platform == "win32":
            try:
                self.iconbitmap(ico_file)
                return
            except tk.TclError:
                pass

        icon_file = self.find_asset_file(ICON_FILE_NAME)
        if icon_file:
            try:
                if Image is not None and ImageTk is not None:
                    self._window_icon = ImageTk.PhotoImage(Image.open(icon_file))
                else:
                    self._window_icon = tk.PhotoImage(file=icon_file)
                self.iconphoto(True, self._window_icon)
                return
            except Exception:
                pass

        try:
            self._empty_icon = tk.PhotoImage(width=1, height=1)
            self.iconphoto(True, self._empty_icon)
        except tk.TclError:
            try:
                self.iconbitmap(default="")
            except tk.TclError:
                pass

    def install_error_reporting_hooks(self):
        self._error_hooks_installed = True
        self._previous_sys_excepthook = sys.excepthook
        self._previous_threading_excepthook = getattr(threading, "excepthook", None)

        def sys_hook(exc_type, exc, tb):
            self.report_exception("sys.excepthook", exc, tb)
            if self._previous_sys_excepthook:
                self._previous_sys_excepthook(exc_type, exc, tb)

        def thread_hook(args):
            self.report_exception(f"threading.{args.thread.name}", args.exc_value, args.exc_traceback)
            if self._previous_threading_excepthook:
                self._previous_threading_excepthook(args)

        sys.excepthook = sys_hook
        if hasattr(threading, "excepthook"):
            threading.excepthook = thread_hook

    def restore_error_reporting_hooks(self):
        if not getattr(self, "_error_hooks_installed", False):
            return
        if getattr(self, "_previous_sys_excepthook", None):
            sys.excepthook = self._previous_sys_excepthook
        if hasattr(threading, "excepthook") and getattr(self, "_previous_threading_excepthook", None):
            threading.excepthook = self._previous_threading_excepthook
        self._error_hooks_installed = False

    def destroy(self):
        self.restore_error_reporting_hooks()
        super().destroy()

    def report_callback_exception(self, exc_type, exc, tb):
        self.report_exception("tkinter callback", exc, tb)
        traceback.print_exception(exc_type, exc, tb)

    def report_exception(self, context, exc, tb=None, extra=None):
        try:
            server_url = self.get_server_url() if hasattr(self, "server_url_var") else DEFAULT_SERVER_URL
            report_error_async(
                server_url,
                context=context,
                message=str(exc),
                traceback_text=format_exception(exc, tb),
                extra=self.build_error_report_extra(context, extra),
                log_tail=getattr(self, "_recent_log_lines", []),
            )
        except Exception:
            pass

    def build_error_report_extra(self, context, extra=None):
        stack = traceback.extract_stack()
        caller_frame = None
        for frame in reversed(stack):
            if frame.name not in ("build_error_report_extra", "report_exception", "report_error_async"):
                caller_frame = frame
                break

        selected_template = None
        if hasattr(self, "template_var"):
            selected_template = self.template_files.get(self.template_var.get())

        settings = {
            "server_url": self.get_server_url() if hasattr(self, "server_url_var") else DEFAULT_SERVER_URL,
            "max_lines_per_slide": self.max_lines_var.get() if hasattr(self, "max_lines_var") else None,
            "max_chars_per_line": self.max_chars_var.get() if hasattr(self, "max_chars_var") else None,
            "lyrics_font_size": self.lyrics_font_size_var.get() if hasattr(self, "lyrics_font_size_var") else None,
            "template": self.template_var.get() if hasattr(self, "template_var") else None,
            "template_path": selected_template,
            "app_title": APP_WINDOW_TITLE,
        }

        state = {
            "context": context,
            "current_song_title": self.current_song_title,
            "sequence_count": len(self.sequence_entries),
            "lyrics_store_count": len(self.lyrics_store),
            "template_download_running": self._template_download_running,
            "template_refresh_complete": self._template_refresh_complete,
            "busy_dialog_open": self._busy_dialog is not None,
        }

        return {
            "caller": {
                "file": caller_frame.filename if caller_frame else None,
                "line": caller_frame.lineno if caller_frame else None,
                "function": caller_frame.name if caller_frame else None,
                "code": caller_frame.line if caller_frame else None,
            },
            "settings": settings,
            "state": state,
            "details": extra if isinstance(extra, dict) else {},
        }

    def find_background_file(self):
        return self.find_asset_file(BACKGROUND_FILE_NAME)

    def find_asset_file(self, file_name):
        base_dirs = [self.base_dir]
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            base_dirs.append(bundle_dir)

        relative_paths = [
            os.path.join(ASSETS_DIR_NAME, file_name),
            file_name,
        ]

        for base_dir in base_dirs:
            for relative_path in relative_paths:
                asset_file = os.path.join(base_dir, relative_path)
                if os.path.exists(asset_file):
                    return asset_file

        return None

    def get_template_download_dir(self):
        template_dir = os.path.join(self.base_dir, ASSETS_DIR_NAME, TEMPLATE_DIR_NAME)
        os.makedirs(template_dir, exist_ok=True)
        return template_dir

    def get_template_search_dirs(self):
        dirs = [self.get_template_download_dir()]
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            dirs.append(os.path.join(bundle_dir, ASSETS_DIR_NAME, TEMPLATE_DIR_NAME))

        result = []
        seen = set()
        for template_dir in dirs:
            template_dir = os.path.abspath(template_dir)
            if template_dir in seen or not os.path.isdir(template_dir):
                continue
            seen.add(template_dir)
            result.append(template_dir)
        return result

    def list_template_files(self):
        templates = []
        seen_names = set()

        for template_dir in self.get_template_search_dirs():
            for root, _, files in os.walk(template_dir):
                for file_name in sorted(files, key=str.casefold):
                    if not file_name.lower().endswith(".pptx"):
                        continue
                    if file_name.casefold() == os.path.basename(SONGLIST_TEMPLATE_FILE_NAME).casefold():
                        continue

                    path = os.path.join(root, file_name)
                    display_name = os.path.relpath(path, template_dir).replace(os.sep, " / ")
                    if display_name in seen_names:
                        continue

                    seen_names.add(display_name)
                    templates.append((display_name, path))

        return sorted(templates, key=lambda item: item[0].casefold(), reverse=True)

    def refresh_template_options(self):
        templates = self.list_template_files()
        self.template_files = {display_name: path for display_name, path in templates}
        values = list(self.template_files)

        if not values:
            self.template_combo.configure(values=["템플릿 없음"], state="disabled")
            self.template_var.set("템플릿 없음")
            self.update_template_preview()
            return

        self.template_combo.configure(values=values, state="normal")
        current = self.template_var.get()

        if current not in self.template_files:
            self.template_var.set(values[0])
        self.update_template_preview()

    def fit_template_preview_image(self, source_image):
        preview = source_image.convert("RGBA")
        resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
        preview.thumbnail(TEMPLATE_PREVIEW_IMAGE_MAX, resample)

        canvas = Image.new(
            "RGBA",
            (TEMPLATE_PREVIEW_WIDTH, TEMPLATE_PREVIEW_HEIGHT),
            (255, 255, 255, 0),
        )
        x = (TEMPLATE_PREVIEW_WIDTH - preview.width) // 2
        y = (TEMPLATE_PREVIEW_HEIGHT - preview.height) // 2
        canvas.alpha_composite(preview, (x, y))
        return canvas

    def build_template_preview_image(self, template_file):
        if Image is None or not template_file or not os.path.exists(template_file):
            return None

        try:
            with zipfile.ZipFile(template_file) as pptx:
                thumbnail_name = next(
                    (
                        name
                        for name in pptx.namelist()
                        if name.casefold().startswith("docprops/thumbnail.")
                    ),
                    None,
                )
                if not thumbnail_name:
                    return None

                thumbnail_data = pptx.read(thumbnail_name)

            return self.fit_template_preview_image(Image.open(io.BytesIO(thumbnail_data)))
        except Exception:
            return None

    def get_template_preview_cache_file(self, template_file):
        stat = os.stat(template_file)
        key = f"{os.path.abspath(template_file)}|{stat.st_mtime_ns}|{stat.st_size}"
        digest = hashlib.sha1(key.encode("utf-8", "surrogatepass")).hexdigest()
        cache_dir = os.path.join(self.get_output_dir(), "template_previews")
        return os.path.join(cache_dir, f"{digest}.png")

    def build_template_preview_image_from_file(self, image_file):
        if Image is None or not image_file or not os.path.exists(image_file):
            return None

        try:
            with Image.open(image_file) as preview:
                return self.fit_template_preview_image(preview)
        except Exception:
            return None

    def hide_template_preview(self):
        if not hasattr(self, "template_preview_label"):
            return

        try:
            self.template_preview_label.place_forget()
            self.template_preview_label.configure(image="", text="")
        finally:
            self._template_preview_photo = None

    def show_template_preview(self, preview_image):
        if preview_image is None or ImageTk is None:
            self.hide_template_preview()
            return

        preview_photo = ImageTk.PhotoImage(preview_image)
        self.template_preview_label.configure(image=preview_photo, text="")
        self.template_preview_label.place(x=0, y=0, relwidth=1, relheight=1)
        self._template_preview_photo = preview_photo

    def render_template_preview_async(self, template_file, cache_file, request_id):
        cache_file = os.path.abspath(cache_file)
        if cache_file in self._template_preview_rendering or cache_file in self._template_preview_failed:
            return

        self._template_preview_rendering.add(cache_file)

        def run():
            error = None
            try:
                os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                export_pptx_to_png(template_file, cache_file, long_edge_px=360)
            except Exception as e:
                error = e

            def on_done():
                self._template_preview_rendering.discard(cache_file)
                selected_file = self.get_selected_template_file()
                is_current = (
                    request_id == self._template_preview_request_id
                    and selected_file
                    and os.path.abspath(selected_file) == os.path.abspath(template_file)
                )

                if error is not None:
                    self._template_preview_failed.add(cache_file)
                    self.report_exception(
                        "template preview render",
                        error,
                        extra={"template_file": template_file, "cache_file": cache_file},
                    )
                    if is_current:
                        self.log(f"[경고] 템플릿 프리뷰를 만들지 못했습니다: {os.path.basename(template_file)}")
                    return

                if is_current:
                    self.show_template_preview(self.build_template_preview_image_from_file(cache_file))

            self.after(0, on_done)

        threading.Thread(target=run, daemon=True).start()

    def update_template_preview(self, *_):
        if not hasattr(self, "template_preview_label"):
            return

        self._template_preview_request_id += 1
        request_id = self._template_preview_request_id

        template_file = self.get_selected_template_file()
        if not template_file:
            self.hide_template_preview()
            return

        preview_image = self.build_template_preview_image(template_file)
        if preview_image is not None:
            self.show_template_preview(preview_image)
            return

        cache_file = self.get_template_preview_cache_file(template_file)
        preview_image = self.build_template_preview_image_from_file(cache_file)
        if preview_image is not None:
            self.show_template_preview(preview_image)
            return

        self.hide_template_preview()
        self.render_template_preview_async(template_file, cache_file, request_id)

    def get_selected_template_file(self):
        selected = self.template_files.get(self.template_var.get())
        if selected and os.path.exists(selected):
            return selected

        if TEMPLATE_FILE_NAME:
            fallback = self.find_asset_file(TEMPLATE_FILE_NAME)
            if fallback:
                return fallback

        templates = self.list_template_files()
        return templates[0][1] if templates else None

    def set_template_loading_state(self, loading, status_text=""):
        self._template_download_running = loading
        self._template_refresh_complete = status_text == "✓"
        if hasattr(self, "template_refresh_btn"):
            self.template_refresh_btn.configure(
                state="disabled" if loading else "normal",
                text=status_text or "↻",
                fg_color="transparent",
                border_width=0,
            )

    def animate_template_loading(self, index=0):
        if not self._template_download_running:
            return

        frames = ("◐", "◓", "◑", "◒")
        self.template_refresh_btn.configure(text=frames[index % len(frames)])
        self.after(160, lambda: self.animate_template_loading(index + 1))

    def on_template_refresh_enter(self, event=None):
        if self._template_refresh_complete and not self._template_download_running:
            self.template_refresh_btn.configure(text="↻")

    def on_template_refresh_leave(self, event=None):
        if self._template_refresh_complete and not self._template_download_running:
            self.template_refresh_btn.configure(text="✓")

    def ensure_templates_async(self, force=False):
        if self._template_download_running:
            return

        self.set_template_loading_state(True)
        self.animate_template_loading()

        def run():
            status_text = "✓"
            try:
                target_dir = self.get_template_download_dir()
                before = {
                    path
                    for _, path in self.list_template_files()
                    if os.path.abspath(path).startswith(os.path.abspath(target_dir))
                }

                self.after(0, lambda: self.log("[안내] 템플릿 저장소를 확인합니다."))

                try:
                    import gdown
                except ImportError:
                    status_text = "!"
                    self.after(
                        0,
                        lambda: self.log("[오류] 템플릿 자동 다운로드에 필요한 gdown 패키지가 없습니다."),
                    )
                    return

                try:
                    gdown.download_folder(
                        TEMPLATE_DOWNLOAD_URL,
                        output=target_dir,
                        quiet=True,
                        use_cookies=False,
                        resume=True,
                        remaining_ok=True,
                    )
                except TypeError:
                    gdown.download_folder(
                        TEMPLATE_DOWNLOAD_URL,
                        output=target_dir,
                        quiet=True,
                        use_cookies=False,
                        resume=True,
                    )

                after = {
                    path
                    for _, path in self.list_template_files()
                    if os.path.abspath(path).startswith(os.path.abspath(target_dir))
                }
                added = sorted(os.path.basename(path) for path in after - before)

                def on_done():
                    self.refresh_template_options()
                    if added:
                        self.log(f"[완료] 새 템플릿 {len(added)}개를 다운로드했습니다: {', '.join(added)}")
                    elif force:
                        self.log("[안내] 템플릿 목록을 최신 상태로 갱신했습니다.")
                    else:
                        self.log("[안내] 템플릿 목록을 확인했습니다.")
                self.after(0, on_done)
            except Exception as e:
                status_text = "!"
                err = e
                self.report_exception("template download", err)
                self.after(0, lambda: self.log(f"[오류] 템플릿 다운로드에 실패했습니다: {err}"))
            finally:
                self.after(0, lambda text=status_text: self.set_template_loading_state(False, text))

        threading.Thread(target=run, daemon=True).start()

    def resolve_font_family(self, candidates):
        available_fonts = set(tkfont.families(self))
        for candidate in candidates:
            if candidate in available_fonts:
                return candidate
        return "맑은 고딕"

    def create_logo_label(self, parent):
        logo_file = self.find_asset_file(LOGO_FILE_NAME)
        if logo_file and Image is not None:
            try:
                logo_image = Image.open(logo_file).convert("RGBA")
                max_width = LOGO_SIZE[0] * LOGO_DISPLAY_SCALE
                max_height = LOGO_SIZE[1] * LOGO_DISPLAY_SCALE
                scale = min(max_width / logo_image.width, max_height / logo_image.height, 1)
                display_size = (
                    max(1, int(logo_image.width * scale)),
                    max(1, int(logo_image.height * scale)),
                )
                self._logo_image = ctk.CTkImage(
                    light_image=logo_image,
                    dark_image=logo_image,
                    size=display_size,
                )
                return ctk.CTkLabel(parent, image=self._logo_image, text="")
            except Exception:
                pass

        return ctk.CTkLabel(
            parent,
            text=APP_DISPLAY_NAME,
            text_color=TITLE_FG,
            font=(self.brand_font_family, 32, "bold"),
        )

    def setup_style(self):
        ctk.set_appearance_mode("light")
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

    def create_widgets(self):
        # Canvas renders the background image / gradient only.
        # place() so the content overlay can sit on top without geometry-manager conflicts.
        self.background_canvas = tk.Canvas(self, bd=0, highlightthickness=0)
        self.background_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.background_canvas.bind(
            "<Configure>", lambda e: self.draw_background(e.width, e.height)
        )

        # Content overlay — owns all widget layout via CTk-native grid.
        content = ctk.CTkFrame(self, fg_color=APP_BG, bg_color=APP_BG, corner_radius=0, border_width=0)
        content.place(relx=0, rely=0, relwidth=1, relheight=1)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)   # workspace row fills remaining space

        # --- Top bar ---
        top_bar = ctk.CTkFrame(content, fg_color="transparent", bg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=44, pady=(22, 14))
        top_bar.columnconfigure(0, weight=1)

        brand_frame = ctk.CTkFrame(top_bar, fg_color="transparent", bg_color="transparent")
        brand_frame.grid(row=0, column=0, sticky=tk.W)

        self.create_logo_label(brand_frame).pack(anchor=tk.W)
        ctk.CTkLabel(
            brand_frame,
            text="레파토리와 가사를 정리해 파워포인트로 만듭니다.",
            text_color=MUTED_FG,
            font=("Segoe UI", 11),
        ).pack(anchor=tk.W, pady=(10, 0))

        right_panel = ctk.CTkFrame(top_bar, fg_color="transparent", bg_color="transparent")
        right_panel.grid(row=0, column=1, sticky=tk.NE)
        right_panel.columnconfigure(0, weight=1)

        self._create_right_menu_bar(right_panel)

        settings_frame = ctk.CTkFrame(right_panel, fg_color="transparent", bg_color="transparent")
        settings_frame.grid(row=1, column=0, sticky=tk.E, pady=(8, 0))
        settings_frame.columnconfigure(3, minsize=54)
        settings_frame.columnconfigure(5, minsize=34)
        settings_frame.columnconfigure(7, minsize=TEMPLATE_PREVIEW_WIDTH)

        ctk.CTkLabel(
            settings_frame,
            text="설정",
            text_color=TEXT_FG,
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=0, sticky=tk.NE, padx=(0, 18), pady=(8, 0))

        ctk.CTkLabel(
            settings_frame,
            text="슬라이드별 최대 줄 수",
            text_color=TEXT_FG,
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=1, sticky=tk.E, pady=4)

        self.max_lines_var = tk.StringVar(value=str(DEFAULT_MAX_LINES_PER_SLIDE))
        ctk.CTkEntry(
            settings_frame,
            textvariable=self.max_lines_var,
            width=72,
            height=34,
            corner_radius=12,
            border_width=1,
            border_color=PANEL_BORDER,
            fg_color=TEXT_BG,
            bg_color="transparent",
            text_color=TEXT_FG,
            justify=tk.CENTER,
            font=("Segoe UI", 12),
        ).grid(row=0, column=2, sticky=tk.W, padx=(8, 0), pady=4)

        ctk.CTkLabel(
            settings_frame,
            text="줄별 최대 글자 수",
            text_color=TEXT_FG,
            font=("Segoe UI", 12, "bold"),
        ).grid(row=1, column=1, sticky=tk.E, pady=4)

        self.max_chars_var = tk.StringVar(value=str(DEFAULT_MAX_CHARS_PER_LINE))
        ctk.CTkEntry(
            settings_frame,
            textvariable=self.max_chars_var,
            width=72,
            height=34,
            corner_radius=12,
            border_width=1,
            border_color=PANEL_BORDER,
            fg_color=TEXT_BG,
            bg_color="transparent",
            text_color=TEXT_FG,
            justify=tk.CENTER,
            font=("Segoe UI", 12),
        ).grid(row=1, column=2, sticky=tk.W, padx=(8, 0), pady=4)

        ctk.CTkLabel(
            settings_frame,
            text="가사 크기",
            text_color=TEXT_FG,
            font=("Segoe UI", 12, "bold"),
        ).grid(row=2, column=1, sticky=tk.E, pady=4)

        self.lyrics_font_size_var = tk.StringVar(value=DEFAULT_LYRICS_FONT_SIZE or "기본")
        ctk.CTkEntry(
            settings_frame,
            textvariable=self.lyrics_font_size_var,
            width=72,
            height=34,
            corner_radius=12,
            border_width=1,
            border_color=PANEL_BORDER,
            fg_color=TEXT_BG,
            bg_color="transparent",
            text_color=TEXT_FG,
            justify=tk.CENTER,
            font=("Segoe UI", 12),
        ).grid(row=2, column=2, sticky=tk.W, padx=(8, 0), pady=4)

        ctk.CTkLabel(
            settings_frame,
            text="템플릿",
            text_color=TEXT_FG,
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=4, sticky=tk.E, pady=4)

        self.template_var = tk.StringVar(value="")
        self.template_refresh_slot = ctk.CTkFrame(
            settings_frame,
            width=34,
            height=34,
            fg_color="transparent",
            bg_color="transparent",
        )
        self.template_refresh_slot.grid(row=0, column=5, sticky=tk.E, padx=(8, 6), pady=4)
        self.template_refresh_slot.grid_propagate(False)

        self.template_refresh_btn = ctk.CTkButton(
            self.template_refresh_slot,
            text="↻",
            command=lambda: self.ensure_templates_async(force=True),
            width=34,
            height=34,
            corner_radius=12,
            fg_color="transparent",
            bg_color="transparent",
            hover=False,
            text_color=TEXT_FG,
            border_width=0,
            font=("Segoe UI", 15, "bold"),
        )
        self.template_refresh_btn.bind("<Enter>", self.on_template_refresh_enter)
        self.template_refresh_btn.bind("<Leave>", self.on_template_refresh_leave)
        self.template_refresh_slot.bind("<Enter>", self.on_template_refresh_enter)
        self.template_refresh_slot.bind("<Leave>", self.on_template_refresh_leave)
        self.template_refresh_btn.place(x=0, y=0, relwidth=1, relheight=1)

        self.template_combo = ctk.CTkComboBox(
            settings_frame,
            values=["템플릿 확인 중"],
            variable=self.template_var,
            command=self.update_template_preview,
            width=190,
            height=34,
            corner_radius=12,
            border_width=1,
            border_color=PANEL_BORDER,
            button_color=ACCENT,
            button_hover_color=ACCENT_DARK,
            fg_color=TEXT_BG,
            bg_color="transparent",
            text_color=TEXT_FG,
            font=("맑은 고딕", 11),
            dropdown_font=("맑은 고딕", 11),
            dropdown_fg_color=TEXT_BG,
            dropdown_text_color=TEXT_FG,
            dropdown_hover_color=ACCENT_SOFT,
        )
        self.template_combo.grid(row=0, column=6, sticky=tk.E, padx=(0, 6), pady=4)

        self.template_preview_slot = ctk.CTkFrame(
            settings_frame,
            width=TEMPLATE_PREVIEW_WIDTH,
            height=TEMPLATE_PREVIEW_HEIGHT,
            fg_color="transparent",
            bg_color="transparent",
        )
        self.template_preview_slot.grid(row=0, column=7, sticky=tk.W, padx=(0, 0), pady=4)
        self.template_preview_slot.grid_propagate(False)

        self._template_preview_photo = None
        self.template_preview_label = tk.Label(
            self.template_preview_slot,
            text="",
            bd=0,
            highlightthickness=0,
            bg=APP_BG,
        )

        ctk.CTkLabel(
            settings_frame,
            text="PPT 서버",
            text_color=TEXT_FG,
            font=("Segoe UI", 12, "bold"),
        ).grid(row=1, column=4, sticky=tk.E, pady=4)

        self.server_url_var = tk.StringVar(value=DEFAULT_SERVER_URL)
        ctk.CTkEntry(
            settings_frame,
            textvariable=self.server_url_var,
            placeholder_text=DEFAULT_SERVER_URL,
            width=190,
            height=34,
            corner_radius=12,
            border_width=1,
            border_color=PANEL_BORDER,
            fg_color=TEXT_BG,
            bg_color="transparent",
            text_color=TEXT_FG,
            font=("Segoe UI", 11),
        ).grid(row=1, column=6, sticky=tk.E, padx=(4, 6), pady=4)

        ctk.CTkLabel(
            settings_frame,
            text="DB 이력 불러오기",
            text_color=TEXT_FG,
            font=("Segoe UI", 12, "bold"),
        ).grid(row=2, column=4, sticky=tk.E, pady=4)

        ctk.CTkButton(
            settings_frame,
            text="↻",
            command=self.reset_loaded_history,
            width=34,
            height=34,
            corner_radius=17,
            fg_color="transparent",
            bg_color="transparent",
            hover_color=ACCENT_SOFT,
            text_color=TEXT_FG,
            border_width=1,
            border_color=PANEL_BORDER,
            font=("Segoe UI", 14, "bold"),
        ).grid(row=2, column=5, sticky=tk.E, padx=(8, 6), pady=4)

        self.history_load_panel = ctk.CTkFrame(
            settings_frame,
            fg_color=PANEL_SOFT_BG,
            bg_color="transparent",
            corner_radius=12,
            border_width=1,
            border_color=PANEL_BORDER,
        )
        self.history_load_panel.grid(row=2, column=6, columnspan=2, sticky="ew", padx=(0, 0), pady=(4, 2))
        self.history_load_panel.columnconfigure(0, weight=1)

        self.history_search_entry = ctk.CTkEntry(
            self.history_load_panel,
            textvariable=self.history_search_var,
            placeholder_text="주차/기간 검색...",
            width=190,
            height=30,
            corner_radius=10,
            border_width=1,
            border_color=PANEL_BORDER,
            fg_color=TEXT_BG,
            bg_color="transparent",
            text_color=TEXT_FG,
            font=("맑은 고딕", 10),
        )
        self.history_search_entry.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        self.history_search_entry.bind("<KeyRelease>", self.on_history_search_keyrelease)

        self.history_dropdown = ttk.Combobox(
            self.history_load_panel,
            textvariable=self.history_select_var,
            state="readonly",
            values=["저장된 DB 이력이 없습니다"],
        )
        self.history_dropdown.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))

        self.history_load_btn = ctk.CTkButton(
            self.history_load_panel,
            text="선택 이력 불러오기",
            command=self.load_selected_history_item,
            height=28,
            corner_radius=8,
            fg_color=ACCENT_SOFT,
            hover_color=ACCENT,
            text_color=TEXT_FG,
            border_width=1,
            border_color=PANEL_BORDER,
            font=("맑은 고딕", 10, "bold"),
        )
        self.history_load_btn.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))

        # --- Workspace ---
        workspace_frame = ctk.CTkFrame(content, fg_color="transparent", bg_color="transparent")
        workspace_frame.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 8))
        workspace_frame.columnconfigure(0, weight=4)
        workspace_frame.columnconfigure(1, weight=5)
        workspace_frame.rowconfigure(0, weight=1)

        sequence_frame = ctk.CTkFrame(
            workspace_frame, fg_color=PANEL_BG, bg_color="transparent", corner_radius=16,
        )
        sequence_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        sequence_frame.rowconfigure(1, weight=0)
        sequence_frame.rowconfigure(3, weight=1)
        sequence_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            sequence_frame,
            text="레파토리 입력",
            text_color=TEXT_FG,
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, sticky=tk.W, padx=18, pady=(16, 10))

        sequence_input_frame = ctk.CTkFrame(
            sequence_frame,
            fg_color="transparent",
            bg_color="transparent",
            corner_radius=0,
        )
        sequence_input_frame.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))
        sequence_input_frame.columnconfigure(0, weight=0)
        sequence_input_frame.columnconfigure(1, weight=0)
        sequence_input_frame.columnconfigure(2, weight=1)

        ctk.CTkButton(
            sequence_input_frame,
            text="레파토리 입력하기",
            command=self.open_repertoire_input_dialog,
            width=140,
            height=34,
            corner_radius=10,
            fg_color="#ffffff",
            bg_color="transparent",
            hover_color=ACCENT_SOFT,
            text_color=TEXT_FG,
            border_width=1,
            border_color=ACCENT,
            font=("맑은 고딕", 11, "bold"),
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            sequence_input_frame,
            text="🔍 DB에서 추가",
            command=self.open_lyrics_search_dialog,
            width=120,
            height=34,
            corner_radius=10,
            fg_color=ACCENT_SOFT,
            bg_color="transparent",
            hover_color=ACCENT,
            text_color=TEXT_FG,
            border_width=1,
            border_color=ACCENT,
            font=("맑은 고딕", 11),
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))

        self.repertoire_summary_var = tk.StringVar(value="입력된 레파토리 없음")
        ctk.CTkLabel(
            sequence_input_frame,
            textvariable=self.repertoire_summary_var,
            text_color=MUTED_FG,
            font=("맑은 고딕", 11),
            anchor="w",
            justify=tk.LEFT,
        ).grid(row=0, column=2, sticky="w", padx=(12, 0))

        ctk.CTkLabel(
            sequence_frame,
            text="붙여넣으면 자동 정리됩니다. 아래 목록에서 드래그로 순서 변경, 더블클릭으로 수정",
            text_color=MUTED_FG,
            font=("맑은 고딕", 10),
            anchor="w",
            justify=tk.LEFT,
        ).grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 8))

        self.repertoire_sort_scroll = ctk.CTkScrollableFrame(
            sequence_frame,
            fg_color=PANEL_SOFT_BG,
            bg_color="transparent",
            corner_radius=14,
            scrollbar_button_color=ACCENT,
            scrollbar_button_hover_color=ACCENT_DARK,
            height=170,
        )
        self.repertoire_sort_scroll.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 16))
        self.repertoire_sort_scroll.columnconfigure(0, weight=1)
        self.refresh_repertoire_sort_list()

        lyrics_frame = ctk.CTkFrame(
            workspace_frame, fg_color=PANEL_BG, bg_color="transparent", corner_radius=16,
        )
        lyrics_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        lyrics_frame.columnconfigure(0, weight=0)
        lyrics_frame.columnconfigure(1, weight=1)
        lyrics_frame.columnconfigure(2, weight=0)
        lyrics_frame.rowconfigure(1, weight=1)

        ctk.CTkLabel(
            lyrics_frame,
            text="가사 편집",
            text_color=TEXT_FG,
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, sticky=tk.W, padx=18, pady=(16, 10))
        ctk.CTkLabel(
            lyrics_frame,
            textvariable=self.current_song_var,
            text_color=MUTED_FG,
            font=("맑은 고딕", 12),
        ).grid(row=0, column=1, sticky=tk.W, padx=(0, 18), pady=(16, 10))

        self.reload_current_lyrics_btn = ctk.CTkButton(
            lyrics_frame,
            text="⟳",
            command=self.reload_current_song_lyrics_from_history,
            width=30,
            height=30,
            corner_radius=15,
            fg_color="transparent",
            bg_color="transparent",
            hover_color=ACCENT_SOFT,
            text_color=TEXT_FG,
            border_width=1,
            border_color=PANEL_BORDER,
            font=("Segoe UI", 13, "bold"),
        )
        self.reload_current_lyrics_btn.grid(row=0, column=2, sticky=tk.E, padx=(0, 14), pady=(12, 10))

        self.song_scroll = ctk.CTkScrollableFrame(
            lyrics_frame,
            fg_color=PANEL_SOFT_BG,
            bg_color="transparent",
            corner_radius=16,
            scrollbar_button_color=ACCENT,
            scrollbar_button_hover_color=ACCENT_DARK,
            width=175,
        )
        self.song_scroll.grid(row=1, column=0, sticky="ns", padx=(18, 10), pady=(0, 18))
        self.song_scroll.columnconfigure(0, weight=1)
        self.song_buttons = []
        self.selected_song_index = None

        self.lyrics_text = ctk.CTkTextbox(
            lyrics_frame,
            fg_color=TEXT_BG,
            bg_color="transparent",
            text_color=TEXT_FG,
            border_color=PANEL_BORDER,
            border_width=1,
            corner_radius=16,
            wrap=tk.WORD,
            font=("맑은 고딕", 12),
        )
        self.lyrics_text.grid(row=1, column=1, sticky="nsew", padx=(0, 18), pady=(0, 18))
        self.lyrics_text.tag_config("placeholder", foreground="#9aa3af")
        self.lyrics_text.bind("<FocusIn>", self.on_lyrics_focus_in)
        self.lyrics_text.bind("<FocusOut>", self.on_lyrics_focus_out)
        self.lyrics_text.bind("<<Modified>>", self.on_lyrics_modified)
        self.show_lyrics_guide()

        # --- Action bar ---
        action_frame = ctk.CTkFrame(
            content,
            fg_color=PANEL_BG,
            bg_color="transparent",
            corner_radius=16,
            border_width=1,
            border_color=PANEL_BORDER,
        )
        action_frame.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 6))

        self.refresh_btn = ctk.CTkButton(
            action_frame,
            text="레파토리 인식",
            command=lambda: self.refresh_song_list(trigger_download=True),
            width=160, height=42, corner_radius=12,
            fg_color="#ffffff", bg_color="transparent", hover_color=ACCENT_SOFT,
            text_color=TEXT_FG, border_width=1, border_color=ACCENT,
            font=("Segoe UI", 13, "bold"),
        )
        self.refresh_btn.pack(side=tk.LEFT, padx=(10, 6), pady=10)


        self.generate_btn = ctk.CTkButton(
            action_frame,
            text="파워포인트 생성",
            command=self.generate_ppt,
            width=168, height=42, corner_radius=12,
            fg_color=ACCENT, bg_color="transparent", hover_color="#efc4d0",
            text_color=TEXT_FG, border_width=1, border_color=ACCENT_DARK,
            font=("Segoe UI", 13, "bold"),
        )
        self.generate_btn.pack(side=tk.RIGHT, padx=(6, 10), pady=10)

        self.songlist_btn = ctk.CTkButton(
            action_frame,
            text="송리스트 카드 생성",
            command=self.generate_songlist_card,
            width=168, height=42, corner_radius=12,
            fg_color="#ffffff", bg_color="transparent", hover_color=ACCENT_SOFT,
            text_color=TEXT_FG, border_width=1, border_color=ACCENT,
            font=("Segoe UI", 13, "bold"),
        )
        self.songlist_btn.pack(side=tk.RIGHT, padx=6, pady=10)

    def draw_background(self, width, height):
        self.background_canvas.delete("background")
        background_file = self.find_background_file()

        if background_file:
            self.draw_background_image(width, height, background_file)
            self.background_canvas.tag_lower("background")
            return

        split = max(1, int(height * 0.55))

        for y in range(height):
            if y < split:
                color = blend_hex(GRADIENT_TOP, GRADIENT_MID, y / split)
            else:
                color = blend_hex(GRADIENT_MID, GRADIENT_BOTTOM, (y - split) / max(1, height - split))
            self.background_canvas.create_line(0, y, width, y, fill=color, tags=("background",))

        self.background_canvas.create_oval(
            int(width * 0.58),
            int(height * 0.52),
            int(width * 1.18),
            int(height * 1.18),
            fill="#eadcf4",
            outline="",
            tags=("background",),
        )
        self.background_canvas.create_oval(
            -int(width * 0.20),
            int(height * 0.36),
            int(width * 0.38),
            int(height * 1.12),
            fill="#dfcaef",
            outline="",
            tags=("background",),
        )
        self.background_canvas.tag_lower("background")

    def draw_background_image(self, width, height, background_file):
        cache_key = (background_file, width, height)

        if Image is not None and ImageTk is not None:
            if self._background_cache_key != cache_key:
                with Image.open(background_file) as source_image:
                    source_image = source_image.convert("RGB")
                    image_ratio = source_image.width / source_image.height
                    target_ratio = width / max(1, height)

                    if image_ratio > target_ratio:
                        new_height = height
                        new_width = max(width, int(height * image_ratio))
                    else:
                        new_width = width
                        new_height = max(height, int(width / image_ratio))

                    resized = source_image.resize((new_width, new_height), Image.LANCZOS)
                    left = max(0, (new_width - width) // 2)
                    top = max(0, (new_height - height) // 2)
                    cropped = resized.crop((left, top, left + width, top + height))

                    palette_overlay = Image.new("RGB", (1, height), PANEL_BG)
                    palette_overlay.putdata(
                        [
                            hex_to_rgb(blend_hex(GRADIENT_TOP, GRADIENT_BOTTOM, y / max(1, height - 1)))
                            for y in range(height)
                        ]
                    )
                    palette_overlay = palette_overlay.resize((width, height))

                    toned = Image.blend(cropped, palette_overlay, 0.38)
                    self._background_image = ImageTk.PhotoImage(toned)
                    self._background_cache_key = cache_key

            self.background_canvas.create_image(
                0,
                0,
                anchor=tk.NW,
                image=self._background_image,
                tags=("background",),
            )
            return

        try:
            self._background_image = tk.PhotoImage(file=background_file)
            self._background_cache_key = cache_key
            self.background_canvas.create_image(
                width // 2,
                height // 2,
                anchor=tk.CENTER,
                image=self._background_image,
                tags=("background",),
            )
        except tk.TclError:
            for y in range(height):
                color = blend_hex(GRADIENT_TOP, GRADIENT_BOTTOM, y / max(1, height))
                self.background_canvas.create_line(0, y, width, y, fill=color, tags=("background",))

    def log(self, message):
        if hasattr(self, "_recent_log_lines"):
            self._recent_log_lines.append(str(message))
            self._recent_log_lines = self._recent_log_lines[-30:]
        if hasattr(self, "log_area"):
            self.log_area.configure(state="normal")
            self.log_area.insert("end", message + "\n")
            self.log_area.see("end")
            self.log_area.configure(state="disabled")
            self.update_idletasks()

    def _create_right_menu_bar(self, parent):
        menu_frame = ctk.CTkFrame(parent, fg_color="transparent", bg_color="transparent")
        menu_frame.grid(row=0, column=0, sticky=tk.E)

        file_items = [
            ("작업 로그 다운로드", self.download_work_log),
            ("-", None),
            ("종료", self.on_close),
        ]
        tools_items = [
            ("레파토리 입력하기", self.open_repertoire_input_dialog),
            ("레파토리 인식", lambda: self.refresh_song_list(trigger_download=True)),
        ]
        log_items = [
            ("작업 로그 다운로드", self.download_work_log),
            ("로그 첨부 버그 리포트", self.report_bug_with_logs),
        ]
        help_items = [
            ("앱 정보", self.show_app_about),
        ]

        self._add_menu_button(menu_frame, "파일", file_items)
        self._add_menu_button(menu_frame, "도구", tools_items)
        self._add_menu_button(menu_frame, "로그", log_items)
        self._add_menu_button(menu_frame, "도움말", help_items)

        self._right_menu_frame = menu_frame

    def _add_menu_button(self, parent, title, items):
        btn = ctk.CTkButton(
            parent,
            text=f"{title} ▾",
            width=84,
            height=30,
            corner_radius=10,
            fg_color="#ffffff",
            bg_color="transparent",
            hover_color=ACCENT_SOFT,
            text_color=TEXT_FG,
            border_width=1,
            border_color=PANEL_BORDER,
            font=("맑은 고딕", 10, "bold"),
            command=None,
        )
        btn.configure(command=lambda b=btn, rows=items: self._open_menu_popup(b, rows))
        btn.pack(side=tk.RIGHT, padx=(6, 0), pady=(0, 2))

    def _open_menu_popup(self, button, items):
        popup = tk.Menu(self, tearoff=0)
        try:
            popup.configure(
                bg=TEXT_BG,
                fg=TEXT_FG,
                activebackground=ACCENT_SOFT,
                activeforeground=TEXT_FG,
                relief=tk.FLAT,
                borderwidth=1,
            )
        except Exception:
            pass

        for label, command in items:
            if label == "-":
                popup.add_separator()
            else:
                popup.add_command(label=label, command=command)

        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height() + 2
        try:
            popup.tk_popup(x, y)
        finally:
            popup.grab_release()

    def show_app_about(self):
        messagebox.showinfo(
            "앱 정보",
            "PPT Gen\n레파토리와 가사를 정리해 파워포인트를 생성합니다.",
        )

    def build_work_log_text(self):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"[{now}] PPT Gen 작업 로그",
            f"서버 URL: {self.get_server_url()}",
            f"현재 선택 곡: {self.current_song_title or '-'}",
            "",
            "[최근 로그]",
        ]
        lines.extend(getattr(self, "_recent_log_lines", []))
        return "\n".join(lines).strip() + "\n"

    def download_work_log(self, show_message=True):
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
            self,
            "서버 버그 리포트",
            "증상과 재현 방법을 입력하세요.\n(저장한 작업 로그가 함께 첨부됩니다)",
        )
        message = (dialog.result or "").strip()
        if not message:
            messagebox.showwarning("서버 버그 리포트", "버그 설명을 입력해 주세요.")
            return

        report = build_error_report(
            context="manual bug report",
            message=message,
            traceback_text="",
            extra={"log_file": os.path.abspath(log_path)},
            log_tail=getattr(self, "_recent_log_lines", []),
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
                if error is not None:
                    self.report_exception("manual bug report", error)
                    messagebox.showerror("서버 버그 리포트", f"리포트 전송에 실패했습니다.\n{error}")
                    return
                self.log("[완료] 서버에 버그 리포트를 전송했습니다.")
                messagebox.showinfo("서버 버그 리포트", "버그 리포트를 전송했습니다.")

            self.after(0, on_done)

        threading.Thread(target=run, daemon=True).start()

    def show_busy_dialog(self, title, message, on_cancel=None):
        self.hide_busy_dialog()
        self._busy_dialog = BusyDialog(self, title, message, on_cancel=on_cancel)
        self._busy_dialog.lift()

    def update_busy_dialog(self, message):
        if self._busy_dialog is not None:
            self._busy_dialog.set_message(message)

    def hide_busy_dialog(self):
        if self._busy_dialog is None:
            return
        try:
            self._busy_dialog.close()
        except tk.TclError:
            pass
        self._busy_dialog = None

    def get_manual_lyrics(self, song_title):
        dialog = MultilineDialog(self, "가사 직접 입력", f"'{song_title}' 가사를 입력하세요.")
        return dialog.result or ""

    def get_output_dir(self):
        output_dir = os.path.join(self.base_dir, "out")
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def get_history_cache_file(self):
        return os.path.join(self.get_output_dir(), WEEKLY_HISTORY_CACHE_FILE_NAME)

    def get_history_db_file(self):
        return os.path.join(self.get_output_dir(), WEEKLY_HISTORY_DB_FILE_NAME)

    def load_local_weekly_history(self):
        cache_file = self.get_history_cache_file()
        if not os.path.exists(cache_file):
            self.weekly_history_items = []
            return

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self.weekly_history_items = data
            else:
                self.weekly_history_items = []
        except Exception as e:
            self.weekly_history_items = []
            self.report_exception("weekly history load", e, extra={"cache_file": cache_file})

    def save_local_weekly_history(self, items):
        cache_file = self.get_history_cache_file()
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

    def sync_weekly_history_from_server(self, log_result=False):
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
                self.render_weekly_history_accordion()
                if error is not None:
                    self.report_exception("weekly history auto sync", error)

            self.after(0, on_done)

        threading.Thread(target=run, daemon=True).start()

    def _sequence_text_from_entries(self, sequence_entries):
        chunks = []
        for entry in sequence_entries:
            if not isinstance(entry, dict):
                continue
            title = str(entry.get("title", "")).strip()
            sequence = str(entry.get("sequence", "")).strip()
            if not title or not sequence:
                continue
            chunks.append(f"{title}\n{sequence}")
        # 빈 줄을 넣어 곡 단위를 시각적으로 구분한다.
        return "\n\n".join(chunks).strip()

    def _history_option_label(self, item):
        week_start = str(item.get("week_start_date", "?"))
        week_end = str(item.get("week_end_date", "?"))
        sequence_entries = item.get("sequence_entries") if isinstance(item, dict) else []
        song_count = len(sequence_entries) if isinstance(sequence_entries, list) else 0
        return f"{week_start} ~ {week_end} ({song_count}곡)"

    def on_history_search_keyrelease(self, event=None):
        self.render_weekly_history_accordion()

    def load_selected_history_item(self):
        selected = self.history_select_var.get().strip()
        if not selected:
            messagebox.showinfo("DB 이력 불러오기", "불러올 이력을 먼저 선택하세요.")
            return

        item = self.history_option_items.get(selected)
        if item is None:
            messagebox.showinfo("DB 이력 불러오기", "선택한 이력을 찾을 수 없습니다.")
            return

        self.apply_weekly_history_item(item)

    def _clean_repertoire_title(self, value):
        text = str(value or "").strip()
        text = re.sub(r"^\s*\d+\s*[\.)]\s*", "", text)
        return text.strip()

    def _normalize_repertoire_entries(self, raw_text):
        lines = [line.strip() for line in str(raw_text or "").splitlines() if line.strip()]
        entries = []
        idx = 0
        while idx + 1 < len(lines):
            title = self._clean_repertoire_title(lines[idx])
            sequence = lines[idx + 1].strip()
            if title and sequence:
                entries.append((title, sequence))
            idx += 2
        return entries

    def _format_repertoire_entries(self, entries):
        rows = []
        for title, sequence in entries:
            rows.append(str(title).strip())
            rows.append(str(sequence).strip())
        return "\n".join(rows).strip()

    def _update_repertoire_summary(self):
        count = len(self.repertoire_entries)
        if count <= 0:
            self.repertoire_summary_var.set("입력된 레파토리 없음")
            return
        self.repertoire_summary_var.set(f"총 {count}곡")

    def open_repertoire_input_dialog(self):
        initial_text = self._format_repertoire_entries(self.repertoire_entries)
        dialog = MultilineDialog(
            self,
            "레파토리 입력",
            "한 곡당 2줄(제목/진행순서)로 입력하세요.\n예)\n한나의 노래\nI-V1-V2-C",
            initial_text=initial_text,
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
        """가사 DB 검색 다이얼로그를 열고, 선택된 항목을 레파토리에 추가합니다."""
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
            # 진행 순서가 없으면 편집 다이얼로그로 직접 입력 유도
            dialog2 = MultilineDialog(
                self,
                "진행 순서 입력",
                f"'{title}'의 진행 순서를 입력하세요.\n예) I-V1-V2-C-C",
                initial_text="",
            )
            sequence = (dialog2.result or "").strip().splitlines()[0].strip() if dialog2.result else ""

        if not sequence:
            messagebox.showwarning("DB에서 추가", "진행 순서가 없어 추가하지 않았습니다.")
            return

        # 이미 있는 곡이면 순서 업데이트
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


        self._sequence_syncing = True
        self.sequence_placeholder_visible = not bool(self.repertoire_entries)
        self._sequence_syncing = False
        self._update_repertoire_summary()

    def _repertoire_target_index_by_y(self, y_root):
        if not self._repertoire_row_frames:
            return 0
        for index, frame in enumerate(self._repertoire_row_frames):
            midpoint = frame.winfo_rooty() + (frame.winfo_height() // 2)
            if y_root < midpoint:
                return index
        return len(self._repertoire_row_frames) - 1

    def _on_repertoire_row_press(self, index, event=None):
        self._repertoire_drag_from_index = index
        self._repertoire_drag_target_index = index
        self._repertoire_drag_start_x = event.x_root if event is not None else None
        self._repertoire_drag_start_y = event.y_root if event is not None else None
        self._repertoire_drag_active = False
        self._set_repertoire_drag_cursor("hand2")
        self._apply_repertoire_drag_visuals()

    def _on_repertoire_row_motion(self, _index, event=None):
        if self._repertoire_drag_from_index is None or event is None:
            return

        if not self._repertoire_drag_active:
            if self._repertoire_drag_start_x is None or self._repertoire_drag_start_y is None:
                return
            moved_x = abs(event.x_root - self._repertoire_drag_start_x)
            moved_y = abs(event.y_root - self._repertoire_drag_start_y)
            if max(moved_x, moved_y) < 6:
                return
            self._repertoire_drag_active = True
            self._set_repertoire_drag_cursor("fleur")
            self._create_repertoire_drag_ghost(self._repertoire_drag_from_index, event)

        self._repertoire_drag_target_index = self._repertoire_target_index_by_y(event.y_root)
        self._move_repertoire_drag_ghost(event)
        self._apply_repertoire_drag_visuals()

    def _on_repertoire_row_release(self, _index, event=None):
        if self._repertoire_drag_from_index is None or event is None:
            self._repertoire_drag_from_index = None
            self._repertoire_drag_target_index = None
            self._repertoire_drag_start_x = None
            self._repertoire_drag_start_y = None
            self._repertoire_drag_active = False
            self._set_repertoire_drag_cursor("hand2")
            self._destroy_repertoire_drag_ghost()
            self._apply_repertoire_drag_visuals()
            return

        if not self._repertoire_drag_active:
            self._repertoire_drag_from_index = None
            self._repertoire_drag_target_index = None
            self._repertoire_drag_start_x = None
            self._repertoire_drag_start_y = None
            self._set_repertoire_drag_cursor("hand2")
            self._destroy_repertoire_drag_ghost()
            self._apply_repertoire_drag_visuals()
            return

        target_index = self._repertoire_target_index_by_y(event.y_root)
        source_index = self._repertoire_drag_from_index
        self._repertoire_drag_from_index = None
        self._repertoire_drag_target_index = None
        self._repertoire_drag_start_x = None
        self._repertoire_drag_start_y = None
        self._repertoire_drag_active = False
        self._set_repertoire_drag_cursor("hand2")
        self._destroy_repertoire_drag_ghost()

        if source_index == target_index:
            self._apply_repertoire_drag_visuals()
            return
        if source_index < 0 or source_index >= len(self.repertoire_entries):
            self._apply_repertoire_drag_visuals()
            return
        if target_index < 0 or target_index >= len(self.repertoire_entries):
            self._apply_repertoire_drag_visuals()
            return

        moved = self.repertoire_entries.pop(source_index)
        self.repertoire_entries.insert(target_index, moved)
        self.refresh_repertoire_sort_list()
        self.sync_sequence_text_from_repertoire()
        self._flash_repertoire_row(target_index)

    def _create_repertoire_drag_ghost(self, index, event=None):
        self._destroy_repertoire_drag_ghost()
        if index < 0 or index >= len(self.repertoire_entries):
            return

        title, sequence = self.repertoire_entries[index]
        short_title = str(title).strip()
        short_sequence = str(sequence).strip()
        if len(short_title) > 18:
            short_title = short_title[:18] + "..."
        if len(short_sequence) > 24:
            short_sequence = short_sequence[:24] + "..."

        ghost = tk.Toplevel(self)
        ghost.overrideredirect(True)
        ghost.attributes("-topmost", True)
        try:
            ghost.attributes("-alpha", 0.93)
        except Exception:
            pass

        ghost.configure(bg=ACCENT_DARK)
        label = tk.Label(
            ghost,
            text=f"☰ {short_title}\n{short_sequence}",
            bg=ACCENT_SOFT,
            fg=TEXT_FG,
            justify=tk.LEFT,
            anchor="w",
            padx=10,
            pady=6,
            font=("맑은 고딕", 10, "bold"),
        )
        label.pack(fill=tk.BOTH, expand=True)

        self._repertoire_drag_ghost = ghost
        if event is not None:
            self._move_repertoire_drag_ghost(event)

    def _move_repertoire_drag_ghost(self, event):
        if self._repertoire_drag_ghost is None or event is None:
            return
        x = int(event.x_root + 16)
        y = int(event.y_root + 12)
        self._repertoire_drag_ghost.geometry(f"+{x}+{y}")

    def _destroy_repertoire_drag_ghost(self):
        if self._repertoire_drag_ghost is None:
            return
        try:
            self._repertoire_drag_ghost.destroy()
        except Exception:
            pass
        self._repertoire_drag_ghost = None

    def _set_repertoire_drag_cursor(self, cursor_name):
        for frame in self._repertoire_row_frames:
            frame.configure(cursor=cursor_name)
            for child in frame.winfo_children():
                try:
                    child.configure(cursor=cursor_name)
                except Exception:
                    pass

    def _apply_repertoire_drag_visuals(self):
        source_index = self._repertoire_drag_from_index
        target_index = self._repertoire_drag_target_index
        for index, frame in enumerate(self._repertoire_row_frames):
            border_color = PANEL_BORDER
            fg_color = TEXT_BG
            border_width = 1
            marker = f"{index + 1}"
            if source_index is not None and index == source_index:
                border_color = ACCENT
                fg_color = ACCENT_SOFT
                border_width = 2
                marker = "☰"
            elif target_index is not None and index == target_index:
                border_color = ACCENT_DARK
                border_width = 2
                marker = "↓"
            frame.configure(border_color=border_color, fg_color=fg_color, border_width=border_width)
            if index < len(self._repertoire_row_no_labels):
                self._repertoire_row_no_labels[index].configure(text=marker)

    def _flash_repertoire_row(self, index, step=0):
        if index < 0 or index >= len(self._repertoire_row_frames):
            return
        frame = self._repertoire_row_frames[index]
        if step == 0:
            frame.configure(border_color=ACCENT, fg_color=ACCENT_SOFT)
            self.after(80, lambda: self._flash_repertoire_row(index, step=1))
            return
        if step == 1:
            frame.configure(border_color=PANEL_BORDER, fg_color=TEXT_BG)
            self.after(70, lambda: self._flash_repertoire_row(index, step=2))
            return
        frame.configure(border_color=ACCENT_DARK, fg_color=TEXT_BG)
        self.after(70, lambda: frame.configure(border_color=PANEL_BORDER, fg_color=TEXT_BG))

    def edit_repertoire_item(self, index):
        if index < 0 or index >= len(self.repertoire_entries):
            return

        title, sequence = self.repertoire_entries[index]
        dialog = MultilineDialog(
            self,
            "레파토리 수정",
            "첫 줄: 곡 제목\n둘째 줄: 진행 순서",
            initial_text=f"{title}\n{sequence}",
        )
        edited = (dialog.result or "").strip()
        if not edited:
            return

        lines = [line.strip() for line in edited.splitlines() if line.strip()]
        if len(lines) < 2:
            messagebox.showwarning("레파토리 수정", "두 줄(곡 제목/진행 순서)로 입력해 주세요.")
            return

        new_title = self._clean_repertoire_title(lines[0])
        new_sequence = lines[1]
        if not new_title or not new_sequence:
            messagebox.showwarning("레파토리 수정", "곡 제목과 진행 순서를 모두 입력해 주세요.")
            return

        self.repertoire_entries[index] = (new_title, new_sequence)
        self.refresh_repertoire_sort_list()
        self.sync_sequence_text_from_repertoire()

    def refresh_repertoire_sort_list(self):
        if not hasattr(self, "repertoire_sort_scroll"):
            return

        self._destroy_repertoire_drag_ghost()
        for child in self.repertoire_sort_scroll.winfo_children():
            child.destroy()
        self._repertoire_row_frames = []
        self._repertoire_row_no_labels = []

        if not self.repertoire_entries:
            ctk.CTkLabel(
                self.repertoire_sort_scroll,
                text="인식된 레파토리가 없습니다.",
                text_color=MUTED_FG,
                font=("맑은 고딕", 11),
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=8, pady=6)
            return

        for index, (title, sequence) in enumerate(self.repertoire_entries):
            row_frame = ctk.CTkFrame(
                self.repertoire_sort_scroll,
                fg_color=TEXT_BG,
                bg_color="transparent",
                corner_radius=10,
                border_width=1,
                border_color=PANEL_BORDER,
            )
            row_frame.grid(row=index, column=0, sticky="ew", padx=6, pady=(0, 8))
            row_frame.columnconfigure(1, weight=1)
            row_frame.columnconfigure(2, weight=0)

            no_label = ctk.CTkLabel(
                row_frame,
                text=f"{index + 1}",
                text_color=MUTED_FG,
                font=("Segoe UI", 11, "bold"),
                width=24,
            )
            no_label.grid(row=0, column=0, sticky="nw", padx=(10, 8), pady=(8, 6))

            title_label = ctk.CTkLabel(
                row_frame,
                text=title,
                text_color=TEXT_FG,
                font=("맑은 고딕", 11, "bold"),
                anchor="w",
                justify=tk.LEFT,
            )
            title_label.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=(8, 2))

            sequence_label = ctk.CTkLabel(
                row_frame,
                text=sequence,
                text_color=MUTED_FG,
                font=("맑은 고딕", 10),
                anchor="w",
                justify=tk.LEFT,
                wraplength=360,
            )
            sequence_label.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=(0, 8))

            edit_btn = ctk.CTkButton(
                row_frame,
                text="✎",
                width=28,
                height=28,
                corner_radius=14,
                fg_color="transparent",
                bg_color="transparent",
                hover_color=ACCENT_SOFT,
                text_color=TEXT_FG,
                border_width=1,
                border_color=PANEL_BORDER,
                font=("Segoe UI", 12, "bold"),
                command=lambda i=index: self.edit_repertoire_item(i),
            )
            edit_btn.grid(row=0, column=2, rowspan=2, sticky="ne", padx=(0, 8), pady=(8, 8))

            for widget in (row_frame, no_label, title_label, sequence_label):
                widget.configure(cursor="hand2")
                widget.bind("<ButtonPress-1>", lambda e, i=index: self._on_repertoire_row_press(i, e))
                widget.bind("<B1-Motion>", lambda e, i=index: self._on_repertoire_row_motion(i, e))
                widget.bind("<ButtonRelease-1>", lambda e, i=index: self._on_repertoire_row_release(i, e))
                widget.bind("<Double-Button-1>", lambda e, i=index: self.edit_repertoire_item(i))

            edit_btn.configure(cursor="hand2")

            self._repertoire_row_frames.append(row_frame)
            self._repertoire_row_no_labels.append(no_label)

        self._apply_repertoire_drag_visuals()

    def _reparse_sequence_text(self):
        if self.sequence_placeholder_visible:
            self.repertoire_entries = []
            self.refresh_repertoire_sort_list()
            return

        raw = self.sequence_text.get("1.0", "end")
        entries = self._normalize_repertoire_entries(raw)
        if not entries:
            self.repertoire_entries = []
            self.refresh_repertoire_sort_list()
            return

        self.repertoire_entries = entries
        self.refresh_repertoire_sort_list()
        self.sync_sequence_text_from_repertoire()

    def on_sequence_modified(self, event=None):
        if self._sequence_syncing:
            self.sequence_text.edit_modified(False)
            return

        if not self.sequence_text.edit_modified():
            return

        self.sequence_text.edit_modified(False)
        if self._sequence_parse_after_id is not None:
            try:
                self.after_cancel(self._sequence_parse_after_id)
            except Exception:
                pass
        self._sequence_parse_after_id = self.after(250, self._reparse_sequence_text)

    def apply_weekly_history_item(self, item):
        sequence_entries = item.get("sequence_entries") if isinstance(item, dict) else None
        lyrics_by_title = item.get("lyrics_by_title") if isinstance(item, dict) else None
        if not isinstance(sequence_entries, list) or not isinstance(lyrics_by_title, dict):
            messagebox.showerror("DB 이력 불러오기", "선택한 주간 작업 이력 형식이 올바르지 않습니다.")
            return

        sequence_text = self._sequence_text_from_entries(sequence_entries)
        if not sequence_text:
            messagebox.showwarning("DB 이력 불러오기", "선택한 주간 작업 이력에 레파토리가 없습니다.")
            return

        self.sequence_text.configure(state="normal")
        self.sequence_text.delete("1.0", "end")
        self.sequence_text.insert("1.0", sequence_text)
        self.sequence_placeholder_visible = False
        self.repertoire_entries = self._normalize_repertoire_entries(sequence_text)
        self.refresh_repertoire_sort_list()

        self.lyrics_store = {str(k): str(v) for k, v in lyrics_by_title.items()}
        self._loaded_history_lyrics_by_title = dict(self.lyrics_store)
        self.refresh_song_list(show_message=False, trigger_download=False)

        week_start = item.get("week_start_date", "?")
        week_end = item.get("week_end_date", "?")
        self.log(f"[완료] 주간 작업 이력을 불러왔습니다: {week_start} ~ {week_end}")

    def reset_loaded_history(self):
        self.sequence_text.configure(state="normal")
        self.show_sequence_guide()
        self.sequence_entries = []
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
            messagebox.showinfo("가사 불러오기", f"'{self.current_song_title}'에 저장된 불러오기 이력이 없습니다.")
            return

        self.lyrics_store[self.current_song_title] = str(lyrics)
        self.set_lyrics_editor_text(str(lyrics))
        self.log(f"[완료] '{self.current_song_title}' 가사를 다시 불러왔습니다.")

    def get_server_url(self):
        return self.server_url_var.get().strip() or DEFAULT_SERVER_URL

    def _save_lyrics_to_catalog_async(self, song_title: str, lyrics: str):
        """가사를 백그라운드에서 서버 카탈로그에 저장합니다 (best-effort)."""
        if not song_title or not lyrics.strip():
            return
        server_url = self.get_server_url()
        sequence = dict(self.sequence_entries).get(song_title, "")

        def run():
            try:
                from ppt_server_client import save_lyrics_to_catalog, PptServerUnavailable
                save_lyrics_to_catalog(server_url, song_title, lyrics, source="manual", sequence=sequence)
            except Exception:
                pass  # best-effort: 서버 오프라인이면 조용히 무시

        threading.Thread(target=run, daemon=True).start()

    def get_max_lines_per_slide(self):
        try:
            return int(self.max_lines_var.get())
        except (TypeError, ValueError):
            return DEFAULT_MAX_LINES_PER_SLIDE

    def get_max_chars_per_line(self):
        try:
            return int(self.max_chars_var.get())
        except (TypeError, ValueError):
            return DEFAULT_MAX_CHARS_PER_LINE

    def get_lyrics_font_size(self):
        value = self.lyrics_font_size_var.get().strip()
        if not value or value == "기본":
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def open_output_file(self, file_path):
        try:
            if sys.platform == "win32":
                os.startfile(os.path.abspath(file_path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", file_path])
            else:
                subprocess.Popen(["xdg-open", file_path])
            return True
        except Exception as e:
            self.report_exception("open output file", e, extra={"file_path": file_path})
            self.log(f"[오류] 생성된 파일을 열지 못했습니다: {e}")
            return False

    def get_sequence_entries(self):
        if self.repertoire_entries:
            return [(title, sequence) for title, sequence in self.repertoire_entries]
        if self.sequence_placeholder_visible:
            raise ValueError("레파토리 입력창이 비어 있습니다.")
        sequence_text = self.sequence_text.get("1.0", "end")
        return parse_sequence_text(sequence_text)

    def set_action_buttons_state(self, state):
        self.refresh_btn.configure(state=state)
        self.generate_btn.configure(state=state)
        self.songlist_btn.configure(state=state)

    def set_editor_state(self, state):
        self.lyrics_text.configure(state=state)
        for _, btn in self.song_buttons:
            btn.configure(state=state)

    def show_sequence_guide(self):
        self.sequence_text.configure(state="normal")
        self.sequence_text.delete("1.0", "end")
        self.sequence_text.insert("1.0", SEQUENCE_GUIDE_TEXT, "placeholder")
        self.sequence_placeholder_visible = True
        self.repertoire_entries = []
        self.refresh_repertoire_sort_list()
        self.sequence_text.edit_modified(False)

    def clear_sequence_guide(self):
        if not self.sequence_placeholder_visible:
            return
        self.sequence_text.delete("1.0", "end")
        self.sequence_placeholder_visible = False
        self.sequence_text.edit_modified(False)

    def on_sequence_focus_in(self, event=None):
        self.clear_sequence_guide()

    def on_sequence_focus_out(self, event=None):
        if not self.sequence_text.get("1.0", "end").strip():
            self.show_sequence_guide()
            return
        self._reparse_sequence_text()

    def show_lyrics_guide(self):
        self.loading_lyrics = True
        self.lyrics_text.configure(state="normal")
        self.lyrics_text.delete("1.0", "end")
        self.lyrics_text.insert("1.0", LYRICS_GUIDE_TEXT, "placeholder")
        self.lyrics_placeholder_visible = True
        self.lyrics_text.edit_modified(False)
        self.loading_lyrics = False

    def clear_lyrics_guide(self):
        if not self.lyrics_placeholder_visible:
            return

        self.loading_lyrics = True
        self.lyrics_text.delete("1.0", "end")
        self.lyrics_placeholder_visible = False
        self.lyrics_text.edit_modified(False)
        self.loading_lyrics = False

    def set_lyrics_editor_text(self, text):
        self.loading_lyrics = True
        self.lyrics_text.configure(state="normal")
        self.lyrics_text.delete("1.0", "end")
        self.lyrics_text.insert("1.0", text)
        self.lyrics_placeholder_visible = False
        self.lyrics_text.edit_modified(False)
        self.loading_lyrics = False

    def get_lyrics_editor_text(self):
        if self.lyrics_placeholder_visible:
            return ""
        return self.lyrics_text.get("1.0", "end").strip()

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

    def _set_song_selection(self, index):
        if self.selected_song_index is not None and self.selected_song_index < len(self.song_buttons):
            _, btn = self.song_buttons[self.selected_song_index]
            btn.configure(fg_color="transparent", text_color=TEXT_FG, hover_color=ACCENT_SOFT)
        if index is not None and index < len(self.song_buttons):
            _, btn = self.song_buttons[index]
            btn.configure(fg_color=ACCENT, text_color=TEXT_FG, hover_color=ACCENT)
        self.selected_song_index = index

    def _on_song_item_click(self, index):
        if self.suppress_song_select:
            return
        if index >= len(self.song_buttons):
            return
        song_title = self.song_buttons[index][0]
        if song_title == self.current_song_title:
            return
        if self.current_song_title and not self.lyrics_placeholder_visible:
            lyrics = self.get_lyrics_editor_text()
            self.lyrics_store[self.current_song_title] = lyrics
            self._save_lyrics_to_catalog_async(self.current_song_title, lyrics)
        self._set_song_selection(index)
        self.load_lyrics_for_song(song_title)

    def populate_song_list(self, sequence_entries, preserve_current=True):
        previous_song = self.current_song_title if preserve_current else None
        selected_index = None

        self.suppress_song_select = True
        for _, btn in self.song_buttons:
            btn.destroy()
        self.song_buttons = []
        self.selected_song_index = None

        for index, (song_title, _) in enumerate(sequence_entries):
            btn = ctk.CTkButton(
                self.song_scroll,
                text=song_title,
                command=lambda idx=index: self._on_song_item_click(idx),
                anchor="w",
                fg_color="transparent",
                hover_color=ACCENT_SOFT,
                text_color=TEXT_FG,
                font=("맑은 고딕", 12),
                height=36,
                corner_radius=8,
            )
            btn.grid(row=index, column=0, sticky="ew", padx=6, pady=2)
            self.song_buttons.append((song_title, btn))

            if previous_song == song_title and selected_index is None:
                selected_index = index

        if selected_index is None and sequence_entries:
            selected_index = 0

        if selected_index is not None:
            self._set_song_selection(selected_index)

        self.suppress_song_select = False
        return selected_index

    def render_weekly_history_accordion(self):
        if not hasattr(self, "history_dropdown"):
            return

        items = self.weekly_history_items or []
        query = self.history_search_var.get().strip().lower() if hasattr(self, "history_search_var") else ""
        if query:
            filtered = [
                item
                for item in items
                if query in self._history_option_label(item).lower()
            ]
        else:
            filtered = list(items)

        self.history_filtered_items = filtered
        self.history_option_items = {}

        if not items:
            self.history_dropdown.configure(values=["저장된 DB 이력이 없습니다"])
            self.history_select_var.set("저장된 DB 이력이 없습니다")
            self.history_load_btn.configure(state="disabled")
            return

        if not filtered:
            self.history_dropdown.configure(values=["검색 결과 없음"])
            self.history_select_var.set("검색 결과 없음")
            self.history_load_btn.configure(state="disabled")
            return

        options = []
        for item in filtered:
            option = self._history_option_label(item)
            options.append(option)
            self.history_option_items[option] = item

        self.history_dropdown.configure(values=options)
        current = self.history_select_var.get().strip()
        if current not in self.history_option_items:
            self.history_select_var.set(options[0])
        self.history_load_btn.configure(state="normal")

    def restore_song_selection(self):
        self.suppress_song_select = True
        target_index = None
        if self.current_song_title:
            for index, (title, _) in enumerate(self.song_buttons):
                if title == self.current_song_title:
                    target_index = index
                    break
        self._set_song_selection(target_index)
        self.suppress_song_select = False

    def refresh_song_list(self, show_message=True, trigger_download=False):
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

    def load_lyrics_for_song(self, song_title):
        self.current_song_title = song_title
        self.current_song_var.set(song_title)

        lyrics = self.lyrics_store.get(song_title, "")
        if lyrics.strip():
            self.set_lyrics_editor_text(lyrics)
        else:
            self.show_lyrics_guide()

    def on_close(self):
        try:
            self.sync_weekly_history_from_server(log_result=False)
            self.render_weekly_history_accordion()
        except Exception as e:
            self.report_exception("weekly history sync on close", e)
            self.log(f"[경고] 종료 시 주간 작업 이력 동기화에 실패했습니다: {e}")
        self.destroy()

    def generate_songlist_card(self):
        if not self.refresh_song_list(show_message=False):
            return

        song_titles = [title for title, _ in self.sequence_entries]
        template_file = self.find_asset_file(SONGLIST_TEMPLATE_FILE_NAME)
        if not template_file:
            err = FileNotFoundError(f"assets/{SONGLIST_TEMPLATE_FILE_NAME}")
            self.report_exception("songlist template missing", err)
            self.log(f"[오류] 송리스트 카드 템플릿을 찾을 수 없습니다: 'assets/{SONGLIST_TEMPLATE_FILE_NAME}'")
            messagebox.showerror("오류", f"템플릿 파일을 찾을 수 없습니다:\nassets/{SONGLIST_TEMPLATE_FILE_NAME}")
            return

        output_file = os.path.join(self.get_output_dir(), SONGLIST_OUTPUT_FILE_NAME)
        output_dir = os.path.dirname(os.path.abspath(output_file))
        fd, temp_output_file = tempfile.mkstemp(
            prefix=".songlist_",
            suffix=".png",
            dir=output_dir,
        )
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
            if cancel_event.is_set():
                return
            cancel_event.set()
            self.log("[취소] 송리스트 카드 생성 취소를 요청했습니다.")
            self.update_busy_dialog("취소 요청을 처리하고 있습니다.")

        self.set_action_buttons_state("disabled")
        self.set_editor_state("disabled")
        self.log("====================================")
        self.log("송리스트 카드를 생성합니다.")
        self.show_busy_dialog(
            "송리스트 생성 중",
            "송리스트 카드를 생성하고 있습니다.",
            on_cancel=request_cancel,
        )

        def run():
            try:
                source = "서버"
                server_url = self.get_server_url()
                raise_if_cancelled()
                self.after(0, lambda: self.log(f"[정보][송리스트][서버요청] endpoint=/songlist-card, 서버={server_url}"))
                self.after(0, lambda: self.update_busy_dialog("서버에 송리스트 생성을 요청하고 있습니다."))
                try:
                    week_num = generate_songlist_card_via_server(
                        server_url,
                        template_file,
                        song_titles,
                        temp_output_file,
                    )
                    raise_if_cancelled()
                except PptServerUnavailable as e:
                    raise_if_cancelled()
                    source = "로컬"
                    self.after(
                        0,
                        lambda err=e: self.log(
                            f"[경고][송리스트][서버연결불가] 로컬 PowerPoint COM으로 전환합니다. PowerPoint가 없으면 LibreOffice를 사용합니다: {err}"
                        ),
                    )
                    self.after(0, lambda: self.log("[정보][송리스트][로컬변환] 로컬 변환을 시작합니다."))
                    self.after(0, lambda: self.update_busy_dialog("서버 연결이 되지 않아 로컬에서 변환하고 있습니다."))
                    week_num = build_songlist_card(template_file, song_titles, temp_output_file)
                    raise_if_cancelled()
                except PptServerResponseError as e:
                    raise_if_cancelled()
                    if e.status_code and e.status_code >= 500:
                        self.report_exception(
                            "songlist server processing fallback",
                            e,
                            extra={"status_code": e.status_code},
                        )
                        source = "로컬"
                        self.after(
                            0,
                            lambda err=e: self.log(
                                f"[경고][송리스트][서버처리오류] 로컬 PowerPoint COM으로 전환합니다. PowerPoint가 없으면 LibreOffice를 사용합니다: {err}"
                            ),
                        )
                        self.after(0, lambda: self.log("[정보][송리스트][로컬변환] 로컬 변환을 시작합니다."))
                        self.after(0, lambda: self.update_busy_dialog("서버 처리 오류로 로컬에서 변환하고 있습니다."))
                        week_num = build_songlist_card(template_file, song_titles, temp_output_file)
                        raise_if_cancelled()
                    else:
                        raise

                os.replace(temp_output_file, output_file)

                def on_done():
                    if cancel_event.is_set():
                        return
                    self.hide_busy_dialog()
                    week_text = f" (Week {week_num})" if week_num else ""
                    self.log(f"[완료] 송리스트 카드를 만들었습니다: '{output_file}' [{source}]{week_text}")
                    opened = self.open_output_file(output_file)
                    open_message = "\n생성된 파일을 엽니다." if opened else "\n생성된 파일 자동 열기에 실패했습니다."
                    messagebox.showinfo(
                        "완료",
                        f"송리스트 카드를 생성했습니다.\n저장 위치: out/{SONGLIST_OUTPUT_FILE_NAME}"
                        + open_message,
                    )
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_done)
            except OperationCancelled:
                def on_cancelled():
                    self.hide_busy_dialog()
                    self.log("[취소] 송리스트 카드 생성을 중단했습니다.")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_cancelled)
            except PptServerResponseError as e:
                err = e
                def on_server_error():
                    if cancel_event.is_set():
                        return
                    self.report_exception("songlist server request", err, extra={"status_code": err.status_code})
                    self.hide_busy_dialog()
                    status_text = f" status={err.status_code}" if err.status_code else ""
                    self.log(f"[오류][송리스트][서버요청실패]{status_text}: {err}")
                    messagebox.showerror("오류", f"송리스트 카드 생성 요청이 거부되었습니다:\n{err}")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_server_error)
            except LocalOfficeUnavailable as e:
                err = e
                def on_local_error():
                    if cancel_event.is_set():
                        return
                    self.report_exception("songlist local office", err)
                    self.hide_busy_dialog()
                    self.log(f"[오류][송리스트][로컬오피스실패]: {err}")
                    messagebox.showerror("오류", f"송리스트 카드 생성에 실패했습니다:\n{err}")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_local_error)
            except Exception as e:
                err = e
                def on_error():
                    if cancel_event.is_set():
                        return
                    self.report_exception("songlist unknown", err)
                    self.hide_busy_dialog()
                    self.log(f"[오류][송리스트][알수없음] 송리스트 카드 생성에 실패했습니다: {err}")
                    messagebox.showerror("오류", f"송리스트 카드 생성에 실패했습니다:\n{err}")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_error)
            finally:
                try:
                    if os.path.exists(temp_output_file):
                        os.remove(temp_output_file)
                except OSError:
                    pass

        threading.Thread(target=run, daemon=True).start()

    def _run_download(self, auto=False):
        try:
            from auto_lyrics_downloader import download_missing_lyrics
        except Exception as e:
            self.report_exception("lyrics downloader import", e, extra={"auto": auto})
            self.log(f"[오류] 가사 다운로드 모듈을 불러오지 못했습니다: {e}")
            if not auto:
                messagebox.showerror("오류", f"가사 다운로드 모듈을 불러오지 못했습니다:\n{e}")
            return

        song_titles = [title for title, _ in self.sequence_entries]
        current_song = self.current_song_title
        server_url = self.get_server_url()
        sequence_map = {title: seq for title, seq in self.sequence_entries}

        self.set_action_buttons_state("disabled")
        self.set_editor_state("disabled")
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
                    self.set_editor_state("normal")
                    if current_song:
                        self.load_lyrics_for_song(current_song)
                    if not auto:
                        messagebox.showinfo("완료", "가사 다운로드 작업이 완료되었습니다.")
                    self.set_action_buttons_state("normal")
                self.after(0, on_done)
            except Exception as e:
                err = e
                def on_error():
                    self.report_exception("lyrics download", err, extra={"auto": auto})
                    self.log(f"[오류] 가사 다운로드에 실패했습니다: {err}")
                    if not auto:
                        messagebox.showerror("오류", f"가사 다운로드에 실패했습니다:\n{err}")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_error)

        threading.Thread(target=run, daemon=True).start()


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
            template_dir = os.path.join(ASSETS_DIR_NAME, TEMPLATE_DIR_NAME)
            err = FileNotFoundError(template_dir)
            self.report_exception("ppt template missing", err)
            self.log(f"[오류] 템플릿 파일을 찾을 수 없습니다: '{template_dir}'")
            messagebox.showerror("오류", f"템플릿 파일을 찾을 수 없습니다:\n{template_dir}")
            return

        lyrics_by_title = dict(self.lyrics_store)
        ready_count = 0
        for song_title, sequence_str in sequence_entries:
            raw_lyrics = lyrics_by_title.get(song_title, "")

            if not raw_lyrics.strip():
                self.log(f"[안내] '{song_title}' 가사가 없어 직접 입력 창을 엽니다.")
                raw_lyrics = self.get_manual_lyrics(song_title)
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
            self.log("[오류] 생성할 가사가 없습니다.")
            messagebox.showwarning("파워포인트 생성", "생성할 가사가 없습니다.")
            return

        output_file = os.path.join(self.get_output_dir(), OUTPUT_FILE_NAME)
        server_url = self.get_server_url()

        self.set_action_buttons_state("disabled")
        self.set_editor_state("disabled")
        self.show_busy_dialog("파워포인트 생성 중", "파워포인트 파일을 생성하고 있습니다.")

        def run():
            try:
                source = "서버"
                self.after(0, lambda: self.log(f"[정보][PPT][서버요청] endpoint=/generate-ppt, 서버={server_url}"))
                self.after(0, lambda: self.update_busy_dialog("서버에 파워포인트 생성을 요청하고 있습니다."))
                try:
                    generated_count = generate_pptx_via_server(
                        server_url,
                        template_file,
                        sequence_entries,
                        lyrics_by_title,
                        max_lines_per_slide,
                        output_file,
                        max_chars_per_line=max_chars_per_line,
                        lyrics_font_size=lyrics_font_size,
                    )
                    if generated_count is None:
                        generated_count = ready_count
                except PptServerUnavailable as e:
                    source = "로컬"
                    self.after(
                        0,
                        lambda err=e: self.log(
                            f"[경고][PPT][서버연결불가] 로컬 PowerPoint COM으로 전환합니다. PowerPoint가 없으면 LibreOffice를 사용합니다: {err}"
                        ),
                    )
                    self.after(0, lambda: self.log("[정보][PPT][로컬생성] 로컬 PPT 생성을 시작합니다."))
                    self.after(0, lambda: self.update_busy_dialog("서버 연결이 되지 않아 로컬에서 생성하고 있습니다."))
                    result = build_integrated_pptx_with_local_office(
                        template_file,
                        sequence_entries,
                        lyrics_by_title,
                        output_file,
                        max_lines_per_slide,
                        max_chars_per_line=max_chars_per_line,
                        lyrics_font_size=lyrics_font_size,
                    )
                    generated_count = result["appended_count"]
                    source = f"로컬 {result.get('method', 'Office')}"
                except PptServerResponseError as e:
                    if e.status_code and e.status_code >= 500:
                        self.report_exception(
                            "ppt server processing fallback",
                            e,
                            extra={"status_code": e.status_code},
                        )
                        source = "로컬"
                        self.after(
                            0,
                            lambda err=e: self.log(
                                f"[경고][PPT][서버처리오류] 로컬 PowerPoint COM으로 전환합니다. PowerPoint가 없으면 LibreOffice를 사용합니다: {err}"
                            ),
                        )
                        self.after(0, lambda: self.log("[정보][PPT][로컬생성] 로컬 PPT 생성을 시작합니다."))
                        self.after(0, lambda: self.update_busy_dialog("서버 처리 오류로 로컬에서 생성하고 있습니다."))
                        result = build_integrated_pptx_with_local_office(
                            template_file,
                            sequence_entries,
                            lyrics_by_title,
                            output_file,
                            max_lines_per_slide,
                            max_chars_per_line=max_chars_per_line,
                            lyrics_font_size=lyrics_font_size,
                        )
                        generated_count = result["appended_count"]
                        source = f"로컬 {result.get('method', 'Office')}"
                    else:
                        raise

                def on_done():
                    self.hide_busy_dialog()
                    self.log(f"\n[완료] 파워포인트 파일을 만들었습니다: '{output_file}' [{source}, {generated_count}곡]\n")
                    opened = self.open_output_file(output_file)
                    open_message = "\n생성된 파일을 엽니다." if opened else "\n생성된 파일 자동 열기에 실패했습니다."
                    messagebox.showinfo(
                        "완료",
                        "파워포인트 파일을 생성했습니다.\n저장 위치: out/integrated_lyrics.pptx"
                        + open_message,
                    )
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_done)
            except PptServerResponseError as e:
                err = e
                def on_server_error():
                    self.report_exception("ppt server request", err, extra={"status_code": err.status_code})
                    self.hide_busy_dialog()
                    status_text = f" status={err.status_code}" if err.status_code else ""
                    self.log(f"[오류][PPT][서버요청실패]{status_text}: {err}")
                    messagebox.showerror("오류", f"PPT 서버 요청이 거부되었습니다:\n{err}")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_server_error)
            except LocalOfficeUnavailable as e:
                err = e
                def on_local_office_error():
                    self.report_exception("ppt local office", err)
                    self.hide_busy_dialog()
                    self.log(f"[오류][PPT][로컬오피스실패]: {err}")
                    messagebox.showerror("오류", str(err))
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_local_office_error)
            except Exception as e:
                err = e
                def on_error():
                    self.report_exception("ppt unknown", err)
                    self.hide_busy_dialog()
                    self.log(f"[오류][PPT][알수없음] 파워포인트 생성에 실패했습니다: {err}")
                    messagebox.showerror("오류", f"파워포인트 파일을 생성하지 못했습니다:\n{err}")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_error)

        threading.Thread(target=run, daemon=True).start()

if __name__ == "__main__":
    app = LyricsApp()
    app.mainloop()
