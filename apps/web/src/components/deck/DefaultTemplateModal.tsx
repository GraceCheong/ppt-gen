import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchTemplates, fetchDefaultTemplate, saveDefaultTemplate } from '../../api/templates'
import { useProjectStore } from '../../store/projectStore'
import { TIPS } from '../../constants/tooltips'
import { X, Check } from 'lucide-react'

interface Props {
  onClose: () => void
}

export function DefaultTemplateModal({ onClose }: Props) {
  const queryClient = useQueryClient()
  const { setTemplateId } = useProjectStore()
  const { data: templateItems = [] } = useQuery({ queryKey: ['templates'], queryFn: fetchTemplates })
  const templates = templateItems.map(t => t.id + '.pptx')
  const { data: currentDefault } = useQuery({
    queryKey: ['template-default'],
    queryFn: fetchDefaultTemplate,
  })

  const [selected, setSelected] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (currentDefault !== undefined) {
      setSelected(currentDefault.template_id ?? null)
    }
  }, [currentDefault])

  async function handleSave() {
    setSaving(true)
    try {
      await saveDefaultTemplate(selected)
      if (selected) setTemplateId(selected)
      queryClient.invalidateQueries({ queryKey: ['template-default'] })
      setSaved(true)
      setTimeout(onClose, 800)
    } catch {
      setSaving(false)
    }
  }

  const currentDefaultId = currentDefault?.template_id ?? null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/40 backdrop-blur-xs px-4"
      onClick={onClose}
    >
      <div
        className="bg-white border border-neutral-200/80 rounded-2xl shadow-2xl w-full max-w-sm flex flex-col max-h-[80vh] overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-neutral-100">
          <div>
            <h2 className="text-sm font-bold text-neutral-900">기본 템플릿 설정</h2>
            <p className="text-[11px] text-neutral-400 mt-0.5">앱 시작 시 자동으로 선택될 PPT 템플릿</p>
          </div>
          <button
            onClick={onClose}
            title={TIPS.template.defaultClose}
            className="text-neutral-400 hover:text-neutral-600 hover:bg-neutral-50 rounded-lg p-1.5 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 목록 */}
        <div className="overflow-y-auto flex-1 py-3 px-4 space-y-1">
          {templates.length === 0 && (
            <p className="text-xs text-neutral-400 text-center py-8">등록된 템플릿이 없습니다</p>
          )}
          {templates.map(name => {
            const id = name.replace(/\.pptx$/i, '')
            const isSelected = id === selected
            const isCurrentDefault = id === currentDefaultId

            return (
              <label
                key={name}
                className={`flex items-center gap-3 px-3.5 py-3 cursor-pointer rounded-xl border transition-all duration-150 select-none
                  ${isSelected 
                    ? 'bg-primary-50/50 border-primary-200 ring-2 ring-primary-500/5' 
                    : 'bg-white border-neutral-100 hover:bg-neutral-50/60'}`}
              >
                <input
                  type="radio"
                  name="default-template"
                  value={id}
                  checked={isSelected}
                  onChange={() => setSelected(id)}
                  className="accent-primary-500 shrink-0 cursor-pointer"
                />
                <span className="text-xs font-semibold text-neutral-700 flex-1 truncate">{id}</span>
                {isCurrentDefault && (
                  <span className="text-[10px] font-bold text-primary-500 bg-primary-100/50 border border-primary-200/50 rounded-full px-2 py-0.5 shrink-0">
                    현재 기본
                  </span>
                )}
              </label>
            )
          })}
        </div>

        {/* 푸터 */}
        <div className="px-6 pb-5 pt-4 border-t border-neutral-100 flex gap-2 justify-end items-center">
          {saved && (
            <span className="text-[11px] font-semibold text-success-600 self-center mr-auto flex items-center gap-1">
              <Check className="w-3.5 h-3.5" />
              <span>설정 저장됨</span>
            </span>
          )}
          <button
            onClick={onClose}
            title={TIPS.template.defaultCancel}
            className="text-xs font-semibold border border-neutral-200 text-neutral-700 rounded-xl px-4 py-2.5 hover:bg-neutral-50 active:bg-neutral-100 transition-colors cursor-pointer"
          >
            취소
          </button>
          <button
            onClick={handleSave}
            disabled={saving || saved || selected === currentDefaultId}
            title={TIPS.template.defaultSave(selected === currentDefaultId)}
            className="text-xs font-semibold bg-primary-600 text-white rounded-xl px-4 py-2.5 hover:bg-primary-700 active:bg-primary-800 disabled:bg-neutral-100 disabled:text-neutral-400 disabled:cursor-not-allowed transition-colors cursor-pointer"
          >
            {saving ? '저장 중...' : '기본값 저장'}
          </button>
        </div>
      </div>
    </div>
  )
}

