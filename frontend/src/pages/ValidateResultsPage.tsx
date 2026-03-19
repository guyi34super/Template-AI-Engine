import { useState } from 'react'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { CheckCircle, XCircle, AlertTriangle, Edit2, Download } from 'lucide-react'
import type { ValidationResult } from '../types'

// Demo validation results
const demoResults: (ValidationResult & { editable?: boolean })[] = [
  { field_name: 'employee_id', status: 'pass', value: 'EMP-00491', cleaned_value: 'EMP-00491' },
  { field_name: 'first_name', status: 'pass', value: 'John', cleaned_value: 'John' },
  { field_name: 'email', status: 'pass', value: 'john.doe@company.com', cleaned_value: 'john.doe@company.com' },
  { field_name: 'phone', status: 'fail', value: '011-555-0100', error_msg: 'Does not match E.164 format. Expected: +27115550100', rule_violated: 'phone_e164' },
  { field_name: 'hire_date', status: 'pass', value: '2024-03-15', cleaned_value: '2024-03-15' },
  { field_name: 'salary', status: 'warning', value: '0', error_msg: 'Value is zero — confirm intentional', rule_violated: 'min' },
  { field_name: 'department', status: 'pass', value: 'Engineering', cleaned_value: 'Engineering' },
  { field_name: 'id_number', status: 'fail', value: '9001015800086', error_msg: 'Checksum digit invalid', rule_violated: 'id_checksum' },
  { field_name: 'iban', status: 'pass', value: 'ZA12345678901234', cleaned_value: 'ZA12345678901234' },
  { field_name: 'postal_code', status: 'warning', value: '00000', error_msg: 'Unusual postal code — verify', rule_violated: 'postal_code_za' },
]

export default function ValidateResultsPage() {
  const [results, setResults] = useState(demoResults)
  const [editingField, setEditingField] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')

  const stats = {
    pass: results.filter((r) => r.status === 'pass').length,
    fail: results.filter((r) => r.status === 'fail').length,
    warning: results.filter((r) => r.status === 'warning').length,
  }

  const allResolved = stats.fail === 0

  const startEdit = (field: string, value: string) => {
    setEditingField(field)
    setEditValue(value)
  }

  const saveEdit = (field: string) => {
    setResults((prev) =>
      prev.map((r) =>
        r.field_name === field
          ? { ...r, value: editValue, status: 'pass', error_msg: undefined, cleaned_value: editValue }
          : r,
      ),
    )
    setEditingField(null)
  }

  const acceptAllWarnings = () => {
    setResults((prev) =>
      prev.map((r) => (r.status === 'warning' ? { ...r, status: 'pass' } : r)),
    )
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pass': return <CheckCircle size={16} className="text-emerald-400" />
      case 'fail': return <XCircle size={16} className="text-red-400" />
      case 'warning': return <AlertTriangle size={16} className="text-amber-400" />
      default: return null
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text)]">Validation Results</h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            Field-level validation with inline editing and re-validation
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={acceptAllWarnings}>Accept All Warnings</Button>
          <Button variant="outline">
            <Download size={16} /> Export CSV
          </Button>
          <Button disabled={!allResolved}>
            Proceed to Export
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="flex gap-4">
        <div className="flex items-center gap-2 rounded-lg bg-emerald-500/10 px-4 py-2">
          <CheckCircle size={16} className="text-emerald-400" />
          <span className="text-sm font-medium text-emerald-400">{stats.pass} Pass</span>
        </div>
        <div className="flex items-center gap-2 rounded-lg bg-red-500/10 px-4 py-2">
          <XCircle size={16} className="text-red-400" />
          <span className="text-sm font-medium text-red-400">{stats.fail} Fail</span>
        </div>
        <div className="flex items-center gap-2 rounded-lg bg-amber-500/10 px-4 py-2">
          <AlertTriangle size={16} className="text-amber-400" />
          <span className="text-sm font-medium text-amber-400">{stats.warning} Warning</span>
        </div>
      </div>

      {/* Results Table */}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="pb-3 text-left text-xs font-semibold text-[var(--color-text-muted)]">Status</th>
                <th className="pb-3 text-left text-xs font-semibold text-[var(--color-text-muted)]">Field</th>
                <th className="pb-3 text-left text-xs font-semibold text-[var(--color-text-muted)]">Value</th>
                <th className="pb-3 text-left text-xs font-semibold text-[var(--color-text-muted)]">Error / Note</th>
                <th className="pb-3 text-left text-xs font-semibold text-[var(--color-text-muted)]">Actions</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr
                  key={r.field_name}
                  className={`border-b border-[var(--color-border)] ${
                    r.status === 'fail' ? 'bg-red-500/5' :
                    r.status === 'warning' ? 'bg-amber-500/5' : ''
                  }`}
                >
                  <td className="py-3 pr-3">{getStatusIcon(r.status)}</td>
                  <td className="py-3 pr-3 font-medium text-[var(--color-text)]">{r.field_name}</td>
                  <td className="py-3 pr-3">
                    {editingField === r.field_name ? (
                      <div className="flex items-center gap-2">
                        <input
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          className="rounded border border-[var(--color-primary)] bg-[var(--color-bg)] px-2 py-1 text-sm text-[var(--color-text)] focus:outline-none"
                          autoFocus
                        />
                        <Button size="sm" onClick={() => saveEdit(r.field_name)}>Save</Button>
                      </div>
                    ) : (
                      <code className="text-[var(--color-text)]">{r.value}</code>
                    )}
                  </td>
                  <td className="py-3 pr-3 text-xs text-[var(--color-text-muted)]">
                    {r.error_msg || '—'}
                  </td>
                  <td className="py-3">
                    {r.status === 'fail' && editingField !== r.field_name && (
                      <Button variant="ghost" size="sm" onClick={() => startEdit(r.field_name, r.value)}>
                        <Edit2 size={12} /> Edit
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
