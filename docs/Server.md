# PPT Generation Server - 리눅스 서버 실행 (systemd)

서버 코드 자체는 OS에 종속되지 않습니다. PPT/PNG 변환 시 Windows에서는 PowerPoint COM을 우선 사용하지만, 리눅스에서는 `sys.platform`을 확인해 자동으로 **LibreOffice**로 대체 실행됩니다 (`src/ppt_service.py`, `src/songlist_builder.py`). 별도의 코드 수정 없이 리눅스에서 그대로 기동할 수 있습니다.

---

## 구성

| 항목 | 값 |
|------|-----|
| 서비스 이름 | `ppt-gen-server` (예시, 자유롭게 지정) |
| 관리 도구 | systemd |
| Python 버전 | **3.12 이상 필수** (아래 "Python 버전 요구사항" 참고) |
| 실행 파일 | `<프로젝트 경로>/.venv/bin/python` |
| 실행 명령 | `-m uvicorn server.convert_server:app --host 0.0.0.0 --port 8010 --log-level info` |
| 포트 | `8010` |
| 로그 | `journalctl -u ppt-gen-server` 또는 `logs/service.log` |
| 시작 방식 | 부팅 시 자동 시작 (`systemctl enable`) |
| API 문서 | http://localhost:8010/docs |

---

## Python 버전 요구사항 (중요)

`server/app/api/exports.py` 등에서 f-string 표현식 내부에 백슬래시를 사용합니다 (`f"...{re.sub(r'[^\\w가-힣\\-]', ...)}"`). 이 문법은 **PEP 701(Python 3.12)** 이전에는 `SyntaxError`가 발생합니다.

```
SyntaxError: f-string expression part cannot include a backslash
```

Ubuntu 22.04(LTS) 기본 `python3`는 3.10입니다. 리눅스 서버에 3.12 이상을 별도로 설치해야 합니다.

```bash
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa   # Ubuntu 22.04 등 3.12가 기본이 아닌 경우
sudo apt update
sudo apt install -y python3.12 python3.12-venv
```

Ubuntu 24.04(LTS)는 `python3.12`가 기본으로 포함되어 있어 위 PPA 단계가 필요 없습니다. `python3.12 --version`으로 확인하세요.

---

## 사전 준비

### 1. 시스템 패키지 설치

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv git libreoffice fonts-noto-cjk
```

- `libreoffice`: PPT COM이 없는 리눅스에서 PPTX 저장·PNG 변환을 담당 (`soffice` 바이너리 필요, `find_libreoffice()`가 `PATH`에서 `soffice`/`libreoffice`를 탐색).
- `fonts-noto-cjk`: 가사/한글 렌더링용 CJK 폰트. 템플릿이 시스템에 없는 커스텀 폰트(예: 송리스트 카드 제목에 쓰이는 `Diphylleia`, `src/songlist_builder.py`의 `_TITLE_FONT`)를 지정한 경우, 해당 폰트 파일을 서버에도 설치해야 LibreOffice가 대체 폰트로 렌더링하지 않습니다.
  ```bash
  mkdir -p ~/.local/share/fonts
  cp /path/to/Diphylleia*.ttf ~/.local/share/fonts/
  fc-cache -f
  ```

### 2. 코드 배치

```bash
sudo mkdir -p /opt/ppt-gen
sudo chown $USER:$USER /opt/ppt-gen
git clone <레포 URL> /opt/ppt-gen
cd /opt/ppt-gen
git checkout fix/korean-font-inheritance   # 배포할 브랜치
```

### 3. 가상환경 및 의존성 설치

```bash
cd /opt/ppt-gen
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt -r server/requirements.txt
```

> **참고:** `server/requirements.txt`의 `comtypes`는 Windows 전용 COM 라이브러리이지만 순수 Python 패키지라 리눅스에도 설치는 됩니다(`import comtypes` 자체는 실패). `/health`, `/api/health`의 `"comtypes": true`는 모듈이 *설치되어 있는지*만 확인하므로 리눅스에서도 `true`로 표시되지만, 실제 COM 기능은 동작하지 않습니다. 아래 "리눅스에서의 기능 제약" 참고.

### 4. 환경변수 (.env, 선택)

Windows 서비스와 동일하게 프로젝트 루트에 `.env` 또는 `env/.env`를 두면 `server/app/config.py`가 자동으로 읽습니다.

```bash
# .env 예시
PORR_CORS_ORIGINS=http://localhost:5173,https://your-web-domain.example
PORR_DATA_DIR=/opt/ppt-gen/out
GDRIVE_SYNC_ENABLED=false
```

### 5. 로그 디렉터리

```bash
mkdir -p /opt/ppt-gen/logs
```

---

## systemd 유닛 등록

`/etc/systemd/system/ppt-gen-server.service` 생성:

```ini
[Unit]
Description=PPT Generation Server (FastAPI/uvicorn)
After=network.target

