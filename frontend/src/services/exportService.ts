/**
 * Export API service — download files, push to DB, poll jobs.
 */
import api from '../lib/api'

export interface DownloadPayload {
  document_id: string
  format: 'xlsx' | 'csv' | 'json' | 'txt'
  data?: Record<string, unknown>
}

export interface DatabasePushPayload {
  document_id: string
  db_type: string
  host: string
  port: number
  database: string
  username: string
  password: string
  schema?: string
  table: string
}

export interface ExportJob {
  id: string
  document_id: string
  format: string
  status: 'processing' | 'complete' | 'failed'
  file_path?: string
  created_at: string
  completed_at?: string
  error?: string
}

export const exportApi = {
  download: (payload: DownloadPayload) =>
    api.post<{ job_id: string; download_url: string }>('/export/download', payload).then((r) => r.data),

  pushToDb: (payload: DatabasePushPayload) =>
    api.post<{ job_id: string; status: string }>('/export/database', payload).then((r) => r.data),

  getJob: (jobId: string) =>
    api.get<ExportJob>(`/export/jobs/${jobId}`).then((r) => r.data),

  /** Download the generated file directly via browser */
  downloadFile: (jobId: string) => {
    const url = `/api/export/jobs/${jobId}/file`
    window.open(url, '_blank')
  },
}
