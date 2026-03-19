// ===== User & Auth =====
export interface User {
  id: string
  email: string
  role: 'viewer' | 'editor' | 'admin' | 'system'
  mfa_enabled: boolean
  created_at: string
  last_login: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

// ===== Templates =====
export interface TemplateField {
  id: string
  name: string
  type: 'text' | 'number' | 'integer' | 'date' | 'email' | 'phone' | 'id_number' | 'iban' | 'currency' | 'boolean' | 'enum' | 'regex_custom' | 'list' | 'nested'
  required: boolean
  regex_pattern?: string
  description?: string
  sort_order: number
  enum_values?: string[]
}

export interface Template {
  id: string
  name: string
  description?: string
  version: number
  status: 'draft' | 'published'
  fields: TemplateField[]
  created_by: string
  created_at: string
  updated_at: string
  published_at?: string
}

// ===== Documents & Extraction =====
export interface ExtractionJob {
  job_id: string
  filename: string
  status: 'pending' | 'uploading' | 'scanning' | 'extracting' | 'classifying' | 'complete' | 'failed'
  template_id?: string
  template_name?: string
  confidence?: number
  extracted_data?: Record<string, unknown>
  validation_results?: ValidationResult[]
  error?: string
  created_at: string
  completed_at?: string
}

// ===== Validation =====
export interface ValidationRule {
  id: string
  field_name: string
  rule_type: 'required' | 'regex' | 'min_length' | 'max_length' | 'min' | 'max' | 'date_format' | 'enum' | 'email' | 'phone_e164' | 'iban_checksum' | 'luhn' | 'custom_rust_fn'
  pattern?: string
  message?: string
  parameters?: Record<string, unknown>
}

export interface ValidationResult {
  field_name: string
  status: 'pass' | 'fail' | 'warning'
  value: string
  cleaned_value?: string
  error_msg?: string
  rule_violated?: string
}

// ===== Mapping =====
export interface FieldMapping {
  source_field: string
  target_field: string
  confidence: number
  type_conversion?: string
}

export interface MappingConfig {
  id: string
  source_schema: string[]
  target_schema: string[]
  mappings: FieldMapping[]
  created_by: string
  created_at: string
}

// ===== Chat =====
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

export interface ChatSession {
  session_id: string
  messages: ChatMessage[]
  file_context?: string
}

// ===== Memory =====
export interface MemoryEntry {
  id: string
  user_id: string
  context_summary: string
  created_at: string
}

export interface MemorySession {
  session_id: string
  user_id: string
  created_at: string
  message_count: number
}

// ===== Export =====
export interface ExportJob {
  id: string
  document_id: string
  format: 'pdf' | 'xlsx' | 'csv' | 'txt'
  status: 'pending' | 'processing' | 'complete' | 'failed'
  file_path?: string
  created_at: string
}

// ===== Dashboard =====
export interface DashboardStats {
  total_documents: number
  active_templates: number
  validation_pass_rate: number
  jobs_in_progress: number
  recent_activity: ActivityItem[]
}

export interface ActivityItem {
  id: string
  action: string
  resource: string
  timestamp: string
  status: string
  user_id?: string
}