[Service]
Type=simple
User=ppt-gen
Group=ppt-gen
WorkingDirectory=/opt/ppt-gen
Environment="PATH=/opt/ppt-gen/.venv/bin"
ExecStart=/opt/ppt-gen/.venv/bin/python -m uvicorn server.convert_server:app --host 0.0.0.0 --port 8010 --log-level info
Restart=on-failure
RestartSec=5
StandardOutput=append:/opt/ppt-gen/logs/service.log
StandardError=append:/opt/ppt-gen/logs/service.log

[Install]
WantedBy=multi-user.target
```

> `User`/`Group`은 SYSTEM 계정처럼 과도한 권한을 주지 않도록 전용 계정(`sudo useradd -r -s /usr/sbin/nologin ppt-gen`) 사용을 권장합니다. Windows와 달리 PowerPoint COM 제약(사용자 계정 필수)이 없으므로 자유롭게 지정 가능합니다.

등록 및 시작:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ppt-gen-server
sudo systemctl start ppt-gen-server
```

---

## 일상 관리 명령어

```bash
# 시작
sudo systemctl start ppt-gen-server

# 중지
sudo systemctl stop ppt-gen-server

# 재시작
sudo systemctl restart ppt-gen-server

# 상태 확인
systemctl status ppt-gen-server

# 로그 확인 (journal)
journalctl -u ppt-gen-server -f

# 로그 확인 (파일)
tail -f /opt/ppt-gen/logs/service.log
```

---

## 설정 변경 후 재시작

코드 변경(`git pull`)만으로는 반영되지 않으며, 재시작이 필요합니다. `requirements.txt`가 변경된 경우 패키지도 다시 설치합니다.

```bash
cd /opt/ppt-gen
git pull
source .venv/bin/activate
pip install -r requirements.txt -r server/requirements.txt   # 의존성 변경 시에만
sudo systemctl restart ppt-gen-server
```

유닛 파일(`ExecStart` 등) 자체를 수정한 경우에는 `daemon-reload`가 먼저 필요합니다.

```bash
sudo systemctl daemon-reload
sudo systemctl restart ppt-gen-server
```

---

## 완전 제거

```bash
sudo systemctl stop ppt-gen-server
sudo systemctl disable ppt-gen-server
sudo rm /etc/systemd/system/ppt-gen-server.service
sudo systemctl daemon-reload
```

---

## 문제 해결

### 서버가 시작되지 않을 때

```bash
# 최근 로그 확인
journalctl -u ppt-gen-server -n 100 --no-pager

# 서비스 상세 상태
systemctl status ppt-gen-server

# venv python으로 직접 실행해 에러 확인
cd /opt/ppt-gen
source .venv/bin/activate
python -m uvicorn server.convert_server:app --host 0.0.0.0 --port 8010
```

### `SyntaxError: f-string expression part cannot include a backslash`

venv가 Python 3.12 미만으로 생성됨. `python --version`으로 확인 후 3.12+로 venv를 다시 만드세요.

```bash
python3.12 --version
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r server/requirements.txt
```

