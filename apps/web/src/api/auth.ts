import { apiFetch } from './client'

export interface UserInfo {
  id: string
  church: string
  nickname: string
  email?: string
  is_admin?: boolean
}

export interface MeResponse {
  mode: 'guest' | 'user'
  user: UserInfo | null
}

export interface AdminUserInfo {
  id: string
  church: string
  nickname: string
  email: string
  created_at: string
  is_admin: boolean
}

export async function fetchMe(): Promise<MeResponse> {
  return apiFetch<MeResponse>('/auth/me')
}

export async function apiLogin(id: string, pw: string): Promise<UserInfo> {
  const res = await apiFetch<{ ok: boolean; user: UserInfo }>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ id, pw }),
  })
  return res.user
}

export async function apiSignup(payload: {
  church: string
  nickname: string
  id: string
  pw: string
  email: string
}): Promise<UserInfo> {
  const res = await apiFetch<{ ok: boolean; user: UserInfo }>('/auth/signup', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return res.user
}

export async function apiLogout(): Promise<void> {
  await apiFetch('/auth/logout', { method: 'POST' })
}

export async function checkIdAvailable(id: string): Promise<{ available: boolean; reason?: string }> {
  return apiFetch(`/auth/check-id?id=${encodeURIComponent(id)}`)
}

export async function fetchChurches(): Promise<string[]> {
  const data = await apiFetch<{ churches: string[] }>('/auth/churches')
  return data.churches
}

export async function changePassword(oldPw: string, newPw: string): Promise<void> {
  await apiFetch('/auth/password', {
    method: 'PUT',
    body: JSON.stringify({ old_pw: oldPw, new_pw: newPw }),
  })
}

export async function updateEmail(email: string): Promise<string> {
  const res = await apiFetch<{ ok: boolean; email: string }>('/auth/email', {
    method: 'PUT',
    body: JSON.stringify({ email }),
  })
  return res.email
}

export async function requestPasswordReset(id: string): Promise<string> {
  const res = await apiFetch<{ ok: boolean; message: string }>('/auth/password-reset/request', {
    method: 'POST',
    body: JSON.stringify({ id }),
  })
  return res.message
}

export async function fetchAdminUsers(): Promise<AdminUserInfo[]> {
  const data = await apiFetch<{ users: AdminUserInfo[] }>('/auth/admin/users')
  return data.users
}

export async function adminResetPassword(
  userId: string,
  newPw?: string,
): Promise<{ tempPassword: string | null }> {
  const res = await apiFetch<{ ok: boolean; temp_password: string | null }>(
    `/auth/admin/users/${encodeURIComponent(userId)}/reset-password`,
    { method: 'POST', body: JSON.stringify(newPw ? { new_pw: newPw } : {}) },
  )
  return { tempPassword: res.temp_password }
}
