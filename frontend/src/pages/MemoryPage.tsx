import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import { Brain, Search, Trash2, Clock, Database } from 'lucide-react'
import { useMemoryStats, useMemorySessions, useMemorySearch } from '../hooks/useApi'
import { useState } from 'react'
import Input from '../components/ui/Input'

export default function MemoryPage() {
  const [searchQuery, setSearchQuery] = useState('')

  const { data: stats } = useMemoryStats()
  const { data: sessions = [] } = useMemorySessions()
  const { data: searchResults } = useMemorySearch(searchQuery)

  const statCards = [
    { label: 'Total Memories', value: stats?.total_memories || 0, icon: Brain, color: 'text-purple-400' },
    { label: 'Active Sessions', value: stats?.total_sessions || sessions.length, icon: Clock, color: 'text-blue-400' },
    { label: 'Memory Store', value: 'SQLite', icon: Database, color: 'text-emerald-400' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text)]">Memory Engine</h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            Cross-session AI memory — Supermemory integration for persistent context
          </p>
        </div>
        <Button variant="danger">
          <Trash2 size={16} /> Clear All Memories
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {statCards.map((s) => (
          <Card key={s.label}>
            <div className="flex items-center gap-4">
              <s.icon className={`${s.color} h-10 w-10`} />
              <div>
                <p className="text-sm text-[var(--color-text-muted)]">{s.label}</p>
                <p className="text-2xl font-bold text-[var(--color-text)]">{s.value}</p>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Memory Search */}
      <Card title="Semantic Search" description="Search memories by meaning, not just keywords">
        <div className="flex gap-3">
          <div className="flex-1">
            <Input
              placeholder="Search memories... (e.g., 'employee onboarding preferences')"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <Button>
            <Search size={16} /> Search
          </Button>
        </div>
        {/* Search Results */}
        {searchResults && searchResults.length > 0 && (
          <div className="mt-4 space-y-2">
            {searchResults.map((r: any, idx: number) => (
              <div key={idx} className="rounded-lg border border-[var(--color-border)] p-3 text-sm text-[var(--color-text)]">
                {r.content || r.context_summary || JSON.stringify(r)}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Sessions */}
      <Card title="Memory Sessions" description="Active and historical sessions">
        <div className="space-y-3">
          {sessions.map((session: any) => (
            <div
              key={session.session_id}
              className="flex items-center justify-between rounded-lg border border-[var(--color-border)] p-4"
            >
              <div className="flex items-center gap-3">
                <Brain size={16} className="text-[var(--color-primary)]" />
                <div>
                  <p className="text-sm font-medium text-[var(--color-text)]">
                    Session {session.session_id?.slice(0, 8)}
                  </p>
                  <p className="text-xs text-[var(--color-text-muted)]">
                    {session.message_count || 0} messages
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="info">Active</Badge>
                <Button variant="ghost" size="sm"><Trash2 size={14} /></Button>
              </div>
            </div>
          ))}
          {sessions.length === 0 && (
            <p className="py-8 text-center text-sm text-[var(--color-text-muted)]">
              No memory sessions yet. Interactions across the platform will build your AI memory.
            </p>
          )}
        </div>
      </Card>

      {/* How it works */}
      <Card title="How Memory Works">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {[
            { step: '1', title: 'Extract', desc: 'Document summaries and extraction results are automatically stored as memories.' },
            { step: '2', title: 'Recall', desc: 'Top-5 relevant memories are retrieved and injected into every LLM call for richer context.' },
            { step: '3', title: 'Learn', desc: 'Mapping preferences and document patterns are remembered across sessions.' },
          ].map((item) => (
            <div key={item.step} className="rounded-lg border border-[var(--color-border)] p-4">
              <div className="mb-2 flex h-8 w-8 items-center justify-center rounded-full bg-[var(--color-primary)] text-sm font-bold text-white">
                {item.step}
              </div>
              <h4 className="text-sm font-semibold text-[var(--color-text)]">{item.title}</h4>
              <p className="mt-1 text-xs text-[var(--color-text-muted)]">{item.desc}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
