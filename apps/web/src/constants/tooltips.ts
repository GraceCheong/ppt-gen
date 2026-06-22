/**
 * 앱 전체 툴팁(title) 문자열 관리 파일
 * 컴포넌트별로 묶어서 관리하며, 동적 값이 필요한 경우 함수로 정의합니다.
 */

export const TIPS = {

  // ── 템플릿 ─────────────────────────────────────────────────────────────────

  template: {
    select:          '사용할 PPT 템플릿을 선택합니다. 선택 즉시 기본값으로 저장됩니다.',
    defaultOpen:     '기본 템플릿 설정',
    defaultClose:    '닫기',
    defaultCancel:   '변경 사항을 저장하지 않고 닫습니다',
    defaultSave:     (isCurrent: boolean) =>
      isCurrent
        ? '이미 기본 템플릿으로 설정되어 있습니다'
        : '선택한 템플릿을 앱 시작 기본값으로 저장합니다',
    upload:          '.pptx 파일을 업로드해 서버에 새 템플릿으로 등록합니다',
  },

  // ── 셋리스트 ───────────────────────────────────────────────────────────────

  setlist: {
    addFromDB:       '가사 DB에서 곡을 검색해 셋리스트에 추가합니다.',
    addDirect:       '곡 제목을 직접 입력해 추가합니다.',
    addConfirm:      '입력한 제목으로 셋리스트에 추가합니다.',
    songMoveUp:      '위로 이동',
    songMoveDown:    '아래로 이동',
    songDragHandle:  '드래그해서 순서 변경',
    songRemove:      '삭제',
    searchClose:     '닫기',
    searchItem:      (sequence?: string | null) =>
      `셋리스트에 추가${sequence ? ` (진행 순서: ${sequence})` : ''}`,
  },

  // ── 가사 편집기 ────────────────────────────────────────────────────────────

  editor: {
    title:           '슬라이드 제목 슬라이드에 표시될 이름',
    lyricsDownload:  'Bugs Music에서 가사를 자동으로 검색해 채웁니다',
    lyricsTextarea:  '절 구분자(V1, V2, C 등)를 빈 줄로 분리해 입력하세요',
    partNoLyrics:    (part: string) => `${part}: 가사 불필요 (클릭해서 필요로 변경)`,
    partHasLyrics:   (part: string) => `${part}: 가사 있음 (클릭해서 불필요로 표시)`,
    partEmpty:       (part: string) => `${part}: 파트 이름은 있지만 가사 내용이 비어 있음 (클릭해서 불필요로 표시)`,
    partMissing:     (part: string) => `${part}: 가사에 파트가 없음 (클릭해서 불필요로 표시)`,
  },

  // ── 덱 패널 ───────────────────────────────────────────────────────────────

  deck: {
    pptGenerate:     (canGenerate: boolean) =>
      canGenerate
        ? '선택한 템플릿으로 PPT 파일을 생성합니다'
        : '모든 곡에 제목과 진행 순서가 필요합니다',
    songlistGenerate:(canGenerate: boolean) =>
      canGenerate
        ? '셋리스트 곡 목록을 PNG 이미지로 내보냅니다'
        : '모든 곡에 제목과 진행 순서가 필요합니다',
    jobDownload:     '생성된 파일을 내 컴퓨터에 저장합니다',
    jobClose:        '이 대화상자를 닫습니다',
  },

  // ── 이력 페이지 ───────────────────────────────────────────────────────────

  history: {
    add:             '날짜와 곡 목록을 입력해 이력을 수동으로 추가합니다',
    sortDesc:        '최신순 (클릭 시 오래된 순)',
    sortAsc:         '오래된 순 (클릭 시 최신순)',
    viewCalendar:    '달력 보기',
    viewList:        '목록 보기',
    weekEdit:        '셋리스트 곡 목록을 수정합니다 (비밀번호 필요)',
    weekLoad:        '이 주의 셋리스트를 현재 작업에 불러옵니다',
    modalClose:      '닫기',
    modalCancel:     '변경 사항을 저장하지 않고 닫습니다',
    modalSave:       (isEdit: boolean) =>
      isEdit ? '셋리스트를 수정합니다 (비밀번호 필요)' : '이력을 새로 추가합니다',
    pasteToggle:     (isPaste: boolean) =>
      isPaste ? '한 줄씩 입력 모드로 전환' : '여러 곡을 한번에 붙여넣기',
    pasteApply:      '입력한 텍스트를 파싱해 곡 목록으로 변환합니다',
    rowRemove:       '이 줄을 삭제합니다',
    rowAdd:          '빈 입력란을 한 줄 추가합니다',
  },

  // ── 달력 뷰 ───────────────────────────────────────────────────────────────

  calendar: {
    prevMonth:       '이전 달',
    nextMonth:       '다음 달',
    rolesEdit:       '인도자·반주자·기도자 담당자를 수정합니다 (비밀번호 필요)',
    rolesAdd:        '인도자·반주자·기도자를 등록합니다',
    rolesRegister:   '이 날의 인도자·반주자·기도자를 등록합니다',
    entriesEdit:     '셋리스트 곡 목록을 수정합니다 (비밀번호 필요)',
    load:            '이 주의 셋리스트를 현재 작업에 불러옵니다',
    rolesClose:      '닫기',
    rolesCancel:     '변경 사항을 저장하지 않고 닫습니다',
    rolesSave:       '담당자 정보를 저장합니다 (비밀번호 필요)',
  },

  // ── 곡 관계도 ─────────────────────────────────────────────────────────────

  graph: {
    minEdge:         '이 횟수 이상 함께 사용된 곡 쌍만 연결선으로 표시합니다',
    nodeClose:       '패널 닫기',
  },

  // ── 서버 상태 ─────────────────────────────────────────────────────────────

  server: {
    reconnect:       '서버에 다시 연결을 시도합니다',
  },

}
