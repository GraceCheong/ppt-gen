# PO,RR 아키텍처 마이그레이션 현황

> **상태**: Phase 1–6 완료. 현재는 기능 추가 단계.

---

## 전체 목표 아키텍처 (달성됨)

```
Python 생성 엔진
    ↓
FastAPI 서버 (server/app/)
    ↓
Job 큐 / 변환 워커
    ↓
DB + 파일 저장소

UI 계층:
  1. React Web App (apps/web/)
  2. Tauri Desktop (apps/desktop/)
  3. CustomTkinter Legacy (src/main_ttk.py)
```

---

## Phase 완료 현황

### ✅ Phase 1 — 코어 추출

`src/porr_core/` 생성:
- `repertoire.py` — 레파토리 텍스트 파싱, 정규화
- `sequence.py` — 시퀀스 파트 정규화, 마지막 반복 파트 감지
- `slide_estimator.py` — 예상 슬라이드 수 계산
- `schemas.py` — SongEntry, PptSettings, PptGeneratePayload

CustomTkinter 앱은 새 core 모듈을 호출하는 방식으로 변경. 기존 동작 보존.

---

### ✅ Phase 2 — 서버 API 리팩터

`server/convert_server.py` → `server/app/` 구조로 분리:

```
server/app/
  main.py
  config.py        환경변수 로드 (PORR_EDIT_PASSWORD 등)
  state.py         전역 상태 (executor 등)
  api/
    health.py
    templates.py
    lyrics.py
    history.py
    exports.py
    jobs.py
    errors.py
  services/
    lyrics_service.py
    history_service.py
    template_service.py
    ppt_generation_service.py
    songlist_service.py
    db.py
```

기존 엔드포인트 유지 (레거시 GUI 호환). `/api` prefix 신규 엔드포인트 추가.

---

### ✅ Phase 3 — Job 기반 export API

메모리 기반 Job Store로 비동기 PPT 생성 구현:

```
server/app/
  jobs/
    job_store.py   메모리 dict 기반, job_id → ExportJob
    job_models.py  JobStatus(queued/running/succeeded/failed), ExportJob
  workers/
    ppt_worker.py
    songlist_worker.py
  storage/
    local_storage.py   out/ 경로 관리
```

추가 API:
```
POST /api/exports/pptx
POST /api/exports/songlist-card
GET  /api/jobs/{job_id}
GET  /api/jobs/{job_id}/download
```

---

### ✅ Phase 4 — React Web MVP

`apps/web/` — React + Vite + TypeScript + Tailwind v4:

- 3-panel 작업 화면 (`/app`)
- dnd-kit setlist 드래그 정렬
- TanStack Query로 서버 상태 관리
- Zustand store (`projectStore.ts`)
- Job polling → 완료 시 다운로드

---

### ✅ Phase 5 — Tauri Desktop

`apps/desktop/` — Tauri v2:

- React 웹 UI 재사용 (web dist)
- `get_server_url` Tauri command로 서버 URL 주입
- Rust sidecar 모듈 구조

---

### ✅ Phase 6 — Local FastAPI Sidecar

- `server/porr_server_main.py` — 단독 실행 진입점
- `tools/build_sidecar.py` — PyInstaller 패키징
- Tauri sidecar 연동

---

## Phase 6 이후 — 기능 추가

### 웹 UI 기능

| 기능 | 경로 | 주요 변경 |
|---|---|---|
| 모바일 셋리스트 정렬 | `SetlistPanel`, `SongCard` | ▲▼ 버튼 (dnd 대안) |
| 송리스트 카드 생성 | `DeckPanel` | `/api/exports/songlist-card` Job 연동 |
| 이력 페이지 달력 뷰 | `CalendarView.tsx` | 월별 달력 + 토요일 상세 패널 |
| 이력 수정 | `HistoryPage.tsx`, `history.py` | PUT endpoints, 비밀번호 인증 |
| 담당자 관리 | `CalendarView.tsx`, `history.py` | 인도자·반주자·기도자 upsert |
| 곡 관계도 | `GraphPage.tsx` | ForceGraph2D, 동적 색상, D+N |
| 노래 DB 자동 저장 | `lyrics.py`, `history.py` | 이력 저장 시 자동 upsert |

### 서버 API 추가

