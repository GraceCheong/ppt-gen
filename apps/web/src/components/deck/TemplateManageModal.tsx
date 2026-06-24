import { useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { X, Trash2, Check, Star, Upload, Lock } from 'lucide-react'
import {
  fetchTemplates,
  fetchDefaultTemplate,
  saveDefaultTemplate,
  deleteTemplate,
  uploadTemplate,
} from '../../api/templates'
import { useProjectStore } from '../../store/projectStore'
import { TemplateUploadGuideModal } from './TemplateUploadGuideModal'

interface Props {
  onClose: () => void
}

export function TemplateManageModal({ onClose }: Props) {
  const queryClient = useQueryClient()
  const { setTemplateId } = useProjectStore()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [showGuide, setShowGuide] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [settingDefault, setSettingDefault] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadIssues, setUploadIssues] = useState<string[] | null>(null)
  const [uploadWarnings, setUploadWarnings] = useState<string[] | null>(null)
  const [uploadLayoutNames, setUploadLayoutNames] = useState<string[] | null>(null)
  const [savedMsg, setSavedMsg] = useState('')

  const { data: templates = [], isLoading } = useQuery({
    queryKey: ['templates'],
    queryFn: fetchTemplates,
  })

  const { data: defaultTemplate } = useQuery({
    queryKey: ['template-default'],
    queryFn: fetchDefaultTemplate,
  })

  const currentDefaultId = defaultTemplate?.template_id ?? null

  async function handleSetDefault(id: string) {
    if (settingDefault) return
    setSettingDefault(id)
    try {
      await saveDefaultTemplate(id)
      setTemplateId(id)
      queryClient.invalidateQueries({ queryKey: ['template-default'] })
      setSavedMsg(`"${id}"을(를) 기본 템플릿으로 설정했습니다`)
      setTimeout(() => setSavedMsg(''), 2500)
    } finally {
      setSettingDefault(null)
    }
  }

  async function handleDelete(id: string) {
    if (!confirm(`"${id}" 템플릿을 삭제할까요?`)) return
    setDeleting(id)
    try {
      await deleteTemplate(id)
      queryClient.invalidateQueries({ queryKey: ['templates'] })
      if (currentDefaultId === id) {
        await saveDefaultTemplate(null)
        queryClient.invalidateQueries({ queryKey: ['template-default'] })
      }
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : '삭제 실패')
    } finally {
      setDeleting(null)
    }
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ''

    setUploadIssues(null)
    setUploadWarnings(null)
    setUploadLayoutNames(null)
    setUploading(true)
    try {
      const result = await uploadTemplate(file)
      if (!result.compatible) {
        setUploadIssues(result.issues ?? [])
        setUploadWarnings(result.warnings ?? [])
        setUploadLayoutNames(result.layout_names ?? [])
      } else {
        if (result.warnings?.length) setUploadWarnings(result.warnings)
        queryClient.invalidateQueries({ queryKey: ['templates'] })
        setSavedMsg(`"${result.template_id}" 업로드 완료`)
        setTimeout(() => setSavedMsg(''), 2500)
      }
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : '업로드 실패')
    } finally {
      setUploading(false)
    }
  }

  return (
    <>
      {showGuide && (
        <TemplateUploadGuideModal
          onClose={() => setShowGuide(false)}
          onConfirm={() => {
            setShowGuide(false)
            fileInputRef.current?.click()
          }}
        />
      )}

      <div
        className="fixed inset-0 z-40 flex items-center justify-center bg-neutral-950/40 backdrop-blur-xs px-4"
        onClick={onClose}
      >
        <div
          className="bg-white border border-neutral-200/80 rounded-2xl shadow-2xl w-full max-w-sm flex flex-col max-h-[85vh] overflow-hidden"
          onClick={e => e.stopPropagation()}
        >
          {/* 헤더 */}
          <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-neutral-100 shrink-0">
            <div>
              <h2 className="text-sm font-bold text-neutral-900">템플릿 관리</h2>
              <p className="text-[11px] text-neutral-400 mt-0.5">템플릿을 추가·삭제하고 기본값을 설정합니다</p>
            </div>
            <button
              onClick={onClose}
              className="text-neutral-400 hover:text-neutral-600 hover:bg-neutral-50 rounded-lg p-1.5 transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* 목록 */}
          <div className="overflow-y-auto flex-1 py-3 px-4 space-y-1">
            {isLoading && (
              <p className="text-xs text-neutral-400 text-center py-8">불러오는 중...</p>
            )}
            {!isLoading && templates.length === 0 && (
              <p className="text-xs text-neutral-400 text-center py-8">등록된 템플릿이 없습니다</p>
            )}
            {templates.map(item => {
              const isDefault = item.id === currentDefaultId
              return (
                <div
                  key={item.id}
                  className={`flex items-center gap-2 px-3.5 py-2.5 rounded-xl border transition-all duration-150
                    ${isDefault
                      ? 'bg-primary-50/50 border-primary-200'
                      : 'bg-white border-neutral-100 hover:bg-neutral-50/60'}`}
                >
                  <span className="text-xs font-semibold text-neutral-800 flex-1 truncate">{item.id}</span>

                  {isDefault && (
                    <span className="text-[10px] font-bold text-primary-500 bg-primary-100/50 border border-primary-200/50 rounded-full px-2 py-0.5 shrink-0">
                      기본
                    </span>
                  )}

                  {!isDefault && (
                    <button
                      onClick={() => handleSetDefault(item.id)}
                      disabled={!!settingDefault}
                      title="기본 템플릿으로 설정"
                      className="p-1.5 rounded-lg text-neutral-300 hover:text-primary-500 hover:bg-primary-50 transition-colors cursor-pointer disabled:opacity-40 shrink-0"
                    >
                      <Star className="w-3.5 h-3.5" />
                    </button>
                  )}

                  {item.deletable ? (
                    <button
                      onClick={() => handleDelete(item.id)}
                      disabled={deleting === item.id}
                      title="삭제"
                      className="p-1.5 rounded-lg text-neutral-300 hover:text-danger-500 hover:bg-danger-50 transition-colors cursor-pointer disabled:opacity-40 shrink-0"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  ) : (
                    <span title="공유 템플릿은 삭제할 수 없습니다" className="p-1.5 text-neutral-200 shrink-0">
                      <Lock className="w-3.5 h-3.5" />
                    </span>
                  )}
                </div>
              )
            })}

            {/* 호환 불가 오류 */}
            {uploadIssues && (
              <div className="mt-2 border border-danger-200 bg-danger-50 rounded-xl p-3 text-[11px]">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-bold text-danger-700">호환되지 않는 템플릿</span>
                  <button onClick={() => { setUploadIssues(null); setUploadWarnings(null) }} className="text-danger-400 hover:text-danger-600 cursor-pointer"><X className="w-3.5 h-3.5" /></button>
                </div>
                <ul className="space-y-0.5 text-danger-600">
                  {uploadIssues.map((issue, i) => <li key={i}>• {issue}</li>)}
                </ul>
                {uploadLayoutNames && uploadLayoutNames.length > 0 && (
                  <p className="mt-1.5 text-danger-500">현재 레이아웃: {uploadLayoutNames.join(', ')}</p>
                )}
              </div>
            )}
            {/* 경고 */}
            {!uploadIssues && uploadWarnings && uploadWarnings.length > 0 && (
              <div className="mt-2 border border-warning-200 bg-warning-50 rounded-xl p-3 text-[11px]">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-bold text-warning-700">주의사항</span>
                  <button onClick={() => setUploadWarnings(null)} className="text-warning-400 hover:text-warning-600 cursor-pointer"><X className="w-3.5 h-3.5" /></button>
                </div>
                <ul className="space-y-0.5 text-warning-600">
                  {uploadWarnings.map((w, i) => <li key={i}>• {w}</li>)}
                </ul>
              </div>
            )}
          </div>

          {/* 푸터 */}
          <div className="px-4 pb-4 pt-3 border-t border-neutral-100 flex items-center gap-2 shrink-0">
            {savedMsg && (
              <span className="text-[11px] font-semibold text-success-600 flex items-center gap-1 mr-auto shrink-0">
                <Check className="w-3.5 h-3.5" />
                <span className="truncate max-w-[160px]">{savedMsg}</span>
              </span>
            )}
            <div className="flex gap-2 ml-auto">
              <button
                onClick={() => setShowGuide(true)}
                disabled={uploading}
                className="flex items-center gap-1.5 text-xs font-semibold border border-neutral-200 text-neutral-700 rounded-xl px-3.5 py-2.5 hover:bg-neutral-50 transition-colors cursor-pointer disabled:opacity-50"
              >
                <Upload className="w-3.5 h-3.5" />
                {uploading ? '업로드 중...' : '추가'}
              </button>
              <button
                onClick={onClose}
                className="text-xs font-semibold bg-neutral-900 text-white rounded-xl px-4 py-2.5 hover:bg-neutral-700 transition-colors cursor-pointer"
              >
                완료
              </button>
            </div>
          </div>
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".pptx"
        className="hidden"
        onChange={handleFileChange}
      />
    </>
  )
}
