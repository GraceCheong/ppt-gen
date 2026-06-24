import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  deleteHistoryEntry,
  fetchHistory,
  saveHistoryEntry,
  updateHistoryEntry,
  type WeeklyHistoryItem,
  type ManualEntry,
} from '../api/history'
import { useProjectStore } from '../store/projectStore'
import { useAuthStore } from '../store/authStore'
import { CalendarView, formatWeekLabel } from '../components/history/CalendarView'
import { TIPS } from '../constants/tooltips'
import { Plus, X, List, Calendar as CalendarIcon, ArrowLeftRight, AlertCircle, Loader2 } from 'lucide-react'

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
    const m1 = line.match(/^([A-Za-z][A-Za-z0-9]*(?:[-][A-Za-z][A-Za-z0-9]*)*)\s+(.+)$/)
    if (m1) return { title: m1[2].trim(), sequence: normalizeSeq(m1[1]) }
    const m2 = line.match(/^(.+?)\s+([A-Za-z][A-Za-z0-9-\s]*)$/)
    if (m2 && /[가-힣]/.test(m2[1]) && !/[가-힣]/.test(m2[2]))
      return { title: m2[1].trim(), sequence: normalizeSeq(m2[2]) }
    return { title: line, sequence: '' }
  }
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
    setSaving(true); setError(null)
    try {
      const cleaned = valid.map(e => ({ title: e.title.trim(), sequence: e.sequence.trim() }))
      if (isEdit) {
        await updateHistoryEntry(existing!.week_end_date, { sequence_entries: cleaned })
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/40 backdrop-blur-xs px-4" onClick={onClose}>
      <div
        className="bg-white border border-neutral-200/80 rounded-2xl shadow-2xl w-full max-w-md flex flex-col max-h-[85vh] overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 pt-5 pb-3 border-b border-neutral-100 bg-neutral-50/20">
          <h2 className="text-sm font-bold text-neutral-900">
            {isEdit ? '예배 셋리스트 수정' : '셋리스트 기록 추가'}
          </h2>
          <button 
            onClick={onClose} 
            title="닫기" 
            className="text-neutral-400 hover:text-neutral-600 hover:bg-neutral-100 rounded-lg p-1.5 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="overflow-y-auto flex-1 px-6 py-4 space-y-4">
          {/* 날짜 */}
          <div className="flex flex-col gap-1.5">
            <label className="block text-[11px] font-bold text-neutral-500">예배 날짜 (주 토요일 기준)</label>
            {isEdit ? (
              <p className="text-xs font-bold text-neutral-800 bg-neutral-50 border border-neutral-200/50 rounded-lg px-3 py-2">{formatWeekLabel(existing!.week_end_date)}</p>
            ) : (
              <input
                type="date"
                value={date}
                onChange={e => setDate(e.target.value)}
                className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-xs font-semibold outline-none bg-neutral-50/50 hover:bg-neutral-50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all text-neutral-800"
              />
            )}
          </div>

          {/* 곡 목록 */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <label className="text-[11px] font-bold text-neutral-500">예배 곡 목록</label>
              <button
                onClick={() => { setPasteMode(v => !v); setPasteText('') }}
                className="text-[11px] font-bold text-primary-500 hover:text-primary-600 flex items-center gap-1 cursor-pointer"
                title={TIPS.history.pasteToggle(pasteMode)}
              >
                <ArrowLeftRight className="w-3 h-3" />
                <span>{pasteMode ? '개별 목록 편집' : '텍스트 일괄 붙여넣기'}</span>
              </button>
            </div>

            {pasteMode ? (
              <div className="space-y-2">
                <textarea
                  autoFocus
                  value={pasteText}
                  onChange={e => setPasteText(e.target.value)}
                  rows={8}
                  placeholder={'한 줄에 한 곡씩 입력하세요.\n예) 한나의노래 i-v-c-o\n예) i-v-c-o 한나의노래\n예) 한나의노래 (순서가 없는 경우도 가능)'}
                  className="w-full border border-neutral-200 rounded-xl px-4 py-3 text-xs outline-none bg-neutral-50/50 hover:bg-neutral-50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all resize-none font-mono leading-relaxed text-neutral-700"
                />
                <button
                  onClick={applyPasteText}
                  title={TIPS.history.pasteApply}
                  className="w-full text-xs font-semibold bg-neutral-800 hover:bg-neutral-900 text-white rounded-lg py-2 shadow-sm transition-all cursor-pointer"
                >
                  텍스트 분석하여 적용
                </button>
              </div>
            ) : (
              <div className="space-y-2.5">
                <div className="space-y-2">
                  {entries.map((entry, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <span className="text-[10px] font-bold bg-neutral-100 text-neutral-500 w-5 h-5 flex items-center justify-center rounded-full shrink-0 select-none">{i + 1}</span>
                      <input
                        type="text" placeholder="곡 제목" value={entry.title}
                        onChange={e => updateRow(i, 'title', e.target.value)}
                        className="flex-1 border border-neutral-200 rounded-lg px-2.5 py-1.5 text-xs outline-none bg-neutral-50/50 hover:bg-neutral-50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all text-neutral-800"
                      />
                      <input
                        type="text" placeholder="순서 (i-v-c)" value={entry.sequence}
                        onChange={e => updateRow(i, 'sequence', e.target.value)}
                        onBlur={e => updateRow(i, 'sequence', normalizeSeq(e.target.value))}
                        className="w-24 border border-neutral-200 rounded-lg px-2.5 py-1.5 text-xs outline-none bg-neutral-50/50 hover:bg-neutral-50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all font-mono uppercase text-neutral-700 text-center"
                      />
                      <button 
                        onClick={() => removeRow(i)} 
                        title={TIPS.history.rowRemove} 
                        className="text-neutral-400 hover:text-danger-500 p-1 rounded hover:bg-neutral-100 shrink-0 cursor-pointer transition-colors"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
                <button 
                  onClick={addRow} 
                  title={TIPS.history.rowAdd} 
                  className="text-xs font-semibold text-primary-500 hover:text-primary-600 flex items-center gap-1 cursor-pointer select-none py-1"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>새 곡 행 추가</span>
                </button>
              </div>
            )}
          </div>
          {error && <p className="text-xs text-danger-500 font-medium">{error}</p>}
        </div>

        <div className="px-6 pb-5 pt-3 border-t border-neutral-100 flex gap-2 justify-end">
          <button onClick={onClose} title={TIPS.history.modalCancel} className="text-xs font-semibold border border-neutral-200 text-neutral-700 rounded-xl px-4 py-2.5 hover:bg-neutral-50 cursor-pointer">취소</button>
          <button
            onClick={handleSave} disabled={saving}
            title={TIPS.history.modalSave(isEdit)}
            className="text-xs font-bold bg-primary-600 text-white rounded-xl px-4 py-2.5 hover:bg-primary-700 active:bg-primary-800 transition-all cursor-pointer"
          >
            {saving ? '저장 중...' : (isEdit ? '수정 사항 저장' : '기록 저장')}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── 목록 뷰 카드 ─────────────────────────────────────────────────────────────

function WeekCard({
  item, onLoad, onEdit, onDelete,
}: {
  item: WeeklyHistoryItem
  onLoad: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  const hasRoles = item.worship_leader || item.accompanist || item.prayer_person || item.event

  return (
    <div className="border border-neutral-200/80 rounded-2xl bg-white overflow-hidden shadow-sm hover:shadow-md transition-all duration-200">
      <div className="flex items-center justify-between px-5 py-4 bg-neutral-50/30 border-b border-neutral-100">
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-xs font-bold text-neutral-800 shrink-0">
            {formatWeekLabel(item.week_end_date)}
          </span>
          <span className="text-[10px] font-bold text-neutral-400 bg-neutral-100 rounded-full px-2.5 py-0.5 shrink-0 border border-neutral-200/40">{item.sequence_entries.length}곡 구성</span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0 ml-2">
          <button
            onClick={onDelete}
            title="이 주차 이력 삭제"
            className="text-[11px] font-semibold text-neutral-400 hover:text-danger-600 border border-neutral-200 hover:border-danger-200 rounded-lg px-2.5 py-1 bg-white hover:bg-danger-50 transition-all cursor-pointer shadow-sm"
          >
            삭제
          </button>
          <button
            onClick={onEdit}
            title={TIPS.history.weekEdit}
            className="text-[11px] font-semibold text-neutral-600 hover:text-neutral-800 border border-neutral-200 hover:border-neutral-300 rounded-lg px-2.5 py-1 bg-white hover:bg-neutral-50 transition-all cursor-pointer shadow-sm"
          >
            수정
          </button>
          <button
            onClick={onLoad}
            title={TIPS.history.weekLoad}
            className="text-[11px] font-bold text-primary-500 hover:text-primary-600 border border-primary-200/50 hover:bg-primary-50/30 rounded-lg px-2.5 py-1 bg-white transition-all cursor-pointer shadow-sm"
          >
            불러오기
          </button>
        </div>
      </div>

      {hasRoles && (
        <div className="px-5 py-3 bg-primary-50/20 border-b border-neutral-100/50 flex flex-col gap-2 text-xs select-none">
          {item.event && (
            <div className="flex items-center gap-1.5">
              <span className="text-[9px] font-bold text-amber-500 uppercase shrink-0">이벤트</span>
              <span className="text-xs font-bold text-amber-700 truncate">{item.event}</span>
            </div>
          )}
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: '인도자', val: item.worship_leader, bold: true },
              { label: '반주자', val: item.accompanist,   bold: false },
              { label: '기도자', val: item.prayer_person,  bold: false },
            ].map(({ label, val, bold }) => val ? (
              <div key={label} className="min-w-0">
                <p className="text-[9px] text-neutral-400 font-bold uppercase">{label}</p>
                <p className={`text-xs ${bold ? 'font-bold text-primary-700' : 'font-semibold text-neutral-700'} truncate mt-0.5`}>{val}</p>
              </div>
            ) : null)}
          </div>
        </div>
      )}

      <ol className="divide-y divide-neutral-100/50">
        {item.sequence_entries.map((e, i) => (
          <li key={i} className="flex items-center gap-3.5 px-5 py-3 hover:bg-neutral-50/20 transition-all">
            <span className="text-[10px] font-bold bg-neutral-100 text-neutral-500 w-5 h-5 flex items-center justify-center rounded-full shrink-0 select-none">{i + 1}</span>
            <span className="text-xs font-semibold text-neutral-800 flex-1 truncate">{e.title}</span>
            {e.sequence && (
              <span className="text-[9px] font-bold font-mono bg-neutral-100 border border-neutral-200/50 rounded px-1.5 py-0.5 text-neutral-400 shrink-0 select-none uppercase">{e.sequence}</span>
            )}
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
  const { mode: authMode } = useAuthStore()
  const queryClient = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [editingItem, setEditingItem] = useState<WeeklyHistoryItem | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('calendar')
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc')

  const { data = [], isLoading, isError } = useQuery({
    queryKey: ['history'],
    queryFn: () => fetchHistory(2020),
    staleTime: 60_000,
    enabled: authMode === 'user',
  })

  // Guest 차단 화면
  if (authMode !== 'user') {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-center px-6 py-20 bg-white select-none">
        <div className="w-12 h-12 rounded-full bg-neutral-50 border border-neutral-100 flex items-center justify-center">
          <AlertCircle className="w-6 h-6 text-neutral-300 animate-pulse" />
        </div>
        <div>
          <p className="text-xs font-semibold text-neutral-700">로그인이 필요한 기능입니다</p>
          <p className="text-[10px] text-neutral-400 mt-1">예배 이력 확인 및 캘린더 기능은 로그인 후에 제공됩니다.</p>
        </div>
        <button
          onClick={() => navigate('/app')}
          className="text-xs font-bold text-primary-500 hover:text-primary-600 border border-primary-200/50 hover:bg-primary-50/30 rounded-xl px-4 py-2 cursor-pointer transition-all mt-2"
        >
          작업 화면으로 돌아가기
        </button>
      </div>
    )
  }

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
    queryClient.invalidateQueries({ queryKey: ['graph'] })
  }

  async function handleDelete(item: WeeklyHistoryItem) {
    if (!window.confirm(`${formatWeekLabel(item.week_end_date)} 이력을 삭제할까요?`)) return
    try {
      await deleteHistoryEntry(item.week_end_date)
      handleSaved()
    } catch (e) {
      alert(e instanceof Error ? e.message : '삭제 실패')
    }
  }

  return (
    <div className="flex flex-col h-full bg-white select-none">
      {/* 상단 헤더 */}
      <div className="px-6 py-3 border-b border-neutral-200 flex items-center gap-3 shrink-0 justify-between bg-neutral-50/20">
        <div>
          <h1 className="text-sm font-bold text-neutral-800">예배 주간 이력</h1>
          <p className="text-[10px] text-neutral-400 mt-0.5">지난 예배에서 불렀던 곡 목록과 담당 예배 팀원 구성 이력을 조회합니다.</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAdd(true)}
            title={TIPS.history.add}
            className="shrink-0 text-xs font-bold bg-primary-600 text-white hover:bg-primary-700 rounded-xl px-4 py-2 cursor-pointer shadow-sm shadow-primary-600/5 hover:shadow-md hover:shadow-primary-600/10 transition-all flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">이력 추가</span>
          </button>

          {viewMode === 'list' && (
            <button
              onClick={() => setSortOrder(o => o === 'desc' ? 'asc' : 'desc')}
              title={sortOrder === 'desc' ? TIPS.history.sortDesc : TIPS.history.sortAsc}
              className="shrink-0 text-xs font-semibold text-neutral-700 border border-neutral-200 hover:border-neutral-300 rounded-xl px-3 py-2 hover:bg-neutral-50 transition-colors text-center cursor-pointer bg-white"
            >
              <span className="hidden sm:inline">{sortOrder === 'desc' ? '최신 순 ↓' : '과거 순 ↑'}</span>
              <span className="sm:hidden">{sortOrder === 'desc' ? '↓' : '↑'}</span>
            </button>
          )}

          <div className="flex rounded-xl overflow-hidden border border-neutral-200 shrink-0 p-0.5 gap-0.5 bg-white">
            {(['calendar', 'list'] as ViewMode[]).map(v => (
              <button
                key={v}
                onClick={() => setViewMode(v)}
                title={v === 'calendar' ? TIPS.history.viewCalendar : TIPS.history.viewList}
                className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer flex items-center gap-1
                  ${viewMode === v ? 'bg-neutral-900 text-white' : 'bg-transparent text-neutral-500 hover:text-neutral-800'}`}
              >
                {v === 'calendar' ? <CalendarIcon className="w-3 h-3" /> : <List className="w-3 h-3" />}
                <span className="hidden sm:inline">{v === 'calendar' ? '달력' : '목록'}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {isLoading && (
        <div className="flex-1 flex flex-col items-center justify-center text-xs text-neutral-400 gap-2">
          <Loader2 className="w-5 h-5 text-primary-500 animate-spin" />
          <span>불러오는 중...</span>
        </div>
      )}
      {isError && (
        <div className="m-5 text-xs text-danger-700 bg-danger-50 border border-danger-100 rounded-xl p-4 flex items-start gap-2.5 font-medium leading-normal">
          <AlertCircle className="w-4 h-4 text-danger-500 shrink-0 mt-0.5" />
          <span>이력을 불러오지 못했습니다. 서버 상태나 인터넷 연결을 확인해 주세요.</span>
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
        <div className="flex-1 overflow-y-auto p-5 bg-neutral-50/20">
          {data.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 px-4 text-center gap-2">
              <CalendarIcon className="w-6 h-6 text-neutral-300" />
              <p className="text-xs text-neutral-400 font-semibold">
                저장된 예배 이력이 없습니다.
              </p>
            </div>
          ) : (
            <div className="max-w-2xl mx-auto flex flex-col gap-4">
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
                    onDelete={() => handleDelete(item)}
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

