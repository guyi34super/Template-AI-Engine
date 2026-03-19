/**
 * Memory (PowerMemory) API service — search, add, delete, sessions.
 */
import api from '../lib/api'

export interface MemoryEntry {
  id: string
  content: string
  context_summary?: string
  created_at: string
}

export interface MemoryStats {
  total_memories: number
  total_sessions: number
}

export const memoryApi = {
  search: (query: string, limit = 5) =>
    api.get<MemoryEntry[]>('/memory/search', { params: { q: query, limit } }).then((r) => r.data),

  add: (content: string, metadata?: Record<string, unknown>) =>
    api.post<MemoryEntry>('/memory', { content, metadata }).then((r) => r.data),

  delete: (id: string) =>
    api.delete(`/memory/${id}`).then(() => undefined),

  stats: () =>
    api.get<MemoryStats>('/memory/stats').then((r) => r.data),

  sessions: () =>
    api.get<{ id: string; created_at: string }[]>('/memory/sessions').then((r) => r.data),
}
