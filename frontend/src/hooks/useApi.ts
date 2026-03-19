/**
 * React Query hooks — thin wrappers around API services.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { templateApi } from '../services/templateService'
import { extractionApi } from '../services/extractionService'
import { validationApi } from '../services/validationService'
import { mappingApi } from '../services/mappingService'
import { exportApi } from '../services/exportService'
import { chatApi } from '../services/chatService'
import { memoryApi } from '../services/memoryService'
import type { ValidationRule } from '../types'

// ─── Templates ────────────────────────────────────────────────────
export const useTemplates = (params?: { status?: string; search?: string }) =>
  useQuery({ queryKey: ['templates', params], queryFn: () => templateApi.list(params) })

export const useTemplate = (id: string) =>
  useQuery({ queryKey: ['template', id], queryFn: () => templateApi.get(id), enabled: !!id })

export const useCreateTemplate = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: templateApi.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['templates'] }),
  })
}

export const useUpdateTemplate = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof templateApi.update>[1] }) =>
      templateApi.update(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['templates'] }),
  })
}

export const useDeleteTemplate = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: templateApi.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['templates'] }),
  })
}

export const usePublishTemplate = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: templateApi.publish,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['templates'] }),
  })
}

// ─── Extraction ───────────────────────────────────────────────────
export const useExtractionJobs = () =>
  useQuery({ queryKey: ['extraction-jobs'], queryFn: extractionApi.listJobs })

export const useExtractionJob = (jobId: string) =>
  useQuery({
    queryKey: ['extraction-job', jobId],
    queryFn: () => extractionApi.getJob(jobId),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'complete' || status === 'failed' ? false : 2000
    },
  })

export const useUploadFiles = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ files, templateId }: { files: File[]; templateId?: string }) =>
      extractionApi.upload(files, templateId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['extraction-jobs'] }),
  })
}

// ─── Validation ───────────────────────────────────────────────────
export const useValidationPatterns = () =>
  useQuery({ queryKey: ['validation-patterns'], queryFn: validationApi.patterns })

export const useValidate = () =>
  useMutation({
    mutationFn: ({ data, rules }: { data: Record<string, unknown>; rules: ValidationRule[] }) =>
      validationApi.validate(data, rules),
  })

// ─── Mapping ──────────────────────────────────────────────────────
export const useAutoMap = () =>
  useMutation({ mutationFn: mappingApi.autoMap })

export const useMappingConfigs = () =>
  useQuery({ queryKey: ['mapping-configs'], queryFn: mappingApi.list })

// ─── Export ───────────────────────────────────────────────────────
export const useExportDownload = () =>
  useMutation({ mutationFn: exportApi.download })

export const useExportDbPush = () =>
  useMutation({ mutationFn: exportApi.pushToDb })

export const useExportJob = (jobId: string) =>
  useQuery({
    queryKey: ['export-job', jobId],
    queryFn: () => exportApi.getJob(jobId),
    enabled: !!jobId,
    refetchInterval: (query) =>
      query.state.data?.status === 'complete' || query.state.data?.status === 'failed'
        ? false
        : 3000,
  })

// ─── Chat ─────────────────────────────────────────────────────────
export const useSendChat = () =>
  useMutation({ mutationFn: ({ message, sessionId }: { message: string; sessionId?: string }) => chatApi.send(message, sessionId) })

// ─── Memory ───────────────────────────────────────────────────────
export const useMemorySearch = (query: string) =>
  useQuery({
    queryKey: ['memory-search', query],
    queryFn: () => memoryApi.search(query),
    enabled: query.length > 0,
  })

export const useMemoryStats = () =>
  useQuery({ queryKey: ['memory-stats'], queryFn: memoryApi.stats })

export const useMemorySessions = () =>
  useQuery({ queryKey: ['memory-sessions'], queryFn: memoryApi.sessions })
