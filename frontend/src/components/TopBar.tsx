import { useAuthStore } from '../stores/authStore'
import { LogOut, User, Clock } from 'lucide-react'
import { useEffect, useState } from 'react'

export default function TopBar() {
  const user = useAuthStore((s) => s.user)
  const sessionExpiry = useAuthStore((s) => s.sessionExpiry)
  const logout = useAuthStore((s) => s.logout)
  const updateSessionExpiry = useAuthStore((s) => s.updateSessionExpiry)
  const [timeLeft, setTimeLeft] = useState('')

  // Session countdown timer
  useEffect(() => {
    const interval = setInterval(() => {
      if (sessionExpiry) {
        const remaining = Math.max(0, sessionExpiry - Date.now())
        const minutes = Math.floor(remaining / 60000)
        const seconds = Math.floor((remaining % 60000) / 1000)
        setTimeLeft(`${minutes}:${seconds.toString().padStart(2, '0')}`)

        if (remaining <= 0) {
          logout()
          window.location.href = '/login'
        }
      }
    }, 1000)
    return () => clearInterval(interval)
  }, [sessionExpiry, logout])

  // Reset session timer on activity
  useEffect(() => {
    const resetTimer = () => updateSessionExpiry()
    window.addEventListener('click', resetTimer)
    window.addEventListener('keypress', resetTimer)
    return () => {
      window.removeEventListener('click', resetTimer)
      window.removeEventListener('keypress', resetTimer)
    }
  }, [updateSessionExpiry])

  return (
    <header className="flex h-16 items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-surface)] px-6">
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-semibold text-[var(--color-text)]">
          AI-RAG Document Processing Engine
        </h1>
      </div>

      <div className="flex items-center gap-6">
        {/* Session timer */}
        <div className="flex items-center gap-2 text-sm text-[var(--color-text-muted)]">
          <Clock size={14} />
          <span>Session: {timeLeft}</span>
        </div>

        {/* User info */}
        <div className="flex items-center gap-2 text-sm">
          <User size={14} className="text-[var(--color-text-muted)]" />
          <span className="text-[var(--color-text)]">{user?.email || 'User'}</span>
          <span className="rounded-full bg-[var(--color-primary)] px-2 py-0.5 text-xs text-white">
            {user?.role || 'editor'}
          </span>
        </div>

        {/* Logout */}
        <button
          onClick={logout}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-danger)]"
        >
          <LogOut size={16} />
          Logout
        </button>
      </div>
    </header>
  )
}
