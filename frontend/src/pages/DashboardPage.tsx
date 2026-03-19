import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar,
} from 'recharts'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import { useNavigate } from 'react-router-dom'
import {
  FileText, Layout, CheckCircle, Loader2,
  Upload, Plus,
} from 'lucide-react'
import { useTemplates, useExtractionJobs } from '../hooks/useApi'
import { formatDate } from '../lib/utils'


// Mock data for charts
const trendData = Array.from({ length: 30 }, (_, i) => ({
  day: `Day ${i + 1}`,
  documents: Math.floor(Math.random() * 20) + 5,
}))

const templateUsage = [
  { name: 'Employee Profile', count: 45 },
  { name: 'Invoice', count: 38 },
  { name: 'Contract', count: 22 },
  { name: 'Pay Stub', count: 18 },
  { name: 'Medical', count: 12 },
]

export default function DashboardPage() {
  const navigate = useNavigate()

  const { data: templates } = useTemplates()
  const { data: jobs } = useExtractionJobs()

  const jobsList = Array.isArray(jobs) ? jobs : (jobs as any)?.jobs ?? []

  const stats = {
    total_documents: jobsList.length,
    active_templates: templates?.length || 0,
    validation_pass_rate: 94.5,
    jobs_in_progress: jobsList.filter((j: any) => j.status === 'processing' || j.status === 'extracting').length,
  }

  const kpiCards = [
    { label: 'Documents Processed', value: stats.total_documents, icon: FileText, color: 'text-blue-400' },
    { label: 'Active Templates', value: stats.active_templates, icon: Layout, color: 'text-emerald-400' },
    { label: 'Validation Pass Rate', value: `${stats.validation_pass_rate}%`, icon: CheckCircle, color: 'text-amber-400' },
    { label: 'Jobs In Progress', value: stats.jobs_in_progress, icon: Loader2, color: 'text-purple-400' },
  ]

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text)]">Dashboard</h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            Overview of your document processing pipeline
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => navigate('/templates')}>
            <Plus size={16} /> New Template
          </Button>
          <Button onClick={() => navigate('/upload')}>
            <Upload size={16} /> Upload Documents
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {kpiCards.map((kpi) => (
          <Card key={kpi.label}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-[var(--color-text-muted)]">{kpi.label}</p>
                <p className="mt-1 text-3xl font-bold text-[var(--color-text)]">{kpi.value}</p>
              </div>
              <kpi.icon className={`${kpi.color} h-10 w-10 opacity-60`} />
            </div>
          </Card>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Extraction Trends */}
        <Card title="Extraction Trends" description="Documents processed per day (30 days)">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="day" tick={{ fill: 'var(--color-text-muted)', fontSize: 10 }} interval={4} />
                <YAxis tick={{ fill: 'var(--color-text-muted)', fontSize: 10 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: '8px',
                    color: 'var(--color-text)',
                  }}
                />
                <Line type="monotone" dataKey="documents" stroke="var(--color-primary)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Template Usage */}
        <Card title="Template Usage" description="Most used templates">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={templateUsage} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis type="number" tick={{ fill: 'var(--color-text-muted)', fontSize: 10 }} />
                <YAxis dataKey="name" type="category" width={120} tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: '8px',
                    color: 'var(--color-text)',
                  }}
                />
                <Bar dataKey="count" fill="var(--color-primary)" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* Recent Activity */}
      <Card title="Recent Activity" description="Latest document processing events">
        <div className="space-y-3">
          {(jobsList.slice(0, 8)).map((job: any) => (
            <div
              key={job.job_id}
              className="flex items-center justify-between rounded-lg border border-[var(--color-border)] p-3"
            >
              <div className="flex items-center gap-3">
                <FileText size={16} className="text-[var(--color-text-muted)]" />
                <div>
                  <p className="text-sm font-medium text-[var(--color-text)]">{job.filename || 'Document'}</p>
                  <p className="text-xs text-[var(--color-text-muted)]">{formatDate(job.created_at || new Date())}</p>
                </div>
              </div>
              <Badge
                variant={
                  job.status === 'complete' ? 'success' :
                  job.status === 'failed' ? 'danger' :
                  job.status === 'processing' ? 'warning' : 'default'
                }
              >
                {job.status}
              </Badge>
            </div>
          ))}
          {jobsList.length === 0 && (
            <p className="py-8 text-center text-sm text-[var(--color-text-muted)]">
              No recent activity. Upload a document to get started.
            </p>
          )}
        </div>
      </Card>
    </div>
  )
}
