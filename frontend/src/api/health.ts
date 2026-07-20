import request from '@/api/request'
import type { ApiResponse, HealthData } from '@/types/api'

/** 获取服务健康状态 */
export function getHealth() {
  return request.get<ApiResponse<HealthData>>('/health')
}
