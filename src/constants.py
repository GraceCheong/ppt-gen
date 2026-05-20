import sys

APP_DISPLAY_NAME = "PO,RR"
APP_WINDOW_TITLE = "PO,RR by a tempo"

ASSETS_DIR_NAME = "assets"
ICON_FILE_NAME = "atempo.png"
ICON_ICO_FILE_NAME = "atempo.ico"
LOGO_FILE_NAME = "logo.png"
LOGO_SIZE = (356, 101)  # (width, height) in pixels
LOGO_DISPLAY_SCALE = 0.66
BACKGROUND_FILE_NAME = "background.png"
TEMPLATE_DIR_NAME = "templates"
TEMPLATE_FILE_NAME = ""
TEMPLATE_DOWNLOAD_URL = "https://drive.google.com/drive/folders/1XkQSzkHLhPXoyPVQ8QB8zmpw9Yv5u0v7?usp=sharing"
OUTPUT_FILE_NAME = "integrated_lyrics.pptx"
SONGLIST_TEMPLATE_FILE_NAME = f"{TEMPLATE_DIR_NAME}/songlist_template.pptx"
SONGLIST_OUTPUT_FILE_NAME = "songlist_card.png"
SERVER_PORT = 8010
LOCAL_SERVER_HOST = "localhost"
RELEASE_SERVER_HOST = "220.93.112.53"
DEFAULT_SERVER_HOST = RELEASE_SERVER_HOST if getattr(sys, "frozen", False) else LOCAL_SERVER_HOST
DEFAULT_SERVER_URL = f"http://{DEFAULT_SERVER_HOST}:{SERVER_PORT}"
DEFAULT_MAX_LINES_PER_SLIDE = 4
DEFAULT_MAX_CHARS_PER_LINE = 18
DEFAULT_LYRICS_FONT_SIZE = ""

TEMPLATE_PREVIEW_WIDTH = 46
TEMPLATE_PREVIEW_HEIGHT = 34
TEMPLATE_PREVIEW_IMAGE_MAX = (42, 24)

BRAND_FONT_CANDIDATES = (
    "Ok Mallang W",
    "나눔스퀘어라운드 ExtraBold",
    "나눔스퀘어 네오 Heavy",
    "나눔스퀘어 네오 ExtraBold",
    "나눔스퀘어 ExtraBold",
    "나눔바른고딕",
    "맑은 고딕",
)

APP_BG = "#eef2f6"
GRADIENT_TOP = "#eef2f6"
GRADIENT_MID = "#a1acbd"
GRADIENT_BOTTOM = "#f4dbe3"
PANEL_BG = "#fffafd"
PANEL_SOFT_BG = "#f1f4f7"
PANEL_BORDER = "#e8c6d0"
TEXT_BG = "#ffffff"
TEXT_FG = "#3d4756"
MUTED_FG = "#6f7a8b"
TITLE_FG = "#3d4756"
ACCENT = "#e7afbf"
ACCENT_DARK = "#bd778c"
ACCENT_SOFT = "#f8e6ec"
LOG_BG = "#3d4756"

SEQUENCE_GUIDE_TEXT = """레파토리를 입력한 후, 버튼을 눌러 가사를 다운로드 하세요:
한나의 노래
I-V1-V2-C-Inter-V2-C-C-Out
나의 하나님
I-V1-V1-C-Inter-V2-C-B-C-C
함께 지어져 가네
I-V-C-Inter-V-C-C-Out
우리 함께 기도해
I-V-C-I-V-C-C-V-C-C"""

LYRICS_GUIDE_TEXT = """가사를 다운로드 한 후, 레파토리에 사용한 파트 구분자를 다음과 같이 적어주세요:
V1
나의 사랑
너는 어여쁘고 참 귀하다
어느 보석보다 귀하다
네가 사랑스럽지 않을 때
너를 온전히 사랑하고
너와 함께 하려 내가 왔노라

V2
주의 사랑
이 사랑은 결코 변치 않아
모든 계절 돌보시네
풀은 마르고 꽃은 시드나
주의 말씀은 신실해
실수가 없으신 주만 바라라

C
주님의 나라와 뜻이
나의 삶 속에 임하시며
주님 알기를 주만 보기를 소망해
거룩히 살아갈 힘과
두렴 없는 믿음 주실
나의 하나님 완전한 사랑 찬양해

B
찬양하리 만군의 주
영원히 함께 하시네
존귀하신 사랑의 왕
영원히 통치하시네"""