### 포트 충돌 확인

```bash
sudo ss -ltnp | grep :8010
# 또는
sudo lsof -i :8010
```

### 서비스 마지막 상태 확인

```bash
systemctl is-active ppt-gen-server
systemctl is-enabled ppt-gen-server
```

### LibreOffice 변환 실패 (`LocalOfficeUnavailable`, 503)

`/generate-ppt`, `/songlist-card`가 PowerPoint COM 대신 LibreOffice로 최종 저장/변환을 시도합니다. 실패 시 확인:

```bash
which soffice || which libreoffice
soffice --headless --convert-to pdf --outdir /tmp /opt/ppt-gen/assets/templates/*.pptx
```

`soffice`가 없으면 `sudo apt install libreoffice`로 설치합니다. 서비스 계정(`User=`)의 홈 디렉터리에 LibreOffice 프로필 캐시(`~/.config/ppt-gen/lo-profile`, `_lo_user_install_arg()`)를 쓸 수 있는 권한이 있는지도 확인하세요.

### 한글/커스텀 폰트가 다르게 보일 때

리눅스 기본 이미지에는 Windows 전용 폰트(맑은 고딕 등)나 이 프로젝트의 커스텀 폰트(`Diphylleia`)가 없습니다. LibreOffice는 없는 폰트를 조용히 대체 폰트로 바꿔치기하므로 오류 없이 결과물만 달라 보입니다.

```bash
fc-list | grep -i diphylleia
fc-list | grep -i -E "nanum|noto.*cjk"
```

필요한 폰트 파일을 `/usr/share/fonts/` 또는 `~/.local/share/fonts/`에 복사한 뒤 `fc-cache -f`를 실행하세요.

### 방화벽 (외부에서 접속해야 하는 경우)

```bash
sudo ufw allow 8010/tcp
```

---

## 리눅스에서의 기능 제약

Windows(PowerPoint COM 사용 가능)와 달리, 리눅스에서는 COM에 의존하는 일부 기능이 자동으로 비활성화되거나 대체됩니다.

| 기능 | Windows | 리눅스 |
|---|---|---|
| `/generate-ppt`, `/songlist-card` | PowerPoint COM → 실패 시 LibreOffice | LibreOffice로 바로 처리 (정상 동작) |
| `POST /convert` (레거시 PPTX→PNG) | PowerPoint COM 렌더링 | **미지원** — `comtypes` import 자체가 실패해 500 에러 반환 (`server/app/api/exports.py:_convert_sync`) |
| 템플릿 썸네일 생성 (COM 렌더링 단계) | 지원 | PPTX 내장 썸네일 추출까지만 지원, 임베디드 썸네일이 없는 템플릿은 실패 (`template_preview_service.py`) |
| `GET /health`, `GET /api/health`의 `comtypes` 필드 | 실제 COM 사용 가능 여부와 대체로 일치 | 모듈 설치 여부만 확인 — 리눅스에서도 `true`로 표시되지만 실제로는 사용 불가 |

메인 웹앱(`apps/web`)이 사용하는 `/api/exports/pptx`, `/api/exports/songlist-card` 흐름은 모두 LibreOffice 경로를 타므로 정상 동작합니다.

---

## Windows(NSSM) 대비 차이 요약

| 항목 | Windows (`docs/Service.md`) | 리눅스 (본 문서) |
|---|---|---|
| 서비스 관리자 | NSSM | systemd |
| 실행 계정 제약 | 반드시 사용자 계정 (PowerPoint COM 때문에 SYSTEM 불가) | 전용 서비스 계정 사용 가능, 별도 제약 없음 |
| PPT 최종 저장/PNG 변환 | PowerPoint COM 우선 | LibreOffice만 사용 |
| 로그 확인 | `Get-Content logs\service.log -Tail 50` | `journalctl -u ppt-gen-server -f` 또는 `tail -f logs/service.log` |
| 등록 명령 | `nssm install ...` | `systemctl enable ppt-gen-server` |
