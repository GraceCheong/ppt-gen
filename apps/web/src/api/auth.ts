import { apiFetch } from './client'

export interface UserInfo {
  id: string
  church: string
  nickname: string
}

export interface MeResponse {
  mode: 'guest' | 'user'
  user: UserInfo | null
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
