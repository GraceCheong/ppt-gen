# PO,RR 구현 메모

> 이 문서는 현재 코드베이스 기준으로 구현된 핵심 기능과 동작 방식을 빠르게 파악하기 위한 내부 메모입니다.
> 마지막 업데이트: 2026-06-22

---

## 1. 제품 목적

- 예배 레파토리와 가사를 입력해 통합 PPT를 생성한다.
- 송리스트 카드(PNG)를 생성한다.
- 웹 앱(React)과 데스크톱 앱(Tauri)에서 사용한다.
- 레거시 GUI(CustomTkinter/ttkbootstrap)도 계속 지원한다.

---

## 2. 전체 구조

```
apps/web/          React + Vite 웹앱
apps/desktop/      Tauri v2 데스크톱

server/
  app/             FastAPI 앱 (현재 메인 서버)
    api/           라우터 (health, templates, lyrics, history, exports, jobs, errors)
    services/      비즈니스 로직
    jobs/          Job Store (메모리 기반)
    workers/       PPT·송리스트 변환 워커
    storage/       파일 출력 경로 관리
  convert_server.py          레거시 엔드포인트 (GUI 호환용)
  porr_server_main.py        단독 실행 진입점 (sidecar용)

src/
  porr_core/       코어 로직 (repertoire, sequence, slide_estimator, schemas)
  ppt_builder.py   PPT 생성 로직
  ppt_service.py   PPT 생성 서비스
  songlist_builder.py  송리스트 카드 생성
  auto_lyrics_downloader.py  Bugs Music 크롤러
  ppt_server_client.py       GUI ↔ 서버 통신
  main_ttk.py      ttkbootstrap GUI (현재 주 GUI)
  main.py          CustomTkinter GUI
  constants.py     SERVER_PORT=8010 등

tools/
  build_sidecar.py  PyInstaller 패키징
  server/run-server.bat  서버 실행 배치 (Task Scheduler용)
```

---

## 3. 주요 기능 현황

### 3-1. Python 생성 로직

**통합 PPT 생성** (`ppt_builder.py`, `ppt_service.py`):
- 템플릿에서 제목/가사 레이아웃 탐색 → 슬라이드 누적 생성
- 파트 시퀀스 파싱, 줄 수 제한, 문자 수 기준 줄바꿈
- **레이아웃 placeholder 폰트 상속**: `add_slide()` 직후 lxml로 `lstStyle/pPr/rPr` 복사
- **마지막 연속 반복 파트 강조**: `…-C-C` → 마지막 C 슬라이드 1장만 생성, 볼드 + `#8B1A1A` (중간 반복 `V1-V1`은 일반 처리)

**송리스트 카드 생성** (`songlist_builder.py`):
- 주차 컬러 계산, 텍스트/도형 반영, PPTX → PNG
- COM 오류 시 해상도 축소 재시도, LibreOffice 경로: PPTX → PDF → 이미지

### 3-2. 레파토리 입력 모델 (`src/porr_core/`)

- 자유 입력 텍스트 → 제목/시퀀스 쌍으로 정규화
- `_normalize_sequence`: 구분자 `-` 기준 파트 이름 공백 제거 + 첫 글자 대문자
- 기존 DB 시퀀스도 앱 기동 시 자동 정규화

### 3-3. FastAPI 서버 (`server/app/`)

**레거시 엔드포인트** (GUI 호환):
```
GET  /health              상태 + COM 사용 가능 여부
POST /convert             PPTX 첫 슬라이드 → PNG
POST /generate-ppt        통합 PPT 생성 + lyrics_catalog 자동 색인
POST /songlist-card        송리스트 카드 PNG
GET  /history/weekly      주간 이력 조회
GET  /lyrics/search       가사 검색
POST /lyrics              가사 저장
```

**신규 API (`/api` prefix)**:
```
GET  /api/health
GET  /api/templates
POST /api/templates
GET  /api/lyrics/search?q=&limit=
GET  /api/lyrics/by-title?title=
POST /api/lyrics
POST /api/lyrics/bulk          ← title+sequence 일괄 upsert (빈 가사 허용)
POST /api/lyrics/download      ← Bugs Music 크롤링
GET  /api/history/weekly?year_from=
POST /api/history/weekly       ← 이력 생성 + lyrics_catalog 자동 upsert
PUT  /api/history/weekly/{date}/entries  ← 곡 목록 수정 (비밀번호)
PUT  /api/history/weekly/{date}/roles    ← 담당자 수정 (비밀번호)
GET  /api/history/db
POST /api/exports/pptx
POST /api/exports/songlist-card
GET  /api/jobs/{job_id}
GET  /api/jobs/{job_id}/download
```

### 3-4. 주간 이력 (`server/app/api/history.py`, `history_service.py`)

