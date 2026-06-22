/**
 * 서버 URL 결정 로직.
 *
 * 브라우저(Vite dev/prod): Vite 프록시가 처리하므로 빈 문자열('')
 * Tauri 앱:
 *   1. PORR_SERVER_URL 환경변수(또는 기본 http://localhost:8010) 원격 서버를 먼저 시도
 *   2. 원격 서버가 응답하지 않으면 로컬 사이드카(porr-server.exe) 자동 시작
 *   3. 사이드카도 실패하면 offline 모드
 */

declare global {
  interface Window {
    __TAURI__?: unknown
    __TAURI_INTERNALS__?: unknown
  }
}

export type ServerMode = 'browser' | 'remote' | 'sidecar' | 'offline'

export interface ServerResolution {
  url: string
  mode: ServerMode
}

export function isTauri(): boolean {
  return (
    typeof window !== 'undefined' &&
    (window.__TAURI__ !== undefined || window.__TAURI_INTERNALS__ !== undefined)
  )
}

async function checkHealth(url: string, timeoutMs = 3000): Promise<boolean> {
  try {
    const res = await fetch(`${url}/health`, {
      signal: AbortSignal.timeout(timeoutMs),
    })
    return res.ok
  } catch {
    return false
  }
}

async function waitForServer(url: string, maxWaitMs = 15_000, pollMs = 500): Promise<boolean> {
  const deadline = Date.now() + maxWaitMs
  while (Date.now() < deadline) {
    if (await checkHealth(url, 2000)) return true
    await new Promise((r) => setTimeout(r, pollMs))
  }
  return false
}

let _promise: Promise<ServerResolution> | null = null

async function _doResolve(): Promise<ServerResolution> {
  if (!isTauri()) {
    return { url: '', mode: 'browser' }
  }

  const { invoke } = await import('@tauri-apps/api/core')

  // 1. 원격 서버 확인
  let remoteUrl: string
  try {
    remoteUrl = await invoke<string>('get_server_url')
  } catch {
    remoteUrl = 'http://localhost:8010'
  }

  if (await checkHealth(remoteUrl)) {
    return { url: remoteUrl, mode: 'remote' }
  }

  // 2. 로컬 사이드카 시작
  try {
    const sidecarUrl = await invoke<string>('start_sidecar')
    if (await waitForServer(sidecarUrl)) {
      return { url: sidecarUrl, mode: 'sidecar' }
    }
  } catch (e) {
    console.warn('[serverConfig] 사이드카 시작 실패:', e)
  }

  // 3. offline (원격 URL로 요청 → API 레벨에서 오류 처리)
  return { url: remoteUrl, mode: 'offline' }
}

/** 앱 마운트 시 호출해 해석을 미리 시작한다. */
export function initServerResolution(): Promise<ServerResolution> {
  if (!_promise) _promise = _doResolve()
  return _promise
}

/** 캐시를 초기화하고 재해석한다 (재연결 버튼 등에서 사용). */
export function resetServerResolution(): void {
  _promise = null
}

/** 기존 apiFetch 인터페이스와의 호환성 유지. */
export async function getServerUrl(): Promise<string> {
  return (await initServerResolution()).url
}
