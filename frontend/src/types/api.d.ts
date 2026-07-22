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

// ── 对话类型 ──────────────────────────────────────────────────────────────

/** 会话 */
export interface Session {
  id: number
  title: string
  model_name: string | null
  created_at: string | null
  updated_at: string | null
}

/** 创建会话请求 */
export interface SessionCreate {
  title?: string
}

/** 更新会话请求 */
export interface SessionUpdate {
  title: string
}

/** 消息 */
export interface Message {
  id: number
  session_id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  status: 'generating' | 'completed' | 'aborted' | 'failed'
  error_message: string | null
  model_name: string | null
  token_count: number | null
  created_at: string | null
}

/** 发送消息请求 */
export interface ChatRequest {
  content: string
  api_key?: string
}

/** 流式对话事件 */
export interface ChatStreamEvent {
  type: 'token' | 'done' | 'error' | 'user_saved'
  content?: string
  message_id?: number
  message?: string
}

// ── 记忆类型 ──────────────────────────────────────────────────────────────

/** 记忆 */
export interface Memory {
  id: number
  content: string
  type: 'fact' | 'preference' | 'event' | 'goal' | 'habit'
  importance: number
  status: 'candidate' | 'confirmed' | 'corrected' | 'rejected' | 'deleted'
  session_id: number | null
  source_version: string | null
  version: number
  error_message: string | null
  created_at: string | null
  updated_at: string | null
}

/** 创建记忆请求 */
export interface MemoryCreate {
  content: string
  type?: string
  importance?: number
  session_id?: number | null
  source_version?: string | null
  source_type?: string
  source_ids?: number[]
}

/** 纠正记忆请求 */
export interface MemoryCorrect {
  content: string
  type: string
  importance: number
}

/** 记忆来源 */
export interface MemorySource {
  id: number
  memory_id: number
  source_type: string
  source_id: number
  content_preview: string | null
  created_at: string | null
}

/** 记忆修订历史 */
export interface MemoryRevision {
  id: number
  memory_id: number
  previous_content: string
  previous_type: string | null
  previous_importance: number | null
  changed_by: string
  created_at: string | null
}

/** 记忆详情 */
export interface MemoryDetail {
  memory: Memory
  sources: MemorySource[]
  revisions: MemoryRevision[]
}

/** 记忆列表查询参数 */
export interface MemoryListQuery {
  status?: string
  type?: string
  session_id?: number
  keyword?: string
  page?: number
  page_size?: number
}

/** Electron API 接口 */
export interface ElectronAPI {
  apiGet: <T>(url: string) => Promise<ApiResponse<T>>
  apiPost: <T>(url: string, data?: unknown) => Promise<ApiResponse<T>>
  apiPut: <T>(url: string, data?: unknown) => Promise<ApiResponse<T>>
  apiDelete: <T>(url: string) => Promise<ApiResponse<T>>
  keystoreSet: (key: string, value: string) => Promise<{ success: boolean; error?: string }>
  keystoreGet: (key: string) => Promise<{ success: boolean; value: string | null }>
  keystoreDelete: (key: string) => Promise<{ success: boolean }>
  keystoreHas: (key: string) => Promise<{ success: boolean; has: boolean }>
  getPlatform: () => Promise<string>
  getAppVersion: () => Promise<string>
  onBackendStatus: (callback: (status: { ready: boolean }) => void) => void
  removeBackendStatusListener: () => void
}
