<template>
  <div class="p-6 max-w-5xl">
    <!-- 页面标题 -->
    <div class="mb-6">
      <h2 class="text-xl font-semibold text-text">活动记录</h2>
      <p class="mt-1 text-sm text-text-secondary">查看和删除桌面活动记录</p>
    </div>

    <!-- 顶部统计栏 -->
    <div class="grid grid-cols-3 gap-4 mb-6">
      <div class="p-4 bg-surface rounded-lg border border-border">
        <p class="text-xs text-text-tertiary">总记录</p>
        <p class="mt-1 text-lg font-semibold text-text">{{ stats.total_count }}</p>
      </div>
      <div class="p-4 bg-surface rounded-lg border border-border">
        <p class="text-xs text-text-tertiary">今日记录</p>
        <p class="mt-1 text-lg font-semibold text-text">{{ stats.today_count }}</p>
      </div>
      <div class="p-4 bg-surface rounded-lg border border-border">
        <p class="text-xs text-text-tertiary">今日应用数</p>
        <p class="mt-1 text-lg font-semibold text-text">{{ stats.unique_apps }}</p>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="mb-4 flex items-center gap-2 flex-wrap">
      <input
        v-model="filters.keyword"
        type="text"
        class="px-3 py-1.5 text-sm border border-border rounded-lg bg-bg text-text placeholder-text-tertiary focus:outline-none focus:border-primary w-48"
        placeholder="搜索应用或窗口标题..."
        @keyup.enter="search"
      />
      <select
        v-model="filters.platform"
        class="px-3 py-1.5 text-sm border border-border rounded-lg bg-bg text-text focus:outline-none focus:border-primary"
        @change="search"
      >
        <option value="">全部平台</option>
        <option value="macos">macOS</option>
        <option value="windows">Windows</option>
      </select>
      <select
        v-model="filters.privacy_action"
        class="px-3 py-1.5 text-sm border border-border rounded-lg bg-bg text-text focus:outline-none focus:border-primary"
        @change="search"
      >
        <option value="">全部状态</option>
        <option value="allowed">已记录</option>
        <option value="blocked">已阻断</option>
        <option value="masked">已脱敏</option>
      </select>
      <button
        class="px-3 py-1.5 text-sm text-primary hover:underline"
        @click="resetFilters"
      >
        重置
      </button>
      <button
        class="px-3 py-1.5 text-sm text-error hover:underline ml-auto"
        @click="handleClearAll"
      >
        清空所有记录
      </button>
    </div>

    <!-- 加载状态 -->
    <LoadingState :loading="loading" loading-text="加载活动记录...">
      <!-- 空状态 -->
      <EmptyState :empty="activities.length === 0" empty-text="暂无活动记录">

        <!-- 活动列表 -->
        <div class="space-y-3">
          <div
            v-for="item in activities"
            :key="item.id"
            class="p-4 bg-surface border border-border rounded-lg hover:border-primary/30 transition-colors"
          >
            <div class="flex items-start justify-between">
              <div class="flex-1 min-w-0">
                <!-- 应用和平台 -->
                <div class="flex items-center gap-2 mb-1">
                  <span class="text-sm font-medium text-text truncate max-w-xs">
                    {{ item.masked_app_name || item.app_name }}
                  </span>
                  <span
                    class="inline-flex items-center px-1.5 py-0.5 text-xs rounded"
                    :class="item.platform === 'macos' ? 'bg-blue-50 text-blue-700' : 'bg-green-50 text-green-700'"
                  >
                    {{ item.platform === 'macos' ? 'macOS' : 'Windows' }}
                  </span>
                  <!-- 隐私处理状态 -->
                  <span
                    v-if="item.privacy_action !== 'allowed'"
                    class="inline-flex items-center px-1.5 py-0.5 text-xs font-medium rounded"
                    :class="privacyActionClass(item.privacy_action)"
                  >
                    {{ privacyActionLabel(item.privacy_action) }}
                  </span>
                </div>
                <!-- 窗口标题 -->
                <p
                  v-if="item.masked_window_title || item.window_title"
                  class="text-xs text-text-tertiary truncate"
                >
                  {{ item.masked_window_title || item.window_title }}
                </p>
                <!-- 时间 -->
                <div class="mt-1 flex items-center gap-3 text-xs text-text-tertiary">
                  <span>{{ formatTime(item.started_at) }}</span>
                  <span v-if="item.duration_seconds">
                    持续 {{ formatDuration(item.duration_seconds) }}
                  </span>
                </div>
              </div>
              <!-- 删除按钮 -->
              <button
                class="ml-3 p-1.5 text-text-tertiary hover:text-error transition-colors rounded hover:bg-error/10"
                title="删除"
                @click="handleDelete(item)"
              >
                <font-awesome-icon :icon="['fas', 'trash']" class="text-xs" />
              </button>
            </div>
          </div>
        </div>
      </EmptyState>
    </LoadingState>

    <!-- 加载更多 -->
    <div v-if="hasMore && !loading" class="mt-4 text-center">
      <button
        class="px-4 py-2 text-sm text-primary hover:underline"
        @click="loadMore"
      >
        加载更多
      </button>
    </div>

    <!-- 分页信息 -->
    <div v-if="total > 0" class="mt-4 text-center text-xs text-text-tertiary">
      共 {{ total }} 条记录，当前第 {{ page }} 页
    </div>

    <!-- 错误状态 -->
    <ErrorState :error="error" :show-retry="true" @retry="fetchActivities" />

    <!-- 清空确认对话框 -->
    <Transition name="fade">
      <div
        v-if="clearDialogVisible"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
        @click.self="clearDialogVisible = false"
      >
        <div class="w-96 p-5 bg-surface rounded-xl border border-border shadow-lg">
          <h3 class="text-base font-medium text-text mb-2">确认清空</h3>
          <p class="text-sm text-text-secondary mb-4">
            确定要清空所有活动记录吗？此操作不可撤销。
          </p>
          <div class="flex justify-end gap-2">
            <button
              class="px-4 py-1.5 text-sm text-text-secondary bg-hover border border-border rounded-lg hover:bg-surface transition-colors"
              @click="clearDialogVisible = false"
            >
              取消
            </button>
            <button
              class="px-4 py-1.5 text-sm text-white bg-error rounded-lg hover:bg-error/90 transition-colors"
              :disabled="actionLoading"
              @click="confirmClearAll"
            >
              确认清空
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import LoadingState from '@/components/custom/LoadingState.vue'
import EmptyState from '@/components/custom/EmptyState.vue'
import ErrorState from '@/components/custom/ErrorState.vue'
import {
  listActivities,
  getActivityStats,
  deleteActivity,
  clearActivities,
} from '@/api/activity'
import type { Activity, ActivityStats as ActivityStatsType } from '@/types/api'

