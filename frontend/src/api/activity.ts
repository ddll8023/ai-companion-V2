import { useApi } from '@/composables/useApi'
import type {
  Activity,
  ActivityListQuery,
  ActivityStats,
  PaginatedResponse,
  PrivacyEvaluateRequest,
  PrivacyEvaluateResult,
  PrivacyRule,
  PrivacyRuleCreate,
  PrivacyRuleListQuery,
  PrivacyRuleUpdate,
} from '@/types/api'

const api = useApi()

// ── 活动记录 API ───────────────────────────────────────────────────────────

/** 查询活动记录列表 */
export async function listActivities(query: ActivityListQuery) {
  return api.post<PaginatedResponse<Activity>>('/api/v1/activities/list', query)
}

/** 获取活动统计 */
export async function getActivityStats() {
  return api.get<ActivityStats>('/api/v1/activities/stats')
}

/** 获取单条活动记录 */
export async function getActivity(id: number) {
  return api.get<Activity>(`/api/v1/activities/${id}`)
}

/** 删除单条活动记录 */
export async function deleteActivity(id: number) {
  return api.delete<null>(`/api/v1/activities/${id}`)
}

/** 清空所有活动记录 */
export async function clearActivities() {
  return api.post<number>('/api/v1/activities/clear')
}

// ── 隐私规则 API ────────────────────────────────────────────────────────────

/** 评估隐私规则 */
export async function evaluatePrivacy(req: PrivacyEvaluateRequest) {
  return api.post<PrivacyEvaluateResult>('/api/v1/activities/privacy/evaluate', req)
}

/** 创建隐私规则 */
export async function createPrivacyRule(data: PrivacyRuleCreate) {
  return api.post<PrivacyRule>('/api/v1/activities/privacy-rules', data)
}

/** 查询隐私规则列表 */
export async function listPrivacyRules(query: PrivacyRuleListQuery) {
  return api.post<PaginatedResponse<PrivacyRule>>('/api/v1/activities/privacy-rules/list', query)
}

/** 获取单条隐私规则 */
export async function getPrivacyRule(id: number) {
  return api.get<PrivacyRule>(`/api/v1/activities/privacy-rules/${id}`)
}

/** 更新隐私规则 */
export async function updatePrivacyRule(id: number, data: PrivacyRuleUpdate) {
  return api.put<PrivacyRule>(`/api/v1/activities/privacy-rules/${id}`, data)
}

/** 删除隐私规则 */
export async function deletePrivacyRule(id: number) {
  return api.delete<null>(`/api/v1/activities/privacy-rules/${id}`)
}
