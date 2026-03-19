import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '../types'

interface AuthState {
  token: string | null
  user: User | null
  isAuthenticated: boolean
  sessionExpiry: number | null
  login: (token: string, user: User) => void
  logout: () => void
  setToken: (token: string) => void
  updateSessionExpiry: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      sessionExpiry: null,

      login: (token, user) =>
        set({
          token,
          user,
          isAuthenticated: true,
          sessionExpiry: Date.now() + 30 * 60 * 1000,
        }),

      logout: () =>
        set({
          token: null,
          user: null,
          isAuthenticated: false,
          sessionExpiry: null,
        }),

      setToken: (token) => set({ token }),

      updateSessionExpiry: () =>
        set({ sessionExpiry: Date.now() + 30 * 60 * 1000 }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
        sessionExpiry: state.sessionExpiry,
        // NOTE: refreshToken is NO LONGER stored in localStorage.
        // It's now in an HttpOnly cookie set by the backend.
      }),
    },
  ),
)
