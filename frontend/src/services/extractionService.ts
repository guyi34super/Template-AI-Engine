/**
 * Extraction / Upload API service — file upload, job tracking, WebSocket progress.
 */
import api from '../lib/api'
import type { ExtractionJob } from '../types'

export const extractionApi = {
  upload: (files: File[], templateId?: string) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    if (templateId) form.append('template_id', templateId)
    return api
      .post<ExtractionJob>('/extract', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120_000,
      })
      .then((r) => r.data)
  },

  getJob: (jobId: string) =>
    api.get<ExtractionJob>(`/extract/jobs/${jobId}`).then((r) => r.data),

  listJobs: () =>
    api.get<ExtractionJob[]>('/extract/jobs').then((r) => r.data),

  deleteJob: (jobId: string) =>
    api.delete(`/extract/jobs/${jobId}`).then(() => undefined),

  /**
   * Open a WebSocket connection for real-time extraction progress.
   * Returns a WebSocket instance; caller should attach onmessage / onclose.
   */
  connectProgress: (jobId: string): WebSocket => {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.host
    return new WebSocket(`${protocol}://${host}/api/ws/extract/${jobId}`)
  },
}
