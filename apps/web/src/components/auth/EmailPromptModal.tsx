import { useState } from 'react'
import { Mail } from 'lucide-react'
import { useAuthStore } from '../../store/authStore'

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

interface EmailPromptModalProps {
  onDismiss: () => void
}

export function EmailPromptModal({ onDismiss }: EmailPromptModalProps) {
  const { updateEmail } = useAuthStore()
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!EMAIL_RE.test(email)) {
      setError('올바른 이메일 주소를 입력해주세요.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await updateEmail(email)
      onDismiss()
    } catch (err) {
      setError(err instanceof Error ? err.message : '이메일 등록에 실패했습니다.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/40 backdrop-blur-xs px-4">
      <div className="bg-white border border-neutral-200/80 rounded-2xl shadow-2xl w-full max-w-sm">
        <div className="flex items-center gap-2 px-6 pt-5 pb-3 border-b border-neutral-100">
          <Mail className="w-4 h-4 text-neutral-400" />
          <h2 className="text-sm font-bold text-neutral-900">이메일을 등록해주세요</h2>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="px-6 py-4 space-y-3">
            <p className="text-xs text-neutral-500 leading-relaxed">
              비밀번호를 잊었을 때 본인 확인 및 계정 복구 안내를 받으려면 이메일이 필요해요.
              한 번만 등록하면 다음부터는 이 안내가 표시되지 않습니다.
            </p>
            <input
              type="email"
              autoFocus
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="example@email.com"
              className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-xs outline-none bg-neutral-50/50 hover:bg-neutral-50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all"
            />
            {error && <p className="text-xs text-danger-500 bg-danger-50 rounded-lg p-2.5 font-medium border border-danger-100">{error}</p>}
          </div>
          <div className="px-6 pb-5 pt-3 border-t border-neutral-100 flex gap-2 justify-end">
            <button type="button" onClick={onDismiss} className="text-xs font-semibold border border-neutral-200 text-neutral-700 rounded-xl px-4 py-2.5 hover:bg-neutral-50 cursor-pointer">
              나중에
            </button>
            <button type="submit" disabled={saving || !email}
              className="text-xs font-semibold bg-primary-600 text-white rounded-xl px-4 py-2.5 hover:bg-primary-700 disabled:opacity-40 cursor-pointer">
              {saving ? '등록 중...' : '등록하기'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
