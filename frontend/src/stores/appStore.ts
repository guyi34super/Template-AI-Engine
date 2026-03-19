import { create } from 'zustand'
import type { ExtractionJob, Template } from '../types'

interface AppState {
  // Active extraction jobs
  jobs: ExtractionJob[]
  addJob: (job: ExtractionJob) => void
  updateJob: (jobId: string, updates: Partial<ExtractionJob>) => void
  removeJob: (jobId: string) => void

  // Selected template for current workflow
  selectedTemplate: Template | null
  setSelectedTemplate: (template: Template | null) => void

  // Current extraction data for mapping/validation
  currentExtractionData: Record<string, unknown> | null
  setCurrentExtractionData: (data: Record<string, unknown> | null) => void

  // Sidebar state
  sidebarOpen: boolean
  toggleSidebar: () => void
}

export const useAppStore = create<AppState>((set) => ({
  jobs: [],
  addJob: (job) => set((state) => ({ jobs: [...state.jobs, job] })),
  updateJob: (jobId, updates) =>
    set((state) => ({
      jobs: state.jobs.map((j) => (j.job_id === jobId ? { ...j, ...updates } : j)),
    })),
  removeJob: (jobId) =>
    set((state) => ({ jobs: state.jobs.filter((j) => j.job_id !== jobId) })),

  selectedTemplate: null,
  setSelectedTemplate: (template) => set({ selectedTemplate: template }),

  currentExtractionData: null,
  setCurrentExtractionData: (data) => set({ currentExtractionData: data }),

  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
}))
