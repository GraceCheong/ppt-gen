import { X, FileText, Type, Layers, AlertCircle } from 'lucide-react'

interface Props {
  onConfirm: () => void
  onClose: () => void
}

const GUIDE_CARDS = [
  {
    icon: <FileText className="w-4 h-4" />,
    badge: '필수',
    badgeColor: 'bg-danger-100 text-danger-600 border-danger-200',
    title: '가사 레이아웃',
    body: '슬라이드 마스터에 정확히 "가사"라는 이름의 레이아웃이 있어야 합니다.',
    detail: '텍스트 박스 2개 — 큰 것: 가사 내용, 작은 것: 곡 제목',
  },
  {
    icon: <Type className="w-4 h-4" />,
    badge: '필수',
    badgeColor: 'bg-danger-100 text-danger-600 border-danger-200',
    title: '제목 레이아웃',
    body: '"제목"이라는 이름의 레이아웃이 각 곡의 표지 슬라이드에 사용됩니다.',
    detail: '텍스트 박스 1개 이상 포함',
  },
  {
    icon: <Layers className="w-4 h-4" />,
    badge: '권장',
    badgeColor: 'bg-primary-100 text-primary-600 border-primary-200',
    title: '기타 레이아웃',
    body: '홈, 예배를 시작하며, 기도 레이아웃이 있으면 해당 슬라이드가 자동 생성됩니다.',
    detail: '없어도 PPT 생성 가능 — 해당 슬라이드는 건너뜁니다',
  },
  {
    icon: <AlertCircle className="w-4 h-4" />,
    badge: '유의',
    badgeColor: 'bg-warning-100 text-warning-600 border-warning-200',
    title: '레이아웃 이름 주의',
    body: 'PowerPoint에서 슬라이드 마스터 > 레이아웃 이름을 정확히 확인하세요.',
    detail: '대소문자·공백이 다르면 레이아웃을 찾지 못할 수 있습니다',
  },
]

export function TemplateUploadGuideModal({ onConfirm, onClose }: Props) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/40 backdrop-blur-xs px-4"
      onClick={onClose}
    >
      <div
        className="bg-white border border-neutral-200/80 rounded-2xl shadow-2xl w-full max-w-md flex flex-col max-h-[90vh] overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-neutral-100 shrink-0">
          <div>
            <h2 className="text-sm font-bold text-neutral-900">템플릿 업로드 안내</h2>
            <p className="text-[11px] text-neutral-400 mt-0.5">업로드 전에 아래 조건을 확인해 주세요</p>
          </div>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-600 hover:bg-neutral-50 rounded-lg p-1.5 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 카드 목록 */}
        <div className="overflow-y-auto flex-1 p-4 space-y-3">
          {GUIDE_CARDS.map(card => (
            <div
              key={card.title}
              className="border border-neutral-100 rounded-xl p-4 bg-neutral-50/40"
            >
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-white border border-neutral-200 flex items-center justify-center shrink-0 text-neutral-500 shadow-sm">
                  {card.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-bold text-neutral-800">{card.title}</span>
                    <span className={`text-[10px] font-bold border rounded-full px-2 py-0.5 shrink-0 ${card.badgeColor}`}>
                      {card.badge}
                    </span>
                  </div>
                  <p className="text-[11px] text-neutral-600 leading-relaxed">{card.body}</p>
                  <p className="text-[10px] text-neutral-400 mt-1">{card.detail}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* 푸터 */}
        <div className="px-6 pb-5 pt-4 border-t border-neutral-100 flex gap-2 justify-end shrink-0">
          <button
            onClick={onClose}
            className="text-xs font-semibold border border-neutral-200 text-neutral-700 rounded-xl px-4 py-2.5 hover:bg-neutral-50 transition-colors cursor-pointer"
          >
            취소
          </button>
          <button
            onClick={onConfirm}
            className="text-xs font-semibold bg-primary-600 text-white rounded-xl px-4 py-2.5 hover:bg-primary-700 transition-colors cursor-pointer"
          >
            알겠습니다, 파일 선택
          </button>
        </div>
      </div>
    </div>
  )
}
