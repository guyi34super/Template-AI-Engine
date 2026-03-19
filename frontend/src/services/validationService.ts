/**
 * Validation API service — rules, patterns, validate.
 */
import api from '../lib/api'
import type { ValidationRule, ValidationResult } from '../types'

export const validationApi = {
  validate: (data: Record<string, unknown>, rules: ValidationRule[]) =>
    api
      .post<ValidationResult[]>('/validation/validate', { data, rules })
      .then((r) => r.data),

  listRules: () =>
    api.get<ValidationRule[]>('/validation/rules').then((r) => r.data),

  createRule: (rule: Omit<ValidationRule, 'id'>) =>
    api.post<ValidationRule>('/validation/rules', rule).then((r) => r.data),

  patterns: () =>
    api.get<Record<string, string>>('/validation/patterns').then((r) => r.data),

  testPattern: (pattern: string, value: string) =>
    api
      .post<{ matches: boolean; groups?: string[] }>('/validation/test-pattern', {
        pattern,
        value,
      })
      .then((r) => r.data),
}
