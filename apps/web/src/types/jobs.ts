export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'

export interface ExportJob {
  id: string
  type: 'pptx' | 'songlist_card'
  status: JobStatus
  progress: number
  message: string | null
  download_url: string | null
  error: string | null
  created_at: string
  updated_at: string
}
