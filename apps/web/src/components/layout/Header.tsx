import { NavLink, useNavigate } from 'react-router-dom'
import { useServerStatus } from '../../hooks/useServerStatus'
import { isTauri } from '../../api/serverConfig'
import { TIPS } from '../../constants/tooltips'
import { useAuthStore } from '../../store/authStore'
import { Presentation, Calendar, TrendingUp, LogOut, RefreshCw } from 'lucide-react'

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

  const showStatus = isTauri()
  const connecting = showStatus && resolution === null
  const serverMode = resolution?.mode ?? 'offline'
  const label = connecting ? '연결 중...' : MODE_LABEL[serverMode] ?? serverMode
  const dotColor = connecting
    ? 'bg-warning-500 animate-pulse ring-4 ring-warning-500/20'
    : (MODE_COLOR[serverMode] ?? 'bg-neutral-400')

  async function handleLogout() {
    await logout()
    navigate('/app')
  }

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
            <span>PPT 만들기</span>
          </NavLink>
          {/* Guest에게는 캘린더 탭 숨김 */}
          {mode === 'user' && (
            <NavLink to="/history" className={tabClass}>
              <Calendar className="w-3.5 h-3.5" />
              <span>캘린더</span>
            </NavLink>
          )}
          <NavLink to="/graph" className={tabClass}>
            <TrendingUp className="w-3.5 h-3.5" />
            <span>워십 그래프</span>
          </NavLink>
        </nav>
      </div>

      <div className="flex items-center gap-3 shrink-0">
        {/* 로그인 사용자 표시 */}
        {mode === 'user' && user && (
          <div className="flex items-center gap-2.5">
            <div className="bg-neutral-100 text-neutral-700 rounded-full px-3 py-1 text-[11px] font-semibold border border-neutral-200/50">
              {user.church} · {user.nickname}
            </div>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1 text-[11px] text-neutral-400 hover:text-danger-600 transition-colors font-medium border border-neutral-200 hover:border-danger-200 rounded-lg px-2.5 py-1 bg-white hover:bg-danger-50 shadow-sm cursor-pointer"
            >
              <LogOut className="w-3 h-3" />
              <span>로그아웃</span>
            </button>
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