// ── 状态 ──────────────────────────────────────────────────────────────────

const loading = ref(false)
const actionLoading = ref(false)
const error = ref<string | null>(null)
const activities = ref<Activity[]>([])
const stats = reactive<ActivityStatsType>({
  total_count: 0,
  today_count: 0,
  unique_apps: 0,
})
const page = ref(1)
const total = ref(0)
const pageSize = 20
const hasMore = ref(false)
const clearDialogVisible = ref(false)

const filters = reactive({
  keyword: '',
  platform: '',
  privacy_action: '',
})

// ── 数据获取 ──────────────────────────────────────────────────────────────

async function fetchStats() {
  try {
    const res = await getActivityStats()
    Object.assign(stats, res.data)
  } catch {
    // 统计不影响主列表
  }
}

async function fetchActivities() {
  loading.value = true
  error.value = null
  try {
    const res = await listActivities({
      keyword: filters.keyword || undefined,
      platform: filters.platform || undefined,
      privacy_action: filters.privacy_action || undefined,
      page: 1,
      page_size: pageSize,
    })
    activities.value = res.data.lists
    total.value = res.data.pagination.total
    page.value = 1
    hasMore.value = res.data.pagination.total_pages > 1
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  if (loading.value || !hasMore.value) return
  loading.value = true
  try {
    const nextPage = page.value + 1
    const res = await listActivities({
      keyword: filters.keyword || undefined,
      platform: filters.platform || undefined,
      privacy_action: filters.privacy_action || undefined,
      page: nextPage,
      page_size: pageSize,
    })
    activities.value.push(...res.data.lists)
    page.value = nextPage
    hasMore.value = nextPage < res.data.pagination.total_pages
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载更多失败'
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  fetchActivities()
}

function resetFilters() {
  filters.keyword = ''
  filters.platform = ''
  filters.privacy_action = ''
  fetchActivities()
}

// ── 删除操作 ──────────────────────────────────────────────────────────────

async function handleDelete(item: Activity) {
  if (actionLoading.value) return
  actionLoading.value = true
  try {
    await deleteActivity(item.id)
    activities.value = activities.value.filter((a) => a.id !== item.id)
    total.value = Math.max(0, total.value - 1)
    fetchStats()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '删除失败'
  } finally {
    actionLoading.value = false
  }
}

function handleClearAll() {
  clearDialogVisible.value = true
}

async function confirmClearAll() {
  if (actionLoading.value) return
  actionLoading.value = true
  try {
    await clearActivities()
    activities.value = []
    total.value = 0
    hasMore.value = false
    clearDialogVisible.value = false
    fetchStats()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '清空失败'
  } finally {
    actionLoading.value = false
  }
}

// ── 工具函数 ──────────────────────────────────────────────────────────────

function formatTime(dateStr: string): string {
  try {
    const d = new Date(dateStr)
    return d.toLocaleString()
  } catch {
    return dateStr
  }
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}秒`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分钟`
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${h}小时${m}分钟`
}

function privacyActionClass(action: string): string {
  switch (action) {
    case 'blocked': return 'bg-red-100 text-red-700'
    case 'masked': return 'bg-yellow-100 text-yellow-700'
    default: return 'bg-green-100 text-green-700'
  }
}

function privacyActionLabel(action: string): string {
  switch (action) {
    case 'blocked': return '已阻断'
    case 'masked': return '已脱敏'
    default: return '已记录'
  }
}

// ── 生命周期 ──────────────────────────────────────────────────────────────

onMounted(() => {
  fetchStats()
  fetchActivities()
})
</script>
