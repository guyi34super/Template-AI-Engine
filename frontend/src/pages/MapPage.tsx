import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import { ArrowRight, Save, Wand2, GripVertical } from 'lucide-react'
import { mappingApi } from '../services/mappingService'
import type { FieldMapping } from '../types'

// Demo data - in production, this comes from extraction results
const demoSourceFields = [
  'emp_id', 'first_name', 'last_name', 'email_address', 'hire_date',
  'department', 'job_title', 'salary', 'phone_number', 'manager',
]

const demoTargetFields = [
  'EmployeeNumber', 'FirstName', 'LastName', 'Email', 'HireDate',
  'Department', 'Position', 'AnnualSalary', 'ContactPhone', 'ManagerName',
]

export default function MapPage() {
  const [mappings, setMappings] = useState<FieldMapping[]>([])
  const [dragSource, setDragSource] = useState<string | null>(null)

  const autoMapMutation = useMutation({
    mutationFn: async () => {
      return mappingApi.autoMap({
        source_schema: demoSourceFields,
        target_schema: demoTargetFields,
      })
    },
    onSuccess: (data) => {
      if (data.mappings) {
        setMappings(data.mappings)
      }
    },
    onError: () => {
      // Fallback: generate demo mappings
      setMappings(
        demoSourceFields.map((sf, i) => ({
          source_field: sf,
          target_field: demoTargetFields[i] || '',
          confidence: Math.random() * 0.4 + 0.6,
        })),
      )
    },
  })

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.9) return 'success'
    if (confidence >= 0.7) return 'warning'
    return 'danger'
  }

  const handleDragStart = (field: string) => setDragSource(field)
  const handleDrop = (targetField: string) => {
    if (!dragSource) return
    setMappings((prev) => {
      const existing = prev.filter((m) => m.source_field !== dragSource && m.target_field !== targetField)
      return [...existing, { source_field: dragSource, target_field: targetField, confidence: 1.0 }]
    })
    setDragSource(null)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text)]">Field Mapping</h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            Auto-map with LLM confidence or drag-and-drop to manually assign fields
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => autoMapMutation.mutate()} loading={autoMapMutation.isPending}>
            <Wand2 size={16} /> Auto Map (LLM)
          </Button>
          <Button>
            <Save size={16} /> Save Config
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Source Fields */}
        <Card title="Source Fields" description="Extracted field names">
          <div className="space-y-2">
            {demoSourceFields.map((field) => {
              const mapping = mappings.find((m) => m.source_field === field)
              return (
                <div
                  key={field}
                  draggable
                  onDragStart={() => handleDragStart(field)}
                  className={`flex cursor-grab items-center gap-2 rounded-lg border p-3 transition-colors ${
                    mapping
                      ? 'border-emerald-500/50 bg-emerald-500/5'
                      : 'border-[var(--color-border)] hover:border-[var(--color-primary)]/50'
                  }`}
                >
                  <GripVertical size={14} className="text-[var(--color-text-muted)]" />
                  <span className="flex-1 text-sm font-medium text-[var(--color-text)]">{field}</span>
                  {mapping && (
                    <Badge variant={getConfidenceColor(mapping.confidence) as any}>
                      {Math.round(mapping.confidence * 100)}%
                    </Badge>
                  )}
                </div>
              )
            })}
          </div>
        </Card>

        {/* Mapping Visualization */}
        <Card title="Mappings" description={`${mappings.length} fields mapped`}>
          <div className="space-y-2">
            {mappings.map((m) => (
              <div key={m.source_field} className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] p-3">
                <span className="flex-1 text-xs font-medium text-[var(--color-text)]">{m.source_field}</span>
                <ArrowRight size={14} className="text-[var(--color-primary)]" />
                <span className="flex-1 text-xs font-medium text-[var(--color-text)]">{m.target_field}</span>
                <Badge variant={getConfidenceColor(m.confidence) as any}>
                  {Math.round(m.confidence * 100)}%
                </Badge>
              </div>
            ))}
            {mappings.length === 0 && (
              <p className="py-8 text-center text-sm text-[var(--color-text-muted)]">
                Click "Auto Map" or drag source fields to targets
              </p>
            )}
          </div>
        </Card>

        {/* Target Fields */}
        <Card title="Target Schema" description="Template field definitions">
          <div className="space-y-2">
            {demoTargetFields.map((field) => {
              const mapping = mappings.find((m) => m.target_field === field)
              return (
                <div
                  key={field}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => handleDrop(field)}
                  className={`flex items-center gap-2 rounded-lg border p-3 transition-colors ${
                    mapping
                      ? 'border-emerald-500/50 bg-emerald-500/5'
                      : 'border-[var(--color-border)] border-dashed hover:border-[var(--color-primary)]'
                  }`}
                >
                  <span className="flex-1 text-sm font-medium text-[var(--color-text)]">{field}</span>
                  {mapping && (
                    <span className="text-xs text-emerald-400">← {mapping.source_field}</span>
                  )}
                </div>
              )
            })}
          </div>
        </Card>
      </div>
    </div>
  )
}
