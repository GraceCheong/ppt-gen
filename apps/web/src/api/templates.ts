import { apiFetch } from './client'
import { getServerUrl } from './serverConfig'

export async function fetchTemplates(): Promise<string[]> {
  const data = await apiFetch<{ templates: string[] }>('/api/templates')
  return data.templates
}

export interface UploadResult {
  compatible: boolean
  template_id?: string
  filename?: string
  issues?: string[]
  warnings?: string[]
  layout_names?: string[]
}

export async function fetchDefaultTemplate(): Promise<{ template_id: string | null }> {
  return apiFetch('/api/templates/default')
}

export async function saveDefaultTemplate(templateId: string | null): Promise<void> {
  await apiFetch('/api/templates/default', {
    method: 'PUT',
    body: JSON.stringify({ template_id: templateId }),
  })
}

export async function uploadTemplate(file: File): Promise<UploadResult> {
  const base = await getServerUrl()
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${base}/api/templates/upload`, {
    method: 'POST',
    body: formData,
  })

  const body = await res.json()

  if (res.status === 422) {
    return { compatible: false, ...body }
  }
  if (!res.ok) {
    throw new Error(body.detail ?? `업로드 실패 (${res.status})`)
  }
  return { compatible: true, ...body }
}
