import { useState } from 'react'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Select from '../components/ui/Select'
import Badge from '../components/ui/Badge'
import Modal from '../components/ui/Modal'
import { Download, Database, FileText } from 'lucide-react'

const formatOptions = [
  { value: 'pdf', label: 'PDF (Branded Letterhead)' },
  { value: 'xlsx', label: 'Excel (.xlsx)' },
  { value: 'csv', label: 'CSV (Raw UTF-8)' },
  { value: 'txt', label: 'Text (Plain)' },
]

const demoHistory = [
  { id: '1', format: 'xlsx', rows: 128, timestamp: '2026-03-18T10:30:00Z', filename: 'employees_export.xlsx' },
  { id: '2', format: 'csv', rows: 45, timestamp: '2026-03-17T15:20:00Z', filename: 'invoices_batch.csv' },
  { id: '3', format: 'pdf', rows: 1, timestamp: '2026-03-16T09:00:00Z', filename: 'contract_001.pdf' },
]

export default function ExportPage() {
  const [format, setFormat] = useState('xlsx')
  const [showDbModal, setShowDbModal] = useState(false)
  const [dbConfig, setDbConfig] = useState({
    type: 'postgresql',
    host: '',
    port: '5432',
    database: '',
    username: '',
    password: '',
    schema: 'public',
    table: '',
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--color-text)]">Export & Connect</h1>
        <p className="text-sm text-[var(--color-text-muted)]">
          Download results or push directly to a connected database
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Download */}
        <Card title="Download" description="Export validated data in your preferred format">
          <div className="space-y-4">
            <Select
              label="Export Format"
              options={formatOptions}
              value={format}
              onChange={(e) => setFormat(e.target.value)}
            />
            <div className="rounded-lg border border-[var(--color-border)] p-4">
              <h4 className="text-sm font-medium text-[var(--color-text)]">Preview</h4>
              <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                128 rows • 10 columns • Template: Employee Profile
              </p>
              <div className="mt-2 rounded bg-[var(--color-bg)] p-2 font-mono text-xs text-[var(--color-text-muted)]">
                {format === 'csv' ? 'employee_id,first_name,last_name,...' :
                 format === 'xlsx' ? 'Formatted spreadsheet with headers and styling' :
                 format === 'pdf' ? 'Branded PDF with company letterhead' :
                 'Plain text with tab-separated values'}
              </div>
            </div>
            <Button className="w-full">
              <Download size={16} /> Download as {format.toUpperCase()}
            </Button>
          </div>
        </Card>

        {/* Database Connection */}
        <Card title="Connect to Database" description="Push validated data directly to your database">
          <div className="space-y-4">
            <Select
              label="Database Type"
              options={[
                { value: 'postgresql', label: 'PostgreSQL' },
                { value: 'mysql', label: 'MySQL' },
                { value: 'mongodb', label: 'MongoDB' },
              ]}
              value={dbConfig.type}
              onChange={(e) => setDbConfig({ ...dbConfig, type: e.target.value })}
            />
            <div className="grid grid-cols-2 gap-3">
              <Input
                label="Host"
                value={dbConfig.host}
                onChange={(e) => setDbConfig({ ...dbConfig, host: e.target.value })}
                placeholder="localhost"
              />
              <Input
                label="Port"
                value={dbConfig.port}
                onChange={(e) => setDbConfig({ ...dbConfig, port: e.target.value })}
                placeholder="5432"
              />
            </div>
            <Input
              label="Database Name"
              value={dbConfig.database}
              onChange={(e) => setDbConfig({ ...dbConfig, database: e.target.value })}
              placeholder="my_database"
            />
            <div className="grid grid-cols-2 gap-3">
              <Input
                label="Username"
                value={dbConfig.username}
                onChange={(e) => setDbConfig({ ...dbConfig, username: e.target.value })}
              />
              <Input
                label="Password"
                type="password"
                value={dbConfig.password}
                onChange={(e) => setDbConfig({ ...dbConfig, password: e.target.value })}
              />
            </div>
            <Input
              label="Target Table"
              value={dbConfig.table}
              onChange={(e) => setDbConfig({ ...dbConfig, table: e.target.value })}
              placeholder="employees_2026"
            />
            <Button className="w-full" onClick={() => setShowDbModal(true)}>
              <Database size={16} /> Push to Database
            </Button>
          </div>
        </Card>
      </div>

      {/* Schema Preview */}
      <Card title="Schema Preview" description="Auto-generated CREATE TABLE statement">
        <pre className="overflow-x-auto rounded-lg bg-[var(--color-bg)] p-4 text-xs text-[var(--color-text-muted)]">
{`CREATE TABLE IF NOT EXISTS employees_2026 (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id  VARCHAR(20) NOT NULL,
  first_name   VARCHAR(100) NOT NULL,
  last_name    VARCHAR(100) NOT NULL,
  email        VARCHAR(255),
  phone        VARCHAR(20),
  hire_date    DATE,
  department   VARCHAR(100),
  job_title    VARCHAR(100),
  salary       DECIMAL(12,2),
  created_at   TIMESTAMP DEFAULT NOW()
);`}
        </pre>
      </Card>

      {/* Download History */}
      <Card title="Download History" description="Previous exports (7-day retention)">
        <div className="space-y-3">
          {demoHistory.map((h) => (
            <div key={h.id} className="flex items-center justify-between rounded-lg border border-[var(--color-border)] p-3">
              <div className="flex items-center gap-3">
                <FileText size={16} className="text-[var(--color-text-muted)]" />
                <div>
                  <p className="text-sm font-medium text-[var(--color-text)]">{h.filename}</p>
                  <p className="text-xs text-[var(--color-text-muted)]">
                    {h.rows} rows • {new Date(h.timestamp).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="info">{h.format.toUpperCase()}</Badge>
                <Button variant="ghost" size="sm"><Download size={14} /></Button>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Push Confirmation Modal */}
      <Modal
        open={showDbModal}
        onClose={() => setShowDbModal(false)}
        title="Confirm Database Push"
        footer={
          <>
            <Button variant="outline" onClick={() => setShowDbModal(false)}>Cancel</Button>
            <Button onClick={() => setShowDbModal(false)}>
              <Database size={16} /> Push Data
            </Button>
          </>
        }
      >
        <div className="space-y-3 text-sm text-[var(--color-text)]">
          <p>You are about to push data to:</p>
          <div className="rounded-lg bg-[var(--color-bg)] p-4">
            <p><strong>Target:</strong> {dbConfig.type}://{dbConfig.host}:{dbConfig.port}/{dbConfig.database}</p>
            <p><strong>Table:</strong> {dbConfig.table || 'employees_2026'}</p>
            <p><strong>Rows:</strong> 128</p>
          </div>
          <p className="text-[var(--color-text-muted)]">This action cannot be undone. Proceed?</p>
        </div>
      </Modal>
    </div>
  )
}
