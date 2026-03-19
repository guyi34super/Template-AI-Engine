import { NavLink } from 'react-router-dom'
import { useAppStore } from '../stores/appStore'
import { cn } from '../lib/utils'
import {
  LayoutDashboard,
  FileText,
  ShieldCheck,
  Upload,
  GitBranch,
  CheckCircle,
  Download,
  MessageSquare,
  Brain,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/templates', label: 'Templates', icon: FileText },
  { path: '/validation', label: 'Validation Rules', icon: ShieldCheck },
  { path: '/upload', label: 'Upload & Extract', icon: Upload },
  { path: '/map', label: 'Field Mapping', icon: GitBranch },
  { path: '/validate-results', label: 'Validation Results', icon: CheckCircle },
  { path: '/export', label: 'Export & Connect', icon: Download },
  { path: '/chat', label: 'Chat Engine', icon: MessageSquare },
  { path: '/memory', label: 'Memory', icon: Brain },
]

export default function Sidebar() {
  const sidebarOpen = useAppStore((s) => s.sidebarOpen)
  const toggleSidebar = useAppStore((s) => s.toggleSidebar)

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 flex h-full flex-col border-r border-[var(--color-border)] bg-[var(--color-surface)] transition-all duration-300',
        sidebarOpen ? 'w-64' : 'w-16',
      )}
    >
      {/* Logo */}
      <div className="flex h-16 items-center justify-between border-b border-[var(--color-border)] px-4">
        {sidebarOpen && (
          <span className="text-lg font-bold text-[var(--color-primary)]">
            AI-RAG Engine
          </span>
        )}
        <button
          onClick={toggleSidebar}
          className="rounded-lg p-1.5 text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text)]"
        >
          {sidebarOpen ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4">
        <ul className="space-y-1 px-2">
          {navItems.map((item) => (
            <li key={item.path}>
              <NavLink
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-[var(--color-primary)] text-white'
                      : 'text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text)]',
                    !sidebarOpen && 'justify-center px-0',
                  )
                }
                title={item.label}
              >
                <item.icon size={20} />
                {sidebarOpen && <span>{item.label}</span>}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/* Version */}
      {sidebarOpen && (
        <div className="border-t border-[var(--color-border)] p-4 text-xs text-[var(--color-text-muted)]">
          AI-RAG Engine v1.0.0
        </div>
      )}
    </aside>
  )
}
