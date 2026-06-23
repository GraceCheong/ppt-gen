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
import { Download, FileText } from 'lucide-react'

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
      <div className="flex flex-col items-center justify-center h-full text-center p-8 gap-3 select-none">
        <div className="w-12 h-12 rounded-full bg-neutral-50 border border-neutral-100 flex items-center justify-center">
          <FileText className="w-6 h-6 text-neutral-300" />
        </div>
        <div>
          <p className="text-xs font-semibold text-neutral-700">선택된 찬양이 없습니다</p>
          <p className="text-[10px] text-neutral-400 mt-1">왼쪽 목록에서 가사나 순서를 편집할 찬양을 선택하세요.</p>
        </div>
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
        setDownloadMsg('가사를 성공적으로 가져왔습니다.')
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
    <div className="flex flex-col h-full p-4 gap-4 bg-white select-none">
      {/* 곡 제목 */}
      <div className="flex flex-col gap-1.5">
        <label className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider block">
          곡 제목
        </label>
        <input
          type="text"
          className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-xs font-semibold outline-none bg-neutral-50/50 hover:bg-neutral-50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all placeholder:text-neutral-400 text-neutral-800"
          value={song.title}
          onChange={e => updateSong(songId, { title: e.target.value })}
          placeholder="곡 제목 입력"
          title={TIPS.editor.title}
        />
      </div>

      {/* 진행 순서 */}
      <div className="flex flex-col gap-1.5">
        <label className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider block">
          진행 순서
        </label>
        <SequenceInput
          value={song.sequence}
          onChange={seq => updateSong(songId, { sequence: seq })}
        />
        <PartButtons song={song} updateSong={updateSong} lyrics={localLyrics} />
      </div>

      {/* 가사 */}
      <div className="flex-1 flex flex-col min-h-0 gap-1.5">
        <div className="flex items-center justify-between">
          <label className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider">가사 내용 입력</label>
          <div className="flex items-center gap-2">
            {downloadMsg && <span className="text-[10px] font-medium text-neutral-500">{downloadMsg}</span>}
            <button
              onClick={handleDownload}
              disabled={downloading || !song.title}
              title={TIPS.editor.lyricsDownload}
              className="text-[11px] font-bold text-primary-500 hover:text-primary-600 disabled:text-neutral-300 transition-colors flex items-center gap-1 cursor-pointer"
            >
              <Download className="w-3 h-3" />
              <span>{downloading ? '가사 검색 중...' : 'Bugs 음원 가사 자동 매칭'}</span>
            </button>
          </div>
        </div>
        <textarea
          className="flex-1 border border-neutral-200 rounded-xl px-4 py-3.5 text-xs font-mono resize-none outline-none bg-neutral-50/30 hover:bg-neutral-50/50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all min-h-0 leading-relaxed text-neutral-700"
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
    <div className="mt-2.5">
      <div className="flex items-center gap-1.5 mb-2 select-none">
        <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider">파트별 가사 상태</span>
        <span className="text-[9px] text-neutral-300">· 클릭하여 가사 생략 설정</span>
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
              className={`text-[10px] font-bold rounded-lg px-2.5 py-1.5 transition-all select-none font-mono border cursor-pointer
                ${noLyrics
                  ? 'text-neutral-400 bg-neutral-50 border-neutral-200/50 hover:bg-neutral-100 hover:border-neutral-300'
                  : status === 'has-content'
                  ? 'text-success-600 bg-success-50 border-success-100 hover:bg-success-100/50'
                  : status === 'empty'
                  ? 'text-warning-600 bg-warning-50 border-warning-200 hover:bg-warning-100/50'
                  : 'text-danger-600 bg-danger-50 border-danger-100 hover:bg-danger-100/50'
                }`}
            >
              {noLyrics ? <span className="line-through text-neutral-300">{part}</span> : part}
            </button>
          )
        })}
      </div>
    </div>
  )
}

