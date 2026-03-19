import { useState } from 'react'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Badge from '../components/ui/Badge'
import Modal from '../components/ui/Modal'
import Select from '../components/ui/Select'
import { Plus, Edit2, Trash2, Eye, Search, GripVertical } from 'lucide-react'
import { useTemplates, useCreateTemplate, useDeleteTemplate, usePublishTemplate } from '../hooks/useApi'
import type { Template, TemplateField } from '../types'

const fieldTypes = [
  { value: 'text', label: 'Text' },
  { value: 'number', label: 'Number' },
  { value: 'integer', label: 'Integer' },
  { value: 'date', label: 'Date' },
  { value: 'email', label: 'Email' },
  { value: 'phone', label: 'Phone' },
  { value: 'id_number', label: 'ID Number' },
  { value: 'iban', label: 'IBAN' },
  { value: 'currency', label: 'Currency' },
  { value: 'boolean', label: 'Boolean' },
  { value: 'enum', label: 'Enum' },
  { value: 'regex_custom', label: 'Custom Regex' },
  { value: 'list', label: 'List' },
  { value: 'nested', label: 'Nested' },
]

const blankField: TemplateField = {
  id: '',
  name: '',
  type: 'text',
  required: false,
  sort_order: 0,
}

export default function TemplatesPage() {
  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<Partial<Template> | null>(null)
  const [fields, setFields] = useState<TemplateField[]>([])
  const [templateName, setTemplateName] = useState('')
  const [templateDesc, setTemplateDesc] = useState('')
  const [testText, setTestText] = useState('')

  // Fetch templates via hook
  const { data: templates = [], isLoading } = useTemplates({ search: search || undefined })
  const { mutateAsync: createTemplate, isPending: isCreating } = useCreateTemplate()
  const { mutateAsync: deleteTemplate } = useDeleteTemplate()
  const { mutateAsync: publishTemplate } = usePublishTemplate()

  const openCreateModal = () => {
    setEditingTemplate(null)
    setTemplateName('')
    setTemplateDesc('')
    setFields([{ ...blankField, id: crypto.randomUUID(), sort_order: 0 }])
    setShowModal(true)
  }

  const openEditModal = (template: Template) => {
    setEditingTemplate(template)
    setTemplateName(template.name)
    setTemplateDesc(template.description || '')
    setFields(template.fields || [])
    setShowModal(true)
  }

  const addField = () => {
    setFields([...fields, { ...blankField, id: crypto.randomUUID(), sort_order: fields.length }])
  }

  const updateField = (idx: number, updates: Partial<TemplateField>) => {
    setFields(fields.map((f, i) => (i === idx ? { ...f, ...updates } : f)))
  }

  const removeField = (idx: number) => {
    setFields(fields.filter((_, i) => i !== idx))
  }

  const filteredTemplates = templates.filter((t: any) =>
    t.name?.toLowerCase().includes(search.toLowerCase()),
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text)]">Template Builder</h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            Create and manage document extraction templates with versioning
          </p>
        </div>
        <Button onClick={openCreateModal}>
          <Plus size={16} /> Create Template
        </Button>
      </div>

      {/* Search */}
      <div className="flex gap-4">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
          <input
            type="text"
            placeholder="Search templates..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] py-2 pl-10 pr-4 text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-primary)] focus:outline-none"
          />
        </div>
      </div>

      {/* Templates List */}
      <div className="grid gap-4">
        {isLoading && (
          <Card><p className="text-center text-[var(--color-text-muted)]">Loading templates...</p></Card>
        )}
        {filteredTemplates.map((template: any) => (
          <Card key={template.id || template.name}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-semibold text-[var(--color-text)]">{template.name}</h3>
                    <Badge variant={template.status === 'published' ? 'success' : 'warning'}>
                      {template.status || 'draft'}
                    </Badge>
                    <Badge variant="info">v{template.version || 1}</Badge>
                  </div>
                  <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                    {template.description || `${(template.fields || []).length} fields defined`}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={() => openEditModal(template)}>
                  <Edit2 size={14} /> Edit
                </Button>
                <Button variant="ghost" size="sm" onClick={() => publishTemplate(template.id)}>
                  <Eye size={14} /> Publish
                </Button>
                <Button variant="ghost" size="sm" onClick={() => deleteTemplate(template.id)}>
                  <Trash2 size={14} />
                </Button>
              </div>
            </div>
          </Card>
        ))}
        {filteredTemplates.length === 0 && !isLoading && (
          <Card>
            <div className="py-12 text-center">
              <p className="text-[var(--color-text-muted)]">No templates found. Create your first template to get started.</p>
              <Button className="mt-4" onClick={openCreateModal}>
                <Plus size={16} /> Create Template
              </Button>
            </div>
          </Card>
        )}
      </div>

      {/* Create/Edit Modal */}
      <Modal
        open={showModal}
        onClose={() => setShowModal(false)}
        title={editingTemplate ? 'Edit Template' : 'Create Template'}
        className="max-w-3xl"
        footer={
          <>
            <Button variant="outline" onClick={() => setShowModal(false)}>Cancel</Button>
            <Button
              disabled={isCreating}
              onClick={async () => {
                await createTemplate({ name: templateName, description: templateDesc, schema_json: fields })
                setShowModal(false)
              }}
            >
              {editingTemplate ? 'Save Changes' : 'Create Template'}
            </Button>
          </>
        }
      >
        <div className="max-h-[60vh] space-y-4 overflow-y-auto">
          <Input
            id="template-name"
            label="Template Name"
            value={templateName}
            onChange={(e) => setTemplateName(e.target.value)}
            placeholder="e.g., Employee Profile"
          />
          <Input
            id="template-desc"
            label="Description"
            value={templateDesc}
            onChange={(e) => setTemplateDesc(e.target.value)}
            placeholder="Describe the document type this template handles"
          />

          {/* Fields */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-semibold text-[var(--color-text)]">Fields</h4>
              <Button variant="outline" size="sm" onClick={addField}>
                <Plus size={14} /> Add Field
              </Button>
            </div>
            {fields.map((field, idx) => (
              <div key={field.id || idx} className="flex items-start gap-2 rounded-lg border border-[var(--color-border)] p-3">
                <GripVertical size={16} className="mt-2 cursor-grab text-[var(--color-text-muted)]" />
                <div className="flex-1 grid grid-cols-3 gap-2">
                  <Input
                    placeholder="Field name"
                    value={field.name}
                    onChange={(e) => updateField(idx, { name: e.target.value })}
                  />
                  <Select
                    options={fieldTypes}
                    value={field.type}
                    onChange={(e) => updateField(idx, { type: e.target.value as any })}
                  />
                  <Input
                    placeholder="Regex pattern (optional)"
                    value={field.regex_pattern || ''}
                    onChange={(e) => updateField(idx, { regex_pattern: e.target.value })}
                  />
                </div>
                <label className="flex items-center gap-1 text-xs text-[var(--color-text-muted)]">
                  <input
                    type="checkbox"
                    checked={field.required}
                    onChange={(e) => updateField(idx, { required: e.target.checked })}
                    className="rounded"
                  />
                  Required
                </label>
                <Button variant="ghost" size="sm" onClick={() => removeField(idx)}>
                  <Trash2 size={14} />
                </Button>
              </div>
            ))}
          </div>

          {/* Live Test Panel */}
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-[var(--color-text)]">Live Test</h4>
            <textarea
              placeholder="Paste sample text to test extraction accuracy..."
              value={testText}
              onChange={(e) => setTestText(e.target.value)}
              rows={4}
              className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-3 text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-primary)] focus:outline-none"
            />
          </div>
        </div>
      </Modal>
    </div>
  )
}
