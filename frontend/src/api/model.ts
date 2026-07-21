import type { ApiResponse, ModelConfig, ModelConfigCreate, ModelConfigUpdate } from '@/types/api'
import request from '@/api/request'

/** 获取支持的供应商列表 */
export async function getProviders() {
  const res = await request.get<ApiResponse<Record<string, string>>>('/api/v1/models/providers')
  return res.data
}

/** 创建模型配置 */
export async function createConfig(data: ModelConfigCreate) {
  const res = await request.post<ApiResponse<ModelConfig>>('/api/v1/models/configs', data)
  return res.data
}

/** 更新模型配置 */
export async function updateConfig(id: number, data: ModelConfigUpdate) {
  const res = await request.put<ApiResponse<ModelConfig>>(`/api/v1/models/configs/${id}`, data)
  return res.data
}

/** 删除模型配置 */
export async function deleteConfig(id: number) {
  const res = await request.delete<ApiResponse>(`/api/v1/models/configs/${id}`)
  return res.data
}

/** 获取全部模型配置 */
export async function listConfigs() {
  const res = await request.get<ApiResponse<ModelConfig[]>>('/api/v1/models/configs')
  return res.data
}

/** 获取单个模型配置 */
export async function getConfig(id: number) {
  const res = await request.get<ApiResponse<ModelConfig>>(`/api/v1/models/configs/${id}`)
  return res.data
}

/** 获取当前激活的配置 */
export async function getActiveConfig() {
  const res = await request.get<ApiResponse<ModelConfig | null>>('/api/v1/models/configs/active/info')
  return res.data
}

/** 激活配置 */
export async function activateConfig(id: number) {
  const res = await request.post<ApiResponse<ModelConfig>>(`/api/v1/models/configs/${id}/activate`)
  return res.data
}

/** 测试模型连接 */
export async function testConnection(id: number, apiKey: string) {
  const res = await request.post<ApiResponse>(`/api/v1/models/configs/${id}/test`, { api_key: apiKey })
  return res.data
}
