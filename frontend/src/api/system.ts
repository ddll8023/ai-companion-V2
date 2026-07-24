import { getAdapter } from '@/composables/useApi'
import type { ApiResponse, AuditLogResponse, AuditStats, PaginatedResponse, SystemStatusResponse } from '@/types/api'

const api = getAdapter()

/** 获取系统状态 */
export async function getSystemStatus() {
  const res = await api.get<SystemStatusResponse>('/api/v1/system/status')
  return res
}

/** 查询审计日志列表 */
export async function getAuditLogs(params: {
  action?: string
  target_type?: string
  result?: number
  start_time?: string
  end_time?: string
  page?: number
  page_size?: number
}) {
  const res = await api.post<PaginatedResponse<AuditLogResponse>>('/api/v1/audit/list', params)
  return res
}

/** 获取审计操作类型列表 */
export async function getAuditActions() {
  const res = await api.get<string[]>('/api/v1/audit/actions')
  return res
}

/** 获取审计对象类型列表 */
export async function getAuditTargetTypes() {
  const res = await api.get<string[]>('/api/v1/audit/target-types')
  return res
}

/** 获取审计日志统计 */
export async function getAuditStats() {
  const res = await api.get<AuditStats>('/api/v1/audit/stats')
  return res
}
