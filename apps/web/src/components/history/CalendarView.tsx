import { useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { updateHistoryRoles, type WeeklyHistoryItem } from '../../api/history'
import { TIPS } from '../../constants/tooltips'

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
  return `${week}주차, ${y.slice(2)}.${m}.${d}`
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
  const [password, setPassword] = useState('')
  const [worshipLeader, setWorshipLeader] = useState(existing?.worship_leader ?? '')
  const [accompanist, setAccompanist] = useState(existing?.accompanist ?? '')
  const [prayerPerson, setPrayerPerson] = useState(existing?.prayer_person ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSave() {
    if (!password) { setError('비밀번호를 입력하세요.'); return }
    setSaving(true); setError(null)
    try {
      await updateHistoryRoles(weekEndDate, { password, worship_leader: worshipLeader, accompanist, prayer_person: prayerPerson })
      onSaved(); onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : '저장 실패')
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-gray-100">
          <div>
            <h2 className="text-sm font-semibold text-gray-800">담당자 입력</h2>
            <p className="text-xs text-gray-400 mt-0.5">{formatWeekLabel(weekEndDate)}</p>
          </div>
          <button onClick={onClose} title={TIPS.calendar.rolesClose} className="text-gray-300 hover:text-gray-500 text-lg">✕</button>
        </div>
        <div className="px-5 py-4 space-y-3">
          <div>
            <label className="text-xs text-gray-500 block mb-1">비밀번호 *</label>
            <input type="password" value={password} autoFocus
              onChange={e => setPassword(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSave()}
              className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm outline-none focus:border-blue-400"
              placeholder="비밀번호 입력" />
          </div>
          {[
            { label: '인도자', val: worshipLeader, set: setWorshipLeader },
            { label: '반주자', val: accompanist, set: setAccompanist },
            { label: '기도자', val: prayerPerson, set: setPrayerPerson },
          ].map(({ label, val, set }) => (
            <div key={label}>
              <label className="text-xs text-gray-500 block mb-1">{label}</label>
              <input type="text" value={val} onChange={e => set(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm outline-none focus:border-blue-400"
                placeholder="이름" />
            </div>
          ))}
          {error && <p className="text-xs text-red-500">{error}</p>}
        </div>
        <div className="px-5 pb-5 pt-3 border-t border-gray-100 flex gap-2 justify-end">
          <button onClick={onClose} title={TIPS.calendar.rolesCancel} className="text-sm border border-gray-300 rounded px-3 py-1.5 hover:bg-gray-50">취소</button>
          <button onClick={handleSave} disabled={saving} title={TIPS.calendar.rolesSave}
            className="text-sm bg-blue-500 text-white rounded px-3 py-1.5 hover:bg-blue-600 disabled:opacity-40">
            {saving ? '저장 중...' : '저장'}
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
    <div className="flex flex-col h-full">
      {/* 헤더 */}
      <div className="px-4 py-3 border-b border-gray-100 shrink-0">
        <p className="text-sm font-semibold text-blue-600">{label}</p>
        {item && <p className="text-xs text-gray-400 mt-0.5">{item.sequence_entries.length}곡</p>}
      </div>

      <div className="flex-1 overflow-y-auto">
        {item ? (
          <>
            {/* 담당자 */}
            <div className="px-4 py-3 border-b border-gray-100">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">담당자</span>
                <button onClick={onEditRoles}
                  title={TIPS.calendar.rolesEdit}
                  className="text-[10px] text-blue-400 hover:text-blue-600">수정</button>
              </div>
              {hasRoles ? (
                <div className="space-y-1.5">
                  {item.worship_leader && (
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-gray-400 w-10">인도자</span>
                      <span className="text-sm font-bold text-gray-800">{item.worship_leader}</span>
                    </div>
                  )}
                  {item.accompanist && (
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-gray-400 w-10">반주자</span>
                      <span className="text-sm text-gray-700">{item.accompanist}</span>
                    </div>
                  )}
                  {item.prayer_person && (
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-gray-400 w-10">기도자</span>
                      <span className="text-sm text-gray-700">{item.prayer_person}</span>
                    </div>
                  )}
                </div>
              ) : (
                <button onClick={onEditRoles}
                  title={TIPS.calendar.rolesAdd}
                  className="text-xs text-blue-400 hover:text-blue-600">+ 담당자 입력</button>
              )}
            </div>

            {/* 셋리스트 */}
            <div className="px-4 py-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">셋리스트</span>
                <button onClick={onEditEntries}
                  title={TIPS.calendar.entriesEdit}
                  className="text-[10px] text-blue-400 hover:text-blue-600">수정</button>
              </div>
              {item.sequence_entries.length > 0 ? (
                <ol className="space-y-2.5">
                  {item.sequence_entries.map((e, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="text-xs text-gray-300 w-4 text-right shrink-0 pt-0.5">{i + 1}</span>
                      <div className="flex flex-col min-w-0">
                        <span className="text-sm text-gray-800 leading-tight">{e.title}</span>
                        {e.sequence && <span className="text-[10px] text-gray-400 mt-0.5">{e.sequence}</span>}
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="text-xs text-gray-400">셋리스트 미등록</p>
              )}
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-full px-4 py-8 text-center gap-3">
            <p className="text-xs text-gray-400">등록된 내용이 없습니다</p>
            <button onClick={onEditRoles}
              title={TIPS.calendar.rolesRegister}
              className="text-xs text-blue-500 hover:text-blue-700 border border-blue-200 rounded px-3 py-1.5">
              + 담당자 등록
            </button>
          </div>
        )}
      </div>

      {/* 하단 액션 */}
      {item && (
        <div className="px-4 py-3 border-t border-gray-100 shrink-0">
          <button onClick={() => onLoad(item)}
            title={TIPS.calendar.load}
            className="w-full text-sm font-medium bg-blue-500 text-white rounded py-2 hover:bg-blue-600 transition-colors">
            불러오기
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
    <div className="flex flex-col md:flex-row flex-1 min-h-0 md:overflow-hidden">

      {/* ── 달력 (주인공) ── */}
      <div className="flex flex-col flex-1 min-w-0 md:overflow-hidden">

        {/* 월 네비게이션 */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100 shrink-0">
          <button onClick={prevMonth}
            title={TIPS.calendar.prevMonth}
            className="text-gray-400 hover:text-gray-700 w-8 h-8 flex items-center justify-center rounded hover:bg-gray-100 transition-colors text-lg">
            ‹
          </button>
          <span className="flex-1 text-center text-sm font-semibold text-gray-700">
            {year}년 {month + 1}월
          </span>
          <button onClick={nextMonth}
            title={TIPS.calendar.nextMonth}
            className="text-gray-400 hover:text-gray-700 w-8 h-8 flex items-center justify-center rounded hover:bg-gray-100 transition-colors text-lg">
            ›
          </button>
        </div>

        {/* 요일 헤더 */}
        <div className="grid grid-cols-7 border-b border-gray-100 shrink-0">
          {DOW.map((d, i) => (
            <div key={d} className={`py-2 text-center text-xs font-medium
              ${i === 0 ? 'text-red-400' : i === 6 ? 'text-blue-500' : 'text-gray-400'}`}>
              {d}
            </div>
          ))}
        </div>

        {/* 날짜 격자 */}
        <div className="flex-1 overflow-y-auto">
          <div className="grid grid-cols-7 h-full" style={{ gridAutoRows: 'minmax(72px, 1fr)' }}>
            {days.map((date, i) => {
              if (!date) return <div key={`e-${i}`} className="border-b border-r border-gray-50 bg-gray-50/30" />
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
                  className={`border-b border-r border-gray-100 p-1.5 flex flex-col transition-colors
                    ${isSat ? 'cursor-pointer' : ''}
                    ${isSelected ? 'bg-blue-50 border-blue-200' : isSat ? 'hover:bg-blue-50/50' : ''}
                  `}
                >
                  {/* 날짜 숫자 */}
                  <span className={`w-6 h-6 flex items-center justify-center rounded-full text-xs font-medium self-start
                    ${isToday ? 'bg-blue-500 text-white' : isSelected && isSat ? 'bg-blue-500 text-white' : isSat ? 'text-blue-600' : isSun ? 'text-red-400' : 'text-gray-600'}
                  `}>
                    {date.getDate()}
                  </span>

                  {/* 토요일: 인도자 이름 미리보기 */}
                  {isSat && item?.worship_leader && (
                    <span className={`text-[10px] mt-1 font-semibold truncate leading-tight
                      ${isSelected ? 'text-blue-700' : 'text-gray-600'}`}>
                      {item.worship_leader}
                    </span>
                  )}
                  {isSat && item && !item.worship_leader && item.sequence_entries.length > 0 && (
                    <span className={`text-[10px] mt-1 truncate leading-tight
                      ${isSelected ? 'text-blue-500' : 'text-gray-400'}`}>
                      {item.sequence_entries.length}곡
                    </span>
                  )}
                  {isSat && !item && (
                    <span className="text-[10px] mt-1 text-gray-200">미등록</span>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* ── 오른쪽 상세 패널 ── */}
      <div className="md:w-64 lg:w-72 shrink-0 border-t md:border-t-0 md:border-l border-gray-100 flex flex-col min-h-[280px] md:min-h-0">
        {selectedDate ? (
          <DetailPanel
            dateStr={selectedDate}
            item={selectedItem}
            onLoad={item => onLoad(item)}
            onEditRoles={() => setEditingDate(selectedDate)}
            onEditEntries={() => selectedItem && onEditEntries(selectedItem)}
          />
        ) : (
          <div className="flex items-center justify-center flex-1 text-xs text-gray-300 px-4 text-center">
            토요일을 선택하면 상세 내용이 표시됩니다
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
