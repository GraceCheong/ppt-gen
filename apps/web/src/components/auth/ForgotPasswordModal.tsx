import { useState } from 'react'
import { X, KeyRound } from 'lucide-react'
import { requestPasswordReset } from '../../api/auth'

interface ForgotPasswordModalProps {
  onClose: () => void
}

function stripStatusPrefix(message: string): string {
  return message.replace(/^\[\d+\]\s*/, '')
}

export function ForgotPasswordModal({ onClose }: ForgotPasswordModalProps) {
  const [id, setId] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!id.trim()) return
    setLoading(true)
    setError(null)
    setMessage(null)
    try {
      const res = await requestPasswordReset(id.trim())
      setMessage(res)
    } catch (err) {
      setError(err instanceof Error ? stripStatusPrefix(err.message) : '요청 처리 중 오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/40 backdrop-blur-xs px-4" onClick={onClose}>
      <div className="bg-white border border-neutral-200/80 rounded-2xl shadow-2xl w-full max-w-sm" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 pt-5 pb-3 border-b border-neutral-100">
          <div className="flex items-center gap-2">
            <KeyRound className="w-4 h-4 text-neutral-400" />
            <h2 className="text-sm font-bold text-neutral-900">비밀번호 찾기</h2>
          </div>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600 hover:bg-neutral-50 rounded-lg p-1.5 transition-colors cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>

        {message ? (
          <div className="px-6 py-8 text-center">
            <p className="text-sm font-semibold text-neutral-800">{message}</p>
            <button onClick={onClose} className="mt-5 text-xs font-semibold bg-primary-600 text-white rounded-xl px-4 py-2.5 hover:bg-primary-700 cursor-pointer">
              확인
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="px-6 py-4 space-y-3">
              <p className="text-xs text-neutral-500 leading-relaxed">
                가입 시 등록한 아이디를 입력하면, 등록된 이메일로 본인 확인 후 관리자 승인을 거쳐 비밀번호를 재설정해드려요.
              </p>
              <div>
                <label className="text-[11px] font-bold text-neutral-500">아이디</label>
                <input
                  type="text"
                  autoFocus
                  value={id}
                  onChange={e => setId(e.target.value)}
                  className="w-full mt-1.5 border border-neutral-200 rounded-lg px-3 py-2 text-xs outline-none bg-neutral-50/50 hover:bg-neutral-50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all"
                />
              </div>
              {error && <p className="text-xs text-danger-500 bg-danger-50 rounded-lg p-2.5 font-medium border border-danger-100">{error}</p>}
            </div>
            <div className="px-6 pb-5 pt-3 border-t border-neutral-100 flex gap-2 justify-end">
              <button type="button" onClick={onClose} className="text-xs font-semibold border border-neutral-200 text-neutral-700 rounded-xl px-4 py-2.5 hover:bg-neutral-50 cursor-pointer">
                취소
              </button>
              <button type="submit" disabled={loading || !id.trim()}
                className="text-xs font-semibold bg-primary-600 text-white rounded-xl px-4 py-2.5 hover:bg-primary-700 disabled:opacity-40 cursor-pointer">
                {loading ? '요청 중...' : '요청하기'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
