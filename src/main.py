import os
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox
import customtkinter as ctk
try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

from ppt_builder import parse_sequence_text
from ppt_server_client import (
    PptServerResponseError,
    PptServerUnavailable,
    generate_pptx_via_server,
    generate_songlist_card_via_server,
)
from ppt_service import (
    LocalOfficeUnavailable,
    build_integrated_pptx_with_local_office,
    build_songlist_card_png,
)
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
    def __init__(self, parent, title, prompt):
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
        self.brand_font_family = self.resolve_font_family(BRAND_FONT_CANDIDATES)
        self.setup_style()
        self.create_widgets()
        self.refresh_template_options()
        self.after(300, self.ensure_templates_async)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def configure_window_icon(self):
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
            return

        self.template_combo.configure(values=values, state="normal")
        current = self.template_var.get()

        if current not in self.template_files:
            self.template_var.set(values[0])

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
        content.rowconfigure(2, weight=1)   # workspace row fills remaining space

        # --- Header ---
        header = ctk.CTkFrame(content, fg_color="transparent", bg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(28, 0))

        ctk.CTkLabel(
            header,
            text=APP_DISPLAY_NAME,
            text_color=TITLE_FG,
            font=(self.brand_font_family, 32, "bold"),
        ).pack()
        ctk.CTkLabel(
            header,
            text="레파토리와 가사를 정리해 파워포인트로 만듭니다.",
            text_color=MUTED_FG,
            font=("Segoe UI", 12),
        ).pack()

        # --- Settings ---
        settings_frame = ctk.CTkFrame(content, fg_color="transparent", bg_color="transparent")
        settings_frame.grid(row=1, column=0, sticky="ew", padx=28, pady=(10, 0))
        settings_frame.columnconfigure(3, weight=1)
        settings_frame.columnconfigure(6, minsize=34)

        ctk.CTkLabel(
            settings_frame,
            text="설정",
            text_color=TEXT_FG,
            font=("Segoe UI", 13, "bold"),
        ).grid(row=0, column=0, sticky=tk.W, padx=(18, 16), pady=14)

        ctk.CTkLabel(
            settings_frame,
            text="슬라이드별 최대 줄 수",
            text_color=TEXT_FG,
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=1, sticky=tk.W)

        self.max_lines_var = tk.StringVar(value="4")
        ctk.CTkComboBox(
            settings_frame,
            values=[str(value) for value in range(1, 11)],
            variable=self.max_lines_var,
            width=72,
            height=34,
            corner_radius=12,
            border_width=1,
            border_color=PANEL_BORDER,
            button_color=ACCENT,
            button_hover_color=ACCENT_DARK,
            fg_color=TEXT_BG,
            bg_color="transparent",
            text_color=TEXT_FG,
            font=("Segoe UI", 12),
            dropdown_font=("Segoe UI", 12),
            dropdown_fg_color=TEXT_BG,
            dropdown_text_color=TEXT_FG,
            dropdown_hover_color=ACCENT_SOFT,
        ).grid(row=0, column=2, sticky=tk.W, padx=(8, 18))

        ctk.CTkLabel(
            settings_frame,
            text="템플릿",
            text_color=TEXT_FG,
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=4, sticky=tk.E)

        self.template_var = tk.StringVar(value="")
        self.template_combo = ctk.CTkComboBox(
            settings_frame,
            values=["템플릿 확인 중"],
            variable=self.template_var,
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
        self.template_combo.grid(row=0, column=5, sticky=tk.E, padx=(8, 6))

        self.template_refresh_slot = ctk.CTkFrame(
            settings_frame,
            width=34,
            height=34,
            fg_color="transparent",
            bg_color="transparent",
        )
        self.template_refresh_slot.grid(row=0, column=6, sticky=tk.W, padx=(0, 18))
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

        ctk.CTkLabel(
            settings_frame,
            text="PPT 서버",
            text_color=TEXT_FG,
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=7, sticky=tk.E)

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
        ).grid(row=0, column=8, sticky=tk.E, padx=(8, 18))

        # --- Workspace ---
        workspace_frame = ctk.CTkFrame(content, fg_color="transparent", bg_color="transparent")
        workspace_frame.grid(row=2, column=0, sticky="nsew", padx=28, pady=(8, 8))
        workspace_frame.columnconfigure(0, weight=4)
        workspace_frame.columnconfigure(1, weight=5)
        workspace_frame.rowconfigure(0, weight=1)

        sequence_frame = ctk.CTkFrame(
            workspace_frame, fg_color=PANEL_BG, bg_color="transparent", corner_radius=16,
        )
        sequence_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        sequence_frame.rowconfigure(1, weight=1)
        sequence_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            sequence_frame,
            text="레파토리 입력",
            text_color=TEXT_FG,
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, sticky=tk.W, padx=18, pady=(16, 10))

        self.sequence_text = ctk.CTkTextbox(
            sequence_frame,
            fg_color=TEXT_BG,
            bg_color="transparent",
            text_color=TEXT_FG,
            border_color=PANEL_BORDER,
            border_width=1,
            corner_radius=16,
            wrap=tk.WORD,
            font=("맑은 고딕", 12),
        )
        self.sequence_text.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.sequence_text.tag_config("placeholder", foreground="#9aa3af")
        self.sequence_text.bind("<FocusIn>", self.on_sequence_focus_in)
        self.sequence_text.bind("<FocusOut>", self.on_sequence_focus_out)
        self.show_sequence_guide()

        lyrics_frame = ctk.CTkFrame(
            workspace_frame, fg_color=PANEL_BG, bg_color="transparent", corner_radius=16,
        )
        lyrics_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        lyrics_frame.columnconfigure(0, weight=0)
        lyrics_frame.columnconfigure(1, weight=1)
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
        action_frame.grid(row=3, column=0, sticky="ew", padx=28, pady=(0, 6))

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

        # --- Log area ---
        log_frame = ctk.CTkFrame(
            content,
            fg_color=PANEL_BG,
            bg_color="transparent",
            corner_radius=16,
            border_width=1,
            border_color=PANEL_BORDER,
        )
        log_frame.grid(row=4, column=0, sticky="ew", padx=28, pady=(6, 24))
        log_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            log_frame,
            text="작업 로그",
            text_color=TEXT_FG,
            font=("Segoe UI", 13, "bold"),
        ).grid(row=0, column=0, sticky=tk.W, padx=18, pady=(12, 6))

        self.log_area = ctk.CTkTextbox(
            log_frame,
            height=100,
            state="disabled",
            fg_color=LOG_BG,
            bg_color="transparent",
            text_color="#f6edf1",
            border_width=0,
            corner_radius=12,
            font=("Consolas", 10),
        )
        self.log_area.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 14))

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
        self.log_area.configure(state="normal")
        self.log_area.insert("end", message + "\n")
        self.log_area.see("end")
        self.log_area.configure(state="disabled")
        self.update_idletasks()

    def get_manual_lyrics(self, song_title):
        dialog = MultilineDialog(self, "가사 직접 입력", f"'{song_title}' 가사를 입력하세요.")
        return dialog.result or ""

    def get_output_dir(self):
        output_dir = os.path.join(self.base_dir, "out")
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def get_server_url(self):
        return self.server_url_var.get().strip() or DEFAULT_SERVER_URL

    def get_sequence_entries(self):
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

    def clear_sequence_guide(self):
        if not self.sequence_placeholder_visible:
            return
        self.sequence_text.delete("1.0", "end")
        self.sequence_placeholder_visible = False

    def on_sequence_focus_in(self, event=None):
        self.clear_sequence_guide()

    def on_sequence_focus_out(self, event=None):
        if not self.sequence_text.get("1.0", "end").strip():
            self.show_sequence_guide()

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
            self.lyrics_store[self.current_song_title] = self.get_lyrics_editor_text()
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
        self.destroy()

    def generate_songlist_card(self):
        if not self.refresh_song_list(show_message=False):
            return

        song_titles = [title for title, _ in self.sequence_entries]
        template_file = self.find_asset_file(SONGLIST_TEMPLATE_FILE_NAME)
        if not template_file:
            self.log(f"[오류] 송리스트 카드 템플릿을 찾을 수 없습니다: 'assets/{SONGLIST_TEMPLATE_FILE_NAME}'")
            messagebox.showerror("오류", f"템플릿 파일을 찾을 수 없습니다:\nassets/{SONGLIST_TEMPLATE_FILE_NAME}")
            return

        output_file = os.path.join(self.get_output_dir(), SONGLIST_OUTPUT_FILE_NAME)

        self.set_action_buttons_state("disabled")
        self.set_editor_state("disabled")
        self.log("====================================")
        self.log("송리스트 카드를 생성합니다.")

        def run():
            try:
                source = "서버"
                server_url = self.get_server_url()
                self.after(0, lambda: self.log(f"[정보][송리스트][서버요청] endpoint=/songlist-card, 서버={server_url}"))
                try:
                    week_num = generate_songlist_card_via_server(
                        server_url,
                        template_file,
                        song_titles,
                        output_file,
                    )
                except PptServerUnavailable as e:
                    source = "로컬"
                    self.after(
                        0,
                        lambda err=e: self.log(
                            f"[경고][송리스트][서버연결불가] 로컬 PowerPoint COM으로 전환합니다. PowerPoint가 없으면 LibreOffice를 사용합니다: {err}"
                        ),
                    )
                    self.after(0, lambda: self.log("[정보][송리스트][로컬변환] 로컬 변환을 시작합니다."))
                    week_num = build_songlist_card_png(template_file, song_titles, output_file)
                except PptServerResponseError as e:
                    if e.status_code and e.status_code >= 500:
                        source = "로컬"
                        self.after(
                            0,
                            lambda err=e: self.log(
                                f"[경고][송리스트][서버처리오류] 로컬 PowerPoint COM으로 전환합니다. PowerPoint가 없으면 LibreOffice를 사용합니다: {err}"
                            ),
                        )
                        self.after(0, lambda: self.log("[정보][송리스트][로컬변환] 로컬 변환을 시작합니다."))
                        week_num = build_songlist_card_png(template_file, song_titles, output_file)
                    else:
                        raise

                def on_done():
                    week_text = f" (Week {week_num})" if week_num else ""
                    self.log(f"[완료] 송리스트 카드를 만들었습니다: '{output_file}' [{source}]{week_text}")
                    messagebox.showinfo(
                        "완료",
                        f"송리스트 카드를 생성했습니다.\n저장 위치: out/{SONGLIST_OUTPUT_FILE_NAME}",
                    )
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_done)
            except PptServerResponseError as e:
                err = e
                def on_server_error():
                    status_text = f" status={err.status_code}" if err.status_code else ""
                    self.log(f"[오류][송리스트][서버요청실패]{status_text}: {err}")
                    messagebox.showerror("오류", f"송리스트 카드 생성 요청이 거부되었습니다:\n{err}")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_server_error)
            except LocalOfficeUnavailable as e:
                err = e
                def on_local_error():
                    self.log(f"[오류][송리스트][로컬오피스실패]: {err}")
                    messagebox.showerror("오류", f"송리스트 카드 생성에 실패했습니다:\n{err}")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_local_error)
            except Exception as e:
                err = e
                def on_error():
                    self.log(f"[오류][송리스트][알수없음] 송리스트 카드 생성에 실패했습니다: {err}")
                    messagebox.showerror("오류", f"송리스트 카드 생성에 실패했습니다:\n{err}")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_error)

        threading.Thread(target=run, daemon=True).start()

    def _run_download(self, auto=False):
        try:
            from auto_lyrics_downloader import download_missing_lyrics
        except Exception as e:
            self.log(f"[오류] 가사 다운로드 모듈을 불러오지 못했습니다: {e}")
            if not auto:
                messagebox.showerror("오류", f"가사 다운로드 모듈을 불러오지 못했습니다:\n{e}")
            return

        song_titles = [title for title, _ in self.sequence_entries]
        current_song = self.current_song_title

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

        try:
            max_lines_per_slide = int(self.max_lines_var.get())
        except (TypeError, ValueError):
            max_lines_per_slide = 4

        template_file = self.get_selected_template_file()
        if not template_file:
            template_dir = os.path.join(ASSETS_DIR_NAME, TEMPLATE_DIR_NAME)
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

        def run():
            try:
                source = "서버"
                self.after(0, lambda: self.log(f"[정보][PPT][서버요청] endpoint=/generate-ppt, 서버={server_url}"))
                try:
                    generated_count = generate_pptx_via_server(
                        server_url,
                        template_file,
                        sequence_entries,
                        lyrics_by_title,
                        max_lines_per_slide,
                        output_file,
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
                    result = build_integrated_pptx_with_local_office(
                        template_file,
                        sequence_entries,
                        lyrics_by_title,
                        output_file,
                        max_lines_per_slide,
                    )
                    generated_count = result["appended_count"]
                    source = f"로컬 {result.get('method', 'Office')}"
                except PptServerResponseError as e:
                    if e.status_code and e.status_code >= 500:
                        source = "로컬"
                        self.after(
                            0,
                            lambda err=e: self.log(
                                f"[경고][PPT][서버처리오류] 로컬 PowerPoint COM으로 전환합니다. PowerPoint가 없으면 LibreOffice를 사용합니다: {err}"
                            ),
                        )
                        self.after(0, lambda: self.log("[정보][PPT][로컬생성] 로컬 PPT 생성을 시작합니다."))
                        result = build_integrated_pptx_with_local_office(
                            template_file,
                            sequence_entries,
                            lyrics_by_title,
                            output_file,
                            max_lines_per_slide,
                        )
                        generated_count = result["appended_count"]
                        source = f"로컬 {result.get('method', 'Office')}"
                    else:
                        raise

                def on_done():
                    self.log(f"\n[완료] 파워포인트 파일을 만들었습니다: '{output_file}' [{source}, {generated_count}곡]\n")
                    messagebox.showinfo("완료", "파워포인트 파일을 생성했습니다.\n저장 위치: out/integrated_lyrics.pptx")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_done)
            except PptServerResponseError as e:
                err = e
                def on_server_error():
                    status_text = f" status={err.status_code}" if err.status_code else ""
                    self.log(f"[오류][PPT][서버요청실패]{status_text}: {err}")
                    messagebox.showerror("오류", f"PPT 서버 요청이 거부되었습니다:\n{err}")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_server_error)
            except LocalOfficeUnavailable as e:
                err = e
                def on_local_office_error():
                    self.log(f"[오류][PPT][로컬오피스실패]: {err}")
                    messagebox.showerror("오류", str(err))
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_local_office_error)
            except Exception as e:
                err = e
                def on_error():
                    self.log(f"[오류][PPT][알수없음] 파워포인트 생성에 실패했습니다: {err}")
                    messagebox.showerror("오류", f"파워포인트 파일을 생성하지 못했습니다:\n{err}")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                self.after(0, on_error)

        threading.Thread(target=run, daemon=True).start()

if __name__ == "__main__":
    app = LyricsApp()
    app.mainloop()
