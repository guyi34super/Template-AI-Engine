import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { useMutation } from '@tanstack/react-query'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import { Upload, FileText, X, RefreshCw, Check, AlertCircle, Loader2 } from 'lucide-react'
import api from '../lib/api'
import { formatFileSize } from '../lib/utils'
import { useAppStore } from '../stores/appStore'

type FileStatus = 'pending' | 'uploading' | 'scanning' | 'extracting' | 'classifying' | 'complete' | 'failed'

interface UploadFile {
  id: string
  file: File
  status: FileStatus
  progress: number
  result?: any
  error?: string
  jobId?: string
}

const statusPipeline: FileStatus[] = ['uploading', 'scanning', 'extracting', 'classifying', 'complete']

export default function UploadPage() {
  const [files, setFiles] = useState<UploadFile[]>([])
  const addJob = useAppStore((s) => s.addJob)

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newFiles: UploadFile[] = acceptedFiles.map((file) => ({
      id: crypto.randomUUID(),
      file,
      status: 'pending' as FileStatus,
      progress: 0,
    }))
    setFiles((prev) => [...prev, ...newFiles])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      'text/csv': ['.csv'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
    },
    maxSize: 50 * 1024 * 1024, // 50 MB
  })

  const uploadMutation = useMutation({
    mutationFn: async (uploadFile: UploadFile) => {
      const formData = new FormData()
      formData.append('file', uploadFile.file)

      // Update status through pipeline
      const updateStatus = (status: FileStatus) => {
        setFiles((prev) =>
          prev.map((f) => (f.id === uploadFile.id ? { ...f, status } : f)),
        )
      }

      updateStatus('uploading')

      try {
        const res = await api.post('/extract/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })

        updateStatus('scanning')
        await new Promise((r) => setTimeout(r, 500))
        updateStatus('extracting')

        // Poll for result
        const jobId = res.data.job_id
        let attempts = 0
        while (attempts < 60) {
          await new Promise((r) => setTimeout(r, 2000))
          try {
            const jobRes = await api.get(`/extract/jobs/${jobId}`)
            if (jobRes.data.status === 'complete') {
              setFiles((prev) =>
                prev.map((f) =>
                  f.id === uploadFile.id
                    ? { ...f, status: 'complete', result: jobRes.data, jobId }
                    : f,
                ),
              )
              addJob({
                job_id: jobId,
                filename: uploadFile.file.name,
                status: 'complete',
                extracted_data: jobRes.data.extracted_data,
                created_at: new Date().toISOString(),
              })
              return jobRes.data
            }
            if (jobRes.data.status === 'failed') {
              throw new Error(jobRes.data.error || 'Extraction failed')
            }
            // Update status based on server
            if (jobRes.data.status === 'classifying') updateStatus('classifying')
          } catch (err: any) {
            if (err.response?.status !== 404) throw err
          }
          attempts++
        }
        throw new Error('Extraction timed out')
      } catch (err: any) {
        setFiles((prev) =>
          prev.map((f) =>
            f.id === uploadFile.id
              ? { ...f, status: 'failed', error: err.message }
              : f,
          ),
        )
        throw err
      }
    },
  })

  const uploadAll = () => {
    files
      .filter((f) => f.status === 'pending' || f.status === 'failed')
      .forEach((f) => uploadMutation.mutate(f))
  }

  const removeFile = (id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id))
  }

  const getStatusIcon = (status: FileStatus) => {
    switch (status) {
      case 'complete': return <Check size={16} className="text-emerald-400" />
      case 'failed': return <AlertCircle size={16} className="text-red-400" />
      case 'pending': return <FileText size={16} className="text-[var(--color-text-muted)]" />
      default: return <Loader2 size={16} className="animate-spin text-[var(--color-primary)]" />
    }
  }

  const getStatusVariant = (status: FileStatus) => {
    switch (status) {
      case 'complete': return 'success' as const
      case 'failed': return 'danger' as const
      case 'pending': return 'default' as const
      default: return 'warning' as const
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text)]">Upload & Extract</h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            Drag-and-drop multi-file upload with real-time extraction progress
          </p>
        </div>
        {files.length > 0 && (
          <Button onClick={uploadAll} loading={uploadMutation.isPending}>
            <Upload size={16} /> Extract All
          </Button>
        )}
      </div>

      {/* Dropzone */}
      <Card>
        <div
          {...getRootProps()}
          className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-12 transition-colors ${
            isDragActive
              ? 'border-[var(--color-primary)] bg-[var(--color-primary)]/5'
              : 'border-[var(--color-border)] hover:border-[var(--color-primary)]/50'
          }`}
        >
          <input {...getInputProps()} />
          <Upload size={48} className="mb-4 text-[var(--color-text-muted)]" />
          <p className="text-lg font-medium text-[var(--color-text)]">
            {isDragActive ? 'Drop files here...' : 'Drag & drop files here'}
          </p>
          <p className="mt-2 text-sm text-[var(--color-text-muted)]">
            PDF, XLSX, DOCX, CSV, TXT, PNG, JPG — max 50 MB per file
          </p>
          <Button variant="outline" className="mt-4">Browse Files</Button>
        </div>
      </Card>

      {/* File List */}
      {files.length > 0 && (
        <Card title={`Files (${files.length})`}>
          <div className="space-y-3">
            {files.map((f) => (
              <div
                key={f.id}
                className="flex items-center gap-4 rounded-lg border border-[var(--color-border)] p-4"
              >
                {getStatusIcon(f.status)}
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-[var(--color-text)]">{f.file.name}</span>
                    <span className="text-xs text-[var(--color-text-muted)]">{formatFileSize(f.file.size)}</span>
                  </div>
                  {f.error && (
                    <p className="mt-1 text-xs text-[var(--color-danger)]">{f.error}</p>
                  )}
                  {/* Status Pipeline */}
                  {f.status !== 'pending' && f.status !== 'failed' && (
                    <div className="mt-2 flex items-center gap-1">
                      {statusPipeline.map((s, idx) => (
                        <div key={s} className="flex items-center gap-1">
                          <div
                            className={`h-1.5 w-8 rounded-full ${
                              statusPipeline.indexOf(f.status) >= idx
                                ? 'bg-[var(--color-primary)]'
                                : 'bg-[var(--color-border)]'
                            }`}
                          />
                          {idx < statusPipeline.length - 1 && (
                            <span className="text-[8px] text-[var(--color-text-muted)]">›</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <Badge variant={getStatusVariant(f.status)}>{f.status}</Badge>
                {f.status === 'failed' && (
                  <Button variant="ghost" size="sm" onClick={() => uploadMutation.mutate(f)}>
                    <RefreshCw size={14} />
                  </Button>
                )}
                <Button variant="ghost" size="sm" onClick={() => removeFile(f.id)}>
                  <X size={14} />
                </Button>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
