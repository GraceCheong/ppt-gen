import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { searchLyrics, fetchRecentLyrics } from '../../api/lyrics'
import type { LyricsCatalogItem } from '../../types/lyrics'
import { TIPS } from '../../constants/tooltips'

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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-xl w-96 max-h-[70vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        <div className="p-3 border-b flex gap-2">
          <input
            autoFocus
            type="text"
            placeholder="곡명 검색..."
            className="flex-1 border border-gray-300 rounded px-3 py-1.5 text-sm outline-none focus:border-blue-400"
            value={q}
            onChange={e => setQ(e.target.value)}
          />
          <button onClick={onClose} title={TIPS.setlist.searchClose} className="text-gray-400 hover:text-gray-600 px-2 text-sm">✕</button>
        </div>
        <div className="overflow-y-auto flex-1">
          {items.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-8">
              {debounced ? '검색 결과 없음' : '최근 추가된 곡이 없습니다'}
            </p>
          )}
          {items.map(item => (
            <button
              key={item.title}
              title={TIPS.setlist.searchItem(item.sequence)}
              className="w-full text-left px-4 py-2.5 hover:bg-blue-50 border-b border-gray-50 last:border-0"
              onClick={() => { onSelect(item); onClose() }}
            >
              <div className="text-sm font-medium text-gray-800">{item.title}</div>
              {item.english_title && (
                <div className="text-xs text-gray-400">{item.english_title}</div>
              )}
              {item.sequence && (
                <div className="text-xs text-gray-400 mt-0.5">{item.sequence}</div>
              )}
            </button>
          ))}
        </div>
        {!debounced && (
          <div className="px-4 py-2 text-xs text-gray-400 border-t">최근 추가순</div>
        )}
      </div>
    </div>
  )
}
