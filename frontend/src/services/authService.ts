/**
 * Auth API service — register, login, refresh, logout, MFA.
 */
import api from '../lib/api'
import type { User } from '../types'

export interface LoginPayload {
  email: string
  password: string
}

export interface RegisterPayload {
  email: string
  password: string
  role?: string
}

export interface TokenResponse {
  access_token: string
  refresh_token?: string
  token_type: string
  expires_in: number
  user: User
}

export const authApi = {
  login: (data: LoginPayload) =>
    api.post<TokenResponse>('/auth/login', data).then((r) => r.data),

  register: (data: RegisterPayload) =>
    api.post<TokenResponse>('/auth/register', data).then((r) => r.data),

  // Refresh token is sent automatically as HttpOnly cookie
  refresh: () =>
    api.post<TokenResponse>('/auth/refresh').then((r) => r.data),

  logout: () => api.post('/auth/logout').then(() => undefined),

  mfaSetup: () =>
    api.post<{ secret: string; qr_uri: string }>('/auth/mfa/setup').then((r) => r.data),

  mfaVerify: (code: string) =>
    api.post<{ verified: boolean; mfa_enabled: boolean }>(`/auth/mfa/verify?code=${code}`).then((r) => r.data),
}
