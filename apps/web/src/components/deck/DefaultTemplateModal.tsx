import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchTemplates, fetchDefaultTemplate, saveDefaultTemplate } from '../../api/templates'
import { useProjectStore } from '../../store/projectStore'
import { TIPS } from '../../constants/tooltips'

interface Props {
  onClose: () => void
}

export function DefaultTemplateModal({ onClose }: Props) {
  const queryClient = useQueryClient()
  const { setTemplateId } = useProjectStore()
  const { data: templates = [] } = useQuery({ queryKey: ['templates'], queryFn: fetchTemplates })
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl w-80 flex flex-col max-h-[80vh]"
        onClick={e => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-gray-100">
          <div>
            <h2 className="text-sm font-semibold text-gray-800">기본 템플릿 설정</h2>
            <p className="text-xs text-gray-400 mt-0.5">앱 시작 시 자동으로 선택될 템플릿</p>
          </div>
          <button
            onClick={onClose}
            title={TIPS.template.defaultClose}
            className="text-gray-300 hover:text-gray-500 transition-colors text-lg leading-none"
          >
            ✕
          </button>
        </div>

        {/* 목록 */}
        <div className="overflow-y-auto flex-1 py-2">
          {templates.length === 0 && (
            <p className="text-xs text-gray-400 text-center py-6">템플릿이 없습니다</p>
          )}
          {templates.map(name => {
            const id = name.replace(/\.pptx$/i, '')
            const isSelected = id === selected
            const isCurrentDefault = id === currentDefaultId

            return (
              <label
                key={name}
                className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-colors
                  ${isSelected ? 'bg-blue-50' : 'hover:bg-gray-50'}`}
              >
                <input
                  type="radio"
                  name="default-template"
                  value={id}
                  checked={isSelected}
                  onChange={() => setSelected(id)}
                  className="accent-blue-500 shrink-0"
                />
                <span className="text-sm text-gray-700 flex-1 truncate">{id}</span>
                {isCurrentDefault && (
                  <span className="text-xs text-blue-400 shrink-0">현재 기본</span>
                )}
              </label>
            )
          })}
        </div>

        {/* 푸터 */}
        <div className="px-5 pb-5 pt-3 border-t border-gray-100 flex gap-2 justify-end">
          {saved && (
            <span className="text-xs text-green-600 self-center mr-auto">✓ 저장됨</span>
          )}
          <button
            onClick={onClose}
            title={TIPS.template.defaultCancel}
            className="text-sm border border-gray-300 rounded px-3 py-1.5 hover:bg-gray-50 transition-colors"
          >
            취소
          </button>
          <button
            onClick={handleSave}
            disabled={saving || saved || selected === currentDefaultId}
            title={TIPS.template.defaultSave(selected === currentDefaultId)}
            className="text-sm bg-blue-500 text-white rounded px-3 py-1.5 hover:bg-blue-600
              disabled:bg-gray-200 disabled:text-gray-400 transition-colors"
          >
            {saving ? '저장 중...' : '저장'}
          </button>
        </div>
      </div>
    </div>
  )
}
