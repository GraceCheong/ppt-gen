import { useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchTemplates, fetchDefaultTemplate, saveDefaultTemplate } from '../../api/templates'
import { useProjectStore } from '../../store/projectStore'
import { TIPS } from '../../constants/tooltips'

export function TemplateSelect() {
  const { templateId, setTemplateId } = useProjectStore()
  const queryClient = useQueryClient()

  const { data: templates = [], isLoading } = useQuery({
    queryKey: ['templates'],
    queryFn: fetchTemplates,
  })

  const { data: defaultTemplate } = useQuery({
    queryKey: ['template-default'],
    queryFn: fetchDefaultTemplate,
  })

  // 목록이 로드되면 기본 템플릿 → 없으면 첫 번째 템플릿 자동 선택
  useEffect(() => {
    if (templates.length === 0 || templateId) return

    const defaultId = defaultTemplate?.template_id
    const ids = templates.map(n => n.replace(/\.pptx$/i, ''))

    const resolved =
      defaultId && ids.includes(defaultId)
        ? defaultId
        : ids[0]

    setTemplateId(resolved)
  }, [templates, defaultTemplate, templateId, setTemplateId])

  if (isLoading) {
    return <p className="text-xs text-gray-400">템플릿 목록 불러오는 중...</p>
  }

  if (templates.length === 0) {
    return <p className="text-xs text-gray-400">서버에 템플릿이 없습니다</p>
  }

  const defaultId = defaultTemplate?.template_id

  return (
    <select
      className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-xs font-semibold outline-none bg-neutral-50/50 hover:bg-neutral-50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all duration-150 cursor-pointer"
      title={TIPS.template.select}
      value={templateId ?? ''}
      onChange={e => {
        const id = e.target.value || null
        setTemplateId(id)
        saveDefaultTemplate(id).then(() => {
          queryClient.invalidateQueries({ queryKey: ['template-default'] })
        })
      }}
    >
      {templates.map(name => {
        const id = name.replace(/\.pptx$/i, '')
        const isDefault = id === defaultId
        return (
          <option key={name} value={id}>
            {id}{isDefault ? ' (기본 템플릿)' : ''}
          </option>
        )
      })}
    </select>
  )
}

