import { getAdapter } from '@/composables/useApi'
import type {
  DataExportRequest,
  DataExportResponse,
  DataVolumeStats,
  BackupCreateRequest,
  BackupResponse,
  BackupListQuery,
  RestoreRequest,
  RestoreResponse,
  RetentionPolicyCreate,
  RetentionPolicyUpdate,
  RetentionPolicyResponse,
  ClearDataRequest,
  ClearDataResponse,
} from '@/types/api'

const adapter = getAdapter()

/** 导出数据 */
export async function exportData(data: DataExportRequest) {
  return adapter.post<DataExportResponse>('/api/v1/data/export', data)
}

/** 查询导出记录列表 */
export async function listExports(page = 1, pageSize = 20) {
  return adapter.post<{ lists: DataExportResponse[]; pagination: { page: number; page_size: number; total: number; total_pages: number } }>(
    '/api/v1/data/exports/list',
    { page, page_size: pageSize },
  )
}

/** 删除导出记录 */
export async function deleteExport(exportId: number) {
  return adapter.delete(`/api/v1/data/exports/${exportId}`)
}

/** 创建备份 */
export async function createBackup(data: BackupCreateRequest) {
  return adapter.post<BackupResponse>('/api/v1/data/backup', data)
}

/** 查询备份记录列表 */
export async function listBackups(query: BackupListQuery) {
  return adapter.post<{ lists: BackupResponse[]; pagination: { page: number; page_size: number; total: number; total_pages: number } }>(
    '/api/v1/data/backups/list',
    query,
  )
}

/** 从备份恢复 */
export async function restoreFromBackup(data: RestoreRequest) {
  return adapter.post<RestoreResponse>('/api/v1/data/restore', data)
}

/** 删除备份记录 */
export async function deleteBackup(backupId: number) {
  return adapter.delete(`/api/v1/data/backups/${backupId}`)
}

/** 查询所有保留策略 */
export async function listRetentionPolicies() {
  return adapter.get<RetentionPolicyResponse[]>('/api/v1/data/retention')
}

/** 创建保留策略 */
export async function createRetentionPolicy(data: RetentionPolicyCreate) {
  return adapter.post<RetentionPolicyResponse>('/api/v1/data/retention', data)
}

/** 更新保留策略 */
export async function updateRetentionPolicy(policyId: number, data: RetentionPolicyUpdate) {
  return adapter.post<RetentionPolicyResponse>(`/api/v1/data/retention/${policyId}`, data)
}

/** 删除保留策略 */
export async function deleteRetentionPolicy(policyId: number) {
  return adapter.delete(`/api/v1/data/retention/${policyId}`)
}

/** 手动触发保留策略清理 */
export async function runRetentionCleanup() {
  return adapter.post<Record<string, number>>('/api/v1/data/retention/cleanup')
}

/** 清除全部数据 */
export async function clearAllData(data: ClearDataRequest) {
  return adapter.post<ClearDataResponse>('/api/v1/data/clear', data)
}

/** 获取数据量统计 */
export async function getDataVolume() {
  return adapter.get<DataVolumeStats>('/api/v1/data/volume')
}
