"""PySide6 + QFluentWidgets port of the PPT Gen application.

Run:  python src/main_qt.py
"""

from __future__ import annotations

import datetime
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import traceback
import zipfile
from typing import Optional

from PySide6.QtCore import (
    Qt, QTimer, QSize, Signal, QObject, QAbstractListModel, QModelIndex,
    QMimeData, QPoint,
)
from PySide6.QtGui import (
    QColor, QFont, QIcon, QLinearGradient, QPainter, QPalette, QPixmap, QImage,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QDialogButtonBox, QFileDialog,
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QScrollArea, QSizePolicy, QSplitter,
    QVBoxLayout, QWidget, QSpacerItem, QGridLayout,
)

from qfluentwidgets import (
    Action,
    BodyLabel,
    CardWidget,
    CaptionLabel,
    ComboBox,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PlainTextEdit,
    PrimaryPushButton,
    PushButton,
    RoundMenu,
    SmoothScrollArea,
    StateToolTip,
    StrongBodyLabel,
    SubtitleLabel,
    ToolButton,
    TransparentPushButton,
    setTheme,
    setThemeColor,
    Theme,
)

try:
    from PIL import Image
except ImportError:
    Image = None

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
    APP_BG, PANEL_BG, PANEL_SOFT_BG, PANEL_BORDER,
    TEXT_BG, TEXT_FG, MUTED_FG, TITLE_FG,
    ACCENT, ACCENT_DARK, ACCENT_SOFT,
    GRADIENT_TOP, GRADIENT_MID, GRADIENT_BOTTOM,
    SEQUENCE_GUIDE_TEXT, LYRICS_GUIDE_TEXT,
    TEMPLATE_PREVIEW_WIDTH, TEMPLATE_PREVIEW_HEIGHT, TEMPLATE_PREVIEW_IMAGE_MAX,
)


# ─── Thread-safe main-thread callback bridge ───────────────────────────────
class _Bridge(QObject):
    """Schedules a callable on the main Qt thread from any thread."""
    _sig = Signal(object)

    def __init__(self):
        super().__init__()
        self._sig.connect(lambda fn: fn(), Qt.QueuedConnection)

    def call(self, fn):
        self._sig.emit(fn)


_bridge: Optional[_Bridge] = None


class OperationCancelled(RuntimeError):
    pass


# ─── Multiline input dialog ────────────────────────────────────────────────
class MultilineDialog(QDialog):
    def __init__(self, parent, title: str, prompt: str, initial_text: str = ""):
        super().__init__(parent)
        self.result: Optional[str] = None
        self.setWindowTitle(title)
        self.setMinimumSize(480, 360)
        self.resize(500, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)

        if prompt:
            lbl = BodyLabel(prompt, self)
            lbl.setWordWrap(True)
            layout.addWidget(lbl)

        self._edit = PlainTextEdit(self)
        if initial_text:
            self._edit.setPlainText(initial_text)
        layout.addWidget(self._edit, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = PushButton("취소", self)
        ok_btn = PrimaryPushButton("확인", self)
        cancel_btn.clicked.connect(self.reject)
        ok_btn.clicked.connect(self._accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        self.exec()

    def _accept(self):
        self.result = self._edit.toPlainText()
        self.accept()


# ─── Lyrics search dialog ──────────────────────────────────────────────────
class LyricsSearchDialog(QDialog):
    def __init__(self, parent, server_url: str):
        super().__init__(parent)
        self.result: Optional[dict] = None
        self._server_url = server_url
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._do_search)

        self.setWindowTitle("가사 DB 검색")
        self.setMinimumSize(520, 440)
        self.resize(560, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        self._search_edit = LineEdit(self)
        self._search_edit.setPlaceholderText("곡명을 입력하세요…")
        self._search_edit.textChanged.connect(lambda: self._debounce.start(300))
        layout.addWidget(self._search_edit)

        self._scroll = SmoothScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(4, 4, 4, 4)
        self._list_layout.setSpacing(6)
        self._scroll.setWidget(self._list_widget)
        layout.addWidget(self._scroll, 1)

        self._status_label = BodyLabel("검색어를 입력하면 결과가 표시됩니다.", self)
        self._list_layout.addWidget(self._status_label)
        self._list_layout.addStretch()

        close_btn = PushButton("닫기", self)
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn, 0, Qt.AlignRight)

        self._search_edit.setFocus()
        self.exec()

    def _do_search(self):
        query = self._search_edit.text().strip()
        if not query:
            self._show_status("검색어를 입력하면 결과가 표시됩니다.")
            return
        self._show_status("검색 중…")
        threading.Thread(target=self._fetch_results, args=(query,), daemon=True).start()

    def _fetch_results(self, query: str):
        try:
            items = search_lyrics_catalog(self._server_url, query, limit=20)
            _bridge.call(lambda r=items: self._render_results(r))
        except (PptServerUnavailable, PptServerEndpointUnavailable):
            _bridge.call(lambda: self._show_status("서버에 연결할 수 없습니다."))
        except Exception as e:
            _bridge.call(lambda err=e: self._show_status(f"검색 오류: {err}"))

    def _clear_list(self):
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _show_status(self, msg: str):
        self._clear_list()
        lbl = BodyLabel(msg, self._list_widget)
        self._list_layout.addWidget(lbl)
        self._list_layout.addStretch()

    def _render_results(self, items: list):
        self._clear_list()
        if not items:
            self._show_status("검색 결과가 없습니다.")
            return
        for item in items:
            self._add_result_row(item)
        self._list_layout.addStretch()

    def _add_result_row(self, item: dict):
        title = str(item.get("title") or "")
        sequence = str(item.get("sequence") or "")
        source = str(item.get("source") or "")
        badge = {"bugs": "🌐 Bugs", "manual": "✏️ 직접", "history": "📅 이력"}.get(source, source)

        row = CardWidget(self._list_widget)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 8, 8, 8)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.addWidget(StrongBodyLabel(title))
        info_text = sequence if sequence else "(진행 순서 없음)"
        text_col.addWidget(CaptionLabel(f"{info_text}  [{badge}]"))
        row_layout.addLayout(text_col, 1)

        add_btn = PrimaryPushButton("추가")
        add_btn.setFixedHeight(32)
        add_btn.clicked.connect(lambda checked=False, i=item: self._select(i))
        row_layout.addWidget(add_btn, 0, Qt.AlignVCenter)

        self._list_layout.addWidget(row)

    def _select(self, item: dict):
        self.result = item
        self.accept()


