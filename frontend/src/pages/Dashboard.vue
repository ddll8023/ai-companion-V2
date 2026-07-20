<template>
  <div class="p-6">
    <div class="mb-6">
      <h2 class="text-xl font-semibold text-text">今日概览</h2>
      <p class="mt-1 text-sm text-text-secondary">查看系统状态和待办事项</p>
    </div>

    <!-- 系统状态卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
      <div class="p-4 bg-surface rounded-lg border border-border">
        <div class="flex items-center gap-2 text-sm text-text-secondary">
          <font-awesome-icon :icon="['fas', 'server']" />
          <span>服务状态</span>
        </div>
        <p
          class="mt-2 text-lg font-semibold"
          :class="healthData?.status === 'running' ? 'text-success' : 'text-error'"
        >
          {{ healthData?.status === 'running' ? '运行中' : '异常' }}
        </p>
      </div>

      <div class="p-4 bg-surface rounded-lg border border-border">
        <div class="flex items-center gap-2 text-sm text-text-secondary">
          <font-awesome-icon :icon="['fas', 'database']" />
          <span>数据库</span>
        </div>
        <p
          class="mt-2 text-lg font-semibold"
          :class="healthData?.database?.ready ? 'text-success' : 'text-error'"
        >
          {{ healthData?.database?.ready ? '就绪' : '不可用' }}
        </p>
      </div>

      <div class="p-4 bg-surface rounded-lg border border-border">
        <div class="flex items-center gap-2 text-sm text-text-secondary">
          <font-awesome-icon :icon="['fas', 'folder']" />
          <span>数据目录</span>
        </div>
        <p
          class="mt-2 text-lg font-semibold"
          :class="healthData?.data_directory?.writable ? 'text-success' : 'text-error'"
        >
          {{ healthData?.data_directory?.writable ? '可写' : '不可写' }}
        </p>
      </div>
    </div>

    <ErrorState
      :error="error"
      :show-retry="true"
      @retry="loadHealth"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getHealth } from '@/api/health'
import type { HealthData } from '@/types/api'
import ErrorState from '@/components/custom/ErrorState.vue'

const healthData = ref<HealthData | null>(null)
const error = ref<string | null>(null)

onMounted(() => {
  loadHealth()
})

async function loadHealth() {
  error.value = null
  try {
    const res = await getHealth()
    healthData.value = res.data
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '无法获取服务状态'
  }
}
</script>
