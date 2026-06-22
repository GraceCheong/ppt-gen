import { useState, useEffect } from 'react'
import { useProjectStore } from '../../store/projectStore'
import { TemplateSelect } from './TemplateSelect'
import { TemplatePreview } from './TemplatePreview'
import { TemplateUploadSection } from './TemplateUploadSection'
import { DefaultTemplateModal } from './DefaultTemplateModal'
import { Checklist } from './Checklist'
import { JobProgressDialog } from './JobProgressDialog'
import { createPptxJob, createSonglistJob } from '../../api/exports'
import { TIPS } from '../../constants/tooltips'

export function DeckPanel() {
  const { songs, templateId, settings, updateSettings } = useProjectStore()

  const [linesStr, setLinesStr] = useState(() => String(settings.maxLinesPerSlide))
  const [charsStr, setCharsStr] = useState(() => String(settings.maxCharsPerLine))
  useEffect(() => { setLinesStr(String(settings.maxLinesPerSlide)) }, [settings.maxLinesPerSlide])
  useEffect(() => { setCharsStr(String(settings.maxCharsPerLine)) }, [settings.maxCharsPerLine])

  const [showDefaultModal, setShowDefaultModal] = useState(false)
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

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* 템플릿 */}
      <section>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">템플릿</span>
          <button
            onClick={() => setShowDefaultModal(true)}
            className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
            title={TIPS.template.defaultOpen}
          >
            기본 설정
          </button>
        </div>
        <TemplatePreview templateId={templateId} />
        <div className="mt-2">
          <TemplateSelect />
        </div>
        <div className="mt-1.5">
          <TemplateUploadSection />
        </div>
      </section>

      {/* 설정 */}
      <section>
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
          슬라이드 설정
        </div>
        <div className="flex flex-col gap-2">
          <label className="flex items-center justify-between text-xs text-gray-600">
            <span>슬라이드당 최대 줄 수</span>
            <input
              type="text"
              inputMode="numeric"
              className="w-16 border border-gray-300 rounded px-2 py-1 text-xs outline-none focus:border-blue-400 text-center"
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
          <label className="flex items-center justify-between text-xs text-gray-600">
            <span>한 줄 최대 글자 수</span>
            <input
              type="text"
              inputMode="numeric"
              className="w-16 border border-gray-300 rounded px-2 py-1 text-xs outline-none focus:border-blue-400 text-center"
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

      {/* 체크리스트 */}
      <section>
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
          체크리스트
        </div>
        <Checklist />
      </section>

      {/* 생성 버튼 */}
      <section className="mt-auto flex flex-col gap-2">
        {error && (
          <p className="text-xs text-red-500 bg-red-50 rounded p-2 break-words">{error}</p>
        )}
        <button
          onClick={() => runJob(
            () => createPptxJob(songs, settings, templateId),
            setLoadingPpt,
            setPptJobId,
          )}
          disabled={!canGenerate || loadingPpt}
          title={TIPS.deck.pptGenerate(canGenerate)}
          className={`w-full py-2.5 rounded text-sm font-medium transition-colors
            ${canGenerate && !loadingPpt
              ? 'bg-blue-500 text-white hover:bg-blue-600'
              : 'bg-gray-100 text-gray-400 cursor-not-allowed'}`}
        >
          {loadingPpt ? 'PPT 생성 요청 중...' : 'PPT 생성'}
        </button>
        <button
          onClick={() => runJob(
            () => createSonglistJob(songs.map(s => s.title).filter(Boolean), null),
            setLoadingSonglist,
            setSonglistJobId,
          )}
          disabled={!canGenerate || loadingSonglist}
          title={TIPS.deck.songlistGenerate(canGenerate)}
          className={`w-full py-2 rounded text-sm font-medium transition-colors border
            ${canGenerate && !loadingSonglist
              ? 'border-gray-300 text-gray-600 hover:bg-gray-50'
              : 'border-gray-200 text-gray-300 cursor-not-allowed'}`}
        >
          {loadingSonglist ? '요청 중...' : '송리스트 카드 생성'}
        </button>
        <p className="text-xs text-gray-400 text-center">
          {songs.length}곡 · 슬라이드당 {settings.maxLinesPerSlide}줄
        </p>
      </section>

      {showDefaultModal && (
        <DefaultTemplateModal onClose={() => setShowDefaultModal(false)} />
      )}

      {pptJobId && (
        <JobProgressDialog jobId={pptJobId} label="PPT" onClose={() => setPptJobId(null)} />
      )}
      {songlistJobId && (
        <JobProgressDialog jobId={songlistJobId} label="송리스트 카드" onClose={() => setSonglistJobId(null)} />
      )}
    </div>
  )
}
