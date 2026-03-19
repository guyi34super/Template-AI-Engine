/**
 * Templates API service — CRUD, version history, field management.
 */
import api from '../lib/api'
import type { Template, TemplateField } from '../types'

export interface CreateTemplatePayload {
  name: string
  description?: string
  schema_json?: TemplateField[]
}

export interface UpdateTemplatePayload {
  name?: string
  description?: string
  schema_json?: TemplateField[]
}

export const templateApi = {
  list: (params?: { status?: string; search?: string }) =>
    api.get<Template[]>('/templates', { params }).then((r) => r.data),

  get: (id: string) =>
    api.get<Template>(`/templates/${id}`).then((r) => r.data),

  create: (data: CreateTemplatePayload) =>
    api.post<Template>('/templates', data).then((r) => r.data),

  update: (id: string, data: UpdateTemplatePayload) =>
    api.put<Template>(`/templates/${id}`, data).then((r) => r.data),

  delete: (id: string) =>
    api.delete(`/templates/${id}`).then(() => undefined),

  publish: (id: string) =>
    api.post<Template>(`/templates/${id}/publish`).then((r) => r.data),

  history: (id: string) =>
    api.get<Template[]>(`/templates/${id}/history`).then((r) => r.data),

  // Fields sub-resource
  listFields: (templateId: string) =>
    api.get<TemplateField[]>(`/templates/${templateId}/fields`).then((r) => r.data),

  addField: (templateId: string, field: Partial<TemplateField>) =>
    api.post<TemplateField>(`/templates/${templateId}/fields`, field).then((r) => r.data),
}
