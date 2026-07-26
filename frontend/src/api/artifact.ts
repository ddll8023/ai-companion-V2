import { getAdapter } from '@/composables/useApi'
import type { AiArtifact, Memory, Task } from '@/types/api'

const api = getAdapter()

export function saveAiArtifact(sessionId: number, assistantMessageId: number) {
  return api.post<AiArtifact>('/api/v1/ai-artifacts', {
    session_id: sessionId,
    assistant_message_id: assistantMessageId,
  })
}
export function rememberAiArtifact(id: number) { return api.post<Memory>(`/api/v1/ai-artifacts/${id}/remember`) }
export function createTaskSuggestionFromArtifact(id: number) { return api.post<Task>(`/api/v1/ai-artifacts/${id}/task-suggestion`) }
