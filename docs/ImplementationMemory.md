# PO,RR 구현 메모

> 코드를 읽어도 알 수 없는 **결정 이유**와 **함정**만 기록한다.
> 마지막 업데이트: 2026-06-23

---

## 결정 이유

### 인증: 비밀번호 → 세션 쿠키

기존에는 `.env`의 `PORR_EDIT_PASSWORD`를 클라이언트가 직접 보내는 방식이었다. 교회별 이력 분리가 필요해지면서 "누가 저장했는가"를 서버가 알아야 해서 세션 기반으로 전환했다. 클라이언트가 보내는 `church` 값은 신뢰하지 않는다 — 서버가 세션에서 꺼낸 `auth.church`만 사용한다.

### 인증 모드가 4개인 이유 (`loading | unauthenticated | guest | user`)

3개(`loading | guest | user`)로 설계했다가, `checkSession()` 실패 시 `'guest'`로 설정하면 로그인 화면을 건너뛰는 버그가 생겼다. 비로그인 상태와 Guest 선택 상태를 구분하기 위해 `'unauthenticated'`를 추가했다.

### 그래프 데이터를 서버에서 빌드하는 이유

이력 API는 `require_user()`라서 Guest가 호출할 수 없다. 그래프는 Guest도 봐야 한다. 그래서 그래프 전용 엔드포인트(`GET /api/graph`)를 따로 만들어 노드/엣지는 전 교회 데이터로 계산하고, D±N은 로그인 사용자의 church 기준으로만 응답한다.

### `weekly_repertoire` PK를 테이블 재생성으로 변경한 이유

SQLite는 `ALTER TABLE ... DROP PRIMARY KEY`를 지원하지 않는다. `weekly_repertoire_new`를 만들어 복사한 뒤 rename하는 방식으로 처리했다. 기존 데이터는 `church='서울중앙'`으로 보정.

### `song_usage_events` 이력 저장 시 delete+insert

이력 수정 시 곡 목록이 바뀌면 usage events를 통째로 지우고 다시 넣는다. upsert나 diff 방식은 삭제된 곡을 처리하기 복잡하기 때문.

---

## 함정

### `argon2-cffi` 예외 클래스 이름

설치 버전(21.3.0)은 `InvalidHash`다. `InvalidHashError`로 import하면 런타임 에러.

```python
# 올바름
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHash
```

### 날짜 처리 — `toISOString()` 금지

`new Date().toISOString()`은 UTC 기준이라 KST(UTC+9)에서 자정 전후로 날짜가 달라진다. 날짜 문자열은 항상 `getFullYear() / getMonth() / getDate()`로 직접 조합한다.

### `graphData` useMemo 고정

`react-force-graph-2d`는 `graphData` 참조가 바뀌면 시뮬레이션을 리셋한다. hover 상태가 바뀌어도 리셋되지 않도록 `useMemo(() => ({ nodes, links }), [nodes, links])`로 객체를 고정한다.

### `lyrics_catalog` 빈 가사 upsert

빈 가사로 upsert하면 기존 가사가 날아간다. `lyrics_service.py`의 upsert SQL에 `CASE WHEN excluded.lyrics != '' THEN excluded.lyrics ELSE lyrics_catalog.lyrics END` 조건이 있어야 기존 가사를 보존한다.

### CORS — 개발 시에만 필요

Vite dev server(`localhost:5173`) ↔ FastAPI(`localhost:8010`) 간 크로스오리진이라 `credentials: 'include'`와 서버 측 CORSMiddleware가 필요하다. 프로덕션(Tauri sidecar 또는 동일 origin 배포)에서는 불필요하다.

### COM 작업 실행 계정

Task Scheduler로 서버를 띄울 때 실행 계정이 COM(PowerPoint) 오브젝트를 생성할 수 있어야 한다. 계정/권한 설정이 맞지 않으면 `songlist_builder`의 COM fallback이 조용히 실패한다. → `docs/Service.md` 참고.

---

## 향후 작업 아이디어

### UX

- **SetlistPanel 붙여넣기** — `한나의노래 V1-V2-C\n사랑해요 I-V-C` 형식 한 번에 붙여넣기. `HistoryPage.tsx`의 `parseRepertoireLine` 로직 재활용 가능.

- **세션 만료 자동 처리** — 현재 401 응답이 그냥 에러 alert으로 나온다. `apiFetch`에서 401 감지 시 `authStore.reset()`을 호출해 로그인 화면으로 보내야 한다.

- **그래프 곡 검색** — 곡이 많아지면 관계도에서 특정 노드를 찾기 어렵다. 검색창에 입력하면 해당 노드를 하이라이트하는 기능.

### 계정

- **비밀번호 변경** — 현재 `PUT /auth/password` 같은 엔드포인트가 없다. 망각 시 DB 직접 수정 외에 방법이 없음.

- **닉네임·교회 수정** — 회원가입 후 변경 불가. `PUT /auth/profile` 필요.

- **이력 날짜 오입력 수정 불가** — `week_end_date`가 PK라 수정이 안 된다. 삭제 후 재입력이 유일한 방법.

### 데이터

- **그래프 클러스터 필터** — minEdge 슬라이더는 있지만 곡군(예: 찬양/경배/봉헌) 단위 분류 표시는 없다. `lyrics_catalog`에 태그 컬럼을 추가하면 연결 가능.

- **이력 내보내기** — 월별/년별 이력을 CSV나 엑셀로 내보내는 기능이 없다. 인도자가 보고서 작성 시 유용.

### Tauri

- **세션 보안** — 현재 Tauri webview 쿠키로 세션을 유지한다. 보안이 중요해지면 Tauri의 OS keychain(tauri-plugin-stronghold) 또는 secure storage로 이전 검토.

---

## 보안·코드 품질 보강

### 완료

- `/api/history/db` 인증 추가 (`require_user`) — 레거시 `/history/db`는 GUI 호환을 위해 유지
- 500 에러 내부 예외 문자열 제거 — `exports.py` 전반, 서버 로그에만 기록
- 닉네임·교회명 50자 길이 제한 (`auth.py`)
- 쿠키 `secure` → `PORR_HTTPS=true` 환경변수로 제어 (`config.py`)
- CORS 오리진 → `PORR_CORS_ORIGINS` 환경변수로 제어 (`config.py`)
- 만료 세션 startup 시 자동 정리 (`auth_service.cleanup_expired_sessions`)
- SQLite WAL 모드 설정 (`PRAGMA journal_mode=WAL` in `db.py`)
- 파일 업로드 최대 크기 제한 — 기본 50MB, `PORR_MAX_UPLOAD_MB`로 변경 (`config.py`)
- `/api/graph` 이력 TTL 캐시 5분 + 이력 변경 시 즉시 무효화 (`graph.invalidate_graph_cache`)

- Rate Limiting — `slowapi`: `/auth/check-id` 20/분, `/auth/signup` 5/분, `/auth/login` 10/분
- 테스트 추가 — `tests/test_auth_service.py` (14개), `tests/test_db_migration.py` (13개), `tests/test_graph_api.py` (13개) / 전체 137개 통과