```
POST /api/lyrics/bulk                        ← 가사 없어도 title+sequence 일괄 등록
POST /api/history/weekly                     ← 이력 생성 + lyrics_catalog 자동 upsert
PUT  /api/history/weekly/{date}/entries      ← 곡 목록 수정 (비밀번호)
PUT  /api/history/weekly/{date}/roles        ← 담당자 수정 (비밀번호)
```

### DB 변경

`weekly_repertoire` 테이블 컬럼 추가:
- `worship_leader` — 인도자
- `accompanist` — 반주자
- `prayer_person` — 기도자

`lyrics_catalog` upsert 정책 변경:
- 빈 가사로 upsert 시 기존 가사 보존 (`CASE WHEN excluded.lyrics != '' THEN ...`)

---

## 현재 구현 규칙 (신규 작업 시 참고)

### 날짜
- 프론트: `toISOString()` 사용 금지 → `getFullYear()/getMonth()/getDate()` 사용 (UTC+9 오프셋)
- 서버: `datetime.date.fromisoformat()` 표준 처리

### 시퀀스 입력
- `onChange`: raw 값 저장
- `onBlur`: `normalizeSeq()` 호출
- 이유: 입력 중 `-` / 공백이 즉시 제거되는 버그 방지

### 비밀번호
- `.env` 파일에만 저장 (`PORR_EDIT_PASSWORD=scc3679`)
- `server/app/config.py`에서 `os.environ.get()` 로드
- 절대 git에 커밋하지 않음

### 그래프 컴포넌트 (`GraphPage.tsx`)
- `graphData = useMemo(() => ({ nodes, links }), [nodes, links])` — 레퍼런스 고정 필수
- `d3Force('link').distance(38)` — `useEffect([nodes, links])`에서 적용
- `warmupTicks={80}` — 첫 렌더 전 pre-시뮬

### 주차 계산
- `isoWeekNum(dateStr)` — `CalendarView.tsx`에서 export
- `formatWeekLabel(weekEndDate)` — `N주차, YY.MM.DD` 형식

---

## 현재 파일 구조

```
c:\dev\ppt-gen\
├── apps/
│   ├── web/          React + Vite 웹앱
│   └── desktop/      Tauri v2 데스크톱
├── server/
│   ├── app/          FastAPI 앱 (main, api/, services/, jobs/, workers/, storage/)
│   ├── convert_server.py         레거시 (호환용 유지)
│   └── porr_server_main.py       sidecar 진입점
├── src/
│   ├── porr_core/    코어 로직
│   ├── main_ttk.py   ttkbootstrap GUI (현재 주 GUI)
│   ├── main.py       CustomTkinter GUI
│   └── constants.py  SERVER_PORT 등
├── tools/
│   └── build_sidecar.py
├── tests/
├── .env              PORR_EDIT_PASSWORD (gitignore)
└── docs/
    ├── ARCHITECTURE_MIGRATION.md  (이 파일)
    ├── ImplementationMemory.md
    ├── Service.md
    └── Release.md
```

---

## 향후 작업 아이디어

| 아이디어 | 설명 |
|---|---|
| 레파토리 붙여넣기 (웹) | `V1 한나의노래\nV2 사랑해요` 형식 → setlist 자동 구성 |
| 가사 자동 다운로드 (웹) | 곡 선택 시 Bugs 크롤러 연동 버튼 |
| 템플릿 미리보기 | 썸네일 API + 웹 표시 |
| 릴리스 파이프라인 | GitHub Actions: Tauri 빌드 + 서명 + 배포 |
| 그래프 클러스터 필터 | 특정 곡군만 표시 |

---

## 보존해야 할 기존 동작

아래는 변경 시 반드시 검증해야 한다:

- **마지막 연속 반복 파트 강조**: `…-C-C` → 마지막 C 슬라이드 1장만 생성, 볼드 + `#8B1A1A`
- **중간 반복은 강조 없음**: `V1-V1` → 일반 처리
- **PPT 레이아웃 placeholder 폰트 상속**: `add_slide()` 직후 `lstStyle/pPr/rPr` 복사
- **가사 카탈로그 source 우선순위**: `manual > history > bugs`
- **주간 이력 기준**: 토요일(`week_end_date`) 기준 저장
- **오류 리포트**: 가사 원문/레파토리 원문 제외
