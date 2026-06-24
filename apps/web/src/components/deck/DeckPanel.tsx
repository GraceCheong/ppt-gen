import { useState, useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useProjectStore } from '../../store/projectStore'
import { useAuthStore } from '../../store/authStore'
import { TemplateSelect } from './TemplateSelect'
import { TemplatePreview } from './TemplatePreview'
import { TemplateUploadSection } from './TemplateUploadSection'
import { TemplateManageModal } from './TemplateManageModal'
import { Checklist } from './Checklist'
import { JobProgressDialog } from './JobProgressDialog'
import { createPptxJob, createSonglistJob } from '../../api/exports'
import { saveHistoryEntry } from '../../api/history'
import { TIPS } from '../../constants/tooltips'
import { Settings, Sliders, CheckSquare, Presentation, FileText, AlertCircle } from 'lucide-react'

function thisOrNextSaturday(): string {
  const d = new Date()
  const day = d.getDay() // 0=일, 6=토
  const diff = day === 6 ? 0 : (6 - day)
  d.setDate(d.getDate() + diff)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${dd}`
}

export function DeckPanel() {
  const { songs, templateId, settings, updateSettings } = useProjectStore()
  const { mode } = useAuthStore()
  const queryClient = useQueryClient()

  const [linesStr, setLinesStr] = useState(() => String(settings.maxLinesPerSlide))
  const [charsStr, setCharsStr] = useState(() => String(settings.maxCharsPerLine))
  useEffect(() => { setLinesStr(String(settings.maxLinesPerSlide)) }, [settings.maxLinesPerSlide])
  useEffect(() => { setCharsStr(String(settings.maxCharsPerLine)) }, [settings.maxCharsPerLine])

  const [showManageModal, setShowManageModal] = useState(false)
  const [pptJobId, setPptJobId] = useState<string | null>(null)
  const [songlistJobId, setSonglistJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loadingPpt, setLoadingPpt] = useState(false)
  const [loadingSonglist, setLoadingSonglist] = useState(false)

  const canGenerate = songs.length > 0 && songs.every(s => s.title && s.sequence)

  async function runJob(
    createJob: () => Promise<string>,
    setLoading: (v: boolean) => void,
    setJobId: (id: string) => void,
  ) {
    setError(null)
    setLoading(true)
    try {
      setJobId(await createJob())
    } catch (e) {
      setError(e instanceof Error ? e.message : '알 수 없는 오류')
    } finally {
      setLoading(false)
    }
  }

  async function handleSaveRepertoire() {
    const weekEndDate = thisOrNextSaturday()
    const entries = songs.map(s => ({ title: s.title, sequence: s.sequence }))
    await saveHistoryEntry(weekEndDate, entries)
    queryClient.invalidateQueries({ queryKey: ['history'] })
    queryClient.invalidateQueries({ queryKey: ['graph'] })
  }

  return (
    <div className="flex flex-col h-full p-4 gap-5">
      {/* 템플릿 */}
      <section className="flex flex-col gap-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-[10px] font-bold text-neutral-400 uppercase tracking-wider">
            <Presentation className="w-3.5 h-3.5 text-neutral-400" />
            <span>디자인 템플릿</span>
          </div>
          <button
            onClick={() => setShowManageModal(true)}
            className="text-[11px] font-medium text-neutral-400 hover:text-neutral-700 flex items-center gap-1 transition-colors cursor-pointer"
            title="템플릿 추가·삭제 및 기본값 설정"
          >
            <Settings className="w-3 h-3" />
            <span>템플릿 관리</span>
          </button>
        </div>
        <div className="border border-neutral-100 rounded-xl overflow-hidden shadow-sm">
          <TemplatePreview templateId={templateId} />
        </div>
        <div className="flex flex-col gap-1.5">
          <TemplateSelect />
          <TemplateUploadSection />
        </div>
      </section>

      <hr className="border-neutral-100" />

      {/* 설정 */}
      <section className="flex flex-col gap-3">
        <div className="flex items-center gap-1.5 text-[10px] font-bold text-neutral-400 uppercase tracking-wider">
          <Sliders className="w-3.5 h-3.5 text-neutral-400" />
          <span>슬라이드 설정</span>
        </div>
        <div className="bg-neutral-50/50 border border-neutral-200/50 rounded-xl p-3 flex flex-col gap-3.5">
          <label className="flex items-center justify-between text-xs font-medium text-neutral-600">
            <span>슬라이드당 최대 줄 수</span>
            <input
              type="text"
              inputMode="numeric"
              className="w-14 border border-neutral-200 bg-white rounded-lg px-2 py-1 text-xs outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all text-center font-bold text-neutral-800"
              value={linesStr}
              onFocus={e => e.target.select()}
              onChange={e => setLinesStr(e.target.value)}
              onBlur={() => {
                const v = parseInt(linesStr, 10)
                const clamped = isNaN(v) ? 4 : Math.max(1, Math.min(10, v))
                setLinesStr(String(clamped))
                updateSettings({ maxLinesPerSlide: clamped })
              }}
            />
          </label>
          <label className="flex items-center justify-between text-xs font-medium text-neutral-600">
            <span>한 줄 최대 글자 수</span>
            <input
              type="text"
              inputMode="numeric"
              className="w-14 border border-neutral-200 bg-white rounded-lg px-2 py-1 text-xs outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all text-center font-bold text-neutral-800"
              value={charsStr}
              onFocus={e => e.target.select()}
              onChange={e => setCharsStr(e.target.value)}
              onBlur={() => {
                const v = parseInt(charsStr, 10)
                const clamped = isNaN(v) ? 18 : Math.max(5, Math.min(50, v))
                setCharsStr(String(clamped))
                updateSettings({ maxCharsPerLine: clamped })
              }}
            />
          </label>
        </div>
      </section>

      <hr className="border-neutral-100" />

      {/* 체크리스트 */}
      <section className="flex flex-col gap-2.5">
        <div className="flex items-center gap-1.5 text-[10px] font-bold text-neutral-400 uppercase tracking-wider">
          <CheckSquare className="w-3.5 h-3.5 text-neutral-400" />
          <span>내보내기 체크리스트</span>
        </div>
        <div className="bg-neutral-50/50 border border-neutral-200/50 rounded-xl p-3.5">
          <Checklist />
        </div>
      </section>

      {/* 생성 버튼 */}
      <section className="mt-auto flex flex-col gap-2.5 pt-4">
        {error && (
          <div className="flex items-start gap-2 text-xs text-danger-600 bg-danger-50 border border-danger-100 rounded-xl p-3 break-words">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}
        <button
          onClick={() => runJob(
            () => createPptxJob(songs, settings, templateId),
            setLoadingPpt,
            setPptJobId,
          )}
          disabled={!canGenerate || loadingPpt}
          title={TIPS.deck.pptGenerate(canGenerate)}
          className={`w-full py-3 rounded-xl text-sm font-semibold transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer shadow-md
            ${canGenerate && !loadingPpt
              ? 'bg-primary-600 text-white hover:bg-primary-700 hover:shadow-lg hover:shadow-primary-600/20 active:bg-primary-800'
              : 'bg-neutral-100 text-neutral-400 cursor-not-allowed shadow-none'}`}
        >
          <Presentation className="w-4 h-4" />
          <span>{loadingPpt ? 'PPT 생성 요청 중...' : 'PPT 생성'}</span>
        </button>
        <button
          onClick={() => runJob(
            () => createSonglistJob(songs.map(s => s.title).filter(Boolean), null),
            setLoadingSonglist,
            setSonglistJobId,
          )}
          disabled={!canGenerate || loadingSonglist}
          title={TIPS.deck.songlistGenerate(canGenerate)}
          className={`w-full py-2.5 rounded-xl text-xs font-semibold transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer border
            ${canGenerate && !loadingSonglist
              ? 'border-neutral-200 text-neutral-700 bg-white hover:bg-neutral-50 active:bg-neutral-100'
              : 'border-neutral-200 bg-neutral-50 text-neutral-300 cursor-not-allowed'}`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>{loadingSonglist ? '요청 중...' : '송리스트 카드 이미지 생성'}</span>
        </button>
        <p className="text-[11px] text-neutral-400 text-center font-medium mt-1">
          {songs.length}곡 · 슬라이드당 {settings.maxLinesPerSlide}줄
        </p>
      </section>

      {showManageModal && (
        <TemplateManageModal onClose={() => setShowManageModal(false)} />
      )}

      {pptJobId && (
        <JobProgressDialog
          jobId={pptJobId}
          label="PPT"
          onClose={() => setPptJobId(null)}
          onSaveRepertoire={mode === 'user' ? handleSaveRepertoire : undefined}
        />
      )}
      {songlistJobId && (
        <JobProgressDialog jobId={songlistJobId} label="송리스트 카드" onClose={() => setSonglistJobId(null)} />
      )}
    </div>
  )
}

