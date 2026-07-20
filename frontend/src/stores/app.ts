import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getHealth } from '@/api/health'
import type { HealthData } from '@/types/api'

/** 应用状态 Store */
export const useAppStore = defineStore('app', () => {
  const healthData = ref<HealthData | null>(null)
  const backendReady = ref(false)
  const loading = ref(false)
  const error = ref<string | null>(null)

  /** 刷新健康状态 */
  async function fetchHealth() {
    loading.value = true
    error.value = null
    try {
      const res = await getHealth()
      healthData.value = res.data
      backendReady.value = res.data.status === 'running'
    } catch (e: unknown) {
      backendReady.value = false
      error.value = e instanceof Error ? e.message : '无法连接服务'
    } finally {
      loading.value = false
    }
  }

  return {
    healthData,
    backendReady,
    loading,
    error,
    fetchHealth,
  }
})
