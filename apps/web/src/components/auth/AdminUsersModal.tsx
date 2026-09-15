import { useEffect, useState } from 'react'
import { X, ShieldCheck, KeyRound, Copy, Check } from 'lucide-react'
import { fetchAdminUsers, adminResetPassword, type AdminUserInfo } from '../../api/auth'

interface AdminUsersModalProps {
  onClose: () => void
}

export function AdminUsersModal({ onClose }: AdminUsersModalProps) {
  const [users, setUsers] = useState<AdminUserInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [resetTarget, setResetTarget] = useState<string | null>(null)
  const [result, setResult] = useState<{ id: string; tempPassword: string } | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    load()
  }, [])

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setUsers(await fetchAdminUsers())
    } catch (err) {
      setError(err instanceof Error ? err.message : '회원 목록을 불러오지 못했습니다.')
    } finally {
      setLoading(false)
    }
  }

  async function handleReset(user: AdminUserInfo) {
    if (!confirm(`${user.nickname} (${user.id})님의 비밀번호를 초기화할까요?\n임시 비밀번호가 발급되며, 해당 회원의 다른 로그인 세션은 모두 로그아웃됩니다.`)) {
      return
    }
    setResetTarget(user.id)
    setResult(null)
    try {
      const { tempPassword } = await adminResetPassword(user.id)
      if (tempPassword) setResult({ id: user.id, tempPassword })
    } catch (err) {
      setError(err instanceof Error ? err.message : '비밀번호 초기화에 실패했습니다.')
    } finally {
      setResetTarget(null)
    }
  }

  function handleCopy() {
    if (!result) return
    navigator.clipboard.writeText(result.tempPassword)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/40 backdrop-blur-xs px-4" onClick={onClose}>
      <div className="bg-white border border-neutral-200/80 rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 pt-5 pb-3 border-b border-neutral-100 shrink-0">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-neutral-400" />
            <h2 className="text-sm font-bold text-neutral-900">회원 관리</h2>
          </div>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600 hover:bg-neutral-50 rounded-lg p-1.5 transition-colors cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>

        {result && (
          <div className="mx-6 mt-4 p-3 rounded-lg bg-primary-50 border border-primary-100 text-xs shrink-0">
            <p className="font-semibold text-primary-700">{result.id}님의 임시 비밀번호가 발급되었습니다.</p>
            <div className="flex items-center gap-2 mt-1.5">
              <code className="flex-1 bg-white border border-primary-100 rounded px-2 py-1.5 font-mono text-neutral-800">{result.tempPassword}</code>
              <button onClick={handleCopy} className="p-1.5 rounded-lg border border-primary-100 hover:bg-primary-100 cursor-pointer" title="복사">
                {copied ? <Check className="w-3.5 h-3.5 text-success-600" /> : <Copy className="w-3.5 h-3.5 text-primary-600" />}
              </button>
            </div>
            <p className="text-primary-500 mt-1.5">이 비밀번호를 회원에게 직접 전달하세요. 로그인 후 변경을 권장합니다.</p>
          </div>
        )}

        {error && <p className="mx-6 mt-4 text-xs text-danger-500 bg-danger-50 rounded-lg p-2.5 font-medium border border-danger-100 shrink-0">{error}</p>}

        <div className="px-6 py-4 overflow-y-auto">
          {loading ? (
            <p className="text-xs text-neutral-400 text-center py-8">불러오는 중...</p>
          ) : (
            <div className="space-y-1.5">
              {users.map(u => (
                <div key={u.id} className="flex items-center justify-between gap-3 px-3 py-2.5 rounded-xl border border-neutral-100 hover:bg-neutral-50/60">
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-bold text-neutral-800 truncate">{u.nickname}</span>
                      {u.is_admin && (
                        <span className="text-[10px] font-semibold text-primary-600 bg-primary-50 border border-primary-100 rounded px-1.5 py-0.5 shrink-0">관리자</span>
                      )}
                    </div>
                    <p className="text-[11px] text-neutral-400 truncate">{u.church} · {u.id}</p>
                  </div>
                  <button
                    onClick={() => handleReset(u)}
                    disabled={resetTarget === u.id}
                    className="flex items-center gap-1.5 text-[11px] font-semibold border border-neutral-200 text-neutral-700 rounded-lg px-2.5 py-1.5 hover:bg-neutral-100 disabled:opacity-40 cursor-pointer shrink-0"
                  >
                    <KeyRound className="w-3 h-3" />
                    {resetTarget === u.id ? '초기화 중...' : '비밀번호 초기화'}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
