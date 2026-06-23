# UI 개선 요청 프롬프트

## 목표

기능은 그대로 유지하되, 전반적인 UI를 더 모던하고 트렌디하게 만드는 것.
지금 UI가 다소 올드패션하고, 컴포넌트 스타일이 나이브하게 느껴진다.
단순히 색만 바꾸는 것이 아니라, 실제 사용자가 봤을 때 더 세련되고 완성도 있는 앱처럼 보이도록 개선해줘.

---

## 기술 스택 (반드시 숙지)

- **React + TypeScript + Vite**
- **Tailwind CSS v4** (CSS 변수 기반 디자인 토큰 시스템 — v3 방식과 다름)
  - 디자인 토큰은 `apps/web/src/index.css` 또는 `tailwind.config.ts`의 v4 방식으로 정의할 것
- **새 UI 컴포넌트 라이브러리 추가 금지** (shadcn/ui, Radix UI 등은 Tailwind v4 호환 이슈 가능)
  - 아이콘이 필요하다면 `lucide-react`는 허용 (이미 설치 여부 확인 후 없으면 추가)
  - 그 외 의존성 추가 시 반드시 이유와 Tailwind v4 호환성을 설명할 것
- 수정 후 `npm run build`에서 오류 없이 빌드되는 상태를 유지할 것

---

## 참고 레퍼런스

아래 앱들의 스타일을 참고해줘:

- **Linear** — 밀도 높은 생산성 도구, 군더더기 없는 레이아웃
- **Vercel Dashboard** — 깔끔한 카드, 명확한 타이포그래피 계층
- **Raycast** — 간결하고 빠른 느낌, 섬세한 hover/focus 처리

공통 키워드: 절제된 색상, 명확한 계층, 부드러운 shadow, 일관된 radius

---

## 현재 UI 구조 파악 (먼저 진행)

아래 경로를 읽고 현재 UI를 파악한 뒤 작업을 시작해줘.

```
apps/web/src/
  components/
    layout/     Header, BottomNav, RootLayout
    deck/       DeckPanel, JobProgressDialog, Checklist, TemplateSelect 등
    setlist/    SetlistPanel, SongCard
    editor/     LyricsEditor, SequenceInput
    history/    CalendarView
    lyrics/     LyricsSearchDialog
  pages/
    AppPage.tsx, HistoryPage.tsx, LyricsPage.tsx, GraphPage.tsx, TemplatesPage.tsx
  index.css     (전역 스타일, 디자인 토큰 위치)
```

---

## 진행 순서 (이 순서대로 작업할 것)

### 1단계: 디자인 토큰 정의
`index.css`에 CSS 변수로 공통 디자인 토큰 정의:
- 색상 팔레트 (primary, secondary, surface, border, text, error, success)
- radius (sm / md / lg / xl)
- shadow (sm / md / lg)
- 폰트 크기 scale

### 2단계: 공통 컴포넌트 스타일 확립
반복 사용되는 패턴을 먼저 확정:
- **버튼**: Primary / Secondary / Ghost / Danger 4종 — 크기·색상·hover/focus/disabled 상태 포함
- **입력창**: 통일된 border, radius, focus ring, placeholder 색상
- **카드/패널**: 배경, 테두리, shadow, padding 규칙
- **섹션 헤더**: 라벨 폰트·크기·색상 규칙

### 3단계: 화면별 적용 (아래 순서로)
1. `Header.tsx` / `RootLayout.tsx` — 네비게이션, 전체 레이아웃
2. `DeckPanel.tsx` / `JobProgressDialog.tsx` — 핵심 생성 화면
3. `SetlistPanel.tsx` / `SongCard.tsx` — 셋리스트 편집
4. `HistoryPage.tsx` / `CalendarView.tsx` — 캘린더
5. `LyricsPage.tsx` / `GraphPage.tsx` — 나머지 화면

---

## 원하는 스타일 방향

- 모던하고 깔끔한 생산성 도구 / SaaS 느낌
- 너무 화려하지 않되 트렌디함
- 둥근 카드, 부드러운 여백, 명확한 버튼 계층
- subtle animation, hover effect, focus state, disabled state 포함
- "PPT를 빠르게 만들어주는 도구"라는 목적이 첫 화면에서 직관적으로 느껴질 것

---

## 진단 항목 (각 항목을 확인하고 수정 여부 판단)

- [ ] 버튼 스타일이 기본값처럼 보이는 문제
- [ ] 입력 폼·카드·패널의 시각적 계층이 약한 문제
- [ ] 여백과 정렬 불균형
- [ ] 색상 사용이 단조롭거나 일관성 없는 문제
- [ ] 앱 전체가 하나의 디자인 시스템으로 묶이지 않는 문제
- [ ] 중요한 액션과 보조 액션이 구분되지 않는 문제
- [ ] 상태 표시, 오류 메시지, 빈 화면, 로딩 화면이 부족한 문제
- [ ] 현대적인 앱다운 느낌이 부족한 문제

---

## 지켜야 할 것

- 기존 기능을 삭제하거나 축소하지 말 것
- API, DB, 파일 생성 로직은 건드리지 말 것 (UI 전용 수정)
- 현재 동작하던 플로우를 깨지 말 것
- 한 번에 전체를 바꾸지 말고 **1단계 → 2단계 → 3단계 순서로** 진행할 것
- 각 단계 후 빌드 오류 없는지 확인할 것 (`npm run build`)
- 한국어 UI 문구는 자연스럽고 짧게 다듬어도 되나, 임의로 기능명을 바꾸지 말 것

---

## 결과물 정리 (수정 완료 후 작성)

- 수정한 파일 목록
- 화면별 개선 내용 요약
- 새로 정의한 디자인 토큰/공통 스타일
- 새 패키지 추가 여부 (있다면 이유 + 설치 명령어)
- 빌드/실행 확인 방법
- 아직 남은 개선 포인트
