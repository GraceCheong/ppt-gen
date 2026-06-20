# PO,RR

예배 레파토리와 가사를 입력해 하나의 PowerPoint 파일로 만드는 도구입니다. GUI 클라이언트는 PPT 서버를 먼저 사용하고, 서버가 응답하지 않으면 로컬 PowerPoint COM → LibreOffice 순으로 자동 전환합니다.

## 파일 구성

```text
src/
  main.py               # 배포 빌드 진입점 (레거시 UI)
  main_ctk.py           # CustomTkinter UI (현재 메인 개발 대상)
  main_ttk.py           # ttkbootstrap UI (대안)
  ppt_server_client.py
  ppt_service.py
  ppt_builder.py
  songlist_builder.py
  auto_lyrics_downloader.py
  constants.py
server/
  convert_server.py
  requirements.txt
tools/
  server/
    run-server.bat
  release/
    build_release.py
    LyricsToPPT.spec
assets/
  templates/
  atempo.ico
  atempo.png
  logo.png
  background.png
  sequences_sample.txt
docs/
requirements.txt
```

## 개발 환경 설정

### Python 버전

- `main_ctk.py` / `main_ttk.py`: Python 3.10 필요 (`venv310`)
- `main.py`: Python 3.9+ 가능

```powershell
# Python 3.10 환경 (CTk/ttk UI)
py -3.10 -m venv venv310
.\venv310\Scripts\pip install -r requirements.txt

# 기존 환경
pip install -r requirements.txt
```

## 실행

```powershell
# CustomTkinter UI (현재 메인)
.\venv310\Scripts\python.exe src/main_ctk.py

# ttkbootstrap UI
.\venv310\Scripts\python.exe src/main_ttk.py

# 레거시 UI
python src/main.py
```

PPT 서버 기본 주소:
- 로컬 개발: `http://localhost:8010`
- 배포 실행 파일: `http://porr.sccatempo.app`

## 빌드

PyInstaller로 Windows 실행 파일을 만들고 배포용 zip으로 패키징합니다.

```powershell
pip install pyinstaller
python tools/release/build_release.py
```

출력: `Release/v1.1.X/LyricsToPPT-Windows-v1.1.X.zip`

이미 같은 버전의 zip이 있으면 오류가 납니다. 덮어쓰려면 `--force`를 추가합니다.

```powershell
python tools/release/build_release.py --force
```

## PPT 서버

```powershell
pip install -r server/requirements.txt
uvicorn server.convert_server:app --host 0.0.0.0 --port 8010
```

포트:
- PPT 서버: `8010`
- GUI 클라이언트: 별도 listen 포트 없음

### 주요 엔드포인트

| 엔드포인트 | 설명 |
|---|---|
| `GET /health` | 서버 상태 및 COM 사용 가능 여부 |
| `POST /generate-ppt` | 통합 PPT 생성 |
| `POST /songlist-card` | 송리스트 카드 PNG 생성 |
| `GET /lyrics/search` | 가사 DB 검색 |
| `GET /lyrics/by-title` | 곡명으로 가사 조회 |
| `POST /lyrics` | 가사 DB 저장/업데이트 |
| `POST /client-error-report` | 클라이언트 오류 리포트 수신 |

### 로컬 fallback 순서

서버가 응답하지 않으면 클라이언트는 순서대로 전환합니다.

1. PowerPoint COM
2. LibreOffice
3. 설치 안내 표시

## 템플릿 구조

`assets/templates/`의 모든 `.pptx` 파일을 시작 시 드롭다운에 자동으로 불러옵니다. Google Drive 공유 폴더와 동기화되며, 새 템플릿이 있으면 다운로드 후 드롭다운을 갱신합니다.

슬라이드 마스터에 아래 레이아웃 이름이 있어야 합니다.

```text
제목    ← 곡 제목 슬라이드
가사    ← 가사 슬라이드
```

가사 슬라이드는 텍스트 자리 표시자를 두 개 권장합니다. 프로그램은 면적이 가장 큰 자리 표시자를 가사 본문, 두 번째를 곡 제목으로 사용합니다.

## 주요 상수 (`src/constants.py`)

| 상수 | 기본값 | 설명 |
|---|---|---|
| `SERVER_PORT` | `8010` | 서버 포트 |
| `LOCAL_SERVER_HOST` | `localhost` | 로컬 개발 주소 |
| `RELEASE_SERVER_HOST` | `220.93.112.53` | 배포 서버 주소 |
| `DEFAULT_MAX_LINES_PER_SLIDE` | `4` | 슬라이드당 최대 줄 수 |

## 로컬 산출물

| 경로 | 내용 |
|---|---|
| `out/integrated_lyrics.pptx` | 생성된 통합 PPT |
| `out/error_reports/` | 클라이언트 오류 리포트 |
| `out/template_previews/` | 템플릿 썸네일 캐시 |
| `logs/service.log` | 서버 로그 (`.gitignore` 제외) |
