<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useApi } from '@/composables/useApi'
import { useAppStore } from '@/stores/app'
import AppLayout from '@/components/system/AppLayout.vue'

const appStore = useAppStore()
const api = useApi()

onMounted(() => {
  // Electron 模式：通过 IPC 事件推送获取后端状态
  // 浏览器模式：onBackendStatus 为 undefined，直接主动请求健康状态
  if (api.onBackendStatus) {
    api.onBackendStatus((status) => {
      appStore.updateBackendStatus(status)
    })
  } else {
    appStore.fetchHealth()
  }
})

onUnmounted(() => {
  if (api.removeBackendStatusListener) {
    api.removeBackendStatusListener()
  }
})
</script>

<template>
  <AppLayout />
</template>
