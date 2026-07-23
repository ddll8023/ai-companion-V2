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
  /** 获取平台各能力状态 */
  getPlatformCapabilities: () => Promise<PlatformCapabilitiesResponse>
  onBackendStatus: (callback: (status: { ready: boolean }) => void) => void
  removeBackendStatusListener: () => void
}

// ── 目标与任务类型 ──────────────────────────────────────────────────────────

/** 目标 */
export interface Goal {
  id: number
  title: string
  description: string | null
  status: number
  target_date: string | null
  progress: number
  created_at: string | null
  updated_at: string | null
}

/** 创建目标请求 */
export interface GoalCreate {
  title: string
  description?: string
  target_date?: string
}

/** 更新目标请求 */
export interface GoalUpdate {
  title?: string
  description?: string
  status?: number
  target_date?: string
}

/** 目标列表查询参数 */
export interface GoalListQuery {
  status?: number
  keyword?: string
  page?: number
  page_size?: number
}

/** 任务 */
export interface Task {
  id: number
  goal_id: number | null
  title: string
  description: string | null
  status: number
  priority: number
  is_from_suggestion: number
  suggestion_status: number
  suggestion_data: string | null
  created_at: string | null
  updated_at: string | null
}

/** 任务（含关联目标标题） */
export interface TaskWithGoal {
  id: number
  goal_id: number | null
  goal_title: string | null
  title: string
  description: string | null
  status: number
  priority: number
  is_from_suggestion: number
  suggestion_status: number
  suggestion_data: string | null
  created_at: string | null
  updated_at: string | null
}

/** 创建任务请求 */
export interface TaskCreate {
  goal_id?: number | null
  title: string
  description?: string
  priority?: number
}

/** 更新任务请求 */
export interface TaskUpdate {
  title?: string
  description?: string
  status?: number
  priority?: number
  goal_id?: number | null
}

/** 任务列表查询参数 */
export interface TaskListQuery {
  goal_id?: number
  status?: number
  suggestion_status?: number
  is_suggestion?: number
  keyword?: string
  page?: number
  page_size?: number
}

/** 创建 AI 建议任务请求 */
export interface TaskSuggestionCreate {
  title: string
  description?: string
  priority?: number
  suggestion_data?: string
}

/** 目标详情（含关联任务） */
export interface GoalDetail {
  goal: Goal
  tasks: Task[]
}

// ── 活动类型 ─────────────────────────────────────────────────────────────────

/** 活动记录 */
export interface Activity {
  id: number
  app_name: string
  window_title: string | null
  started_at: string
  ended_at: string | null
  duration_seconds: number | null
  is_idle: boolean
  platform: string
  privacy_action: string
  masked_app_name: string | null
  masked_window_title: string | null
  created_at: string
}

/** 活动事件（Electron 上报用） */
export interface ActivityEvent {
  app_name: string
  window_title?: string
  started_at: string
  ended_at?: string
  duration_seconds?: number
  is_idle?: boolean
  platform: string
  source_id?: string
}

/** 批量活动事件上报 */
export interface BatchActivityEvent {
  events: ActivityEvent[]
}

/** 活动列表查询参数 */
export interface ActivityListQuery {
  app_name?: string
  platform?: string
  privacy_action?: string
  keyword?: string
  start_time?: string
  end_time?: string
  page?: number
  page_size?: number
}

/** 活动统计 */
export interface ActivityStats {
  total_count: number
  today_count: number
  unique_apps: number
}

// ── 隐私规则类型 ─────────────────────────────────────────────────────────────

/** 隐私规则 */
export interface PrivacyRule {
  id: number
  rule_type: string
  rule_value: string
  description: string | null
  is_active: boolean
  priority: number
  created_at: string
  updated_at: string
}

/** 创建隐私规则请求 */
export interface PrivacyRuleCreate {
  rule_type: string
  rule_value: string
  description?: string
  priority?: number
}

/** 更新隐私规则请求 */
export interface PrivacyRuleUpdate {
  rule_type?: string
  rule_value?: string
  description?: string
  is_active?: boolean
  priority?: number
}

/** 隐私规则列表查询参数 */
export interface PrivacyRuleListQuery {
  rule_type?: string
  is_active?: boolean
  page?: number
  page_size?: number
}

/** 隐私评估请求 */
export interface PrivacyEvaluateRequest {
  app_name: string
  window_title?: string
  platform: string
}

/** 隐私评估结果 */
export interface PrivacyEvaluateResult {
  allowed: boolean
  action: string
  reason: string | null
  matched_rule_id: number | null
  masked_app_name: string | null
  masked_window_title: string | null
}

/** 平台单项能力 */
export interface PlatformCapability {
  name: string
  status: 'available' | 'pending_auth' | 'denied' | 'restricted' | 'unsupported' | 'not_implemented'
  label: string
  description: string | null
}

/** 平台能力列表 */
export interface PlatformCapabilitiesResponse {
  platform: string
  capabilities: PlatformCapability[]
}

// ── 画像类型 ────────────────────────────────────────────────────────────────────

/** 画像特征 */
export interface Profile {
  id: number
  category: string
  content: string
  confidence: number
  status: 'candidate' | 'confirmed' | 'corrected' | 'rejected' | 'deleted'
  is_auto_extracted: number
  version: number
  source_version: string | null
  error_message: string | null
  created_at: string | null
  updated_at: string | null
}

/** 画像来源 */
export interface ProfileSource {
  id: number
  profile_id: number
  source_type: string
  memory_id: number | null
  content_preview: string | null
  evidence_text: string | null
  created_at: string | null
}

/** 画像修订历史 */
export interface ProfileRevision {
  id: number
  profile_id: number
  previous_category: string | null
  previous_content: string
  previous_confidence: number | null
  previous_status: string | null
  changed_by: string
  created_at: string | null
}

/** 画像详情 */
export interface ProfileDetail {
  profile: Profile
  sources: ProfileSource[]
  revisions: ProfileRevision[]
}

/** 创建画像请求 */
export interface ProfileCreate {
  category: string
  content: string
  confidence?: number
  is_auto_extracted?: number
  memory_ids?: number[]
  evidence_texts?: string[]
}

/** 纠正画像请求 */
export interface ProfileCorrect {
  category: string
  content: string
  confidence: number
}

/** 画像列表查询参数 */
export interface ProfileListQuery {
  category?: string
  status?: string
  keyword?: string
  is_auto_extracted?: number
  page?: number
  page_size?: number
}

/** 画像提取请求（当前无需参数，预留位置） */
export interface ProfileExtractRequest {
  // 当前为空，API Key 由后端进程内存缓存管理
}

/** 行为统计查询参数 */
export interface BehaviorStatsQuery {
  days?: number
}

/** 行为统计响应 */
export interface BehaviorStatsResponse {
  active_hours: { hour: number; count: number }[]
  app_usage: { app_name: string; total_minutes: number; percentage: number }[]
  chat_activity: { date: string; message_count: number }[]
}
