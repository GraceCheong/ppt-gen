import { useEffect, useMemo, useRef, useState } from 'react'
import { useProjectStore } from '../../store/projectStore'
import { SequenceInput } from './SequenceInput'
import { downloadLyrics } from '../../api/lyrics'
import {
  DEFAULT_NO_LYRICS_PARTS,
  getUniqueParts,
  isPartNoLyrics,
  getLyricsSectionStatus,
} from '../../types/project'
import { TIPS } from '../../constants/tooltips'

export function LyricsEditorPanel() {
  const { songs, selectedSongId, updateSong } = useProjectStore()
  const song = songs.find(s => s.id === selectedSongId)

  const [localLyrics, setLocalLyrics] = useState(song?.lyrics ?? '')
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    setLocalLyrics(song?.lyrics ?? '')
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current) }
  }, [song?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const [downloading, setDownloading] = useState(false)
  const [downloadMsg, setDownloadMsg] = useState<string | null>(null)

  if (!song) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400 text-sm">
        왼쪽에서 곡을 선택해 주세요
      </div>
    )
  }

  const songId = song.id

  function handleLyricsChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const val = e.target.value
    setLocalLyrics(val)
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => updateSong(songId, { lyrics: val }), 400)
  }

  function handleLyricsBlur(e: React.FocusEvent<HTMLTextAreaElement>) {
    if (saveTimer.current) clearTimeout(saveTimer.current)
    updateSong(songId, { lyrics: e.target.value })
  }

  async function handleDownload() {
    setDownloading(true)
    setDownloadMsg(null)
    try {
      const result = await downloadLyrics(song?.title ?? '', song?.sequence)
      if (result.found) {
        setLocalLyrics(result.lyrics)
        updateSong(songId, { lyrics: result.lyrics })
        setDownloadMsg('가사를 가져왔습니다.')
      } else {
        setDownloadMsg('가사를 찾지 못했습니다.')
      }
    } catch {
      setDownloadMsg('다운로드 중 오류가 발생했습니다.')
    } finally {
      setDownloading(false)
      setTimeout(() => setDownloadMsg(null), 3000)
    }
  }

  return (
    <div className="flex flex-col h-full p-3 gap-2">
      {/* 곡 제목 */}
      <div>
        <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-1">
          곡 제목
        </label>
        <input
          type="text"
          className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm outline-none focus:border-blue-400"
          value={song.title}
          onChange={e => updateSong(songId, { title: e.target.value })}
          placeholder="곡 제목"
          title={TIPS.editor.title}
        />
      </div>

      {/* 진행 순서 */}
      <div>
        <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-1">
          진행 순서
        </label>
        <SequenceInput
          value={song.sequence}
          onChange={seq => updateSong(songId, { sequence: seq })}
        />
        <PartButtons song={song} updateSong={updateSong} lyrics={localLyrics} />
      </div>

      {/* 가사 */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="flex items-center justify-between mb-1">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">가사</label>
          <div className="flex items-center gap-2">
            {downloadMsg && <span className="text-xs text-gray-500">{downloadMsg}</span>}
            <button
              onClick={handleDownload}
              disabled={downloading || !song.title}
              title={TIPS.editor.lyricsDownload}
              className="text-xs text-blue-500 hover:text-blue-700 disabled:text-gray-300 transition-colors"
            >
              {downloading ? '받는 중...' : 'Bugs에서 가져오기'}
            </button>
          </div>
        </div>
        <textarea
          className="flex-1 border border-gray-300 rounded px-3 py-2 text-sm font-mono resize-none outline-none focus:border-blue-400 min-h-0"
          value={localLyrics}
          onChange={handleLyricsChange}
          onBlur={handleLyricsBlur}
          placeholder={`I\n인트로 가사\n\nV1\n1절 가사\n\nC\n코러스 가사`}
          spellCheck={false}
          title={TIPS.editor.lyricsTextarea}
        />
      </div>
    </div>
  )
}

// ── 파트 토글 버튼 ────────────────────────────────────────────────────────────

import type { SongEntry } from '../../types/project'

interface PartButtonsProps {
  song: SongEntry
  lyrics: string
  updateSong: (id: string, patch: Partial<Omit<SongEntry, 'id'>>) => void
}

function PartButtons({ song, lyrics, updateSong }: PartButtonsProps) {
  const uniqueParts = useMemo(() => getUniqueParts(song.sequence), [song.sequence])

  if (uniqueParts.length === 0) return null

  function toggleNoLyrics(part: string) {
    const current = song.noLyricsParts ?? uniqueParts.filter(p => DEFAULT_NO_LYRICS_PARTS.has(p))
    const next = current.includes(part)
      ? current.filter(p => p !== part)
      : [...current, part]
    updateSong(song.id, { noLyricsParts: next })
  }

  return (
    <div className="mt-2">
      <div className="flex items-center gap-1.5 mb-1.5">
        <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">파트 구성</span>
        <span className="text-[10px] text-gray-300">· 클릭으로 가사 불필요 파트 표시</span>
      </div>
      <div className="flex gap-1.5 flex-wrap">
        {uniqueParts.map(part => {
          const noLyrics = isPartNoLyrics(song, part)
          const status = noLyrics ? null : getLyricsSectionStatus(lyrics, part, uniqueParts)

          return (
            <button
              key={part}
              type="button"
              onClick={() => toggleNoLyrics(part)}
              title={
                noLyrics            ? TIPS.editor.partNoLyrics(part)
                : status === 'has-content' ? TIPS.editor.partHasLyrics(part)
                : status === 'empty'       ? TIPS.editor.partEmpty(part)
                :                            TIPS.editor.partMissing(part)
              }
              className={`text-xs rounded px-2.5 py-0.5 transition-colors select-none font-mono border
                ${noLyrics
                  ? 'text-gray-300 bg-gray-50 border-gray-200'
                  : status === 'has-content'
                  ? 'text-green-600 bg-green-50 border-green-200'
                  : status === 'empty'
                  ? 'text-amber-500 bg-amber-50 border-amber-300'
                  : 'text-orange-500 bg-orange-50 border-orange-200'
                }`}
            >
              {noLyrics ? <span className="line-through">{part}</span> : part}
            </button>
          )
        })}
      </div>
    </div>
  )
}
