import { useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { updateHistoryRoles, type WeeklyHistoryItem } from '../../api/history'
import { TIPS } from '../../constants/tooltips'
import { ChevronLeft, ChevronRight, X, User, Music, BookOpen, Edit, Plus, FolderOpen, AlertCircle } from 'lucide-react'

// ── 날짜 유틸 ─────────────────────────────────────────────────────────────────

function toDateStr(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function todayStr(): string {
  return toDateStr(new Date())
}

export function isoWeekNum(dateStr: string): number {
  const [y, m, d] = dateStr.split('-').map(Number)
  const date = new Date(y, m - 1, d)
  const dayNum = date.getDay() === 0 ? 7 : date.getDay()
  date.setDate(date.getDate() + 4 - dayNum)
  const yearStart = new Date(date.getFullYear(), 0, 1)
  return Math.ceil(((date.getTime() - yearStart.getTime()) / 86400000 + 1) / 7)
}

export function formatWeekLabel(weekEndDate: string): string {
  const week = isoWeekNum(weekEndDate)
  const [y, m, d] = weekEndDate.split('-')
  return `${week}주차 (${y.slice(2)}.${m}.${d})`
}

// 이번 달 가장 가까운 토요일 (오늘 포함)
function defaultSaturday(year: number, month: number): string | null {
  const today = new Date()
  // 이번 달 토요일 목록
  const sats: string[] = []
  const last = new Date(year, month + 1, 0).getDate()
  for (let d = 1; d <= last; d++) {
    const dt = new Date(year, month, d)
    if (dt.getDay() === 6) sats.push(toDateStr(dt))
  }
  if (!sats.length) return null
  // 오늘 이후 가장 가까운 토요일 우선
  const todayTs = today.getTime()
  const upcoming = sats.find(s => new Date(s + 'T00:00:00').getTime() >= todayTs)
  if (upcoming) return upcoming
  // 없으면 마지막 토요일
  return sats[sats.length - 1]
}

// ── 담당자 수정 모달 ──────────────────────────────────────────────────────────

function RolesEditModal({
  weekEndDate, existing, onClose, onSaved,
}: {
  weekEndDate: string
  existing: WeeklyHistoryItem | null
  onClose: () => void
  onSaved: () => void
}) {
  const [worshipLeader, setWorshipLeader] = useState(existing?.worship_leader ?? '')
  const [accompanist, setAccompanist] = useState(existing?.accompanist ?? '')
  const [prayerPerson, setPrayerPerson] = useState(existing?.prayer_person ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSave() {
    setSaving(true); setError(null)
    try {
      await updateHistoryRoles(weekEndDate, { worship_leader: worshipLeader, accompanist, prayer_person: prayerPerson })
      onSaved(); onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : '저장 실패')
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/40 backdrop-blur-xs px-4" onClick={onClose}>
      <div className="bg-white border border-neutral-200/80 rounded-2xl shadow-2xl w-full max-w-sm" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 pt-5 pb-3 border-b border-neutral-100">
          <div>
            <h2 className="text-sm font-bold text-neutral-900 font-sans">담당 예배 팀원 구성</h2>
            <p className="text-[11px] text-neutral-400 mt-0.5">{formatWeekLabel(weekEndDate)}</p>
          </div>
          <button 
            onClick={onClose} 
            title={TIPS.calendar.rolesClose} 
            className="text-neutral-400 hover:text-neutral-600 hover:bg-neutral-50 rounded-lg p-1.5 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="px-6 py-4 space-y-4">
          {[
            { label: '찬양 인도자 (Leader)', val: worshipLeader, set: setWorshipLeader, icon: <User className="w-3.5 h-3.5 text-neutral-400" /> },
            { label: '메인 반주자 (Keyboard)', val: accompanist, set: setAccompanist, icon: <Music className="w-3.5 h-3.5 text-neutral-400" /> },
            { label: '예배 대표 기도자 (Prayer)', val: prayerPerson, set: setPrayerPerson, icon: <BookOpen className="w-3.5 h-3.5 text-neutral-400" /> },
          ].map(({ label, val, set, icon }) => (
            <div key={label} className="flex flex-col gap-1.5">
              <label className="text-[11px] font-bold text-neutral-500 flex items-center gap-1.5">
                {icon}
                <span>{label}</span>
              </label>
              <input type="text" value={val} onChange={e => set(e.target.value)}
                className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-xs outline-none bg-neutral-50/50 hover:bg-neutral-50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all placeholder:text-neutral-400 text-neutral-800"
                placeholder="담당자 이름 입력" />
            </div>
          ))}
          {error && <p className="text-xs text-danger-500 font-medium">{error}</p>}
        </div>
        <div className="px-6 pb-5 pt-3 border-t border-neutral-100 flex gap-2 justify-end">
          <button onClick={onClose} title={TIPS.calendar.rolesCancel} className="text-xs font-semibold border border-neutral-200 text-neutral-700 rounded-xl px-4 py-2.5 hover:bg-neutral-50 cursor-pointer">취소</button>
          <button onClick={handleSave} disabled={saving} title={TIPS.calendar.rolesSave}
            className="text-xs font-semibold bg-primary-600 text-white rounded-xl px-4 py-2.5 hover:bg-primary-700 disabled:opacity-40 cursor-pointer">
            {saving ? '저장 중...' : '저장 완료'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── 오른쪽 상세 패널 (선택된 토요일) ─────────────────────────────────────────

function DetailPanel({
  dateStr, item, onLoad, onEditRoles, onEditEntries,
}: {
  dateStr: string
  item: WeeklyHistoryItem | null
  onLoad: (item: WeeklyHistoryItem) => void
  onEditRoles: () => void
  onEditEntries: () => void
}) {
  const label = formatWeekLabel(dateStr)
  const hasRoles = item && (item.worship_leader || item.accompanist || item.prayer_person)

  return (
    <div className="flex flex-col h-full bg-white select-none">
      {/* 헤더 */}
      <div className="px-5 py-4 border-b border-neutral-100 shrink-0 bg-neutral-50/20">
        <p className="text-xs font-bold text-primary-600 tracking-tight">{label}</p>
        {item && <p className="text-[10px] text-neutral-400 font-bold mt-1 uppercase tracking-wider">{item.sequence_entries.length}곡 저장됨</p>}
      </div>

      <div className="flex-1 overflow-y-auto divide-y divide-neutral-100">
        {item ? (
          <>
            {/* 담당자 */}
            <div className="px-5 py-4 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider">담당 팀원</span>
                <button onClick={onEditRoles}
                  title={TIPS.calendar.rolesEdit}
                  className="text-[11px] font-bold text-primary-500 hover:text-primary-600 flex items-center gap-1 cursor-pointer">
                  <Edit className="w-3 h-3" />
                  <span>수정</span>
                </button>
              </div>
              
              {hasRoles ? (
                <div className="space-y-2">
                  {item.worship_leader && (
                    <div className="flex items-center gap-2.5 bg-neutral-50/50 border border-neutral-200/40 rounded-xl p-2.5">
                      <div className="w-6 h-6 rounded-lg bg-primary-50 flex items-center justify-center shrink-0">
                        <User className="w-3.5 h-3.5 text-primary-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-[9px] text-neutral-400 font-bold">인도자</p>
                        <p className="text-xs font-bold text-neutral-800 truncate">{item.worship_leader}</p>
                      </div>
                    </div>
                  )}
                  {item.accompanist && (
                    <div className="flex items-center gap-2.5 bg-neutral-50/50 border border-neutral-200/40 rounded-xl p-2.5">
                      <div className="w-6 h-6 rounded-lg bg-neutral-50 flex items-center justify-center shrink-0">
                        <Music className="w-3.5 h-3.5 text-neutral-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-[9px] text-neutral-400 font-bold">반주자</p>
                        <p className="text-xs font-semibold text-neutral-700 truncate">{item.accompanist}</p>
                      </div>
                    </div>
                  )}
                  {item.prayer_person && (
                    <div className="flex items-center gap-2.5 bg-neutral-50/50 border border-neutral-200/40 rounded-xl p-2.5">
                      <div className="w-6 h-6 rounded-lg bg-neutral-50 flex items-center justify-center shrink-0">
                        <BookOpen className="w-3.5 h-3.5 text-neutral-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-[9px] text-neutral-400 font-bold">기도자</p>
                        <p className="text-xs font-semibold text-neutral-700 truncate">{item.prayer_person}</p>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <button onClick={onEditRoles}
                  title={TIPS.calendar.rolesAdd}
                  className="text-xs font-semibold text-primary-500 hover:text-primary-600 border border-primary-200/40 hover:bg-primary-50/30 rounded-xl py-2 cursor-pointer transition-all flex items-center justify-center gap-1">
                  <Plus className="w-3.5 h-3.5" />
                  <span>예배 담당자 구성</span>
                </button>
              )}
            </div>

            {/* 셋리스트 */}
            <div className="px-5 py-4 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider">찬양 셋리스트</span>
                <button onClick={onEditEntries}
                  title={TIPS.calendar.entriesEdit}
                  className="text-[11px] font-bold text-primary-500 hover:text-primary-600 flex items-center gap-1 cursor-pointer">
                  <Edit className="w-3 h-3" />
                  <span>수정</span>
                </button>
              </div>
              
              {item.sequence_entries.length > 0 ? (
                <ol className="space-y-2">
                  {item.sequence_entries.map((e, i) => (
                    <li key={i} className="flex gap-3 items-center bg-neutral-50/40 border border-neutral-100 rounded-xl p-2.5 hover:bg-neutral-50/80 transition-all">
                      <span className="text-[10px] font-bold bg-neutral-200 text-neutral-600 w-5 h-5 flex items-center justify-center rounded-full shrink-0 select-none">{i + 1}</span>
                      <div className="flex-1 min-w-0">
                        <span className="text-xs font-bold text-neutral-800 leading-tight block truncate">{e.title}</span>
                        {e.sequence && (
                          <span className="inline-block text-[9px] font-bold font-mono bg-neutral-200/60 text-neutral-500 rounded px-1 mt-1">{e.sequence}</span>
                        )}
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="text-xs text-neutral-400 py-2">셋리스트가 아직 없습니다.</p>
              )}
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center py-20 px-4 text-center gap-3">
            <AlertCircle className="w-6 h-6 text-neutral-300 animate-pulse" />
            <p className="text-xs font-semibold text-neutral-700">기록된 데이터가 없습니다</p>
            <button onClick={onEditRoles}
              title={TIPS.calendar.rolesRegister}
              className="text-xs font-semibold text-primary-500 hover:text-primary-600 border border-primary-200 hover:bg-primary-50/40 rounded-xl px-4 py-2 cursor-pointer transition-all">
              + 예배 담당자 등록
            </button>
          </div>
        )}
      </div>

      {/* 하단 액션 */}
      {item && (
        <div className="px-5 py-4 border-t border-neutral-100 shrink-0 bg-neutral-50/20">
          <button onClick={() => onLoad(item)}
            title={TIPS.calendar.load}
            className="w-full text-xs font-bold bg-primary-600 text-white rounded-xl py-3 hover:bg-primary-700 shadow-md shadow-primary-600/5 hover:shadow-lg hover:shadow-primary-600/15 active:bg-primary-800 transition-all flex items-center justify-center gap-1.5 cursor-pointer">
            <FolderOpen className="w-3.5 h-3.5" />
            <span>셋리스트 불러오기</span>
          </button>
        </div>
      )}
    </div>
  )
}

// ── 달력 본체 ─────────────────────────────────────────────────────────────────

const DOW = ['일', '월', '화', '수', '목', '금', '토']

interface Props {
  history: WeeklyHistoryItem[]
  onLoad: (item: WeeklyHistoryItem) => void
  onEditEntries: (item: WeeklyHistoryItem) => void
}

export function CalendarView({ history, onLoad, onEditEntries }: Props) {
  const queryClient = useQueryClient()
  const today = todayStr()

  const [viewDate, setViewDate] = useState(() => {
    const d = new Date()
    return new Date(d.getFullYear(), d.getMonth(), 1)
  })

  const year = viewDate.getFullYear()
  const month = viewDate.getMonth()

  const byDate = useMemo(() => {
    const m = new Map<string, WeeklyHistoryItem>()
    for (const item of history) m.set(item.week_end_date, item)
    return m
  }, [history])

  const [selectedDate, setSelectedDate] = useState<string | null>(() => {
    const d = new Date()
    return defaultSaturday(d.getFullYear(), d.getMonth())
  })

  const [editingDate, setEditingDate] = useState<string | null>(null)

  // 달에 바뀌면 기본 선택 토요일도 바꿈
  const days = useMemo<(Date | null)[]>(() => {
    const first = new Date(year, month, 1)
    const last = new Date(year, month + 1, 0)
    const result: (Date | null)[] = []
    const dow = first.getDay()
    for (let i = 0; i < dow; i++) result.push(null)
    for (let d = 1; d <= last.getDate(); d++) result.push(new Date(year, month, d))
    while (result.length % 7 !== 0) result.push(null)
    return result
  }, [year, month])

  function prevMonth() {
    const d = new Date(year, month - 1, 1)
    setViewDate(d)
    setSelectedDate(defaultSaturday(d.getFullYear(), d.getMonth()))
  }

  function nextMonth() {
    const d = new Date(year, month + 1, 1)
    setViewDate(d)
    setSelectedDate(defaultSaturday(d.getFullYear(), d.getMonth()))
  }

  const selectedItem = selectedDate ? (byDate.get(selectedDate) ?? null) : null

  return (
    <div className="flex flex-col md:flex-row flex-1 min-h-0 md:overflow-hidden bg-white select-none">

      {/* ── 달력 (주인공) ── */}
      <div className="flex flex-col flex-1 min-w-0 md:overflow-hidden border-b md:border-b-0 md:border-r border-neutral-100">

        {/* 월 네비게이션 */}
        <div className="flex items-center gap-2 px-5 py-4 border-b border-neutral-100 shrink-0 bg-neutral-50/20">
          <button onClick={prevMonth}
            title={TIPS.calendar.prevMonth}
            className="text-neutral-400 hover:text-neutral-700 w-8 h-8 flex items-center justify-center rounded-lg hover:bg-neutral-100 transition-all cursor-pointer">
            <ChevronLeft className="w-5 h-5" />
          </button>
          <span className="flex-1 text-center text-xs font-bold text-neutral-800 select-none">
            {year}년 {month + 1}월
          </span>
          <button onClick={nextMonth}
            title={TIPS.calendar.nextMonth}
            className="text-neutral-400 hover:text-neutral-700 w-8 h-8 flex items-center justify-center rounded-lg hover:bg-neutral-100 transition-all cursor-pointer">
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>

        {/* 요일 헤더 */}
        <div className="grid grid-cols-7 border-b border-neutral-100 shrink-0 bg-neutral-50/20 divide-x divide-neutral-100/30">
          {DOW.map((d, i) => (
            <div key={d} className={`py-2 text-center text-[10px] font-bold select-none uppercase tracking-wider
              ${i === 0 ? 'text-danger-500' : i === 6 ? 'text-primary-500' : 'text-neutral-400'}`}>
              {d}
            </div>
          ))}
        </div>

        {/* 날짜 격자 */}
        <div className="flex-1 overflow-y-auto bg-neutral-50/10">
          <div className="grid grid-cols-7 h-full divide-y divide-x divide-neutral-100/50" style={{ gridAutoRows: 'minmax(84px, 1fr)' }}>
            {days.map((date, i) => {
              if (!date) return <div key={`e-${i}`} className="border-b border-r border-neutral-100/30 bg-neutral-50/30" />
              const dow = date.getDay()
              const isSat = dow === 6
              const isSun = dow === 0
              const ds = toDateStr(date)
              const item = isSat ? byDate.get(ds) : undefined
              const isToday = ds === today
              const isSelected = ds === selectedDate

              return (
                <div
                  key={ds}
                  onClick={() => isSat && setSelectedDate(ds)}
                  className={`border-b border-r border-neutral-100/50 p-2.5 flex flex-col justify-between transition-all duration-150 relative
                    ${isSat ? 'cursor-pointer' : ''}
                    ${isSelected ? 'bg-primary-50/30 border-r border-b border-primary-200/50' : isSat ? 'hover:bg-neutral-50 bg-white' : 'bg-white'}
                  `}
                >
                  {/* 날짜 숫자 */}
                  <span className={`w-6 h-6 flex items-center justify-center rounded-lg text-xs font-bold self-start select-none
                    ${isToday 
                      ? 'bg-primary-600 text-white shadow-md shadow-primary-600/10' 
                      : isSelected && isSat 
                      ? 'bg-primary-100 text-primary-700 border border-primary-300/30' 
                      : isSat 
                      ? 'text-primary-600' 
                      : isSun 
                      ? 'text-danger-500' 
                      : 'text-neutral-600'}
                  `}>
                    {date.getDate()}
                  </span>

                  {/* 토요일: 인도자 이름 미리보기 */}
                  {isSat && item?.worship_leader && (
                    <span className={`text-[10px] font-bold truncate leading-tight rounded-md px-1.5 py-0.5 border select-none w-full text-center mt-2
                      ${isSelected 
                        ? 'text-primary-700 bg-primary-100/50 border-primary-200/30' 
                        : 'text-neutral-600 bg-neutral-100/80 border-neutral-200/40'}`}>
                      {item.worship_leader}
                    </span>
                  )}
                  {isSat && item && !item.worship_leader && item.sequence_entries.length > 0 && (
                    <span className={`text-[10px] font-semibold truncate leading-tight rounded-md px-1.5 py-0.5 border select-none w-full text-center mt-2
                      ${isSelected 
                        ? 'text-primary-500 bg-primary-50/50 border-primary-200/30' 
                        : 'text-neutral-400 bg-neutral-50/50 border-neutral-200/30'}`}>
                      {item.sequence_entries.length}곡
                    </span>
                  )}
                  {isSat && !item && (
                    <span className="text-[9px] font-bold text-neutral-300 mt-2 select-none self-end">미등록</span>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* ── 오른쪽 상세 패널 ── */}
      <div className="md:w-68 lg:w-76 shrink-0 flex flex-col min-h-[300px] md:min-h-0">
        {selectedDate ? (
          <DetailPanel
            dateStr={selectedDate}
            item={selectedItem}
            onLoad={item => onLoad(item)}
            onEditRoles={() => setEditingDate(selectedDate)}
            onEditEntries={() => selectedItem && onEditEntries(selectedItem)}
          />
        ) : (
          <div className="flex flex-col items-center justify-center flex-1 text-xs text-neutral-400 px-4 py-8 text-center gap-2 bg-neutral-50/20 select-none">
            <AlertCircle className="w-5 h-5 text-neutral-300 animate-pulse" />
            <span>토요일을 선택하시면 해당 주의 상세 정보가 표시됩니다</span>
          </div>
        )}
      </div>

      {/* 담당자 수정 모달 */}
      {editingDate && (
        <RolesEditModal
          weekEndDate={editingDate}
          existing={byDate.get(editingDate) ?? null}
          onClose={() => setEditingDate(null)}
          onSaved={() => queryClient.invalidateQueries({ queryKey: ['history'] })}
        />
      )}
    </div>
  )
}

