import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchJob, getDownloadUrl } from '../../api/jobs'
import type { ExportJob } from '../../types/jobs'
import { TIPS } from '../../constants/tooltips'

interface Props {
  jobId: string
  label?: string
  onClose: () => void
}

export function JobProgressDialog({ jobId, label = 'PPT', onClose }: Props) {
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

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && isDone) onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [isDone, onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-lg shadow-xl w-80 p-6">
        <h2 className="text-sm font-semibold text-gray-800 mb-4">
          {status === 'queued' && `${label} 생성 대기 중...`}
          {status === 'running' && `${label} 생성 중...`}
          {status === 'succeeded' && `${label} 생성 완료!`}
          {status === 'failed' && `${label} 생성 실패`}
        </h2>

        {/* Progress bar */}
        <div className="h-2 bg-gray-100 rounded-full overflow-hidden mb-3">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              status === 'failed' ? 'bg-red-400' : 'bg-blue-500'
            }`}
            style={{ width: `${job?.progress ?? 0}%` }}
          />
        </div>

        {job?.message && (
          <p className="text-xs text-gray-500 mb-4">{job.message}</p>
        )}

        {status === 'failed' && job?.error && (
          <p className="text-xs text-red-500 bg-red-50 rounded p-2 mb-4 break-words">{job.error}</p>
        )}

        <div className="flex gap-2 justify-end">
          {status === 'succeeded' && job?.download_url && (
            <a
              href={getDownloadUrl(jobId)}
              download
              title={TIPS.deck.jobDownload}
              className="text-sm bg-blue-500 text-white rounded px-4 py-2 hover:bg-blue-600 transition-colors"
            >
              다운로드
            </a>
          )}
          {isDone && (
            <button
              onClick={onClose}
              title={TIPS.deck.jobClose}
              className="text-sm border border-gray-300 rounded px-4 py-2 hover:bg-gray-50 transition-colors"
            >
              닫기
            </button>
          )}
          {!isDone && (
            <p className="text-xs text-gray-400 self-center">생성 중...</p>
          )}
        </div>
      </div>
    </div>
  )
}