# ─── Background widget (gradient) ─────────────────────────────────────────
class _GradientWidget(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        h = self.height()
        w = self.width()
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(GRADIENT_TOP))
        grad.setColorAt(0.55, QColor(GRADIENT_MID))
        grad.setColorAt(1.0, QColor(GRADIENT_BOTTOM))
        painter.fillRect(self.rect(), grad)

        # decorative circles
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#eadcf4"))
        painter.drawEllipse(int(w * 0.58), int(h * 0.52), int(w * 0.60), int(h * 0.66))
        painter.setBrush(QColor("#dfcaef"))
        painter.drawEllipse(-int(w * 0.20), int(h * 0.36), int(w * 0.58), int(h * 0.76))


# ─── Repertoire list widget with drag-drop reorder ─────────────────────────
class _RepertoireList(QListWidget):
    order_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSpacing(3)
        self.setStyleSheet(f"""
            QListWidget {{
                border: none;
                background: transparent;
                outline: none;
            }}
            QListWidget::item {{
                background: {TEXT_BG};
                border: 1px solid {PANEL_BORDER};
                border-radius: 8px;
                padding: 8px 12px;
                color: {TEXT_FG};
                min-height: 52px;
            }}
            QListWidget::item:selected {{
                background: {ACCENT_SOFT};
                border: 2px solid {ACCENT_DARK};
                color: {TEXT_FG};
            }}
            QListWidget::item:hover:!selected {{
                background: {ACCENT_SOFT};
                border: 1px solid {ACCENT};
            }}
        """)

    def dropEvent(self, event):
        super().dropEvent(event)
        self.order_changed.emit()


# ─── Song list widget ──────────────────────────────────────────────────────
class _SongList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSpacing(2)
        self.setStyleSheet(f"""
            QListWidget {{
                border: none;
                background: transparent;
                outline: none;
            }}
            QListWidget::item {{
                height: 36px;
                padding: 4px 10px;
                border-radius: 6px;
                color: {TEXT_FG};
                font-family: "맑은 고딕";
                font-size: 11pt;
            }}
            QListWidget::item:selected {{
                background: {ACCENT};
                color: {TEXT_FG};
            }}
            QListWidget::item:hover:!selected {{
                background: {ACCENT_SOFT};
            }}
        """)


