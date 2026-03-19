/**
 * Mapping API service — auto-map, save, load configs.
 */
import api from '../lib/api'
import type { MappingConfig, FieldMapping } from '../types'

export interface AutoMapPayload {
  source_schema: string[]
  target_schema: string[]
}

export const mappingApi = {
  autoMap: (payload: AutoMapPayload) =>
    api
      .post<{ mappings: FieldMapping[]; confidence: number }>('/mapping/auto-map', payload)
      .then((r) => r.data),

  save: (config: Omit<MappingConfig, 'id'>) =>
    api.post<MappingConfig>('/mapping/configs', config).then((r) => r.data),

  list: () =>
    api.get<MappingConfig[]>('/mapping/configs').then((r) => r.data),

  get: (id: string) =>
    api.get<MappingConfig>(`/mapping/configs/${id}`).then((r) => r.data),

  delete: (id: string) =>
    api.delete(`/mapping/configs/${id}`).then(() => undefined),
}
