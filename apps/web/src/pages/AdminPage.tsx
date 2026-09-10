import { useEffect, useState } from 'react'
import { Clipboard, KeyRound, RefreshCw, Search, ShieldCheck, Users } from 'lucide-react'
import { adminResetPassword, fetchAdminUsers, type AdminUserInfo } from '../api/auth'

export function AdminPage() {
  const [users, setUsers] = useState<AdminUserInfo[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [resettingId, setResettingId] = useState<string | null>(null)
  const [temporaryPassword, setTemporaryPassword] = useState<{ userId: string; value: string } | null>(null)
  const [copied, setCopied] = useState(false)

  async function loadUsers() {
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

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadUsers()
  }, [])

  async function handleReset(user: AdminUserInfo) {
    if (!window.confirm(`${user.nickname}님의 비밀번호를 초기화할까요?`)) return
    setResettingId(user.id)
    setTemporaryPassword(null)
    setError(null)
    try {
      const result = await adminResetPassword(user.id)
      if (result.tempPassword) setTemporaryPassword({ userId: user.id, value: result.tempPassword })
    } catch (err) {
      setError(err instanceof Error ? err.message : '비밀번호 초기화에 실패했습니다.')
    } finally {
      setResettingId(null)
    }
  }

  async function copyPassword() {
    if (!temporaryPassword) return
    await navigator.clipboard.writeText(temporaryPassword.value)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1500)
  }

  const normalizedQuery = query.trim().toLowerCase()
  const filteredUsers = users.filter(user =>
    !normalizedQuery || [user.id, user.nickname, user.church].some(value => value.toLowerCase().includes(normalizedQuery)),
  )

  return (
    <main className="h-full overflow-y-auto bg-neutral-50 px-4 py-6 sm:px-8">
      <div className="mx-auto max-w-5xl">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="mb-2 flex items-center gap-2 text-primary-600">
              <ShieldCheck className="h-5 w-5" />
              <span className="text-xs font-bold uppercase tracking-widest">Admin</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-neutral-900">회원 관리</h1>
            <p className="mt-1 text-sm text-neutral-500">가입 회원을 확인하고 비밀번호를 초기화할 수 있습니다.</p>
          </div>
          <button
            type="button"
            onClick={() => void loadUsers()}
            disabled={loading}
            title="회원 목록 새로고침"
            className="flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-700 shadow-sm transition hover:bg-neutral-50 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            새로고침
          </button>
        </div>

        {error && <p className="mb-4 rounded-lg border border-danger-100 bg-danger-50 px-3 py-2 text-sm text-danger-600">{error}</p>}

        {temporaryPassword && (
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-warning-100 bg-warning-50 px-4 py-3">
            <div>
              <p className="text-xs font-semibold text-warning-600">{temporaryPassword.userId} 임시 비밀번호</p>
              <code className="mt-1 block text-base font-bold tracking-wider text-neutral-900">{temporaryPassword.value}</code>
            </div>
            <button type="button" onClick={() => void copyPassword()} className="flex items-center gap-1.5 rounded-md border border-warning-200 bg-white px-3 py-2 text-xs font-semibold text-warning-700 hover:bg-warning-50">
              <Clipboard className="h-3.5 w-3.5" />
              {copied ? '복사됨' : '복사'}
            </button>
          </div>
        )}

        <section className="overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-neutral-100 px-4 py-3">
            <div className="flex items-center gap-2 text-sm font-bold text-neutral-800">
              <Users className="h-4 w-4 text-primary-500" />
              전체 회원 <span className="text-neutral-400">{users.length}명</span>
            </div>
            <label className="flex w-full items-center gap-2 rounded-md border border-neutral-200 bg-neutral-50 px-2.5 py-1.5 sm:w-64">
              <Search className="h-3.5 w-3.5 text-neutral-400" />
              <input value={query} onChange={e => setQuery(e.target.value)} placeholder="아이디, 닉네임, 교회 검색" className="min-w-0 flex-1 bg-transparent text-xs outline-none placeholder:text-neutral-400" />
            </label>
          </div>

          {loading ? <p className="px-4 py-10 text-center text-sm text-neutral-400">불러오는 중...</p> : filteredUsers.length === 0 ? <p className="px-4 py-10 text-center text-sm text-neutral-400">회원이 없습니다.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[620px] text-left text-sm">
                <thead className="bg-neutral-50 text-xs text-neutral-500">
                  <tr><th className="px-4 py-3 font-semibold">아이디</th><th className="px-4 py-3 font-semibold">닉네임</th><th className="px-4 py-3 font-semibold">교회</th><th className="px-4 py-3 font-semibold">이메일</th><th className="px-4 py-3 font-semibold">가입일</th><th className="px-4 py-3 text-right font-semibold">관리</th></tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {filteredUsers.map(user => (
                    <tr key={user.id} className="hover:bg-neutral-50/70">
                      <td className="px-4 py-3 font-semibold text-neutral-800">{user.id}{user.is_admin && <span className="ml-2 rounded bg-primary-50 px-1.5 py-0.5 text-[10px] text-primary-600">관리자</span>}</td>
                      <td className="px-4 py-3 text-neutral-600">{user.nickname}</td>
                      <td className="px-4 py-3 text-neutral-600">{user.church}</td>
                      <td className="px-4 py-3 text-neutral-500">{user.email || <span className="text-neutral-300">미등록</span>}</td>
                      <td className="px-4 py-3 text-xs text-neutral-400">{user.created_at ? new Date(user.created_at).toLocaleDateString('ko-KR') : '-'}</td>
                      <td className="px-4 py-3 text-right"><button type="button" onClick={() => void handleReset(user)} disabled={resettingId === user.id} className="inline-flex items-center gap-1.5 rounded-md border border-neutral-200 px-2.5 py-1.5 text-xs font-semibold text-neutral-600 hover:border-primary-200 hover:bg-primary-50 hover:text-primary-700 disabled:opacity-50"><KeyRound className="h-3.5 w-3.5" />{resettingId === user.id ? '처리 중' : '비밀번호 초기화'}</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </main>
  )
}
