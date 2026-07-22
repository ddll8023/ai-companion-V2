import { getAdapter } from '@/composables/useApi'
import type { Memory, MemoryCorrect, MemoryCreate, MemoryDetail, MemoryListQuery } from '@/types/api'

const adapter = getAdapter()

/** 创建候选记忆 */
export async function createMemory(data: MemoryCreate) {
  return adapter.post<Memory>('/api/v1/memories', data)
}

/** 查询记忆列表（支持筛选） */
export async function listMemories(query: MemoryListQuery) {
  return adapter.post<{ lists: Memory[]; pagination: { page: number; page_size: number; total: number; total_pages: number } }>(
    '/api/v1/memories/list',
    query,
  )
}

/** 获取记忆详情（含来源和修订历史） */
export async function getMemory(id: number) {
  return adapter.get<MemoryDetail>(`/api/v1/memories/${id}`)
}

/** 确认候选记忆 */
export async function confirmMemory(id: number) {
  return adapter.post<Memory>(`/api/v1/memories/${id}/confirm`)
}

/** 纠正记忆 */
export async function correctMemory(id: number, data: MemoryCorrect) {
  return adapter.post<Memory>(`/api/v1/memories/${id}/correct`, data)
}

/** 否定候选记忆 */
export async function rejectMemory(id: number) {
  return adapter.post<Memory>(`/api/v1/memories/${id}/reject`)
}

/** 删除记忆 */
export async function deleteMemory(id: number) {
  return adapter.delete(`/api/v1/memories/${id}`)
}
