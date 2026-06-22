import { useProjectStore } from '../../store/projectStore'
import {
  getUniqueParts,
  isPartNoLyrics,
  getLyricsSectionStatus,
} from '../../types/project'
import type { SongEntry } from '../../types/project'

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
    <div>
      {items.map((item, i) => (
        <div key={i} className="py-0.5">
          <div className="flex items-center gap-2">
            <span className={item.ok ? 'text-green-500' : 'text-gray-300'}>
              {item.ok ? '✓' : '○'}
            </span>
            <span className={`text-xs ${item.ok ? 'text-gray-600' : 'text-gray-400'}`}>
              {item.label}
            </span>
          </div>
          {!item.ok && item.detail && (
            <p className="text-[10px] text-orange-400 ml-5 mt-0.5 leading-snug">{item.detail}</p>
          )}
        </div>
      ))}
      {allOk && (
        <p className="text-xs text-green-600 font-medium mt-2">PPT 생성 준비 완료</p>
      )}
    </div>
  )
}
