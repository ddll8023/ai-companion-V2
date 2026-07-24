import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '@/composables/useApi'
import type { HealthData } from '@/types/api'

/** IPC 后端状态事件类型 */
interface BackendStatusEvent {
  ready: boolean
}

/** 应用状态 Store */
export const useAppStore = defineStore('app', () => {
  const healthData = ref<HealthData | null>(null)
  const backendReady = ref(false)
  const loading = ref(false)
  const error = ref<string | null>(null)
  /** 是否已创建过会话（供 Dashboard 引导流程使用） */
  const hasSession = ref(false)

  /** 刷新健康状态 */
  async function fetchHealth() {
    loading.value = true
    error.value = null
    try {
      const api = useApi()
      const res = await api.get<HealthData>('/health')
      healthData.value = res.data
      backendReady.value = res.data.status === 'running'
    } catch (e: unknown) {
      backendReady.value = false
      error.value = e instanceof Error ? e.message : '无法连接服务'
    } finally {
      loading.value = false
    }
  }

  /** 由 IPC 事件通知更新后端状态（Electron 模式） */
  function updateBackendStatus(status: BackendStatusEvent) {
    backendReady.value = status.ready
    if (!status.ready) {
      error.value = '本地服务不可用'
    } else {
      error.value = null
      // 服务恢复时自动刷新完整健康状态
      fetchHealth()
    }
  }

  return {
    healthData,
    backendReady,
    loading,
    error,
    hasSession,
    fetchHealth,
    updateBackendStatus,
  }
})
