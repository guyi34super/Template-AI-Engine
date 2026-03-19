import { useState } from 'react'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Badge from '../components/ui/Badge'
import Select from '../components/ui/Select'
import { Plus, Play, Download, Trash2 } from 'lucide-react'

const builtInPatterns = [
  { name: 'Email (RFC 5322)', category: 'Contact', pattern: '^[\\w.-]+@[\\w.-]+\\.[a-zA-Z]{2,}$' },
  { name: 'Phone (E.164)', category: 'Contact', pattern: '^\\+[1-9]\\d{1,14}$' },
  { name: 'SA ID Number', category: 'Identity', pattern: '^\\d{13}$' },
  { name: 'IBAN', category: 'Financial', pattern: '^[A-Z]{2}\\d{2}[A-Z0-9]{4,30}$' },
  { name: 'SWIFT/BIC', category: 'Financial', pattern: '^[A-Z]{6}[A-Z2-9][A-NP-Z0-9]([A-Z0-9]{3})?$' },
  { name: 'URL (HTTPS)', category: 'Web', pattern: '^https://[^\\s/$.?#].[^\\s]*$' },
  { name: 'Date (ISO)', category: 'Date', pattern: '^\\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\\d|3[01])$' },
  { name: 'Postal Code (ZA)', category: 'Address', pattern: '^\\d{4}$' },
  { name: 'IPv4', category: 'Network', pattern: '^(?:(?:25[0-5]|2[0-4]\\d|[01]?\\d\\d?)\\.){3}(?:25[0-5]|2[0-4]\\d|[01]?\\d\\d?)$' },
  { name: 'Company Reg (ZA)', category: 'Identity', pattern: '^\\d{4}/\\d{6}/\\d{2}$' },
]

const ruleTypes = [
  { value: 'required', label: 'Required' },
  { value: 'regex', label: 'Regex Pattern' },
  { value: 'min_length', label: 'Min Length' },
  { value: 'max_length', label: 'Max Length' },
  { value: 'min', label: 'Min Value' },
  { value: 'max', label: 'Max Value' },
  { value: 'date_format', label: 'Date Format' },
  { value: 'enum', label: 'Enum Values' },
  { value: 'email', label: 'Email (built-in)' },
  { value: 'phone_e164', label: 'Phone E.164 (built-in)' },
  { value: 'iban_checksum', label: 'IBAN Checksum (built-in)' },
]

interface Rule {
  id: string
  field_name: string
  rule_type: string
  pattern: string
  message: string
}

export default function ValidationPage() {
  const [rules, setRules] = useState<Rule[]>([])
  const [testValue, setTestValue] = useState('')
  const [testPattern, setTestPattern] = useState('')
  const [testResult, setTestResult] = useState<null | boolean>(null)
  const [selectedCategory, setSelectedCategory] = useState('All')

  const addRule = () => {
    setRules([...rules, {
      id: crypto.randomUUID(),
      field_name: '',
      rule_type: 'required',
      pattern: '',
      message: '',
    }])
  }

  const updateRule = (idx: number, updates: Partial<Rule>) => {
    setRules(rules.map((r, i) => (i === idx ? { ...r, ...updates } : r)))
  }

  const removeRule = (idx: number) => {
    setRules(rules.filter((_, i) => i !== idx))
  }

  const testRegex = () => {
    try {
      const regex = new RegExp(testPattern)
      setTestResult(regex.test(testValue))
    } catch {
      setTestResult(false)
    }
  }

  const categories = ['All', ...new Set(builtInPatterns.map((p) => p.category))]
  const filteredPatterns = selectedCategory === 'All'
    ? builtInPatterns
    : builtInPatterns.filter((p) => p.category === selectedCategory)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text)]">Validation Rules</h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            Per-column regex rule editor with live test harness
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => {
            const json = JSON.stringify(rules, null, 2)
            const blob = new Blob([json], { type: 'application/json' })
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = 'validation_rules.json'
            a.click()
          }}>
            <Download size={16} /> Export JSON
          </Button>
          <Button onClick={addRule}>
            <Plus size={16} /> Add Rule
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Pattern Library Sidebar */}
        <Card title="Pattern Library" className="lg:col-span-1">
          <div className="space-y-3">
            <div className="flex flex-wrap gap-1.5">
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                    selectedCategory === cat
                      ? 'bg-[var(--color-primary)] text-white'
                      : 'bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
            <div className="space-y-2">
              {filteredPatterns.map((p) => (
                <div
                  key={p.name}
                  className="cursor-pointer rounded-lg border border-[var(--color-border)] p-3 hover:border-[var(--color-primary)]"
                  onClick={() => setTestPattern(p.pattern)}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-[var(--color-text)]">{p.name}</span>
                    <Badge variant="info">{p.category}</Badge>
                  </div>
                  <code className="mt-1 block text-xs text-[var(--color-text-muted)]">{p.pattern}</code>
                </div>
              ))}
            </div>
          </div>
        </Card>

        {/* Rules Editor + Tester */}
        <div className="space-y-6 lg:col-span-2">
          {/* Regex Tester */}
          <Card title="Live Regex Tester">
            <div className="space-y-3">
              <Input
                label="Pattern"
                value={testPattern}
                onChange={(e) => { setTestPattern(e.target.value); setTestResult(null) }}
                placeholder="^[A-Z]{2}\\d{13}$"
              />
              <div className="flex gap-3">
                <div className="flex-1">
                  <Input
                    label="Test Value"
                    value={testValue}
                    onChange={(e) => { setTestValue(e.target.value); setTestResult(null) }}
                    placeholder="Enter test value..."
                  />
                </div>
                <div className="flex items-end">
                  <Button onClick={testRegex}>
                    <Play size={14} /> Test
                  </Button>
                </div>
              </div>
              {testResult !== null && (
                <div className={`rounded-lg p-3 text-sm font-medium ${testResult ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                  {testResult ? 'MATCH — Value passes validation' : 'NO MATCH — Value fails validation'}
                </div>
              )}
            </div>
          </Card>

          {/* Rules */}
          <Card title="Column Rules" action={<Button size="sm" onClick={addRule}><Plus size={14} /> Add</Button>}>
            <div className="space-y-3">
              {rules.map((rule, idx) => (
                <div key={rule.id} className="flex items-start gap-2 rounded-lg border border-[var(--color-border)] p-3">
                  <div className="flex-1 grid grid-cols-2 gap-2">
                    <Input
                      placeholder="Field name"
                      value={rule.field_name}
                      onChange={(e) => updateRule(idx, { field_name: e.target.value })}
                    />
                    <Select
                      options={ruleTypes}
                      value={rule.rule_type}
                      onChange={(e) => updateRule(idx, { rule_type: e.target.value })}
                    />
                    <Input
                      placeholder="Pattern / value"
                      value={rule.pattern}
                      onChange={(e) => updateRule(idx, { pattern: e.target.value })}
                    />
                    <Input
                      placeholder="Error message"
                      value={rule.message}
                      onChange={(e) => updateRule(idx, { message: e.target.value })}
                    />
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => removeRule(idx)}>
                    <Trash2 size={14} />
                  </Button>
                </div>
              ))}
              {rules.length === 0 && (
                <p className="py-8 text-center text-sm text-[var(--color-text-muted)]">
                  No rules defined. Click "Add Rule" to create your first validation rule.
                </p>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
