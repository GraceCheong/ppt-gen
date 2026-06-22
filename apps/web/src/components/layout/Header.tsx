import { NavLink } from 'react-router-dom'
import { useServerStatus } from '../../hooks/useServerStatus'
import { isTauri } from '../../api/serverConfig'
import { TIPS } from '../../constants/tooltips'

const MODE_LABEL: Record<string, string> = {
  browser: '',
  remote: '원격 서버',
  sidecar: '로컬 서버',
  offline: '오프라인',
}

const MODE_COLOR: Record<string, string> = {
  browser: 'bg-green-400',
  remote: 'bg-green-400',
  sidecar: 'bg-blue-400',
  offline: 'bg-red-400',
}

const tabClass = ({ isActive }: { isActive: boolean }) =>
  `h-full px-4 flex items-center text-sm font-medium border-b-2 transition-colors -mb-px ${
    isActive
      ? 'text-blue-600 border-blue-500'
      : 'text-gray-500 border-transparent hover:text-gray-800 hover:border-gray-300'
  }`

export function Header() {
  const { resolution, reconnect } = useServerStatus()

  const showStatus = isTauri()
  const connecting = showStatus && resolution === null
  const mode = resolution?.mode ?? 'offline'
  const label = connecting ? '연결 중...' : MODE_LABEL[mode] ?? mode
  const dotColor = connecting
    ? 'bg-yellow-400 animate-pulse'
    : (MODE_COLOR[mode] ?? 'bg-gray-400')

  return (
    <header className="h-12 flex items-center px-4 bg-white border-b border-gray-200 shrink-0 gap-2">
      <span className="font-semibold text-gray-800 tracking-tight mr-2 shrink-0">PO,RR</span>

      <nav className="flex items-stretch h-full gap-1">
        <NavLink to="/app" className={tabClass}>작업</NavLink>
        <NavLink to="/history" className={tabClass}>이력</NavLink>
        <NavLink to="/graph" className={tabClass}>관계도</NavLink>
      </nav>

      {showStatus && (
        <div className="ml-auto flex items-center gap-2 shrink-0">
          <span className={`w-2 h-2 rounded-full shrink-0 ${dotColor}`} />
          <span className="text-xs text-gray-500">{label}</span>
          {mode === 'offline' && !connecting && (
            <button onClick={reconnect} title={TIPS.server.reconnect} className="text-xs text-blue-500 hover:underline">
              재연결
            </button>
          )}
        </div>
      )}
    </header>
  )
}
