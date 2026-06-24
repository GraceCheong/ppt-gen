import { NavLink, useNavigate } from 'react-router-dom'
import { useServerStatus } from '../../hooks/useServerStatus'
import { isTauri } from '../../api/serverConfig'
import { TIPS } from '../../constants/tooltips'
import { useAuthStore } from '../../store/authStore'
import { Presentation, Calendar, TrendingUp, LogOut, RefreshCw, UserCircle, Building2, User } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'

const MODE_LABEL: Record<string, string> = {
  browser: '',
  remote: '원격',
  sidecar: '로컬',
  offline: '오프라인',
}

const MODE_COLOR: Record<string, string> = {
  browser: 'bg-success-500 ring-4 ring-success-500/20',
  remote: 'bg-success-500 ring-4 ring-success-500/20',
  sidecar: 'bg-primary-500 ring-4 ring-primary-500/20',
  offline: 'bg-danger-500 ring-4 ring-danger-500/20',
}

const tabClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all duration-200 select-none ${
    isActive
      ? 'text-neutral-900 bg-neutral-100'
      : 'text-neutral-500 hover:text-neutral-900 hover:bg-neutral-50'
  }`

export function Header() {
  const { resolution, reconnect } = useServerStatus()
  const { mode, user, logout } = useAuthStore()
  const navigate = useNavigate()
  const [profileOpen, setProfileOpen] = useState(false)
  const profileRef = useRef<HTMLDivElement>(null)

  const showStatus = isTauri()
  const connecting = showStatus && resolution === null
  const serverMode = resolution?.mode ?? 'offline'
  const label = connecting ? '연결 중...' : MODE_LABEL[serverMode] ?? serverMode
  const dotColor = connecting
    ? 'bg-warning-500 animate-pulse ring-4 ring-warning-500/20'
    : (MODE_COLOR[serverMode] ?? 'bg-neutral-400')

  async function handleLogout() {
    await logout()
    setProfileOpen(false)
    navigate('/app')
  }

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false)
      }
    }
    if (profileOpen) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [profileOpen])

  return (
    <header className="h-14 flex items-center px-5 bg-white border-b border-neutral-200 shrink-0 gap-4 justify-between">
      <div className="flex items-center gap-6">
        {/* 브랜드 로고 */}
        <div className="flex items-center gap-2 cursor-pointer select-none" onClick={() => navigate('/app')}>
          <img src="/atempo.ico" className="w-8 h-8 object-contain rounded-lg shadow-sm" alt="Logo" />
          <span className="font-bold text-neutral-900 tracking-tight text-sm">PO,RR</span>
        </div>

        {/* 메인 네비게이션 */}
        <nav className="flex items-center gap-1">
          <NavLink to="/app" className={tabClass}>
            <Presentation className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">PPT 만들기</span>
          </NavLink>
          {/* Guest에게는 캘린더 탭 숨김 */}
          {mode === 'user' && (
            <NavLink to="/history" className={tabClass}>
              <Calendar className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">캘린더</span>
            </NavLink>
          )}
          <NavLink to="/graph" className={tabClass}>
            <TrendingUp className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">워십 그래프</span>
          </NavLink>
        </nav>
      </div>

      <div className="flex items-center gap-3 shrink-0">
        {/* 게스트 모드: 로그인 유도 아이콘 */}
        {mode === 'guest' && (
          <button
            onClick={() => logout()}
            title="로그인하기"
            className="w-8 h-8 flex items-center justify-center rounded-full border border-neutral-200 bg-neutral-100 text-neutral-400 hover:bg-neutral-200 hover:text-neutral-600 transition-all cursor-pointer"
          >
            <UserCircle className="w-5 h-5" />
          </button>
        )}

        {/* 로그인 사용자 표시 */}
        {mode === 'user' && user && (
          <div className="relative" ref={profileRef}>
            <button
              onClick={() => setProfileOpen(o => !o)}
              className={`w-8 h-8 flex items-center justify-center rounded-full border transition-all cursor-pointer
                ${profileOpen
                  ? 'bg-primary-50 border-primary-300 text-primary-600'
                  : 'bg-neutral-100 border-neutral-200 text-neutral-500 hover:bg-neutral-200 hover:text-neutral-700'}`}
            >
              <UserCircle className="w-5 h-5" />
            </button>

            {profileOpen && (
              <div className="absolute right-0 top-10 w-52 bg-white border border-neutral-200 rounded-2xl shadow-xl z-50 overflow-hidden">
                <div className="px-4 py-3.5 border-b border-neutral-100 bg-neutral-50/50">
                  <div className="flex items-center gap-2 text-[11px] text-neutral-500 font-medium mb-1">
                    <Building2 className="w-3 h-3 shrink-0" />
                    <span className="truncate">{user.church}</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-neutral-800 font-bold">
                    <User className="w-3 h-3 shrink-0 text-neutral-400" />
                    <span className="truncate">{user.nickname}</span>
                  </div>
                </div>
                <div className="p-1.5">
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2 px-3 py-2 text-xs font-semibold text-danger-600 hover:bg-danger-50 rounded-xl transition-colors cursor-pointer"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    <span>로그아웃</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 서버 상태 (Tauri 전용) */}
        {showStatus && (
          <div className="flex items-center gap-2 bg-neutral-50 border border-neutral-200/60 rounded-full px-2.5 py-1">
            <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotColor}`} />
            <span className="text-[10px] text-neutral-600 font-semibold">{label}</span>
            {serverMode === 'offline' && !connecting && (
              <button 
                onClick={reconnect} 
                title={TIPS.server.reconnect} 
                className="text-[10px] text-primary-500 hover:text-primary-600 flex items-center justify-center p-0.5 hover:bg-neutral-100 rounded"
              >
                <RefreshCw className="w-2.5 h-2.5 animate-spin-slow" />
              </button>
            )}
          </div>
        )}
      </div>
    </header>
  )
}

