/**
 * Chat API service — send messages, get history.
 */
import api from '../lib/api'

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp?: string
}

export interface ChatResponse {
  reply: string
  result?: string
  message?: string
  context?: Record<string, unknown>
}

export const chatApi = {
  send: (message: string, sessionId?: string) =>
    api
      .post<ChatResponse>('/chat', { message, session_id: sessionId })
      .then((r) => r.data),

  history: (sessionId: string) =>
    api.get<ChatMessage[]>(`/chat/history/${sessionId}`).then((r) => r.data),
}
