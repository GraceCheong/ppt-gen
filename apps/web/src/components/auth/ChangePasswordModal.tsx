import { useState } from 'react'
import { X, KeyRound } from 'lucide-react'
import { useAuthStore } from '../../store/authStore'

interface ChangePasswordModalProps {
  onClose: () => void
}

export function ChangePasswordModal({ onClose }: ChangePasswordModalProps) {
  const { changePassword } = useAuthStore()
  const [oldPw, setOldPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (newPw.length < 8) {
      setError('새 비밀번호는 최소 8자 이상이어야 합니다.')
      return
    }
    if (newPw !== confirmPw) {
      setError('새 비밀번호가 일치하지 않습니다.')
      return
    }
    setSaving(true)
    try {
      await changePassword(oldPw, newPw)
      setSuccess(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : '비밀번호 변경에 실패했습니다.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/40 backdrop-blur-xs px-4" onClick={onClose}>
      <div className="bg-white border border-neutral-200/80 rounded-2xl shadow-2xl w-full max-w-sm" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 pt-5 pb-3 border-b border-neutral-100">
          <div className="flex items-center gap-2">
            <KeyRound className="w-4 h-4 text-neutral-400" />
            <h2 className="text-sm font-bold text-neutral-900">비밀번호 변경</h2>
          </div>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600 hover:bg-neutral-50 rounded-lg p-1.5 transition-colors cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>

        {success ? (
          <div className="px-6 py-8 text-center">
            <p className="text-sm font-semibold text-neutral-800">비밀번호가 변경되었습니다.</p>
            <p className="text-xs text-neutral-400 mt-1">다른 기기에서는 다시 로그인해야 합니다.</p>
            <button onClick={onClose} className="mt-5 text-xs font-semibold bg-primary-600 text-white rounded-xl px-4 py-2.5 hover:bg-primary-700 cursor-pointer">
              확인
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="px-6 py-4 space-y-3.5">
              <div className="flex flex-col gap-1.5">
                <label className="text-[11px] font-bold text-neutral-500">현재 비밀번호</label>
                <input
                  type="password"
                  value={oldPw}
                  onChange={e => setOldPw(e.target.value)}
                  autoFocus
                  className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-xs outline-none bg-neutral-50/50 hover:bg-neutral-50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-[11px] font-bold text-neutral-500">새 비밀번호 (8자 이상)</label>
                <input
                  type="password"
                  value={newPw}
                  onChange={e => setNewPw(e.target.value)}
                  className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-xs outline-none bg-neutral-50/50 hover:bg-neutral-50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-[11px] font-bold text-neutral-500">새 비밀번호 확인</label>
                <input
                  type="password"
                  value={confirmPw}
                  onChange={e => setConfirmPw(e.target.value)}
                  className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-xs outline-none bg-neutral-50/50 hover:bg-neutral-50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all"
                />
              </div>
              {error && <p className="text-xs text-danger-500 bg-danger-50 rounded-lg p-2.5 font-medium border border-danger-100">{error}</p>}
            </div>
            <div className="px-6 pb-5 pt-3 border-t border-neutral-100 flex gap-2 justify-end">
              <button type="button" onClick={onClose} className="text-xs font-semibold border border-neutral-200 text-neutral-700 rounded-xl px-4 py-2.5 hover:bg-neutral-50 cursor-pointer">
                취소
              </button>
              <button type="submit" disabled={saving || !oldPw || !newPw || !confirmPw}
                className="text-xs font-semibold bg-primary-600 text-white rounded-xl px-4 py-2.5 hover:bg-primary-700 disabled:opacity-40 cursor-pointer">
                {saving ? '변경 중...' : '변경하기'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
