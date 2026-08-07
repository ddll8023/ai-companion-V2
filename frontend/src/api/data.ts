import { getAdapter } from '@/composables/useApi'
import type {
  DataExportRequest,
  DataExportResponse,
  DataVolumeStats,
  BackupResponse,
  BackupListQuery,
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

/** 创建手动备份 */
export async function createBackup() {
  return adapter.post<BackupResponse>('/api/v1/data/backup')
}

/** 查询备份记录列表 */
export async function listBackups(query: BackupListQuery) {
  return adapter.post<{ lists: BackupResponse[]; pagination: { page: number; page_size: number; total: number; total_pages: number } }>(
    '/api/v1/data/backups/list',
    query,
  )
}

/** 删除备份记录 */
export async function deleteBackup(backupId: number) {
  return adapter.delete(`/api/v1/data/backups/${backupId}`)
}

/** 清除全部数据 */
export async function clearAllData(data: ClearDataRequest) {
  return adapter.post<ClearDataResponse>('/api/v1/data/clear', data)
}

/** 获取数据量统计 */
export async function getDataVolume() {
  return adapter.get<DataVolumeStats>('/api/v1/data/volume')
}
