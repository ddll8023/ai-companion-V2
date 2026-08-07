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
  enable_reasoning: boolean
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
  enable_reasoning?: boolean
}

/** 更新模型配置请求 */
export interface ModelConfigUpdate {
  name?: string
  provider?: string
  model_name?: string
  api_base?: string
  enable_reasoning?: boolean
  has_key?: boolean
}

// ── 对话类型 ──────────────────────────────────────────────────────────────

/** 会话 */
export interface Session {
  id: number
  title: string
  model_name: string | null
  last_extracted_message_id?: number | null
  last_extracted_at?: string | null
  extractable_message_count?: number
  is_extracting?: boolean
  created_at: string | null
  updated_at: string | null
}

/** 会话提取任务创建结果 */
export interface SessionExtractResult {
  task_id: number
  from_message_id: number
  to_message_id: number
}

/** 后台任务信息（提取任务轮询用） */
export interface BackgroundTaskInfo {
  id: number
  task_type: string
  status: 'pending' | 'processing' | 'retrying' | 'completed' | 'failed' | 'cancelled'
  result: string | null
  error_message: string | null
}

/** 创建会话请求 */
export interface SessionCreate {
  title?: string
}

/** 更新会话请求 */
export interface SessionUpdate {
  title: string
}

/** 记忆引用（对话中引用到的记忆） */
export interface MemoryReference {
  id: number
  message_id: number
  memory_id: number | null
  memory_content_preview: string | null
  relevance_score: number | null
  rank: number | null
  created_at: string | null
}

/** 消息 */
export interface Message {
  id: number
  session_id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  reasoning_content: string | null
  status: 'generating' | 'completed' | 'aborted' | 'failed'
  error_message: string | null
  model_name: string | null
  token_count: number | null
  memory_references?: MemoryReference[]
  created_at: string | null
}

/** 发送消息请求 */
export interface ChatRequest {
  content: string
  api_key?: string
}

/** 流式对话事件 */
export interface ChatStreamEvent {
  type: 'token' | 'reasoning_token' | 'done' | 'error'
  content?: string
  message_id?: number
  message?: string
}

export interface AiArtifact {
  id: number
  session_id: number
  assistant_message_id: number
  title: string
  content: string
  status: 'saved' | 'adopted' | 'dismissed'
  created_at: string | null
  updated_at: string | null
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
  version: number
  error_message: string | null
  created_at: string | null
  updated_at: string | null
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
  evidence_text: string | null
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

// ── 人物理解类型 ───────────────────────────────────────────────────────────

export interface Observation {
  id: number
  observation_type: string
  dimension: string
  content: string
  session_id: number | null
  source_message_id: number | null
  evidence: string
  reflected_at: string | null
  is_deleted: boolean
  created_at: string | null
}

export interface Insight {
  id: number
  insight_type: string
  dimension: string
  content: string
  abstraction_level: number
  maturity: 'emerging' | 'developing' | 'established' | 'declining' | 'superseded' | 'rejected'
  confidence: number
  stability_score: number
  support_count: number
  contradiction_count: number
  user_override: boolean
  version: number
  created_at: string | null
  updated_at: string | null
}

export interface PersonaDocument {
  id: number
  content: string
  structured_sections: Record<string, unknown>
  user_edited_sections: Record<string, unknown>
  cited_insight_ids: number[]
  version: number
  is_active: boolean
  change_summary: string | null
  edited_by: string
  created_at: string | null
}

export interface PersonaListQuery {
  dimension?: string
  maturity?: string
  observation_type?: string
  page?: number
  page_size?: number
}



// ── 活动类型 ─────────────────────────────────────────────────────────────────

/** 活动记录 */
export interface Activity {
  id: number
  app_name: string
  window_title: string | null
  started_at: string
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
  priority?: number
}

/** 隐私规则列表查询参数 */
export interface PrivacyRuleListQuery {
  rule_type?: string
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

// ── 数据治理类型 ──────────────────────────────────────────────────────────────// ── 数据治理类型 ──────────────────────────────────────────────────────────────

/** 数据导出请求 */
export interface DataExportRequest {
  export_type: 'full' | 'partial'
  scope?: string[]
  start_time?: string
  end_time?: string
}

/** 数据导出响应 */
export interface DataExportResponse {
  id: number
  export_type: string
  scope: string | null
  start_time: string | null
  end_time: string | null
  status: string
  file_path: string
  file_size_bytes: number | null
  record_count: number | null
  error_message: string | null
  created_at: string | null
}

/** 备份响应 */
export interface BackupResponse {
  id: number
  file_path: string
  file_size_bytes: number | null
  status: string
  error_message: string | null
  created_at: string | null
}

/** 备份列表查询参数 */
export interface BackupListQuery {
  page?: number
  page_size?: number
}

/** 清除全部数据请求 */
export interface ClearDataRequest {
  confirm_key: string
}

/** 清除全部数据响应 */
export interface ClearDataResponse {
  cleared_tables: string[]
  cleared_backups: boolean
  cleared_exports: boolean
}

/** 数据量统计响应 */
export interface DataVolumeStats {
  sessions: number
  messages: number
  memories: number
  memory_sources: number
  memory_revisions: number
  memory_references: number
  activities: number
  privacy_rules: number
  observations: number
  insights: number
  insight_evidence: number
  insight_revisions: number
  persona_states: number
  persona_documents: number
  audit_logs: number
  background_tasks: number
  model_configs: number
  data_exports: number
  backup_records: number
}

// ── 系统状态类型 ──────────────────────────────────────────────────────────

/** 系统状态响应 */
export interface SystemStatusResponse {
  service: {
    name: string
    version: string
    status: string
    uptime: string | null
  }
  database: {
    status: 'ok' | 'error'
    error_message?: string | null
    ready: boolean
    migration_completed: boolean
    file_size_bytes: number
    fts5_ready: boolean
    fts5_index_count: number
    vector_ready: boolean
    vector_index_count: number
    table_counts: Record<string, number>
  }
  model_config: {
    status: 'ok' | 'error'
    error_message?: string | null
    total_configs: number
    active_count: number
    error_count: number
    active_config: {
      id: number
      name: string
      provider: string
      model_name: string
      status: string
      has_key: boolean
      error_message: string | null
    } | null
    configured: boolean
    available: boolean
  }
  data_directory: {
    path: string
    writable: boolean
    file_count: number
    total_size_bytes: number
    scan_limited: boolean
  }
  background_tasks: {
    status: 'ok' | 'error'
    error_message?: string | null
    pending: number
    running: number
    failed: number
    retrying: number
    total_backlog: number
    healthy: boolean
  }
  backup: {
    status: 'ok' | 'error'
    error_message?: string | null
    total_backups: number
    latest_backup_at: string | null
    latest_backup_status: string | null
    latest_backup_size_bytes: number | null
  }
  activity_collection: {
    status: 'ok' | 'error'
    error_message?: string | null
    privacy_rules_total: number
    activities_today: number
    activities_total: number
  }
  checked_at: string
}

/** 审计日志统计 */
export interface AuditStats {
  total: number
  success: number
  fail: number
  by_action: { action: string; count: number }[]
}

/** 审计日志记录 */
export interface AuditLogResponse {
  id: number
  action: string
  target_type: string | null
  target_id: number | null
  summary: string | null
  detail: string | null
  result: number
  created_at: string | null
}

// ── Electron 运行时状态类型 ──────────────────────────────────────────

/** Electron 运行时状态 */
export interface ElectronAppStatus {
  electronVersion: string
  nodeVersion: string
  chromeVersion: string
  appVersion: string
  pid: number
  platform: string
  uptime: number
}