# ─── Main Application Window ───────────────────────────────────────────────
class LyricsApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_WINDOW_TITLE)
        self.resize(1080, 760)
        self.setMinimumSize(900, 640)

        if getattr(sys, "frozen", False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # ── State variables ─────────────────────────────────────────────
        self.sequence_entries = []
        self.current_song_title: Optional[str] = None
        self.loading_lyrics = False
        self.suppress_song_select = False
        self.lyrics_store: dict = {}
        self.template_files: dict = {}
        self._template_download_running = False
        self._template_refresh_complete = False
        self._template_preview_request_id = 0
        self._template_preview_rendering: set = set()
        self._template_preview_failed: set = set()
        self._recent_log_lines: list = []
        self.weekly_history_items: list = []
        self._loaded_history_lyrics_by_title: dict = {}
        self.repertoire_entries: list = []
        self._busy_state_tip: Optional[StateToolTip] = None
        self.song_buttons: list = []
        self.selected_song_index: Optional[int] = None
        self._animate_timer: Optional[QTimer] = None
        self._animate_index = 0
        self._log_dialog: Optional[QDialog] = None
        self._log_edit: Optional[PlainTextEdit] = None

        self._build_ui()
        self._configure_icon()

        self.load_local_weekly_history()
        QTimer.singleShot(500, self.sync_weekly_history_from_server_async)
        self.refresh_template_options()
        QTimer.singleShot(300, self.ensure_templates_async)

    # ── Window icon ────────────────────────────────────────────────────
    def _configure_icon(self):
        ico = self.find_asset_file(ICON_ICO_FILE_NAME)
        if ico and sys.platform == "win32":
            self.setWindowIcon(QIcon(ico))
            return
        png = self.find_asset_file(ICON_FILE_NAME)
        if png:
            self.setWindowIcon(QIcon(png))

    # ── UI construction ────────────────────────────────────────────────
    def _build_ui(self):
        root = _GradientWidget(self)
        self.setCentralWidget(root)

        main = QVBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        main.addWidget(self._build_top_bar())
        main.addWidget(self._build_workspace(), 1)
        main.addWidget(self._build_action_bar())

    def _build_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("topBar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(44, 22, 44, 14)
        h.setSpacing(0)

        # ── Brand block (left)
        brand = QVBoxLayout()
        brand.setSpacing(6)

        logo_lbl = self._make_logo_label()
        brand.addWidget(logo_lbl)

        sub = BodyLabel("레파토리와 가사를 정리해 파워포인트로 만듭니다.")
        sub.setStyleSheet(f"color: {MUTED_FG};")
        brand.addWidget(sub)
        h.addLayout(brand)
        h.addStretch()

        # ── Right block (menu + settings)
        right = QVBoxLayout()
        right.setSpacing(8)
        right.setAlignment(Qt.AlignRight)
        right.addLayout(self._build_menu_bar())
        right.addLayout(self._build_settings_grid())
        h.addLayout(right)

        return bar

    def _make_logo_label(self) -> QWidget:
        logo_file = self.find_asset_file(LOGO_FILE_NAME)
        if logo_file and Image is not None:
            try:
                img = Image.open(logo_file).convert("RGBA")
                max_w = LOGO_SIZE[0] * LOGO_DISPLAY_SCALE
                max_h = LOGO_SIZE[1] * LOGO_DISPLAY_SCALE
                scale = min(max_w / img.width, max_h / img.height, 1.0)
                dw = max(1, int(img.width * scale))
                dh = max(1, int(img.height * scale))
                img = img.resize((dw, dh), Image.LANCZOS)
                data = img.tobytes("raw", "RGBA")
                qimg = QImage(data, dw, dh, QImage.Format_RGBA8888)
                pix = QPixmap.fromImage(qimg)
                lbl = QLabel()
                lbl.setPixmap(pix)
                lbl.setFixedSize(dw, dh)
                return lbl
            except Exception:
                pass

        lbl = SubtitleLabel(APP_DISPLAY_NAME)
        lbl.setStyleSheet(f"color: {TITLE_FG}; font-size: 24pt; font-weight: bold;")
        return lbl

    def _build_menu_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)
        row.setAlignment(Qt.AlignRight)

        file_items = [
            ("작업 로그 다운로드", self.download_work_log),
            ("-", None),
            ("종료", self.close),
        ]
        tools_items = [
            ("레파토리 입력하기", self.open_repertoire_input_dialog),
            ("레파토리 인식", lambda: self.refresh_song_list(trigger_download=True)),
        ]
        log_items = [
            ("작업 로그 보기", self._show_log_dialog),
            ("작업 로그 다운로드", self.download_work_log),
            ("로그 첨부 버그 리포트", self.report_bug_with_logs),
        ]
        help_items = [
            ("앱 정보", self.show_app_about),
        ]

        for title, items in [("파일", file_items), ("도구", tools_items),
                              ("로그", log_items), ("도움말", help_items)]:
            row.addWidget(self._make_menu_button(title, items))

        return row

    def _make_menu_button(self, title: str, items: list) -> PushButton:
        btn = PushButton(f"{title} ▾", self)
        btn.setFixedHeight(30)
        menu = RoundMenu(parent=self)
        for label, command in items:
            if label == "-":
                menu.addSeparator()
            else:
                act = Action(label)
                act.triggered.connect(command)
                menu.addAction(act)
        btn.clicked.connect(
            lambda checked=False, b=btn, m=menu: m.exec(
                b.mapToGlobal(QPoint(0, b.height() + 2))
            )
        )
        return btn

    def _build_settings_grid(self) -> QGridLayout:
        g = QGridLayout()
        g.setSpacing(4)
        g.setAlignment(Qt.AlignRight)

        def lbl(text):
            l = BodyLabel(text)
            l.setStyleSheet(f"color: {TEXT_FG}; font-weight: bold;")
            return l

        g.addWidget(lbl("설정"), 0, 0, Qt.AlignRight | Qt.AlignVCenter)
        g.addWidget(lbl("슬라이드별 최대 줄 수"), 0, 1, Qt.AlignRight)
        self.max_lines_edit = LineEdit(self)
        self.max_lines_edit.setText(str(DEFAULT_MAX_LINES_PER_SLIDE))
        self.max_lines_edit.setFixedWidth(72)
        g.addWidget(self.max_lines_edit, 0, 2)

        g.addWidget(lbl("줄별 최대 글자 수"), 1, 1, Qt.AlignRight)
        self.max_chars_edit = LineEdit(self)
        self.max_chars_edit.setText(str(DEFAULT_MAX_CHARS_PER_LINE))
        self.max_chars_edit.setFixedWidth(72)
        g.addWidget(self.max_chars_edit, 1, 2)

        g.addWidget(lbl("가사 크기"), 2, 1, Qt.AlignRight)
        self.lyrics_font_size_edit = LineEdit(self)
        self.lyrics_font_size_edit.setText(DEFAULT_LYRICS_FONT_SIZE or "기본")
        self.lyrics_font_size_edit.setFixedWidth(72)
        g.addWidget(self.lyrics_font_size_edit, 2, 2)

        g.addWidget(lbl("템플릿"), 0, 3, Qt.AlignRight)
        self.template_combo = ComboBox(self)
        self.template_combo.addItem("템플릿 확인 중")
        self.template_combo.setFixedWidth(200)
        self.template_combo.currentTextChanged.connect(self._on_template_changed)
        g.addWidget(self.template_combo, 0, 4)

        self.template_refresh_btn = ToolButton(FluentIcon.SYNC, self)
        self.template_refresh_btn.setToolTip("템플릿 다운로드")
        self.template_refresh_btn.clicked.connect(lambda: self.ensure_templates_async(force=True))
        g.addWidget(self.template_refresh_btn, 0, 5)

        g.addWidget(lbl("PPT 서버"), 1, 3, Qt.AlignRight)
        self.server_url_edit = LineEdit(self)
        self.server_url_edit.setText(DEFAULT_SERVER_URL)
        self.server_url_edit.setPlaceholderText(DEFAULT_SERVER_URL)
        self.server_url_edit.setFixedWidth(200)
        g.addWidget(self.server_url_edit, 1, 4)

        return g

    def _build_workspace(self) -> QWidget:
        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(28, 0, 28, 8)
        h.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal, container)
        splitter.setHandleWidth(8)
        splitter.addWidget(self._build_sequence_panel())
        splitter.addWidget(self._build_lyrics_panel())
        splitter.setSizes([400, 520])
        h.addWidget(splitter)

        return container

    def _build_sequence_panel(self) -> CardWidget:
        card = CardWidget(self)
        v = QVBoxLayout(card)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(8)

        v.addWidget(StrongBodyLabel("레파토리 입력"))

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        input_btn = PushButton("레파토리 입력하기")
        input_btn.clicked.connect(self.open_repertoire_input_dialog)
        btn_row.addWidget(input_btn)

        db_btn = PushButton("🔍 DB에서 추가")
        db_btn.clicked.connect(self.open_lyrics_search_dialog)
        btn_row.addWidget(db_btn)

        self._repertoire_summary_label = CaptionLabel("입력된 레파토리 없음")
        self._repertoire_summary_label.setStyleSheet(f"color: {MUTED_FG};")
        btn_row.addWidget(self._repertoire_summary_label, 1)
        v.addLayout(btn_row)

        hint = CaptionLabel("드래그로 순서 변경 | 더블클릭으로 수정")
        hint.setStyleSheet(f"color: {MUTED_FG};")
        v.addWidget(hint)

        self.repertoire_list = _RepertoireList(card)
        self.repertoire_list.order_changed.connect(self._on_repertoire_order_changed)
        self.repertoire_list.itemDoubleClicked.connect(self._on_repertoire_double_click)
        v.addWidget(self.repertoire_list, 1)

        self.refresh_repertoire_sort_list()
        return card

    def _build_lyrics_panel(self) -> CardWidget:
        card = CardWidget(self)
        v = QVBoxLayout(card)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(8)

        header = QHBoxLayout()
        header.addWidget(StrongBodyLabel("가사 편집"))
        self.current_song_label = BodyLabel("곡을 선택하세요")
        self.current_song_label.setStyleSheet(f"color: {MUTED_FG};")
        header.addWidget(self.current_song_label, 1)

        reload_btn = ToolButton(FluentIcon.UPDATE, card)
        reload_btn.setToolTip("불러온 이력에서 현재 곡 가사 다시 불러오기")
        reload_btn.clicked.connect(self.reload_current_song_lyrics_from_history)
        header.addWidget(reload_btn)
        v.addLayout(header)

        content_splitter = QSplitter(Qt.Horizontal, card)
        content_splitter.setHandleWidth(6)

        # Song list (left)
        self.song_list = _SongList(card)
        self.song_list.setFixedWidth(175)
        self.song_list.currentRowChanged.connect(self._on_song_row_changed)
        content_splitter.addWidget(self.song_list)

        # Lyrics editor (right)
        self.lyrics_edit = PlainTextEdit(card)
        self.lyrics_edit.setPlaceholderText(LYRICS_GUIDE_TEXT)
        self.lyrics_edit.textChanged.connect(self._on_lyrics_text_changed)
        content_splitter.addWidget(self.lyrics_edit)

        content_splitter.setSizes([175, 400])
        v.addWidget(content_splitter, 1)

        return card

    def _build_action_bar(self) -> QWidget:
        bar = CardWidget(self)
        bar.setFixedHeight(62)
        h = QHBoxLayout(bar)
        h.setContentsMargins(14, 10, 14, 10)
        h.setSpacing(8)

        self.refresh_btn = PushButton("레파토리 인식")
        self.refresh_btn.setFixedHeight(42)
        self.refresh_btn.clicked.connect(lambda: self.refresh_song_list(trigger_download=True))
        h.addWidget(self.refresh_btn)

        h.addStretch()

        self.songlist_btn = PushButton("송리스트 카드 생성")
        self.songlist_btn.setFixedHeight(42)
        self.songlist_btn.clicked.connect(self.generate_songlist_card)
        h.addWidget(self.songlist_btn)

        self.generate_btn = PrimaryPushButton("파워포인트 생성")
        self.generate_btn.setFixedHeight(42)
        self.generate_btn.clicked.connect(self.generate_ppt)
        h.addWidget(self.generate_btn)

        return bar

    # ── Log dialog ─────────────────────────────────────────────────────
    def _show_log_dialog(self):
        if self._log_dialog and self._log_dialog.isVisible():
            self._log_dialog.raise_()
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("작업 로그")
        dlg.resize(600, 400)
        v = QVBoxLayout(dlg)
        self._log_edit = PlainTextEdit(dlg)
        self._log_edit.setReadOnly(True)
        self._log_edit.setPlainText("\n".join(self._recent_log_lines))
        v.addWidget(self._log_edit)
        self._log_dialog = dlg
        dlg.show()

    # ── Repertoire list ────────────────────────────────────────────────
    def _on_repertoire_order_changed(self):
        new_entries = []
        for i in range(self.repertoire_list.count()):
            item = self.repertoire_list.item(i)
            old_idx = item.data(Qt.UserRole)
            if isinstance(old_idx, int) and 0 <= old_idx < len(self.repertoire_entries):
                new_entries.append(self.repertoire_entries[old_idx])
        if len(new_entries) == len(self.repertoire_entries):
            self.repertoire_entries = new_entries
        self.refresh_repertoire_sort_list()

    def _on_repertoire_double_click(self, item: QListWidgetItem):
        visual_idx = self.repertoire_list.row(item)
        self.edit_repertoire_item(visual_idx)

    def refresh_repertoire_sort_list(self):
        if not hasattr(self, "repertoire_list"):
            return
        self.repertoire_list.blockSignals(True)
        self.repertoire_list.clear()

        if not self.repertoire_entries:
            empty = QListWidgetItem("인식된 레파토리가 없습니다.")
            empty.setFlags(empty.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsDragEnabled)
            self.repertoire_list.addItem(empty)
            self.repertoire_list.blockSignals(False)
            self._update_repertoire_summary()
            return

        for idx, (title, sequence) in enumerate(self.repertoire_entries):
            short_title = title if len(title) <= 22 else title[:22] + "…"
            short_seq = sequence if len(sequence) <= 30 else sequence[:30] + "…"
            item = QListWidgetItem(f"{idx + 1}.  {short_title}\n    {short_seq}")
            item.setData(Qt.UserRole, idx)
            item.setToolTip(f"{title}\n{sequence}")
            self.repertoire_list.addItem(item)

        self.repertoire_list.blockSignals(False)
        self._update_repertoire_summary()

    def _update_repertoire_summary(self):
        count = len(self.repertoire_entries)
        if not hasattr(self, "_repertoire_summary_label"):
            return
        if count <= 0:
            self._repertoire_summary_label.setText("입력된 레파토리 없음")
        else:
            self._repertoire_summary_label.setText(f"총 {count}곡")

    def sync_sequence_text_from_repertoire(self):
        self._update_repertoire_summary()

    # ── Song list ──────────────────────────────────────────────────────
    def _on_song_row_changed(self, index: int):
        if self.suppress_song_select:
            return
        if index < 0 or index >= len(self.song_buttons):
            return
        song_title = self.song_buttons[index][0]
        if song_title == self.current_song_title:
            return
        if self.current_song_title:
            lyrics = self.get_lyrics_editor_text()
            self.lyrics_store[self.current_song_title] = lyrics
            self._save_lyrics_to_catalog_async(self.current_song_title, lyrics)
        self.selected_song_index = index
        self.load_lyrics_for_song(song_title)

    def _set_song_selection(self, index: Optional[int]):
        self.selected_song_index = index
        self.suppress_song_select = True
        self.song_list.blockSignals(True)
        if index is not None:
            self.song_list.setCurrentRow(index)
        else:
            self.song_list.clearSelection()
        self.song_list.blockSignals(False)
        self.suppress_song_select = False

    def populate_song_list(self, sequence_entries: list, preserve_current: bool = True):
        previous_song = self.current_song_title if preserve_current else None
        selected_index = None

        self.suppress_song_select = True
        self.song_list.blockSignals(True)
        self.song_list.clear()
        self.song_buttons = []
        self.selected_song_index = None

        for index, (song_title, _) in enumerate(sequence_entries):
            item = QListWidgetItem(song_title)
            self.song_list.addItem(item)
            self.song_buttons.append((song_title, None))
            if previous_song == song_title and selected_index is None:
                selected_index = index

        if selected_index is None and sequence_entries:
            selected_index = 0

        if selected_index is not None:
            self.song_list.setCurrentRow(selected_index)
            self.selected_song_index = selected_index

        self.song_list.blockSignals(False)
        self.suppress_song_select = False
        return selected_index

    # ── Lyrics editor ──────────────────────────────────────────────────
    def _on_lyrics_text_changed(self):
        if self.loading_lyrics:
            return
        text = self.get_lyrics_editor_text()
        if self.current_song_title and text:
            self.lyrics_store[self.current_song_title] = text

    def get_lyrics_editor_text(self) -> str:
        return self.lyrics_edit.toPlainText().strip()

    def set_lyrics_editor_text(self, text: str):
        self.loading_lyrics = True
        self.lyrics_edit.setPlainText(text)
        self.loading_lyrics = False

    def show_lyrics_guide(self):
        self.loading_lyrics = True
        self.lyrics_edit.clear()
        self.loading_lyrics = False

    def load_lyrics_for_song(self, song_title: str):
        self.current_song_title = song_title
        self.current_song_label.setText(song_title)
        lyrics = self.lyrics_store.get(song_title, "")
        if lyrics.strip():
            self.set_lyrics_editor_text(lyrics)
        else:
            self.show_lyrics_guide()

    # ── Template combo ─────────────────────────────────────────────────
    def _on_template_changed(self, _text: str):
        self.update_template_preview()

    def refresh_template_options(self):
        templates = self.list_template_files()
        self.template_files = {dn: path for dn, path in templates}
        values = list(self.template_files)

        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        if not values:
            self.template_combo.addItem("템플릿 없음")
            self.template_combo.setEnabled(False)
        else:
            for v in values:
                self.template_combo.addItem(v)
            self.template_combo.setEnabled(True)
        self.template_combo.blockSignals(False)

    def update_template_preview(self, *_):
        pass  # template preview is not displayed in the Qt version

    def get_selected_template_file(self) -> Optional[str]:
        selected = self.template_files.get(self.template_combo.currentText())
        if selected and os.path.exists(selected):
            return selected
        templates = self.list_template_files()
        return templates[0][1] if templates else None

    # ── Template download ──────────────────────────────────────────────
    def set_template_loading_state(self, loading: bool, status_text: str = ""):
        self._template_download_running = loading
        self._template_refresh_complete = status_text == "✓"
        if hasattr(self, "template_refresh_btn"):
            self.template_refresh_btn.setEnabled(not loading)
            if not loading and self._animate_timer:
                self._animate_timer.stop()

    def ensure_templates_async(self, force: bool = False):
        if self._template_download_running:
            return
        self.set_template_loading_state(True)

        if self._animate_timer is None:
            self._animate_timer = QTimer(self)
            self._animate_timer.timeout.connect(self._animate_template_step)
        self._animate_index = 0
        self._animate_timer.start(160)

        def run():
            status = "✓"
            try:
                target_dir = self.get_template_download_dir()
                before = {p for _, p in self.list_template_files()
                          if os.path.abspath(p).startswith(os.path.abspath(target_dir))}
                _bridge.call(lambda: self.log("[안내] 템플릿 저장소를 확인합니다."))
                try:
                    import gdown
                except ImportError:
                    status = "!"
                    _bridge.call(lambda: self.log("[오류] 템플릿 자동 다운로드에 필요한 gdown 패키지가 없습니다."))
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
                        self.log(f"[완료] 새 템플릿 {len(added)}개를 다운로드했습니다: {', '.join(added)}")
                    elif force:
                        self.log("[안내] 템플릿 목록을 최신 상태로 갱신했습니다.")
                    else:
                        self.log("[안내] 템플릿 목록을 확인했습니다.")
                _bridge.call(on_done)
            except Exception as e:
                status = "!"
                err = e
                self.report_exception("template download", err)
                _bridge.call(lambda: self.log(f"[오류] 템플릿 다운로드에 실패했습니다: {err}"))
            finally:
                _bridge.call(lambda s=status: self.set_template_loading_state(False, s))

        threading.Thread(target=run, daemon=True).start()

    def _animate_template_step(self):
        if not self._template_download_running:
            if self._animate_timer:
                self._animate_timer.stop()
            return
        frames = ("◐", "◓", "◑", "◒")
        # Just log animation state; tooltip shows in button hover
        self._animate_index += 1

    # ── Busy indicator (StateToolTip) ──────────────────────────────────
    def show_busy_dialog(self, title: str, message: str, on_cancel=None):
        self.hide_busy_dialog()
        self._busy_state_tip = StateToolTip(title, message, self)
        pos = self._busy_state_tip.getSuitablePos()
        self._busy_state_tip.move(pos)
        self._busy_state_tip.show()

    def update_busy_dialog(self, message: str):
        if self._busy_state_tip:
            self._busy_state_tip.setContent(message)

    def hide_busy_dialog(self):
        if self._busy_state_tip:
            try:
                self._busy_state_tip.close()
            except Exception:
                pass
            self._busy_state_tip = None

    # ── Action state ───────────────────────────────────────────────────
    def set_action_buttons_state(self, state: str):
        enabled = (state == "normal")
        self.refresh_btn.setEnabled(enabled)
        self.generate_btn.setEnabled(enabled)
        self.songlist_btn.setEnabled(enabled)

    def set_editor_state(self, state: str):
        enabled = (state == "normal")
        self.lyrics_edit.setReadOnly(not enabled)
        self.song_list.setEnabled(enabled)

    # ── Logging ────────────────────────────────────────────────────────
    def log(self, message: str):
        self._recent_log_lines.append(str(message))
        self._recent_log_lines = self._recent_log_lines[-50:]
        if self._log_edit and self._log_dialog and self._log_dialog.isVisible():
            self._log_edit.setPlainText("\n".join(self._recent_log_lines))
            cursor = self._log_edit.textCursor()
            cursor.movePosition(cursor.End)
            self._log_edit.setTextCursor(cursor)

    # ── Asset helpers ──────────────────────────────────────────────────
    def find_asset_file(self, file_name: str) -> Optional[str]:
        base_dirs = [self.base_dir]
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            base_dirs.append(bundle_dir)
        for base in base_dirs:
            for rel in [os.path.join(ASSETS_DIR_NAME, file_name), file_name]:
                path = os.path.join(base, rel)
                if os.path.exists(path):
                    return path
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

    # ── Settings accessors ─────────────────────────────────────────────
    def get_server_url(self) -> str:
        return self.server_url_edit.text().strip() or DEFAULT_SERVER_URL

    def get_max_lines_per_slide(self) -> int:
        try:
            return int(self.max_lines_edit.text())
        except (TypeError, ValueError):
            return DEFAULT_MAX_LINES_PER_SLIDE

    def get_max_chars_per_line(self) -> int:
        try:
            return int(self.max_chars_edit.text())
        except (TypeError, ValueError):
            return DEFAULT_MAX_CHARS_PER_LINE

    def get_lyrics_font_size(self) -> Optional[float]:
        value = self.lyrics_font_size_edit.text().strip()
        if not value or value == "기본":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    # ── Error reporting ────────────────────────────────────────────────
    def report_exception(self, context: str, exc, tb=None, extra=None):
        try:
            server_url = self.get_server_url() if hasattr(self, "server_url_edit") else DEFAULT_SERVER_URL
            report_error_async(
                server_url,
                context=context,
                message=str(exc),
                traceback_text=format_exception(exc, tb),
                extra=self._build_error_extra(context, extra),
                log_tail=self._recent_log_lines,
            )
        except Exception:
            pass

    def _build_error_extra(self, context: str, extra=None) -> dict:
        stack = traceback.extract_stack()
        caller = None
        for frame in reversed(stack):
            if frame.name not in ("_build_error_extra", "report_exception"):
                caller = frame
                break
        settings = {
            "server_url": self.get_server_url() if hasattr(self, "server_url_edit") else DEFAULT_SERVER_URL,
            "max_lines_per_slide": self.max_lines_edit.text() if hasattr(self, "max_lines_edit") else None,
            "max_chars_per_line": self.max_chars_edit.text() if hasattr(self, "max_chars_edit") else None,
            "lyrics_font_size": self.lyrics_font_size_edit.text() if hasattr(self, "lyrics_font_size_edit") else None,
            "template": self.template_combo.currentText() if hasattr(self, "template_combo") else None,
        }
        state = {
            "context": context,
            "current_song_title": self.current_song_title,
            "sequence_count": len(self.sequence_entries),
            "lyrics_store_count": len(self.lyrics_store),
        }
        return {
            "caller": {
                "file": caller.filename if caller else None,
                "line": caller.lineno if caller else None,
                "function": caller.name if caller else None,
            },
            "settings": settings,
            "state": state,
            "details": extra if isinstance(extra, dict) else {},
        }

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
            if not title or not sequence:
                continue
            chunks.append(f"{title}\n{sequence}")
        return "\n\n".join(chunks).strip()

    def _history_option_label(self, item: dict) -> str:
        week_start = str(item.get("week_start_date", "?"))
        week_end = str(item.get("week_end_date", "?"))
        seq = item.get("sequence_entries") if isinstance(item, dict) else []
        count = len(seq) if isinstance(seq, list) else 0
        return f"{week_start} ~ {week_end} ({count}곡)"

    # ── Repertoire dialog ──────────────────────────────────────────────
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
            QMessageBox.warning(self, "레파토리 입력", "입력 형식을 확인해 주세요. (제목/진행순서 2줄 구성)")
            return
        self.repertoire_entries = entries
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
            QMessageBox.warning(self, "DB에서 추가", "진행 순서가 없어 추가하지 않았습니다.")
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
            QMessageBox.warning(self, "레파토리 수정", "두 줄(곡 제목/진행 순서)로 입력해 주세요.")
            return
        new_title = self._clean_repertoire_title(lines[0])
        new_seq = lines[1]
        if not new_title or not new_seq:
            QMessageBox.warning(self, "레파토리 수정", "곡 제목과 진행 순서를 모두 입력해 주세요.")
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
                if error is not None:
                    self.report_exception("weekly history auto sync", error)
            _bridge.call(on_done)

        threading.Thread(target=run, daemon=True).start()

    def apply_weekly_history_item(self, item: dict):
        sequence_entries = item.get("sequence_entries") if isinstance(item, dict) else None
        lyrics_by_title = item.get("lyrics_by_title") if isinstance(item, dict) else None
        if not isinstance(sequence_entries, list) or not isinstance(lyrics_by_title, dict):
            QMessageBox.critical(self, "DB 이력 불러오기", "선택한 주간 작업 이력 형식이 올바르지 않습니다.")
            return

        sequence_text = self._sequence_text_from_entries(sequence_entries)
        if not sequence_text:
            QMessageBox.warning(self, "DB 이력 불러오기", "선택한 주간 작업 이력에 레파토리가 없습니다.")
            return

        self.repertoire_entries = self._normalize_repertoire_entries(sequence_text)
        self.refresh_repertoire_sort_list()

        self.lyrics_store = {str(k): str(v) for k, v in lyrics_by_title.items()}
        self._loaded_history_lyrics_by_title = dict(self.lyrics_store)
        self.refresh_song_list(show_message=False, trigger_download=False)

        week_start = item.get("week_start_date", "?")
        week_end = item.get("week_end_date", "?")
        self.log(f"[완료] 주간 작업 이력을 불러왔습니다: {week_start} ~ {week_end}")

    def reset_loaded_history(self):
        self.repertoire_entries = []
        self.refresh_repertoire_sort_list()
        self.lyrics_store = {}
        self._loaded_history_lyrics_by_title = {}
        self.current_song_title = None
        self.current_song_label.setText("곡을 선택하세요")
        self.populate_song_list([], preserve_current=False)
        self.show_lyrics_guide()
        self.log("[안내] 불러온 작업 내용을 초기화했습니다.")

    def reload_current_song_lyrics_from_history(self):
        if not self.current_song_title:
            QMessageBox.information(self, "가사 불러오기", "먼저 곡을 선택하세요.")
            return
        lyrics = self._loaded_history_lyrics_by_title.get(self.current_song_title, "")
        if not str(lyrics).strip():
            QMessageBox.information(
                self, "가사 불러오기",
                f"'{self.current_song_title}'에 저장된 불러오기 이력이 없습니다.",
            )
            return
        self.lyrics_store[self.current_song_title] = str(lyrics)
        self.set_lyrics_editor_text(str(lyrics))
        self.log(f"[완료] '{self.current_song_title}' 가사를 다시 불러왔습니다.")

    # ── Song list refresh ──────────────────────────────────────────────
    def get_sequence_entries(self) -> list:
        if self.repertoire_entries:
            return [(title, seq) for title, seq in self.repertoire_entries]
        raise ValueError("레파토리 입력창이 비어 있습니다.")

    def refresh_song_list(self, show_message: bool = True,
                           trigger_download: bool = False) -> bool:
        try:
            sequence_entries = self.get_sequence_entries()
        except ValueError as e:
            self.log(f"[오류] {e}")
            QMessageBox.critical(self, "레파토리 입력 오류", str(e))
            return False

        self.sequence_entries = sequence_entries
        selected_index = self.populate_song_list(sequence_entries)

        if selected_index is not None:
            song_title = sequence_entries[selected_index][0]
            if song_title != self.current_song_title:
                self.load_lyrics_for_song(song_title)
        else:
            self.current_song_title = None
            self.current_song_label.setText("곡을 선택하세요")
            self.show_lyrics_guide()

        if show_message:
            self.log(f"[안내] 레파토리 {len(sequence_entries)}곡을 인식했습니다.")

        if trigger_download:
            QTimer.singleShot(100, lambda: self._run_download(auto=True))

        return True

    # ── Lyrics download ────────────────────────────────────────────────
    def _run_download(self, auto: bool = False):
        try:
            from auto_lyrics_downloader import download_missing_lyrics
        except Exception as e:
            self.report_exception("lyrics downloader import", e, extra={"auto": auto})
            self.log(f"[오류] 가사 다운로드 모듈을 불러오지 못했습니다: {e}")
            if not auto:
                QMessageBox.critical(self, "오류", f"가사 다운로드 모듈을 불러오지 못했습니다:\n{e}")
            return

        song_titles = [t for t, _ in self.sequence_entries]
        current_song = self.current_song_title
        server_url = self.get_server_url()
        sequence_map = {t: s for t, s in self.sequence_entries}

        self.set_action_buttons_state("disabled")
        self.set_editor_state("disabled")
        self.log("====================================")
        self.log("가사 다운로드를 시작합니다.")

        def run():
            try:
                downloaded = download_missing_lyrics(
                    song_titles=song_titles,
                    existing_lyrics=self.lyrics_store,
                    log_func=lambda msg: _bridge.call(lambda m=msg: self.log(m)),
                    server_url=server_url,
                    sequence_map=sequence_map,
                )
                def on_done():
                    self.lyrics_store.update(downloaded)
                    self.set_editor_state("normal")
                    if current_song:
                        self.load_lyrics_for_song(current_song)
                    if not auto:
                        QMessageBox.information(self, "완료", "가사 다운로드 작업이 완료되었습니다.")
                    self.set_action_buttons_state("normal")
                _bridge.call(on_done)
            except Exception as e:
                err = e
                def on_error():
                    self.report_exception("lyrics download", err, extra={"auto": auto})
                    self.log(f"[오류] 가사 다운로드에 실패했습니다: {err}")
                    if not auto:
                        QMessageBox.critical(self, "오류", f"가사 다운로드에 실패했습니다:\n{err}")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                _bridge.call(on_error)

        threading.Thread(target=run, daemon=True).start()

    # ── Lyrics catalog save ────────────────────────────────────────────
    def _save_lyrics_to_catalog_async(self, song_title: str, lyrics: str):
        if not song_title or not lyrics.strip():
            return
        server_url = self.get_server_url()
        seq_map = {t: s for t, s in self.sequence_entries}
        sequence = seq_map.get(song_title, "")

        def run():
            try:
                from ppt_server_client import save_lyrics_to_catalog, PptServerUnavailable
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
            err = FileNotFoundError(f"assets/{SONGLIST_TEMPLATE_FILE_NAME}")
            self.report_exception("songlist template missing", err)
            self.log(f"[오류] 송리스트 카드 템플릿을 찾을 수 없습니다: 'assets/{SONGLIST_TEMPLATE_FILE_NAME}'")
            QMessageBox.critical(self, "오류", f"템플릿 파일을 찾을 수 없습니다:\nassets/{SONGLIST_TEMPLATE_FILE_NAME}")
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
            if cancel_event.is_set():
                return
            cancel_event.set()
            self.log("[취소] 송리스트 카드 생성 취소를 요청했습니다.")
            self.update_busy_dialog("취소 요청을 처리하고 있습니다.")

        self.set_action_buttons_state("disabled")
        self.set_editor_state("disabled")
        self.log("====================================")
        self.log("송리스트 카드를 생성합니다.")
        self.show_busy_dialog("송리스트 생성 중", "송리스트 카드를 생성하고 있습니다.", on_cancel=request_cancel)

        def run():
            try:
                source = "서버"
                server_url = self.get_server_url()
                raise_if_cancelled()
                _bridge.call(lambda: self.log(f"[정보][송리스트][서버요청] endpoint=/songlist-card, 서버={server_url}"))
                _bridge.call(lambda: self.update_busy_dialog("서버에 송리스트 생성을 요청하고 있습니다."))
                try:
                    week_num = generate_songlist_card_via_server(
                        server_url, template_file, song_titles, temp_output_file)
                    raise_if_cancelled()
                except PptServerUnavailable as e:
                    raise_if_cancelled()
                    source = "로컬"
                    _bridge.call(lambda err=e: self.log(f"[경고][송리스트][서버연결불가] 로컬 변환으로 전환: {err}"))
                    _bridge.call(lambda: self.update_busy_dialog("서버 연결이 되지 않아 로컬에서 변환하고 있습니다."))
                    week_num = build_songlist_card(template_file, song_titles, temp_output_file)
                    raise_if_cancelled()
                except PptServerResponseError as e:
                    raise_if_cancelled()
                    if e.status_code and e.status_code >= 500:
                        self.report_exception("songlist server processing fallback", e)
                        source = "로컬"
                        _bridge.call(lambda err=e: self.log(f"[경고][송리스트][서버처리오류] 로컬 변환으로 전환: {err}"))
                        _bridge.call(lambda: self.update_busy_dialog("서버 처리 오류로 로컬에서 변환하고 있습니다."))
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
                    open_msg = "\n생성된 파일을 엽니다." if opened else "\n생성된 파일 자동 열기에 실패했습니다."
                    QMessageBox.information(
                        self, "완료",
                        f"송리스트 카드를 생성했습니다.\n저장 위치: out/{SONGLIST_OUTPUT_FILE_NAME}" + open_msg,
                    )
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                _bridge.call(on_done)

            except OperationCancelled:
                def on_cancelled():
                    self.hide_busy_dialog()
                    self.log("[취소] 송리스트 카드 생성을 중단했습니다.")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                _bridge.call(on_cancelled)

            except PptServerResponseError as e:
                err = e
                def on_server_error():
                    if cancel_event.is_set():
                        return
                    self.report_exception("songlist server request", err)
                    self.hide_busy_dialog()
                    self.log(f"[오류][송리스트][서버요청실패]: {err}")
                    QMessageBox.critical(self, "오류", f"송리스트 카드 생성 요청이 거부되었습니다:\n{err}")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                _bridge.call(on_server_error)

            except LocalOfficeUnavailable as e:
                err = e
                def on_local_error():
                    if cancel_event.is_set():
                        return
                    self.report_exception("songlist local office", err)
                    self.hide_busy_dialog()
                    self.log(f"[오류][송리스트][로컬오피스실패]: {err}")
                    QMessageBox.critical(self, "오류", f"송리스트 카드 생성에 실패했습니다:\n{err}")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                _bridge.call(on_local_error)

            except Exception as e:
                err = e
                def on_error():
                    if cancel_event.is_set():
                        return
                    self.report_exception("songlist unknown", err)
                    self.hide_busy_dialog()
                    self.log(f"[오류][송리스트][알수없음]: {err}")
                    QMessageBox.critical(self, "오류", f"송리스트 카드 생성에 실패했습니다:\n{err}")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                _bridge.call(on_error)

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
            template_dir = os.path.join(ASSETS_DIR_NAME, TEMPLATE_DIR_NAME)
            err = FileNotFoundError(template_dir)
            self.report_exception("ppt template missing", err)
            self.log(f"[오류] 템플릿 파일을 찾을 수 없습니다: '{template_dir}'")
            QMessageBox.critical(self, "오류", f"템플릿 파일을 찾을 수 없습니다:\n{template_dir}")
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
            self.log("[오류] 생성할 가사가 없습니다.")
            QMessageBox.warning(self, "파워포인트 생성", "생성할 가사가 없습니다.")
            return

        output_file = os.path.join(self.get_output_dir(), OUTPUT_FILE_NAME)
        server_url = self.get_server_url()

        self.set_action_buttons_state("disabled")
        self.set_editor_state("disabled")
        self.show_busy_dialog("파워포인트 생성 중", "파워포인트 파일을 생성하고 있습니다.")

        def run():
            try:
                source = "서버"
                _bridge.call(lambda: self.log(f"[정보][PPT][서버요청] endpoint=/generate-ppt, 서버={server_url}"))
                _bridge.call(lambda: self.update_busy_dialog("서버에 파워포인트 생성을 요청하고 있습니다."))
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
                    _bridge.call(lambda err=e: self.log(
                        f"[경고][PPT][서버연결불가] 로컬 PowerPoint COM으로 전환합니다: {err}"))
                    _bridge.call(lambda: self.update_busy_dialog("서버 연결이 되지 않아 로컬에서 생성하고 있습니다."))
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
                        _bridge.call(lambda err=e: self.log(
                            f"[경고][PPT][서버처리오류] 로컬 PowerPoint COM으로 전환합니다: {err}"))
                        _bridge.call(lambda: self.update_busy_dialog("서버 처리 오류로 로컬에서 생성하고 있습니다."))
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
                    self.log(f"\n[완료] 파워포인트 파일을 만들었습니다: '{output_file}' [{source}, {generated_count}곡]\n")
                    opened = self.open_output_file(output_file)
                    open_msg = "\n생성된 파일을 엽니다." if opened else "\n생성된 파일 자동 열기에 실패했습니다."
                    QMessageBox.information(
                        self, "완료",
                        "파워포인트 파일을 생성했습니다.\n저장 위치: out/integrated_lyrics.pptx" + open_msg,
                    )
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                _bridge.call(on_done)

            except PptServerResponseError as e:
                err = e
                def on_server_error():
                    self.report_exception("ppt server request", err)
                    self.hide_busy_dialog()
                    self.log(f"[오류][PPT][서버요청실패]: {err}")
                    QMessageBox.critical(self, "오류", f"PPT 서버 요청이 거부되었습니다:\n{err}")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                _bridge.call(on_server_error)

            except LocalOfficeUnavailable as e:
                err = e
                def on_local_office_error():
                    self.report_exception("ppt local office", err)
                    self.hide_busy_dialog()
                    self.log(f"[오류][PPT][로컬오피스실패]: {err}")
                    QMessageBox.critical(self, "오류", str(err))
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                _bridge.call(on_local_office_error)

            except Exception as e:
                err = e
                def on_error():
                    self.report_exception("ppt unknown", err)
                    self.hide_busy_dialog()
                    self.log(f"[오류][PPT][알수없음] 파워포인트 생성에 실패했습니다: {err}")
                    QMessageBox.critical(self, "오류", f"파워포인트 파일을 생성하지 못했습니다:\n{err}")
                    self.set_editor_state("normal")
                    self.set_action_buttons_state("normal")
                _bridge.call(on_error)

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
            self.log(f"[오류] 생성된 파일을 열지 못했습니다: {e}")
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

    def download_work_log(self, show_message: bool = True) -> Optional[str]:
        default_name = f"work-log-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        try:
            initial_dir = self.get_output_dir()
        except Exception:
            initial_dir = os.getcwd()

        save_path, _ = QFileDialog.getSaveFileName(
            self, "작업 로그 저장",
            os.path.join(initial_dir, default_name),
            "Text Files (*.txt);;All Files (*.*)",
        )
        if not save_path:
            return None

        with open(save_path, "w", encoding="utf-8") as f:
            f.write(self.build_work_log_text())

        self.log(f"[완료] 작업 로그를 저장했습니다: {save_path}")
        if show_message:
            QMessageBox.information(self, "작업 로그", f"작업 로그를 저장했습니다.\n{save_path}")
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
            QMessageBox.warning(self, "서버 버그 리포트", "버그 설명을 입력해 주세요.")
            return

        report = build_error_report(
            context="manual bug report",
            message=message,
            traceback_text="",
            extra={"log_file": os.path.abspath(log_path)},
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
                if error is not None:
                    self.report_exception("manual bug report", error)
                    QMessageBox.critical(self, "서버 버그 리포트", f"리포트 전송에 실패했습니다.\n{error}")
                    return
                self.log("[완료] 서버에 버그 리포트를 전송했습니다.")
                QMessageBox.information(self, "서버 버그 리포트", "버그 리포트를 전송했습니다.")
            _bridge.call(on_done)

        threading.Thread(target=run, daemon=True).start()

    def show_app_about(self):
        QMessageBox.information(
            self, "앱 정보",
            "PPT Gen\n레파토리와 가사를 정리해 파워포인트를 생성합니다.",
        )

    # ── Window close ───────────────────────────────────────────────────
    def closeEvent(self, event):
        try:
            self.sync_weekly_history_from_server(log_result=False)
        except Exception as e:
            self.report_exception("weekly history sync on close", e)
        event.accept()


# ─── Entry point ────────────────────────────────────────────────────────────
def main():
    global _bridge

    # Enable high-DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(APP_DISPLAY_NAME)

    # Apply Fluent Design
    setTheme(Theme.LIGHT)
    setThemeColor("#D63B6E")  # Brand Rose

    # Initialize main-thread callback bridge
    _bridge = _Bridge()

    window = LyricsApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
