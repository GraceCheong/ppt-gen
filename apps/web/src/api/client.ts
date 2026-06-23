import { getServerUrl } from './serverConfig'

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const base = await getServerUrl()
  const res = await fetch(base + path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {}
    throw new Error(`[${res.status}] ${detail}`)
  }
  return res.json() as Promise<T>
}
