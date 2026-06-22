# CLAUDE.md

## Project: PO,RR

예배 PPT 및 송리스트 카드를 생성하는 도구.

---

## 현재 아키텍처

```
Python 생성 엔진 (ppt_builder, ppt_service, songlist_builder)
        ↓
FastAPI 서버 (server/app/)  —  port 8010
        ↓
React Web App (apps/web/)   —  Vite + TypeScript + Tailwind v4
        ↓
Tauri Desktop (apps/desktop/) — v2, local sidecar 포함
```

| 레이어 | 경로 | 비고 |
|---|---|---|
| GUI (Legacy) | `src/main_ttk.py`, `src/main.py` | ttkbootstrap / CustomTkinter |
| 코어 로직 | `src/porr_core/` | repertoire, sequence, slide_estimator, schemas |
| 서버 | `server/app/` | FastAPI, routers/services/jobs/workers/storage |
| 웹앱 | `apps/web/src/` | React + Vite |
| 데스크톱 | `apps/desktop/` | Tauri v2 |
| DB | `weekly_repertoire.db` (SQLite) | lyrics_catalog + weekly_repertoire |

---

## 환경 설정

- **비밀번호**: `.env` → `PORR_EDIT_PASSWORD=scc3679` (gitignore 됨, 커밋 절대 금지)
- **서버 포트**: `8010` (`src/constants.py`의 `SERVER_PORT`)
- **서버 실행**: Task Scheduler `PPTGenServer` (`docs/Service.md` 참고)

---

## 중요 규칙

한 번에 전체를 바꾸지 않는다. 항상 작은 단계로 작업한다.

각 작업 전:
1. `docs/ARCHITECTURE_MIGRATION.md` 읽기
2. 요청된 작업의 범위 파악
3. 해당 범위만 구현
4. 기존 동작 보존 — CustomTkinter 앱이 계속 작동해야 함
5. PPT 생성 결과를 바꾸지 않음 (명시적 요청 없이)
6. 대규모 재작성 금지 — 추출·호환 래퍼를 선호

---

## 완료된 작업

### Phase 1–6 (아키텍처 마이그레이션)

| Phase | 내용 | 주요 경로 |
|---|---|---|
| 1 | 코어 추출 | `src/porr_core/` |
| 2 | 서버 API 리팩터 | `server/app/` |
| 3 | Job 기반 export API | `server/app/jobs/`, `workers/`, `storage/` |
| 4 | React Web MVP | `apps/web/` |
| 5 | Tauri Desktop | `apps/desktop/` |
| 6 | Local FastAPI Sidecar | `server/porr_server_main.py`, `tools/build_sidecar.py` |

### 웹 기능 (Phase 6 이후)

**셋리스트 패널**
- dnd-kit 드래그 정렬 + 모바일 ▲▼ 버튼 (`SetlistPanel`, `SongCard`)
- 가사 편집기, 진행 순서 입력

**DeckPanel**
- 슬라이드당 줄 수 / 글자 수 설정 (`type="text" inputMode="numeric"`, blur 시 검증)
- PPT 생성 / 송리스트 카드 생성 버튼

**이력 페이지 (`/history`)**
- 달력 뷰: 월별 달력 + 선택된 토요일 상세 패널 (인도자·반주자·기도자·셋리스트)
- 목록 뷰: `N주차, YY.MM.DD` 형식, 인도자 굵게
- 주간 이력 등록(POST) / 곡 수정(PUT) / 담당자 수정(PUT) — 모두 비밀번호 필요
- 이력 저장·수정 시 자동으로 `lyrics_catalog`에 upsert

**곡 관계도 (`/graph`)**
- `react-force-graph-2d` — 노드 크기: 사용 횟수 비례
- 동적 노드 색상: min-max 정규화 → blue-300 → indigo-500 → violet-700
- 클릭 시 D+N (마지막 사용 후 경과 일수) 표시
- 링크 거리: D3 기본값 × 1.25 (`useEffect`로 데이터 변경 시 적용)
- `graphData`를 `useMemo`로 고정 — hover 시 시뮬 리셋 방지

