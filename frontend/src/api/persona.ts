import { useApi } from '@/composables/useApi'
import type { Insight, Observation, PaginatedResponse, PersonaDocument } from '@/types/api'

const api = useApi()

export async function listObservations(query: Record<string, unknown> = {}) {
  return api.post<PaginatedResponse<Observation>>('/api/v1/persona/observations/list', { page: 1, page_size: 50, ...query })
}

export async function deleteObservation(id: number) {
  return api.delete<null>(`/api/v1/persona/observations/${id}`)
}

export async function listInsights(query: Record<string, unknown> = {}) {
  return api.post<PaginatedResponse<Insight>>('/api/v1/persona/insights/list', { page: 1, page_size: 50, ...query })
}

export async function correctInsight(id: number, content: string, dimension?: string) {
  return api.post<Insight>(`/api/v1/persona/insights/${id}/correct`, { content, dimension })
}

export async function rejectInsight(id: number) {
  return api.post<Insight>(`/api/v1/persona/insights/${id}/reject`)
}

export async function getPersonaDocument() {
  return api.get<PersonaDocument | null>('/api/v1/persona/document')
}

export async function editPersonaDocument(content: string, edited_sections: Record<string, unknown> = {}) {
  return api.post<PersonaDocument>('/api/v1/persona/document/edit', { content, edited_sections })
}

export async function reflectPersona() {
  return api.post<{ task_id: number }>('/api/v1/persona/reflect')
}
