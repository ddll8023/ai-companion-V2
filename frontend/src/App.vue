<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useAppStore } from '@/stores/app'
import AppLayout from '@/components/system/AppLayout.vue'

const appStore = useAppStore()

onMounted(() => {
  // 浏览器开发模式：直接获取健康状态
  if (!window.electronAPI) {
    appStore.fetchHealth()
  }

  // Electron 模式：监听后端状态事件
  if (window.electronAPI) {
    window.electronAPI.onBackendStatus((status) => {
      appStore.updateBackendStatus(status)
    })
  }
})

onUnmounted(() => {
  if (window.electronAPI) {
    window.electronAPI.removeBackendStatusListener()
  }
})
</script>

<template>
  <AppLayout />
</template>
