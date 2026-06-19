# PO,RR 구현 메모 (2026-06-20)

이 문서는 현재 코드베이스 기준으로, 지금까지 구현된 핵심 기능과 동작 방식을 빠르게 파악하기 위한 내부 메모입니다.

## 1) 제품 목적

- 예배 레파토리와 가사를 입력해 하나의 통합 PPT를 생성한다.
- 추가로 송리스트 카드를 PNG로 생성한다.
- GUI 클라이언트는 서버 우선, 실패 시 로컬 오피스 경로로 자동 전환한다.

## 2) 전체 구조

- GUI: `src/main.py`
- 생성 로직: `src/ppt_builder.py`, `src/ppt_service.py`, `src/songlist_builder.py`
- 자동 가사 다운로드: `src/auto_lyrics_downloader.py`
- 서버 통신: `src/ppt_server_client.py`
- 서버(FastAPI): `server/convert_server.py`
- 오류 리포팅: `src/error_reporter.py`
- 배포/운영: `tools/release/build_release.py`, `tools/server/run-server.bat`, `docs/Service.md`
- CI/CD: `.github/workflows/build.yml` (GitHub Actions, tag 기반 Windows/macOS 릴리스 자동 빌드)

## 3) 구현 완료 기능

### 3-1. GUI 워크플로우

- 레파토리 입력/인식, 곡별 가사 편집, PPT 생성, 송리스트 카드 생성까지 단일 화면에서 처리.
- 템플릿 드롭다운 자동 로딩 및 템플릿 프리뷰(썸네일/캐시 기반) 제공.
- 템플릿 Google Drive 동기화(gdown) 및 수동 새로고침 버튼 제공.
- 비동기 작업 중 BusyDialog(진행 표시/취소 지원) 제공.

### 3-2. 레파토리 입력 모델 고도화

- 자유 입력 텍스트를 제목/시퀀스 쌍으로 정규화해 `repertoire_entries` 구조로 관리.
- 레파토리 정렬 리스트를 통한 드래그 앤 드롭 순서 변경 지원.
- 항목 더블클릭 편집 지원.
- 정렬/편집 결과를 시퀀스 텍스트로 동기화.

### 3-3. 통합 PPT 생성

- 템플릿에서 제목/가사 레이아웃을 찾아 슬라이드를 누적 생성.
- 파트 시퀀스 파싱, 본문 줄 수 제한, 문자 수 기준 줄바꿈, 폰트 크기 적용 지원.
- 누락 가사/파트에 대한 스킵 처리 및 결과 카운트 반환.

### 3-4. 송리스트 카드 생성(PNG)

- 송리스트용 템플릿에 곡 목록을 반영해 PPTX 생성 후 PNG 변환.
- 주차(week) 컬러 계산과 텍스트/도형 컬러 반영.
- 변환 경로 다중화: 서버/COM/LibreOffice.

### 3-5. 서버(FastAPI) 기능

- `/health`: 상태 및 COM 사용 가능 여부 제공.
- `/convert`: PPTX 첫 슬라이드 PNG 변환.
- `/generate-ppt`: 템플릿 + payload로 통합 PPT 생성.
- `/songlist-card`: 송리스트 카드 PNG 생성.
- `/history/weekly`, `/history/db`: 주간 이력 조회/DB 다운로드.
- `/client-error-report`: 클라이언트 오류 리포트 수집.

### 3-6. 주간 이력 저장

- 서버에서 주차 기준(토요일 종료)으로 레파토리 스냅샷을 SQLite에 업서트 저장.
- 클라이언트는 서버 이력을 동기화하고 로컬 캐시로 유지.
- 과거 주차 이력을 UI 아코디언 형태로 조회/적용 가능.

### 3-7. 오류 보고 체계

- 클라이언트 예외 훅(sys/threading/tkinter) 연동.
- 오류 발생 시 컨텍스트/설정/상태/최근 로그를 포함해 서버로 비동기 전송.
- 개인정보 민감도가 높은 가사 원문/레파토리 원문은 전송 대상에서 제외.

### 3-8. 배포/운영 체계

- PyInstaller 기반 Windows 단일 배포 패키지 생성 스크립트 제공.
- 서버는 작업 스케줄러(Task Scheduler) 기반 상시 운영 문서화.
- 서비스 로그 확인/재등록/제거 절차 정리.

### 3-9. 자동 가사 다운로드

- 레파토리 등록 후 Bugs Music 크롤링으로 가사 자동 수집 (`auto_lyrics_downloader.py`).
- 이미 가사가 있는 곡은 건너뜁니다.
- **조회 우선순위:** 메모리 → 서버 lyrics_catalog DB → Bugs 크롤링 → 크롤링 성공 시 catalog 저장.
- 레파토리 새로고침 시 자동 트리거(auto=True) 및 버튼 수동 실행 모두 지원.

### 3-10. 가사 카탈로그 DB 연동 검색

- 서버 SQLite `lyrics_catalog` 테이블에 가사를 누적 저장 (title 정규화 키 기준 중복 방지).
- **색인 경로:** PPT 생성(`/generate-ppt`) 시 스냅샷에서 자동 색인 (`source='history'`), Bugs 크롤링 성공 시 자동 저장 (`source='bugs'`), 가사 편집 후 곡 전환 시 백그라운드 저장 (`source='manual'`).
- **서버 엔드포인트:**
  - `GET /lyrics/search?q=검색어&limit=10` — 곡명 부분일치 검색
  - `GET /lyrics/by-title?title=곡명` — 정확한 곡명 조회 (404 = 없음)
  - `POST /lyrics` — `{title, lyrics, source, sequence}` upsert
- **GUI:** 레파토리 패널 상단 "🔍 DB에서 추가" 버튼 → `LyricsSearchDialog` 팝업 (300ms debounce 검색) → 선택 시 레파토리·가사 한 번에 채움.


## 4) 실패 대비(Fallback) 전략

### 4-1. GUI 기준 변환/생성 fallback

- 서버 우선 호출.
- 서버 불가 시 로컬 PowerPoint COM 시도.
- COM 실패 시 LibreOffice 시도.
- 최종 실패 시 설치/복구 안내 표시.

### 4-2. 송리스트 PNG 변환 안정화 포인트

- COM 내보내기에서 메모리 관련 오류가 발생할 수 있어 해상도 축소 재시도로 복원력 확보.
- LibreOffice 경로는 PPTX -> PDF -> 이미지(렌더링) 경유를 사용.
- 렌더링 실패 시 graceful failure 경로를 유지.

## 5) 데이터/산출물 위치

- 결과물: `out/integrated_lyrics.pptx` 등 `out/` 하위
- 주간 이력 DB: `out/history/weekly_repertoire.db`
- 오류 리포트: `out/error_reports/YYYY-MM-DD.jsonl`
- 템플릿 프리뷰 캐시: `out/template_previews/`

## 6) 현재 확인된 운영 포인트

- 서버 포트는 8010 사용.
- 서버 템플릿은 주기적으로 Google Drive와 동기화.
- COM 사용이 필요한 작업은 실행 계정/권한 설정에 민감하므로 `docs/Service.md`의 계정 설정 지침을 따라야 함.

## 7) 참고 문서

- `README.md`
- `docs/Service.md`
- `docs/Release.md`
