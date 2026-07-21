import request from '@/api/request'
import type { ApiResponse, HealthData } from '@/types/api'

/** 获取服务健康状态 */
export async function getHealth() {
  const res = await request.get<ApiResponse<HealthData>>('/health')
  return res.data
}
