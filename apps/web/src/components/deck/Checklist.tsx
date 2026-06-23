import { useProjectStore } from '../../store/projectStore'
import {
  getUniqueParts,
  isPartNoLyrics,
  getLyricsSectionStatus,
} from '../../types/project'
import type { SongEntry } from '../../types/project'
import { CheckCircle2, Circle, AlertTriangle } from 'lucide-react'

interface CheckItem {
  ok: boolean
  label: string
  detail?: string
}

function allPartsComplete(song: SongEntry): boolean {
  if (!song.sequence.trim()) return true
  const uniqueParts = getUniqueParts(song.sequence)
  const required = uniqueParts.filter(p => !isPartNoLyrics(song, p))
  if (required.length === 0) return true
  return required.every(p => getLyricsSectionStatus(song.lyrics, p, uniqueParts) === 'has-content')
}

function getMissingPartsDetail(songs: SongEntry[]): string {
  const issues: string[] = []
  for (const s of songs) {
    if (!s.sequence.trim()) continue
    const uniqueParts = getUniqueParts(s.sequence)
    const problems = uniqueParts
      .filter(p => !isPartNoLyrics(s, p))
      .flatMap(p => {
        const st = getLyricsSectionStatus(s.lyrics, p, uniqueParts)
        if (st === 'missing') return [p]
        if (st === 'empty')   return [`${p}(빈 파트)`]
        return []
      })
    if (problems.length > 0) issues.push(`${s.title || '(제목 없음)'}: ${problems.join(', ')}`)
  }
  return issues.join(' / ')
}

export function Checklist() {
  const { songs } = useProjectStore()

  const allComplete = songs.every(allPartsComplete)
  const missingDetail = allComplete ? '' : getMissingPartsDetail(songs)

  const items: CheckItem[] = [
    { ok: songs.length > 0, label: '곡이 1개 이상 있음' },
    { ok: songs.every(s => s.title.trim()), label: '모든 곡에 제목 있음' },
    { ok: songs.every(s => s.sequence.trim()), label: '모든 곡에 진행 순서 있음' },
    { ok: songs.every(s => s.lyrics.trim()), label: '모든 곡에 가사 있음' },
    {
      ok: allComplete,
      label: '모든 레파토리 구성 완료',
      detail: missingDetail || undefined,
    },
  ]

  const allOk = items.every(i => i.ok)

  return (
    <div className="space-y-2">
      {items.map((item, i) => (
        <div key={i} className="flex flex-col">
          <div className="flex items-center gap-2.5">
            {item.ok ? (
              <CheckCircle2 className="w-4 h-4 text-success-500 shrink-0" />
            ) : (
              <Circle className="w-4 h-4 text-neutral-300 shrink-0" />
            )}
            <span className={`text-xs font-medium ${item.ok ? 'text-neutral-700' : 'text-neutral-400'}`}>
              {item.label}
            </span>
          </div>
          {!item.ok && item.detail && (
            <div className="flex items-start gap-1 mt-1 ml-6.5 text-[10px] text-warning-600 bg-warning-50 border border-warning-100 rounded px-2 py-1 leading-snug">
              <AlertTriangle className="w-3 h-3 shrink-0 mt-0.5" />
              <span>{item.detail}</span>
            </div>
          )}
        </div>
      ))}
      {allOk && (
        <div className="mt-3.5 bg-success-50 border border-success-100 rounded-lg py-2 px-3 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-success-600 shrink-0" />
          <p className="text-xs text-success-700 font-semibold">PPT 생성 준비 완료</p>
        </div>
      )}
    </div>
  )
}