**가사 DB (`/lyrics`)**
- 검색 / 추가 / Bugs Music 자동 다운로드
- `POST /api/lyrics/bulk`: 가사 없이도 title+sequence 일괄 등록

---

## 현재 활성 서버 API

### 웹앱용 (`/api` prefix)

```
GET    /api/health
GET    /api/templates
POST   /api/templates
GET    /api/lyrics/search?q=&limit=
GET    /api/lyrics/by-title?title=
POST   /api/lyrics
POST   /api/lyrics/bulk
POST   /api/lyrics/download
GET    /api/history/weekly?year_from=
POST   /api/history/weekly
PUT    /api/history/weekly/{date}/entries    # 비밀번호 필요
PUT    /api/history/weekly/{date}/roles      # 비밀번호 필요
GET    /api/history/db
POST   /api/exports/pptx
POST   /api/exports/songlist-card
GET    /api/jobs/{job_id}
GET    /api/jobs/{job_id}/download
```

### Legacy GUI용

```
GET    /health
POST   /convert
POST   /generate-ppt
POST   /songlist-card
GET    /history/weekly
GET    /lyrics/search
POST   /lyrics
```

---

## 웹앱 주요 구조 (`apps/web/src/`)

```
api/
  client.ts        apiFetch 공통 함수
  history.ts       fetchHistory, saveHistoryEntry, updateHistoryEntry, updateHistoryRoles
  lyrics.ts        searchLyrics, fetchRecentLyrics, bulkSaveToLyricsDb, downloadLyrics
  exports.ts       createPptxJob, createSonglistJob
  jobs.ts          pollJob
  templates.ts     fetchTemplates

components/
  deck/            DeckPanel, TemplateSelect, TemplatePreview, Checklist, JobProgressDialog
  editor/          LyricsEditor, SequenceInput
  history/         CalendarView (달력 + 토요일 상세패널 + RolesEditModal)
  layout/          RootLayout, Header, BottomNav
  lyrics/          LyricsSearchDialog
  setlist/         SetlistPanel, SongCard (▲▼ + drag handle)

pages/
  AppPage.tsx      3-panel 작업 화면
  HistoryPage.tsx  이력 (달력/목록 뷰, HistoryEntryModal, WeekCard)
  LyricsPage.tsx   가사 DB
  GraphPage.tsx    곡 관계도
  TemplatesPage.tsx

store/
  projectStore.ts  Zustand (songs, selectedSongId, templateId, settings)

types/
  lyrics.ts, jobs.ts, project.ts
```

---

## 핵심 기술 결정 사항

| 항목 | 결정 | 이유 |
|---|---|---|
| 비밀번호 | `.env` + `config.py` 로드, 커밋 금지 | 보안 |
| 날짜 처리 | `getFullYear()/getMonth()/getDate()` (toISOString 금지) | UTC+9 오프셋 버그 |
| 시퀀스 정규화 | `onChange`에서 raw 유지, `onBlur`에서 정규화 | 입력 중 `-` / 공백 입력 가능하도록 |
| ISO 주차 | `isoWeekNum()` — `CalendarView.tsx`에서 export, `HistoryPage.tsx`에서 import | 공통 사용 |
| 그래프 데이터 | `useMemo(() => ({ nodes, links }), [nodes, links])` | hover state 변경 시 시뮬 리셋 방지 |
| 노래 DB upsert | 빈 가사로 upsert 시 기존 가사 보존 | `lyrics_service.py` CASE 조건 |
| Windows 로그 | asyncio WinError 10054 필터링 | `server/app/main.py` logging.Filter |

---

## 향후 작업 아이디어 (우선순위 없음)

- **레파토리 붙여넣기** — `V1 한나의노래\nV2 사랑해요` 형식 → setlist 자동 구성 (웹)
- **가사 자동 다운로드** (웹) — 곡 선택 시 Bugs 크롤러 연동 버튼
- **템플릿 미리보기** — 썸네일 이미지 생성 API + 웹 UI
- **릴리스 파이프라인** — GitHub Actions: Tauri 앱 빌드 + 서명 + 배포
- **그래프 클러스터 필터** — 특정 곡군만 표시
