import { apiFetch } from './client'
import { getServerUrl } from './serverConfig'

export interface SheetFile {
  id: string
  folder_id: string | null
  song_title_key: string
  display_title: string
  normalized_title: string
  key_root: string
  key_mode: string
  key_display?: string
  page_number: number
  page_count: number | null
  version: number
  original_filename: string
  stored_filename: string
  storage_path: string
  mime_type: string
  extension: string
  size_bytes: number
  sha256: string
  status: string
  uploaded_by: string
  uploaded_at: string
  updated_at: string
  deleted_by: string | null
  deleted_at: string | null
  replaced_file_id: string | null
  is_event_only: boolean
}

export interface SheetFolder {
  id: string
  parent_id: string | null
  name: string
  path: string
  status: string
  created_by: string
  created_at: string
  updated_at: string
  deleted_by: string | null
  deleted_at: string | null
}

export interface UploadConflict {
  conflict: true
  existing_id: string
  title_key: string
  key_root: string
  key_mode: string
  page_number: number
}

export interface MeResponse {
  user_id: string
  is_super: boolean
}

export async function fetchSheetMe(): Promise<MeResponse> {
  return apiFetch<MeResponse>('/api/sheets/me')
}

export interface SyncStatus {
  enabled: boolean
  configured: boolean
  google_libs: boolean
  folder_id: string | null
}

export async function fetchSyncStatus(): Promise<SyncStatus> {
  return apiFetch<SyncStatus>('/api/sheets/sync/status')
}

export async function triggerSync(): Promise<{ message: string }> {
  return apiFetch('/api/sheets/sync', { method: 'POST' })
}

export async function searchSheets(params: {
  q?: string
  key_root?: string
  key_mode?: string
  folder_id?: string
  extension?: string
  is_event_only?: boolean
  has_key?: boolean
  uploaded_by?: string
  sort_by?: string
  sort_dir?: string
}): Promise<SheetFile[]> {
  const qs = new URLSearchParams()
  if (params.q) qs.set('q', params.q)
  if (params.key_root) qs.set('key_root', params.key_root)
  if (params.key_mode) qs.set('key_mode', params.key_mode)
  if (params.folder_id) qs.set('folder_id', params.folder_id)
  if (params.extension) qs.set('extension', params.extension)
  if (params.is_event_only != null) qs.set('is_event_only', String(params.is_event_only))
  if (params.has_key != null) qs.set('has_key', String(params.has_key))
  if (params.uploaded_by) qs.set('uploaded_by', params.uploaded_by)
  if (params.sort_by) qs.set('sort_by', params.sort_by)
  if (params.sort_dir) qs.set('sort_dir', params.sort_dir)
  const data = await apiFetch<{ items: SheetFile[] }>(`/api/sheets/search?${qs}`)
  return data.items
}

export async function uploadSheet(formData: FormData): Promise<SheetFile | UploadConflict> {
  const base = await getServerUrl()
  const res = await fetch(base + '/api/sheets/upload', {
    method: 'POST',
    credentials: 'include',
    body: formData,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {}
    throw new Error(`[${res.status}] ${detail}`)
  }
  return res.json()
}

export async function getSheet(fileId: string): Promise<SheetFile> {
  return apiFetch<SheetFile>(`/api/sheets/${fileId}`)
}

export async function downloadSheetFile(fileId: string): Promise<void> {
  const base = await getServerUrl()
  const res = await fetch(base + `/api/sheets/${fileId}/download`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`[${res.status}] 다운로드 실패`)
  const disposition = res.headers.get('Content-Disposition') ?? ''
  const match = disposition.match(/filename="(.+?)"/)
  const filename = match ? match[1] : 'download'
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export async function deleteSheet(fileId: string): Promise<void> {
  await apiFetch(`/api/sheets/${fileId}`, { method: 'DELETE' })
}

export async function restoreSheet(fileId: string): Promise<SheetFile | { conflict: true; conflicting_id: string }> {
  return apiFetch(`/api/sheets/${fileId}/restore`, { method: 'POST' })
}

export async function permanentDeleteSheet(fileId: string): Promise<void> {
  await apiFetch(`/api/sheets/${fileId}/permanent`, { method: 'DELETE' })
}

export async function listTrash(q?: string): Promise<SheetFile[]> {
  const qs = q ? `?q=${encodeURIComponent(q)}` : ''
  const data = await apiFetch<{ items: SheetFile[] }>(`/api/sheets/trash${qs}`)
  return data.items
}

export async function listFolders(parentId?: string | null): Promise<SheetFolder[]> {
  const qs = parentId ? `?parent_id=${encodeURIComponent(parentId)}` : ''
  const data = await apiFetch<{ items: SheetFolder[] }>(`/api/sheets/folders${qs}`)
  return data.items
}

export async function createFolder(name: string, parentId?: string | null): Promise<SheetFolder> {
  return apiFetch<SheetFolder>('/api/sheets/folders', {
    method: 'POST',
    body: JSON.stringify({ name, parent_id: parentId ?? null }),
  })
}

export async function renameFolder(folderId: string, name: string): Promise<SheetFolder> {
  return apiFetch<SheetFolder>(`/api/sheets/folders/${folderId}`, {
    method: 'PATCH',
    body: JSON.stringify({ name }),
  })
}

export async function deleteFolder(folderId: string): Promise<void> {
  await apiFetch(`/api/sheets/folders/${folderId}`, { method: 'DELETE' })
}

export async function restoreFolder(folderId: string): Promise<void> {
  await apiFetch(`/api/sheets/folders/${folderId}/restore`, { method: 'POST' })
}

export async function permanentDeleteFolder(folderId: string): Promise<void> {
  await apiFetch(`/api/sheets/folders/${folderId}/permanent`, { method: 'DELETE' })
}

export async function getSheetsBySong(titleKey: string): Promise<SheetFile[]> {
  const data = await apiFetch<{ items: SheetFile[] }>(`/api/sheets/by-song/${encodeURIComponent(titleKey)}`)
  return data.items
}

export async function getSheetsByTitles(
  titleKeys: string[]
): Promise<Record<string, (SheetFile & { key_display: string })[]>> {
  return apiFetch('/api/sheets/by-titles', {
    method: 'POST',
    body: JSON.stringify({ title_keys: titleKeys }),
  })
}

export async function downloadSheetsBySongKey(
  titleKey: string,
  keyRoot: string,
  keyMode: string
): Promise<void> {
  const base = await getServerUrl()
  const qs = new URLSearchParams({ key_root: keyRoot, key_mode: keyMode })
  const res = await fetch(
    base + `/api/sheets/by-song/${encodeURIComponent(titleKey)}/download?${qs}`,
    { credentials: 'include' }
  )
  if (!res.ok) throw new Error(`[${res.status}] 다운로드 실패`)
  const disposition = res.headers.get('Content-Disposition') ?? ''
  const match = disposition.match(/filename="(.+?)"/)
  const filename = match ? match[1] : 'sheets.zip'
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
