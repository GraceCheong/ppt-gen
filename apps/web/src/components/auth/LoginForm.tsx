import { useState } from 'react'
import { useAuthStore } from '../../store/authStore'

interface LoginFormProps {
  onSwitchToSignup: () => void
}

export function LoginForm({ onSwitchToSignup }: LoginFormProps) {
  const { login, enterGuestMode } = useAuthStore()
  const [id, setId] = useState('')
  const [pw, setPw] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!id.trim() || !pw) return
    setLoading(true)
    setError(null)
    try {
      await login(id.trim(), pw)
    } catch (err) {
      setError(err instanceof Error ? err.message : '로그인에 실패했습니다.')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-neutral-50 px-4">
      <div className="bg-white border border-neutral-200/80 rounded-2xl shadow-xl w-full max-w-sm px-8 py-10 transition-all duration-300">
        <div className="flex flex-col items-center mb-8">
          <img src="/atempo.ico" className="w-12 h-12 object-contain rounded-xl mb-2.5 shadow-sm" alt="Logo" />
          <h1 className="text-2xl font-bold text-neutral-900 tracking-tight">PO,RR</h1>
          <p className="text-xs text-neutral-400 mt-1">예배 PPT 자동 생성 플랫폼</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-neutral-600 mb-1.5">아이디</label>
            <input
              type="text"
              autoFocus
              value={id}
              onChange={e => setId(e.target.value)}
              placeholder="아이디 입력"
              className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm outline-none bg-neutral-50/50 hover:bg-neutral-50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all duration-200 placeholder:text-neutral-400"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-neutral-600 mb-1.5">비밀번호</label>
            <input
              type="password"
              value={pw}
              onChange={e => setPw(e.target.value)}
              placeholder="비밀번호 입력"
              className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm outline-none bg-neutral-50/50 hover:bg-neutral-50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all duration-200 placeholder:text-neutral-400"
            />
          </div>

          {error && (
            <p className="text-xs text-danger-500 bg-danger-50 rounded-lg p-2.5 font-medium border border-danger-100">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading || !id.trim() || !pw}
            className="w-full bg-primary-600 text-white rounded-lg py-2.5 text-sm font-semibold shadow-md shadow-primary-600/10 hover:bg-primary-700 hover:shadow-lg hover:shadow-primary-600/20 active:bg-primary-800 disabled:bg-neutral-100 disabled:text-neutral-400 disabled:shadow-none disabled:cursor-not-allowed transition-all duration-200 cursor-pointer"
          >
            {loading ? '로그인 중...' : '로그인'}
          </button>
        </form>

        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center" aria-hidden="true">
            <div className="w-full border-t border-neutral-200"></div>
          </div>
          <div className="relative flex justify-center text-xs font-medium uppercase">
            <span className="bg-white px-2.5 text-neutral-400">또는</span>
          </div>
        </div>

        <div className="space-y-3">
          <button
            onClick={onSwitchToSignup}
            className="w-full border border-neutral-200 text-neutral-700 rounded-lg py-2 text-sm font-medium hover:bg-neutral-50 focus:bg-neutral-50 active:bg-neutral-100 transition-all duration-200 cursor-pointer"
          >
            회원가입하기
          </button>
          <button
            onClick={enterGuestMode}
            className="w-full border border-neutral-200 text-neutral-700 rounded-lg py-2 text-sm font-medium hover:bg-neutral-50 focus:bg-neutral-50 active:bg-neutral-100 transition-all duration-200 cursor-pointer"
          >
            로그인 없이 Guest Mode로 시작
          </button>
        </div>

        <p className="text-center text-[10px] text-neutral-400 mt-5">
          로그인 없이 Guest Mode 를 사용하면 교회 데이터와 연동이 불가합니다.
        </p>
      </div>
    </div>
  )
}

