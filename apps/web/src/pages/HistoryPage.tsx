import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  fetchHistory,
  saveHistoryEntry,
  updateHistoryEntry,
  type WeeklyHistoryItem,
  type ManualEntry,
} from '../api/history'
import { useProjectStore } from '../store/projectStore'
import { CalendarView, formatWeekLabel } from '../components/history/CalendarView'
import { TIPS } from '../constants/tooltips'

// ── 날짜 ─────────────────────────────────────────────────────────────────────

function toLocalDateStr(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function thisOrNextSaturday(): string {
  const d = new Date()
  const diff = (6 - d.getDay() + 7) % 7
  d.setDate(d.getDate() + diff)
  return toLocalDateStr(d)
}

// ── 레파토리 파서 ─────────────────────────────────────────────────────────────

function normalizeSeq(seq: string): string {
  const tokens = seq.trim().split(/[-\s]+/).filter(Boolean)
  if (!tokens.length) return ''
  return tokens.map(t => t.charAt(0).toUpperCase() + t.slice(1).toLowerCase()).join('-')
}

function parseRepertoireLine(line: string): { title: string; sequence: string } | null {
  line = line.trim()
  if (!line) return null
  const hasKorean = /[가-힣]/.test(line)
  if (hasKorean) {
    // "{ASCII시퀀스} {한국어제목}" 형식
    const m1 = line.match(/^([A-Za-z][A-Za-z0-9]*(?:[-][A-Za-z][A-Za-z0-9]*)*)\s+(.+)$/)
    if (m1) return { title: m1[2].trim(), sequence: normalizeSeq(m1[1]) }
    // "{한국어제목} {ASCII시퀀스}" 형식
    const m2 = line.match(/^(.+?)\s+([A-Za-z][A-Za-z0-9-\s]*)$/)
    if (m2 && /[가-힣]/.test(m2[1]) && !/[가-힣]/.test(m2[2]))
      return { title: m2[1].trim(), sequence: normalizeSeq(m2[2]) }
    return { title: line, sequence: '' }
  }
  // 영어만 있는 줄: 마지막 단어가 시퀀스처럼 보이면 분리
  const parts = line.split(/\s+/)
  if (parts.length >= 2 && /^[A-Za-z][A-Za-z0-9-]*$/.test(parts[parts.length - 1]))
    return { title: parts.slice(0, -1).join(' '), sequence: normalizeSeq(parts[parts.length - 1]) }
  return { title: line, sequence: '' }
}

// ── 추가/수정 모달 ────────────────────────────────────────────────────────────

interface HistoryEntryModalProps {
  existing?: WeeklyHistoryItem
  onClose: () => void
  onSaved: () => void
}

function HistoryEntryModal({ existing, onClose, onSaved }: HistoryEntryModalProps) {
  const isEdit = !!existing
  const [date, setDate] = useState(() =>
    existing ? existing.week_end_date : thisOrNextSaturday()
  )
  const [entries, setEntries] = useState<ManualEntry[]>(() =>
    existing?.sequence_entries.length
      ? existing.sequence_entries.map(e => ({ title: e.title, sequence: e.sequence }))
      : [{ title: '', sequence: '' }]
  )
  const [password, setPassword] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pasteMode, setPasteMode] = useState(false)
  const [pasteText, setPasteText] = useState('')

  function addRow() { setEntries(p => [...p, { title: '', sequence: '' }]) }
  function removeRow(i: number) { setEntries(p => p.filter((_, idx) => idx !== i)) }
  function updateRow(i: number, field: keyof ManualEntry, val: string) {
    setEntries(p => p.map((e, idx) => idx === i ? { ...e, [field]: val } : e))
  }

  function applyPasteText() {
    const parsed = pasteText
      .split('\n')
      .map(parseRepertoireLine)
      .filter((r): r is { title: string; sequence: string } => r !== null && r.title !== '')
    if (parsed.length) {
      setEntries(parsed)
      setPasteMode(false)
      setPasteText('')
    }
  }

  async function handleSave() {
    const valid = entries.filter(e => e.title.trim())
    if (!valid.length) { setError('곡을 하나 이상 입력하세요.'); return }
    if (isEdit && !password) { setError('비밀번호를 입력하세요.'); return }
    setSaving(true); setError(null)
    try {
      const cleaned = valid.map(e => ({ title: e.title.trim(), sequence: e.sequence.trim() }))
      if (isEdit) {
        await updateHistoryEntry(existing!.week_end_date, { password, sequence_entries: cleaned })
      } else {
        await saveHistoryEntry(date, cleaned)
      }
      onSaved(); onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : '저장 실패')
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-xl w-full max-w-md flex flex-col max-h-[85vh]"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-800">
            {isEdit ? '셋리스트 수정' : '셋리스트 기록 추가'}
          </h2>
          <button onClick={onClose} title="닫기" className="text-gray-300 hover:text-gray-500">✕</button>
        </div>

        <div className="overflow-y-auto flex-1 px-5 py-4 space-y-4">
          {/* 날짜 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">날짜 (주 마지막 날)</label>
            {isEdit ? (
              <p className="text-sm text-gray-700 font-medium">{formatWeekLabel(existing!.week_end_date)}</p>
            ) : (
              <input
                type="date"
                value={date}
                onChange={e => setDate(e.target.value)}
                className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm outline-none focus:border-blue-400"
              />
            )}
          </div>

          {/* 비밀번호 (수정 시에만) */}
          {isEdit && (
            <div>
              <label className="block text-xs text-gray-500 mb-1">비밀번호 *</label>
              <input
                type="password"
                autoFocus
                value={password}
                onChange={e => setPassword(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSave()}
                className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm outline-none focus:border-blue-400"
                placeholder="비밀번호 입력"
              />
            </div>
          )}

          {/* 곡 목록 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs text-gray-500">곡 목록</label>
              <button
                onClick={() => { setPasteMode(v => !v); setPasteText('') }}
                className="text-xs text-blue-400 hover:text-blue-600"
                title={TIPS.history.pasteToggle(pasteMode)}
              >
                {pasteMode ? '← 개별 입력' : '붙여넣기 입력'}
              </button>
            </div>

            {pasteMode ? (
              <div className="space-y-2">
                <textarea
                  autoFocus
                  value={pasteText}
                  onChange={e => setPasteText(e.target.value)}
                  rows={8}
                  placeholder={'한 줄에 한 곡씩 입력\n예) 한나의노래 i-v-c-o\n예) i-v-c-o 한나의노래\n예) 한나의노래 (순서 없이도 가능)'}
                  className="w-full border border-gray-200 rounded px-3 py-2 text-sm outline-none focus:border-blue-400 resize-none font-mono"
                />
                <button
                  onClick={applyPasteText}
                  title={TIPS.history.pasteApply}
                  className="w-full text-sm bg-blue-500 text-white rounded px-3 py-1.5 hover:bg-blue-600"
                >
                  적용
                </button>
              </div>
            ) : (
              <>
                <div className="space-y-2">
                  {entries.map((entry, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <span className="text-xs text-gray-300 w-4 text-right shrink-0">{i + 1}</span>
                      <input
                        type="text" placeholder="곡 제목" value={entry.title}
                        onChange={e => updateRow(i, 'title', e.target.value)}
                        className="flex-1 border border-gray-200 rounded px-2 py-1 text-sm outline-none focus:border-blue-400 min-w-0"
                      />
                      <input
                        type="text" placeholder="순서 (예: i-v-c)" value={entry.sequence}
                        onChange={e => updateRow(i, 'sequence', e.target.value)}
                        onBlur={e => updateRow(i, 'sequence', normalizeSeq(e.target.value))}
                        className="w-24 border border-gray-200 rounded px-2 py-1 text-xs outline-none focus:border-blue-400 shrink-0"
                      />
                      <button onClick={() => removeRow(i)} title={TIPS.history.rowRemove} className="text-gray-300 hover:text-red-400 shrink-0">✕</button>
                    </div>
                  ))}
                </div>
                <button onClick={addRow} title={TIPS.history.rowAdd} className="mt-2 text-xs text-blue-500 hover:text-blue-700">+ 곡 추가</button>
              </>
            )}
          </div>
          {error && <p className="text-xs text-red-500">{error}</p>}
        </div>

        <div className="px-5 pb-5 pt-3 border-t border-gray-100 flex gap-2 justify-end">
          <button onClick={onClose} title={TIPS.history.modalCancel} className="text-sm border border-gray-300 rounded px-3 py-1.5 hover:bg-gray-50">취소</button>
          <button
            onClick={handleSave} disabled={saving}
            title={TIPS.history.modalSave(isEdit)}
            className="text-sm bg-blue-500 text-white rounded px-3 py-1.5 hover:bg-blue-600 disabled:bg-gray-200 disabled:text-gray-400"
          >
            {saving ? '저장 중...' : (isEdit ? '수정 저장' : '저장')}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── 목록 뷰 카드 ─────────────────────────────────────────────────────────────

function WeekCard({
  item, onLoad, onEdit,
}: {
  item: WeeklyHistoryItem
  onLoad: () => void
  onEdit: () => void
}) {
  const hasRoles = item.worship_leader || item.accompanist || item.prayer_person

  return (
    <div className="border border-gray-200 rounded-lg bg-white overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-100">
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-sm font-semibold text-gray-700 shrink-0">
            {formatWeekLabel(item.week_end_date)}
          </span>
          <span className="text-xs text-gray-400 shrink-0">{item.sequence_entries.length}곡</span>
        </div>
        <div className="flex items-center gap-2 shrink-0 ml-2">
          <button
            onClick={onEdit}
            title={TIPS.history.weekEdit}
            className="text-xs text-gray-400 hover:text-gray-700 border border-gray-200 rounded px-2 py-0.5"
          >
            수정
          </button>
          <button
            onClick={onLoad}
            title={TIPS.history.weekLoad}
            className="text-xs font-medium text-blue-500 hover:text-blue-700 transition-colors"
          >
            불러오기
          </button>
        </div>
      </div>

      {hasRoles && (
        <div className="px-4 py-2 bg-indigo-50/50 border-b border-indigo-100 grid grid-cols-3 gap-2 text-xs">
          {[
            { label: '인도자', val: item.worship_leader, bold: true },
            { label: '반주자', val: item.accompanist,   bold: false },
            { label: '기도자', val: item.prayer_person,  bold: false },
          ].map(({ label, val, bold }) => val ? (
            <div key={label}>
              <p className="text-[10px] text-gray-400">{label}</p>
              <p className={`${bold ? 'font-bold' : 'font-medium'} text-gray-800 truncate`}>{val}</p>
            </div>
          ) : null)}
        </div>
      )}

      <ol className="divide-y divide-gray-50">
        {item.sequence_entries.map((e, i) => (
          <li key={i} className="flex items-baseline gap-3 px-4 py-2">
            <span className="text-xs text-gray-300 w-4 text-right shrink-0">{i + 1}</span>
            <span className="text-sm text-gray-800">{e.title}</span>
            <span className="text-xs text-gray-400 ml-auto shrink-0">{e.sequence}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}

// ── 페이지 ───────────────────────────────────────────────────────────────────

type ViewMode = 'calendar' | 'list'

export function HistoryPage() {
  const navigate = useNavigate()
  const { loadSongs } = useProjectStore()
  const queryClient = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [editingItem, setEditingItem] = useState<WeeklyHistoryItem | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('calendar')
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc')

  const { data = [], isLoading, isError } = useQuery({
    queryKey: ['history'],
    queryFn: () => fetchHistory(2020),
    staleTime: 60_000,
  })

  function handleLoad(item: WeeklyHistoryItem) {
    loadSongs(
      item.sequence_entries.map((e, i) => ({
        id: `hist_${item.week_end_date}_${i}`,
        title: e.title,
        sequence: e.sequence,
        lyrics: item.lyrics_by_title[e.title] ?? '',
      }))
    )
    navigate('/app')
  }

  function handleSaved() {
    queryClient.invalidateQueries({ queryKey: ['history'] })
  }

  return (
    <div className="flex flex-col h-full">
      {/* 상단 헤더 */}
      <div className="px-4 sm:px-6 pt-4 pb-3 border-b border-gray-100 flex items-center gap-3 shrink-0">
        <div className="flex-1 min-w-0">
          <h1 className="text-base font-semibold text-gray-800">주간 이력</h1>
        </div>

        <button
          onClick={() => setShowAdd(true)}
          title={TIPS.history.add}
          className="shrink-0 text-xs font-medium text-blue-500 border border-blue-200 rounded px-3 py-1.5 hover:bg-blue-50 transition-colors"
        >
          + 추가
        </button>

        {viewMode === 'list' && (
          <button
            onClick={() => setSortOrder(o => o === 'desc' ? 'asc' : 'desc')}
            title={sortOrder === 'desc' ? TIPS.history.sortDesc : TIPS.history.sortAsc}
            className="shrink-0 w-24 text-xs text-gray-500 border border-gray-200 rounded px-2.5 py-1.5 hover:bg-gray-50 transition-colors text-center"
          >
            {sortOrder === 'desc' ? '최신순 ↓' : '오래된 순 ↑'}
          </button>
        )}

        <div className="flex rounded overflow-hidden border border-gray-200 shrink-0">
          {(['calendar', 'list'] as ViewMode[]).map(v => (
            <button
              key={v}
              onClick={() => setViewMode(v)}
              title={v === 'calendar' ? TIPS.history.viewCalendar : TIPS.history.viewList}
              className={`px-3 py-1.5 text-xs font-medium transition-colors
                ${viewMode === v ? 'bg-blue-500 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'}`}
            >
              {v === 'calendar' ? '달력' : '목록'}
            </button>
          ))}
        </div>
      </div>

      {isLoading && (
        <div className="flex-1 flex items-center justify-center text-sm text-gray-400">불러오는 중...</div>
      )}
      {isError && (
        <div className="m-4 text-sm text-red-500 bg-red-50 rounded p-4">
          이력을 불러올 수 없습니다. 서버 연결을 확인하세요.
        </div>
      )}

      {!isLoading && !isError && viewMode === 'calendar' && (
        <CalendarView
          history={data}
          onLoad={handleLoad}
          onEditEntries={setEditingItem}
        />
      )}

      {!isLoading && !isError && viewMode === 'list' && (
        <div className="flex-1 overflow-y-auto p-4 sm:p-6">
          {data.length === 0 ? (
            <div className="flex items-center justify-center py-20 text-sm text-gray-400">
              저장된 이력이 없습니다.
            </div>
          ) : (
            <div className="max-w-2xl mx-auto flex flex-col gap-3">
              {[...data]
                .sort((a, b) =>
                  sortOrder === 'desc'
                    ? b.week_end_date.localeCompare(a.week_end_date)
                    : a.week_end_date.localeCompare(b.week_end_date)
                )
                .map(item => (
                  <WeekCard
                    key={item.week_end_date}
                    item={item}
                    onLoad={() => handleLoad(item)}
                    onEdit={() => setEditingItem(item)}
                  />
                ))}
            </div>
          )}
        </div>
      )}

      {showAdd && (
        <HistoryEntryModal
          onClose={() => setShowAdd(false)}
          onSaved={handleSaved}
        />
      )}

      {editingItem && (
        <HistoryEntryModal
          existing={editingItem}
          onClose={() => setEditingItem(null)}
          onSaved={handleSaved}
        />
      )}
    </div>
  )
}
