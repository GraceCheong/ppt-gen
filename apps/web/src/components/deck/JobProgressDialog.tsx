import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchJob, getDownloadUrl } from '../../api/jobs'
import type { ExportJob } from '../../types/jobs'
import { TIPS } from '../../constants/tooltips'
import { Loader2, Calendar, Download, XCircle, CheckCircle2, AlertCircle } from 'lucide-react'

interface Props {
  jobId: string
  label?: string
  onClose: () => void
  /** PPT 완료 후 이번주 레파토리 저장 콜백 — 제공되면 저장 확인 UI 표시 */
  onSaveRepertoire?: () => Promise<void>
}

export function JobProgressDialog({ jobId, label = 'PPT', onClose, onSaveRepertoire }: Props) {
  const { data: job } = useQuery<ExportJob>({
    queryKey: ['job', jobId],
    queryFn: () => fetchJob(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'succeeded' || status === 'failed') return false
      return 1000
    },
  })

  const status = job?.status ?? 'queued'
  const isDone = status === 'succeeded' || status === 'failed'

  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'dismissed' | 'error'>('idle')

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && isDone && saveState !== 'saving') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [isDone, saveState, onClose])

  async function handleSave() {
    if (!onSaveRepertoire || saveState === 'saving' || saveState === 'saved') return
    setSaveState('saving')
    try {
      await onSaveRepertoire()
      setSaveState('saved')
    } catch {
      setSaveState('error')
    }
  }

  const showSavePrompt = status === 'succeeded' && onSaveRepertoire && saveState === 'idle'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/40 backdrop-blur-xs px-4">
      <div className="bg-white border border-neutral-200/80 rounded-2xl shadow-2xl w-full max-w-xs p-6 space-y-4">
        <div className="flex items-center gap-2">
          {!isDone && <Loader2 className="w-4 h-4 text-primary-500 animate-spin" />}
          {status === 'succeeded' && <CheckCircle2 className="w-4 h-4 text-success-500" />}
          {status === 'failed' && <XCircle className="w-4 h-4 text-danger-500" />}
          
          <h2 className="text-sm font-bold text-neutral-800">
            {status === 'queued' && `${label} 생성 대기 중...`}
            {status === 'running' && `${label} 생성 중...`}
            {status === 'succeeded' && `${label} 생성 완료!`}
            {status === 'failed' && `${label} 생성 실패`}
          </h2>
        </div>

        {/* Progress bar */}
        <div className="h-2 bg-neutral-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              status === 'failed' ? 'bg-danger-500' : 'bg-primary-500'
            }`}
            style={{ width: `${job?.progress ?? 0}%` }}
          />
        </div>

        {job?.message && (
          <p className="text-xs text-neutral-500 leading-normal">{job.message}</p>
        )}

        {status === 'failed' && job?.error && (
          <p className="text-[11px] text-danger-600 bg-danger-50 border border-danger-100 rounded-xl p-3 break-words font-medium">
            {job.error}
          </p>
        )}

        {/* 이번주 레파토리 저장 확인 */}
        {showSavePrompt && (
          <div className="bg-primary-50/50 rounded-xl border border-primary-100 p-3.5 space-y-2.5">
            <div className="flex items-center gap-1.5 text-primary-800 font-semibold text-[11px]">
              <Calendar className="w-3.5 h-3.5 text-primary-500" />
              <span>이번주 찬양 레파토리로 저장할까요?</span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleSave}
                className="flex-1 text-xs font-semibold bg-primary-600 text-white rounded-lg py-1.5 hover:bg-primary-700 transition-colors cursor-pointer"
              >
                저장
              </button>
              <button
                onClick={() => setSaveState('dismissed')}
                className="flex-1 text-xs font-semibold border border-neutral-200 text-neutral-600 rounded-lg py-1.5 hover:bg-neutral-50 transition-colors cursor-pointer"
              >
                나중에
              </button>
            </div>
          </div>
        )}

        {saveState === 'saving' && (
          <p className="text-xs text-primary-500 font-medium flex items-center gap-1.5">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            <span>캘린더에 저장하는 중...</span>
          </p>
        )}

        {saveState === 'saved' && (
          <div className="bg-success-50 border border-success-100 rounded-xl p-2.5 flex items-center gap-1.5 text-xs text-success-700 font-semibold">
            <CheckCircle2 className="w-4 h-4 text-success-500 shrink-0" />
            <span>캘린더에 저장 완료되었습니다.</span>
          </div>
        )}

        {saveState === 'error' && (
          <div className="bg-danger-50 border border-danger-100 rounded-xl p-2.5 flex items-start gap-1.5 text-xs text-danger-700 font-medium leading-normal">
            <AlertCircle className="w-4 h-4 text-danger-500 shrink-0 mt-0.5" />
            <span>저장에 실패했습니다. 캘린더 탭에서 직접 기록하실 수 있습니다.</span>
          </div>
        )}

        <div className="flex gap-2 justify-end pt-2 border-t border-neutral-100">
          {status === 'succeeded' && job?.download_url && (
            <a
              href={getDownloadUrl(jobId)}
              download
              title={TIPS.deck.jobDownload}
              className="text-xs font-bold bg-primary-600 text-white rounded-xl px-4 py-2.5 hover:bg-primary-700 transition-colors flex items-center gap-1.5 cursor-pointer shadow-md shadow-primary-600/10 hover:shadow-lg hover:shadow-primary-600/20 active:bg-primary-800"
            >
              <Download className="w-3.5 h-3.5" />
              <span>다운로드</span>
            </a>
          )}
          {isDone && (
            <button
              onClick={onClose}
              disabled={saveState === 'saving'}
              title={TIPS.deck.jobClose}
              className="text-xs font-semibold border border-neutral-200 rounded-xl px-4 py-2.5 hover:bg-neutral-50 transition-colors disabled:opacity-40 cursor-pointer"
            >
              닫기
            </button>
          )}
          {!isDone && (
            <p className="text-[11px] text-neutral-400 font-medium self-center">서버 작업 처리 대기 중...</p>
          )}
        </div>
      </div>
    </div>
  )
}