- 토요일(`week_end_date`) 기준 레파토리 스냅샷을 SQLite에 upsert 저장
- 컬럼: `week_end_date`, `sequence_entries` (JSON), `worship_leader`, `accompanist`, `prayer_person`
- 이력 저장·수정 시 `lyrics_catalog`에 자동 upsert (빈 가사, source='history')
- 비밀번호 검증: `.env`의 `PORR_EDIT_PASSWORD` (`os.environ.get`, 서버 시작 시 로드)

### 3-5. 가사 카탈로그 DB (`lyrics_catalog` 테이블)

**색인 경로:**
- `/generate-ppt` PPT 생성 시 (source='history')
- Bugs 크롤링 성공 시 (source='bugs')
- 가사 편집 후 곡 전환 시 (source='manual')
- 이력 저장·수정 시 (source='history')

**upsert 정책** (`lyrics_service.py`):
- 빈 가사로 upsert 시 기존 가사 보존: `CASE WHEN excluded.lyrics != '' THEN excluded.lyrics ELSE lyrics_catalog.lyrics END`

**검색 우선순위 (GUI)**: 메모리 → DB → Bugs 크롤링 → 성공 시 DB 저장

### 3-6. React 웹앱 (`apps/web/`)

**페이지:**
| 경로 | 기능 |
|---|---|
| `/app` | 3-panel 작업 화면 (SetlistPanel + LyricsEditor + DeckPanel) |
| `/history` | 이력 (달력/목록 뷰) |
| `/lyrics` | 가사 DB 검색·관리 |
| `/graph` | 곡 관계도 |
| `/templates` | 템플릿 관리 |

**이력 달력 뷰** (`CalendarView.tsx`):
- 월별 달력 그리드 + 선택된 토요일 상세 패널 (md:w-64)
- 토요일 셀에 인도자 이름 인라인 표시
- `isoWeekNum(dateStr)` / `formatWeekLabel(weekEndDate)` — `N주차, YY.MM.DD`
- 자동 선택: 가장 가까운 미래 토요일

**곡 관계도** (`GraphPage.tsx`):
- `react-force-graph-2d` — ForceGraph2D
- 노드 크기: `Math.max(10, Math.min(28, 10 + weight * 2.5))`
- 노드 색상: min-max 정규화 → blue-300 → indigo-500 → violet-700
- 클릭 시 D+N (마지막 사용 후 경과 일수) 표시
- 링크 거리: 38 (D3 기본 30 × 1.25)
- `graphData = useMemo(() => ({ nodes, links }), [nodes, links])` — 레퍼런스 고정 (hover 시 시뮬 리셋 방지)

**기술 스택**: React 18, Vite, TypeScript, Tailwind v4, TanStack Query, Zustand, dnd-kit

### 3-7. Fallback 전략 (GUI)

1. 서버 우선 호출
2. 서버 불가 → 로컬 PowerPoint COM
3. COM 실패 → LibreOffice
4. 최종 실패 → 안내 메시지

### 3-8. 오류 보고

- 클라이언트 예외 훅(sys/threading/tkinter) 연동
- 오류 발생 시 컨텍스트/설정/상태/최근 로그 포함 → 서버 비동기 전송
- 가사 원문/레파토리 원문은 제외

### 3-9. 배포·운영

- PyInstaller 기반 Windows 단일 배포 패키지
- 서버: Task Scheduler `PPTGenServer` (`docs/Service.md`)
- Tauri 데스크톱: sidecar 포함 패키지 (`tools/build_sidecar.py`)

---

## 4. 데이터·산출물 위치

| 경로 | 내용 |
|---|---|
| `out/integrated_lyrics.pptx` | 생성된 통합 PPT |
| `out/songlist/` | 송리스트 카드 PNG |
| `out/jobs/` | Job 출력 파일 |
| `out/error_reports/YYYY-MM-DD.jsonl` | 오류 리포트 |
| `out/template_previews/` | 템플릿 썸네일 캐시 |
| `logs/service.log` | 서버 로그 |
| `weekly_repertoire.db` | SQLite (lyrics_catalog + weekly_repertoire) |

---

## 5. 운영 포인트

- 서버 포트: `8010` (변경: `src/constants.py`의 `SERVER_PORT`)
- 비밀번호: `.env` → `PORR_EDIT_PASSWORD` (gitignore, 커밋 금지)
- COM 작업은 실행 계정/권한 설정에 민감 → `docs/Service.md`
- GUI 실행: Python 3.10 (`venv310`) 필요

---

## 6. 참고 문서

- `docs/Service.md` — 서버 운영 (Task Scheduler)
- `docs/ARCHITECTURE_MIGRATION.md` — 마이그레이션 이력 + 향후 계획
- `CLAUDE.md` — 프로젝트 규칙 + 완료 작업 + API 목록
