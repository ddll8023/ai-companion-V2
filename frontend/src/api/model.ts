import { getAdapter } from '@/composables/useApi'
import type { ApiResponse, ModelConfig, ModelConfigCreate, ModelConfigUpdate } from '@/types/api'

const adapter = getAdapter()

/** 获取支持的供应商列表 */
export async function getProviders() {
  return adapter.get<Record<string, string>>('/api/v1/models/providers')
}

/** 创建模型配置 */
export async function createConfig(data: ModelConfigCreate) {
  return adapter.post<ModelConfig>('/api/v1/models/configs', data)
}

/** 更新模型配置 */
export async function updateConfig(id: number, data: ModelConfigUpdate) {
  return adapter.put<ModelConfig>(`/api/v1/models/configs/${id}`, data)
}

/** 删除模型配置 */
export async function deleteConfig(id: number) {
  return adapter.delete(`/api/v1/models/configs/${id}`)
}

/** 获取全部模型配置 */
export async function listConfigs() {
  return adapter.get<ModelConfig[]>('/api/v1/models/configs')
}

/** 获取单个模型配置 */
export async function getConfig(id: number) {
  return adapter.get<ModelConfig>(`/api/v1/models/configs/${id}`)
}

/** 获取当前激活的配置 */
export async function getActiveConfig() {
  return adapter.get<ModelConfig | null>('/api/v1/models/configs/active/info')
}

/** 激活配置 */
export async function activateConfig(id: number) {
  return adapter.post<ModelConfig>(`/api/v1/models/configs/${id}/activate`)
}

/** 测试模型连接 */
export async function testConnection(id: number, apiKey: string) {
  return adapter.post(`/api/v1/models/configs/${id}/test`, { api_key: apiKey })
}
