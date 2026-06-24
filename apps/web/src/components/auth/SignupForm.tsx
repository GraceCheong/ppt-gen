import { useState } from 'react'
import { useAuthStore } from '../../store/authStore'
import { checkIdAvailable } from '../../api/auth'

interface SignupFormProps {
  onSwitchToLogin: () => void
}

export function SignupForm({ onSwitchToLogin }: SignupFormProps) {
  const { signup, enterGuestMode } = useAuthStore()
  const [church, setChurch] = useState('')
  const [nickname, setNickname] = useState('')
  const [id, setId] = useState('')
  const [pw, setPw] = useState('')
  const [idStatus, setIdStatus] = useState<'idle' | 'checking' | 'ok' | 'taken' | 'invalid'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleCheckId() {
    const trimmed = id.trim()
    if (!trimmed) return
    setIdStatus('checking')
    try {
      const res = await checkIdAvailable(trimmed)
      if (res.available) {
        setIdStatus('ok')
      } else {
        setIdStatus('taken')
      }
    } catch {
      setIdStatus('invalid')
    }
  }

  function handleIdChange(v: string) {
    setId(v)
    setIdStatus('idle')
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (idStatus !== 'ok') {
      setError('아이디 중복 확인을 해주세요.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      await signup({ church: church.trim(), nickname: nickname.trim(), id: id.trim(), pw })
    } catch (err) {
      setError(err instanceof Error ? err.message : '회원가입에 실패했습니다.')
      setLoading(false)
    }
  }

  const idHint =
    idStatus === 'ok' ? '사용 가능한 아이디입니다.' :
    idStatus === 'taken' ? '이미 사용 중인 아이디입니다.' :
    idStatus === 'invalid' ? '유효하지 않은 아이디입니다.' : null

  const idHintColor =
    idStatus === 'ok' ? 'text-success-600 bg-success-50 border-success-100' : 'text-danger-600 bg-danger-50 border-danger-100'

  return (
    <div className="min-h-screen flex items-center justify-center bg-neutral-50 px-4 py-8">
      <div className="bg-white border border-neutral-200/80 rounded-2xl shadow-xl w-full max-w-sm px-8 py-10">
        <div className="flex flex-col items-center mb-8">
          <img src="/atempo.ico" className="w-12 h-12 object-contain rounded-xl mb-2.5 shadow-sm" alt="Logo" />
          <h1 className="text-2xl font-bold text-neutral-900 tracking-tight">회원가입</h1>
          <p className="text-xs text-neutral-400 mt-1">교회 계정을 만들어 예배 찬양 PPT를 관리하세요</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-neutral-600 mb-1.5">교회명 *</label>
            <input
              type="text"
              autoFocus
              value={church}
              onChange={e => setChurch(e.target.value)}
              placeholder="예: 서울중앙"
              className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm outline-none bg-neutral-50/50 hover:bg-neutral-50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all duration-200 placeholder:text-neutral-400"
            />
            <p className="text-[10px] text-neutral-400 mt-1.5">'교회'를 제외한 교회명만 입력해 주세요.</p>
          </div>
          <div>
            <label className="block text-xs font-semibold text-neutral-600 mb-1.5">닉네임 *</label>
            <input
              type="text"
              value={nickname}
              onChange={e => setNickname(e.target.value)}
              placeholder="예배 인도자 이름 또는 직분"
              className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm outline-none bg-neutral-50/50 hover:bg-neutral-50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all duration-200 placeholder:text-neutral-400"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-neutral-600 mb-1.5">아이디 *</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={id}
                onChange={e => handleIdChange(e.target.value)}
                placeholder="영문·숫자 (3~30자)"
                className="flex-1 border border-neutral-200 rounded-lg px-3 py-2 text-sm outline-none bg-neutral-50/50 hover:bg-neutral-50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all duration-200 placeholder:text-neutral-400 min-w-0"
              />
              <button
                type="button"
                onClick={handleCheckId}
                disabled={!id.trim() || idStatus === 'checking'}
                className="shrink-0 text-xs font-medium border border-neutral-200 rounded-lg px-3 py-2 hover:bg-neutral-50 disabled:bg-neutral-100 disabled:text-neutral-400 transition-all duration-200 cursor-pointer"
              >
                {idStatus === 'checking' ? '확인 중' : '중복 확인'}
              </button>
            </div>
            {idHint && (
              <p className={`text-xs mt-1.5 px-2.5 py-1.5 border rounded-lg font-medium ${idHintColor}`}>{idHint}</p>
            )}
          </div>
          <div>
            <label className="block text-xs font-semibold text-neutral-600 mb-1.5">비밀번호 * (8자 이상)</label>
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
            disabled={loading || !church.trim() || !nickname.trim() || !id.trim() || !pw || idStatus !== 'ok'}
            className="w-full bg-primary-600 text-white rounded-lg py-2.5 text-sm font-semibold shadow-md shadow-primary-600/10 hover:bg-primary-700 hover:shadow-lg hover:shadow-primary-600/20 active:bg-primary-800 disabled:bg-neutral-100 disabled:text-neutral-400 disabled:shadow-none disabled:cursor-not-allowed transition-all duration-200 cursor-pointer"
          >
            {loading ? '가입 중...' : '회원가입'}
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
            onClick={onSwitchToLogin}
            className="w-full border border-neutral-200 text-neutral-700 rounded-lg py-2 text-sm font-medium hover:bg-neutral-50 focus:bg-neutral-50 active:bg-neutral-100 transition-all duration-200 cursor-pointer"
          >
            로그인으로 돌아가기
          </button>
          <button
            onClick={enterGuestMode}
            className="w-full text-neutral-400 hover:text-neutral-600 text-xs font-medium py-1 transition-all duration-200 cursor-pointer hover:underline"
          >
            로그인 없이 Guest Mode로 시작
          </button>
        </div>
      </div>
    </div>
  )
}

