/** 后端统一响应结构 */
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

/** 分页信息 */
export interface PaginationInfo {
  page: number
  page_size: number
  total: number
  total_pages: number
}

/** 分页响应结构 */
export interface PaginatedResponse<T> {
  lists: T[]
  pagination: PaginationInfo
}

/** 健康检查响应 */
export interface HealthData {
  status: string
  service: string
  version: string
  database: {
    ready: boolean
    migration_completed: boolean
    path: string
  }
  data_directory: {
    path: string
    writable: boolean
  }
}

/** 模型供应商信息 */
export interface ModelProvider {
  [key: string]: string
}

/** 模型配置 */
export interface ModelConfig {
  id: number
  name: string
  provider: string
  model_name: string
  api_base: string | null
  is_active: boolean
  has_key: boolean
  status: string
  error_message: string | null
  created_at: string | null
  updated_at: string | null
}

/** 创建模型配置请求 */
export interface ModelConfigCreate {
  name: string
  provider: string
  model_name: string
  api_base?: string
}

/** 更新模型配置请求 */
export interface ModelConfigUpdate {
  name?: string
  provider?: string
  model_name?: string
  api_base?: string
  has_key?: boolean
}
