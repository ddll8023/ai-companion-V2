import request from '@/api/request'
import type { ApiResponse, AuditLogResponse, AuditStats, PaginatedResponse, SystemStatusResponse } from '@/types/api'

/** 获取系统状态 */
export async function getSystemStatus() {
  const res = await request.get<ApiResponse<SystemStatusResponse>>('/api/v1/system/status')
  return res.data
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
  const res = await request.post<ApiResponse<PaginatedResponse<AuditLogResponse>>>('/api/v1/system/audit/list', params)
  return res.data
}

/** 获取审计操作类型列表 */
export async function getAuditActions() {
  const res = await request.get<ApiResponse<string[]>>('/api/v1/system/audit/actions')
  return res.data
}

/** 获取审计对象类型列表 */
export async function getAuditTargetTypes() {
  const res = await request.get<ApiResponse<string[]>>('/api/v1/system/audit/target-types')
  return res.data
}

/** 获取审计日志统计 */
export async function getAuditStats() {
  const res = await request.get<ApiResponse<AuditStats>>('/api/v1/system/audit/stats')
  return res.data
}
