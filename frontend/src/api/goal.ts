import { getAdapter } from '@/composables/useApi'
import type { Goal, GoalCreate, GoalDetail, GoalListQuery, GoalUpdate, Task, TaskCreate, TaskListQuery, TaskSuggestionCreate, TaskUpdate, TaskWithGoal } from '@/types/api'

const adapter = getAdapter()

// ── 目标 API ─────────────────────────────────────────────────────────────────

/** 创建目标 */
export async function createGoal(data: GoalCreate) {
  return adapter.post<Goal>('/api/v1/goals', data)
}

/** 查询目标列表 */
export async function listGoals(query: GoalListQuery) {
  return adapter.post<{ lists: Goal[]; pagination: { page: number; page_size: number; total: number; total_pages: number } }>(
    '/api/v1/goals/list',
    query,
  )
}

/** 获取目标详情（含关联任务） */
export async function getGoal(id: number) {
  return adapter.get<GoalDetail>(`/api/v1/goals/${id}`)
}

/** 更新目标 */
export async function updateGoal(id: number, data: GoalUpdate) {
  return adapter.put<Goal>(`/api/v1/goals/${id}`, data)
}

/** 删除目标 */
export async function deleteGoal(id: number, taskAction = 'unlink') {
  return adapter.delete(`/api/v1/goals/${id}?task_action=${taskAction}`)
}

// ── 任务 API ─────────────────────────────────────────────────────────────────

/** 创建任务 */
export async function createTask(data: TaskCreate) {
  return adapter.post<Task>('/api/v1/goals/tasks', data)
}

/** 查询任务列表 */
export async function listTasks(query: TaskListQuery) {
  return adapter.post<{ lists: TaskWithGoal[]; pagination: { page: number; page_size: number; total: number; total_pages: number } }>(
    '/api/v1/goals/tasks/list',
    query,
  )
}

/** 获取任务详情 */
export async function getTask(id: number) {
  return adapter.get<TaskWithGoal>(`/api/v1/goals/tasks/${id}`)
}

/** 更新任务 */
export async function updateTask(id: number, data: TaskUpdate) {
  return adapter.put<Task>(`/api/v1/goals/tasks/${id}`, data)
}

/** 删除任务 */
export async function deleteTask(id: number) {
  return adapter.delete(`/api/v1/goals/tasks/${id}`)
}

// ── AI 建议 API ──────────────────────────────────────────────────────────────

/** 创建 AI 建议任务 */
export async function createSuggestion(data: TaskSuggestionCreate) {
  return adapter.post<Task>('/api/v1/goals/suggestions', data)
}

/** 接受 AI 建议 */
export async function acceptSuggestion(id: number) {
  return adapter.post<Task>(`/api/v1/goals/tasks/${id}/accept-suggestion`)
}

/** 拒绝 AI 建议 */
export async function rejectSuggestion(id: number) {
  return adapter.post<Task>(`/api/v1/goals/tasks/${id}/reject-suggestion`)
}
