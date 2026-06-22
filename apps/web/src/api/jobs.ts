import { apiFetch } from './client'
import type { ExportJob } from '../types/jobs'

export async function fetchJob(jobId: string): Promise<ExportJob> {
  return apiFetch<ExportJob>(`/api/jobs/${jobId}`)
}

export function getDownloadUrl(jobId: string): string {
  return `/api/jobs/${jobId}/download`
}
