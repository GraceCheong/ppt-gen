# PO,RR

예배 레파토리와 가사를 입력해 하나의 PowerPoint 파일로 만드는 도구입니다. GUI 클라이언트는 PPT 서버를 먼저 사용하고, 서버가 응답하지 않으면 로컬 PowerPoint COM → LibreOffice 순으로 자동 전환합니다.

## 파일 구성

```text
src/
  main.py
  ppt_server_client.py
  ppt_service.py
  ppt_builder.py
  songlist_builder.py
  auto_lyrics_downloader.py
server/
  convert_server.py
  requirements.txt
scripts/
  build_release.py
  LyricsToPPT.spec
assets/
  templates/template 2.pptx
  atempo.ico
  atempo.png
  logo.png
  background.png
  sequences_sample.txt
tests/
docs/
requirements.txt
```

## 개발 환경 설정

```powershell
pip install -r requirements.txt
```

## 실행

```powershell
python src/main.py
```

Python으로 직접 실행할 때 PPT 서버 기본 주소는 `http://localhost:8010`입니다. 배포 실행 파일의 기본값은 `http://220.93.112.53:8010`입니다.

## 빌드

PyInstaller로 Windows 실행 파일을 만들고 배포용 zip으로 패키징합니다.

```powershell
pip install pyinstaller
python scripts/build_release.py
```

출력: `Release/v1.0.X/LyricsToPPT-Windows-v1.0.X.zip`

이미 같은 버전의 zip이 있으면 오류가 납니다. 덮어쓰려면 `--force`를 추가합니다.

```powershell
python scripts/build_release.py --force
```

## PPT 서버

```powershell
pip install -r server/requirements.txt
uvicorn server.convert_server:app --host 0.0.0.0 --port 8010
```

포트:
- PPT 서버: `8010`
- GUI 클라이언트: 별도 listen 포트 없음 (Windows가 임시 포트 자동 할당)

### 로컬 fallback 순서

서버가 응답하지 않으면 클라이언트는 순서대로 전환합니다.

1. PowerPoint COM
2. LibreOffice
3. 설치 안내 표시

### 오류 리포트

처리되지 않은 예외나 생성 실패 시 서버의 `/client-error-report`로 자동 전송합니다. 리포트에는 호출 함수, 파일/라인, 현재 설정값, 선택 템플릿, 서버 주소, 최근 로그 일부가 포함됩니다. 가사 본문과 레파토리 원문은 전송하지 않습니다. 서버는 수신한 리포트를 `out/error_reports/YYYY-MM-DD.jsonl`에 저장합니다.

## 테스트

```powershell
pytest
```

## 템플릿 구조

`assets/templates/`의 모든 `.pptx` 파일을 시작 시 드롭다운에 자동으로 불러옵니다. Google Drive 공유 폴더와 동기화되며, 새 템플릿이 있으면 다운로드 후 드롭다운을 갱신합니다.

슬라이드 마스터에 아래 레이아웃이 있어야 합니다.

```text
제목
가사
```
