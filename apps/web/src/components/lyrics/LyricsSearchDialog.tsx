import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { searchLyrics, fetchRecentLyrics } from '../../api/lyrics'
import { getSheetsByTitles, downloadSheetsBySongKey } from '../../api/sheets'
import type { LyricsCatalogItem } from '../../types/lyrics'
import { TIPS } from '../../constants/tooltips'
import { Search, X, Clock, Download } from 'lucide-react'

interface Props {
  onSelect: (item: LyricsCatalogItem) => void
  onClose: () => void
}

export function LyricsSearchDialog({ onSelect, onClose }: Props) {
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 300)
    return () => clearTimeout(t)
  }, [q])

  const { data: searchResults } = useQuery({
    queryKey: ['lyrics-search', debounced],
    queryFn: () => searchLyrics(debounced),
    enabled: debounced.length > 0,
  })

  const { data: recentResults } = useQuery({
    queryKey: ['lyrics-recent'],
    queryFn: () => fetchRecentLyrics(20),
    enabled: debounced.length === 0,
  })

  const items = debounced ? (searchResults ?? []) : (recentResults ?? [])

  // normalize_title 서버 로직과 동일: NFC, strip, 연속공백 축약, 소문자
  function normTitle(t: string) {
    return t.normalize('NFC').trim().replace(/\s+/g, ' ').toLowerCase()
  }

  const titleKeys = items.map(item => normTitle(item.title))
  const { data: sheetsMap } = useQuery({
    queryKey: ['sheets-by-titles', titleKeys],
    queryFn: () => getSheetsByTitles(titleKeys),
    enabled: titleKeys.length > 0,
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/40 backdrop-blur-xs px-4" onClick={onClose}>
      <div
        className="bg-white border border-neutral-200/80 rounded-2xl shadow-2xl w-full max-w-md max-h-[70vh] flex flex-col overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* Raycast-style Search bar */}
        <div className="p-3.5 border-b border-neutral-100 flex items-center gap-2.5 bg-neutral-50/30">
          <Search className="w-4 h-4 text-neutral-400 shrink-0 ml-1" />
          <input
            autoFocus
            type="text"
            placeholder="가사 데이터베이스에서 찬양 검색..."
            className="flex-1 text-xs font-semibold outline-none bg-transparent placeholder:text-neutral-400 text-neutral-800"
            value={q}
            onChange={e => setQ(e.target.value)}
          />
          <button 
            onClick={onClose} 
            title={TIPS.setlist.searchClose} 
            className="text-neutral-400 hover:text-neutral-600 hover:bg-neutral-100 rounded-lg p-1 transition-colors cursor-pointer shrink-0"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 결과 리스트 */}
        <div className="overflow-y-auto flex-1 py-1 divide-y divide-neutral-100/50">
          {items.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 px-4 text-center gap-2">
              <Search className="w-5 h-5 text-neutral-300 animate-pulse" />
              <p className="text-xs text-neutral-400 font-semibold">
                {debounced ? '검색 결과가 없습니다' : '최근 추가된 찬양이 없습니다'}
              </p>
            </div>
          )}
          {items.map(item => {
            const titleKey = normTitle(item.title)
            const sheetFiles = sheetsMap?.[titleKey] ?? []
            // 같은 key별로 그룹화해서 고유 key 목록 추출
            const uniqueKeys = Array.from(
              new Map(sheetFiles.map(f => [f.key_display ?? `${f.key_root}${f.key_mode === 'minor' ? 'm' : ''}`, f])).entries()
            )
            return (
              <div key={item.title} className="border-b border-neutral-100/50 last:border-0">
                <button
                  title={TIPS.setlist.searchItem(item.sequence)}
                  className="w-full text-left px-5 py-3.5 hover:bg-primary-50/40 active:bg-primary-50/80 flex items-center justify-between gap-4 transition-all cursor-pointer group"
                  onClick={() => { onSelect(item); onClose() }}
                >
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-bold text-neutral-800 group-hover:text-primary-600 transition-colors">{item.title}</div>
                    {item.english_title && (
                      <div className="text-[10px] text-neutral-400 mt-0.5">{item.english_title}</div>
                    )}
                  </div>

                  {item.sequence && (
                    <div className="shrink-0 flex items-center">
                      <span className="text-[9px] font-bold font-mono bg-neutral-100 text-neutral-500 border border-neutral-200/50 rounded px-1.5 py-0.5 group-hover:bg-primary-100/50 group-hover:text-primary-600 group-hover:border-primary-200/50 transition-all">
                        {item.sequence}
                      </span>
                    </div>
                  )}
                </button>

                {uniqueKeys.length > 0 && (
                  <div className="px-5 pb-2.5 flex flex-wrap gap-1.5">
                    {uniqueKeys.map(([keyDisplay, file]) => (
                      <button
                        key={keyDisplay}
                        onClick={e => {
                          e.stopPropagation()
                          downloadSheetsBySongKey(titleKey, file.key_root, file.key_mode)
                        }}
                        className="flex items-center gap-1 text-[9px] font-bold bg-primary-50 text-primary-600 border border-primary-100 rounded px-2 py-1 hover:bg-primary-100 hover:border-primary-200 transition-all cursor-pointer"
                      >
                        <Download className="w-2.5 h-2.5" />
                        {keyDisplay} 악보 다운로드
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* 리스트 하단 풋터 */}
        {!debounced && (
          <div className="px-5 py-2.5 text-[9px] font-bold text-neutral-400 border-t border-neutral-100 bg-neutral-50/40 flex items-center gap-1.5 select-none uppercase tracking-wider">
            <Clock className="w-3 h-3 text-neutral-400" />
            <span>최근 추가된 찬양 목록</span>
          </div>
        )}
      </div>
    </div>
  )
}

