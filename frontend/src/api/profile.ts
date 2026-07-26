import { useApi } from '@/composables/useApi'
import type {
  BehaviorStatsQuery,
  BehaviorStatsResponse,
  PaginatedResponse,
  Profile,
  ProfileCorrect,
  ProfileCreate,
  ProfileDetail,
  ProfileListQuery,
} from '@/types/api'

const api = useApi()

// ── 画像 API ─────────────────────────────────────────────────────────────

/** 创建候选画像 */
export async function createProfile(data: ProfileCreate) {
  return api.post<Profile>('/api/v1/profiles', data)
}

/** 查询画像列表 */
export async function listProfiles(query: ProfileListQuery) {
  return api.post<PaginatedResponse<Profile>>('/api/v1/profiles/list', query)
}

/** 获取画像详情 */
export async function getProfile(id: number) {
  return api.get<ProfileDetail>(`/api/v1/profiles/${id}`)
}

/** 确认候选画像 */
export async function confirmProfile(id: number) {
  return api.post<Profile>(`/api/v1/profiles/${id}/confirm`)
}

/** 纠正画像 */
export async function correctProfile(id: number, data: ProfileCorrect) {
  return api.post<Profile>(`/api/v1/profiles/${id}/correct`, data)
}

/** 否定画像 */
export async function rejectProfile(id: number) {
  return api.post<Profile>(`/api/v1/profiles/${id}/reject`)
}

/** 删除画像 */
export async function deleteProfile(id: number) {
  return api.delete<null>(`/api/v1/profiles/${id}`)
}

/** 提取画像（从已确认记忆中） */
/** 画像演化结果统计 */
export interface ProfileEvolveResult {
  created?: number
  reinforced?: number
  revised?: number
  skipped?: number
  reason?: string
  error?: string
}

export async function extractProfiles() {
  return api.post<{ result: ProfileEvolveResult }>('/api/v1/profiles/extract')
}

/** 获取行为统计 */
export async function getBehaviorStats(query: BehaviorStatsQuery) {
  return api.post<BehaviorStatsResponse>('/api/v1/statistics/behavior', query)
}
