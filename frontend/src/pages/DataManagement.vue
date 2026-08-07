<template>
  <div class="p-6 max-w-4xl">
    <!-- 页面标题 -->
    <div class="mb-6">
      <h2 class="text-xl font-semibold text-text">数据管理</h2>
      <p class="mt-1 text-sm text-text-secondary">管理数据导出、手动备份和数据清理</p>
    </div>

    <!-- ── 数据量概览 ──────────────────────────────────────── -->
    <div class="mb-6">
      <h3 class="text-sm font-medium text-text mb-3">数据量概览</h3>
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
        <div
          v-for="item in volumeItems"
          :key="item.key"
          class="p-3 bg-surface border border-border rounded-lg text-center"
        >
          <div class="text-lg font-semibold text-text">{{ volume[item.key] ?? 0 }}</div>
          <div class="mt-0.5 text-xs text-text-tertiary">{{ item.label }}</div>
        </div>
      </div>
      <div v-if="volumeLoading" class="mt-2 text-xs text-text-tertiary">加载中...</div>
      <div v-if="volumeError" class="mt-2 text-xs text-error flex items-center gap-1">
        <font-awesome-icon :icon="['fas', 'triangle-exclamation']" />
        <span>{{ volumeError }}</span>
        <button class="ml-1 underline hover:text-error/80" @click="fetchVolume">重试</button>
      </div>
    </div>

    <!-- ── 导出与备份 ──────────────────────────────────────── -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
      <!-- 导出 -->
      <div class="p-4 bg-surface border border-border rounded-lg">
        <h3 class="text-sm font-medium text-text mb-1">数据导出</h3>
        <p class="text-xs text-text-tertiary mb-4">将本地数据导出为 JSON 文件</p>

        <div class="space-y-3">
          <button
            class="w-full px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50"
            :disabled="exporting"
            @click="handleExport"
          >
            <font-awesome-icon v-if="exporting" :icon="['fas', 'spinner']" class="mr-1 animate-spin" />
            <font-awesome-icon v-else :icon="['fas', 'download']" class="mr-1" />
            {{ exporting ? '导出中...' : '导出全部数据' }}
          </button>

          <div v-if="exportResult" class="p-2 bg-bg rounded-lg text-xs space-y-1">
            <div class="text-text-secondary">导出完成</div>
            <div class="text-text-tertiary">记录数: {{ exportResult.record_count }}</div>
            <div class="text-text-tertiary">大小: {{ formatFileSize(exportResult.file_size_bytes) }}</div>
            <div class="text-text-tertiary truncate" :title="exportResult.file_path">
              路径: {{ exportResult.file_path }}
            </div>
          </div>
          <div v-if="exportError" class="text-xs text-error">{{ exportError }}</div>
        </div>
      </div>

      <!-- 备份 -->
      <div class="p-4 bg-surface border border-border rounded-lg">
        <h3 class="text-sm font-medium text-text mb-1">数据库备份</h3>
        <p class="text-xs text-text-tertiary mb-4">创建和删除数据库备份</p>

        <div class="space-y-3">
          <button
            class="w-full px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50"
            :disabled="backingUp"
            @click="handleCreateBackup"
          >
            <font-awesome-icon v-if="backingUp" :icon="['fas', 'spinner']" class="mr-1 animate-spin" />
            <font-awesome-icon v-else :icon="['fas', 'floppy-disk']" class="mr-1" />
            {{ backingUp ? '备份中...' : '创建备份' }}
          </button>

          <div v-if="backupResult" class="p-2 bg-bg rounded-lg text-xs space-y-1">
            <div class="text-text-secondary">备份完成</div>
            <div class="text-text-tertiary">大小: {{ formatFileSize(backupResult.file_size_bytes) }}</div>
          </div>
          <div v-if="backupError" class="text-xs text-error">{{ backupError }}</div>
        </div>
      </div>
    </div>

    <!-- ── 备份记录 ──────────────────────────────────────── -->
    <div class="p-4 bg-surface border border-border rounded-lg mb-6">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-medium text-text">备份记录</h3>
      </div>

      <LoadingState :loading="backupsLoading" loading-text="加载备份记录...">
        <EmptyState :empty="backups.length === 0" empty-text="暂无备份记录">
          <div class="space-y-2">
            <div
              v-for="b in backups"
              :key="b.id"
              class="flex items-center justify-between p-3 bg-bg rounded-lg"
            >
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="text-sm text-text">{{ formatTime(b.created_at) }}</span>
                  <span
                    class="inline-flex items-center px-1.5 py-0.5 text-xs rounded"
                    :class="backupStatusClass(b.status)"
                  >
                    {{ backupStatusLabel(b.status) }}
                  </span>
                </div>
                <p class="mt-0.5 text-xs text-text-tertiary">
                  {{ formatFileSize(b.file_size_bytes) }}
                </p>
              </div>
              <div class="flex items-center gap-1 ml-3 shrink-0">
                <button
                  class="p-1.5 text-xs text-text-tertiary hover:text-error rounded hover:bg-error/10 transition-colors"
                  title="删除"
                  @click="handleDeleteBackup(b)"
                >
                  <font-awesome-icon :icon="['fas', 'trash-can']" />
                </button>
              </div>
            </div>
          </div>
        </EmptyState>
      </LoadingState>
      <ErrorState :error="backupsError" :show-retry="true" @retry="fetchBackups" />
    </div>

    <!-- ── 导出记录 ──────────────────────────────────────── -->
    <div class="p-4 bg-surface border border-border rounded-lg mb-6">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-medium text-text">导出记录</h3>
      </div>

      <LoadingState :loading="exportsLoading" loading-text="加载导出记录...">
        <EmptyState :empty="exports.length === 0" empty-text="暂无导出记录">
          <div class="space-y-2">
            <div
              v-for="exp in exports"
              :key="exp.id"
              class="flex items-center justify-between p-3 bg-bg rounded-lg"
            >
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="text-sm text-text">{{ formatTime(exp.created_at) }}</span>
                  <span class="text-xs text-text-tertiary">{{ exp.export_type === 'full' ? '全量' : '部分' }}</span>
                  <span
                    class="inline-flex items-center px-1.5 py-0.5 text-xs rounded"
                    :class="exp.status === 'completed' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
                  >
                    {{ exp.status === 'completed' ? '完成' : '失败' }}
                  </span>
                </div>
                <p class="mt-0.5 text-xs text-text-tertiary">
                  {{ exp.record_count ?? 0 }} 条记录 · {{ formatFileSize(exp.file_size_bytes) }}
                </p>
              </div>
              <button
                class="p-1.5 text-xs text-text-tertiary hover:text-error rounded hover:bg-error/10 transition-colors"
                title="删除"
                @click="handleDeleteExport(exp)"
              >
                <font-awesome-icon :icon="['fas', 'trash-can']" />
              </button>
            </div>
          </div>
        </EmptyState>
      </LoadingState>
      <ErrorState :error="exportsError" :show-retry="true" @retry="fetchExports" />
    </div>

    <!-- ── 清除全部数据 ──────────────────────────────────────── -->
    <div class="p-4 bg-surface border border-border rounded-lg border-error/20">
      <h3 class="text-sm font-medium text-error mb-1">清除全部数据</h3>
      <p class="text-xs text-text-tertiary mb-4">
        此操作将清除所有本地数据，包括对话、记忆和活动记录。此操作不可逆。
      </p>

      <div class="space-y-3">
        <div class="flex items-center gap-2">
          <input
            v-model="clearConfirmText"
            type="text"
            placeholder="输入 CLEAR ALL DATA 确认"
            class="flex-1 px-3 py-1.5 text-sm border border-border rounded-lg bg-bg text-text placeholder-text-tertiary focus:outline-none focus:border-error"
            maxlength="20"
          />
          <button
            class="px-4 py-1.5 text-sm font-medium text-white bg-error rounded-lg hover:bg-error/90 transition-colors disabled:opacity-50"
            :disabled="clearConfirmText !== 'CLEAR ALL DATA' || clearing"
            @click="handleClearAll"
          >
            <font-awesome-icon v-if="clearing" :icon="['fas', 'spinner']" class="mr-1 animate-spin" />
            <font-awesome-icon v-else :icon="['fas', 'trash-can']" class="mr-1" />
            {{ clearing ? '清除中...' : '清除全部数据' }}
          </button>
        </div>

        <div v-if="clearResult" class="p-2 bg-bg rounded-lg text-xs text-text-secondary">
          已清除 {{ clearResult.cleared_tables.length }} 张表
        </div>
        <div v-if="clearError" class="text-xs text-error">{{ clearError }}</div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import LoadingState from '@/components/custom/LoadingState.vue'
import EmptyState from '@/components/custom/EmptyState.vue'
import ErrorState from '@/components/custom/ErrorState.vue'
import { formatTime } from '@/utils/format'
import {
  getDataVolume,
  exportData,
  listExports,
  deleteExport,
  createBackup,
  listBackups,
  deleteBackup,
  clearAllData,
} from '@/api/data'
import type {
  DataExportResponse,
  BackupResponse,
  ClearDataResponse,
} from '@/types/api'

// ── 数据量 ─────────────────────────────────────────────────────────────────

const volume = reactive<Record<string, number>>({})
const volumeLoading = ref(false)
const volumeError = ref<string | null>(null)

const volumeItems = [
  { key: 'sessions', label: '会话' },
  { key: 'messages', label: '消息' },
  { key: 'memories', label: '记忆' },
  { key: 'activities', label: '活动' },
  { key: 'observations', label: '人物观察' },
  { key: 'insights', label: '人物洞见' },
  { key: 'persona_documents', label: '人物侧写' },
  { key: 'audit_logs', label: '审计日志' },
  { key: 'background_tasks', label: '后台任务' },
]

async function fetchVolume() {
  volumeLoading.value = true
  volumeError.value = null
  try {
    const res = await getDataVolume()
    Object.assign(volume, res.data)
  } catch (e: unknown) {
    volumeError.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    volumeLoading.value = false
  }
}

// ── 导出 ────────────────────────────────────────────────────────────────────

const exporting = ref(false)
const exportResult = ref<DataExportResponse | null>(null)
const exportError = ref<string | null>(null)
const exports = ref<DataExportResponse[]>([])
const exportsLoading = ref(false)
const exportsError = ref<string | null>(null)

async function handleExport() {
  if (exporting.value) return
  exporting.value = true
  exportError.value = null
  exportResult.value = null
  try {
    const res = await exportData({ export_type: 'full' })
    exportResult.value = res.data
    await fetchExports()
  } catch (e: unknown) {
    exportError.value = e instanceof Error ? e.message : '导出失败'
  } finally {
    exporting.value = false
  }
}

async function fetchExports() {
  exportsLoading.value = true
  exportsError.value = null
  try {
    const res = await listExports(1, 20)
    exports.value = res.data.lists
  } catch (e: unknown) {
    exportsError.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    exportsLoading.value = false
  }
}

async function handleDeleteExport(exp: DataExportResponse) {
  try {
    await deleteExport(exp.id)
    await fetchExports()
  } catch (e: unknown) {
    exportsError.value = e instanceof Error ? e.message : '删除失败'
  }
}

// ── 备份 ────────────────────────────────────────────────────────────────────

const backingUp = ref(false)
const backupResult = ref<BackupResponse | null>(null)
const backupError = ref<string | null>(null)
const backups = ref<BackupResponse[]>([])
const backupsLoading = ref(false)
const backupsError = ref<string | null>(null)

async function handleCreateBackup() {
  if (backingUp.value) return
  backingUp.value = true
  backupError.value = null
  backupResult.value = null
  try {
    const res = await createBackup()
    backupResult.value = res.data
    await fetchBackups()
  } catch (e: unknown) {
    backupError.value = e instanceof Error ? e.message : '备份失败'
  } finally {
    backingUp.value = false
  }
}

async function fetchBackups() {
  backupsLoading.value = true
  backupsError.value = null
  try {
    const res = await listBackups({ page: 1, page_size: 50 })
    backups.value = res.data.lists
  } catch (e: unknown) {
    backupsError.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    backupsLoading.value = false
  }
}

async function handleDeleteBackup(backup: BackupResponse) {
  try {
    await deleteBackup(backup.id)
    await fetchBackups()
  } catch (e: unknown) {
    backupsError.value = e instanceof Error ? e.message : '删除失败'
  }
}

// ── 清除全部数据 ────────────────────────────────────────────────────────────

const clearConfirmText = ref('')
const clearing = ref(false)
const clearResult = ref<ClearDataResponse | null>(null)
const clearError = ref<string | null>(null)

async function handleClearAll() {
  if (clearing.value) return
  clearing.value = true
  clearError.value = null
  clearResult.value = null
  try {
    const res = await clearAllData({ confirm_key: clearConfirmText.value })
    clearResult.value = res.data
    clearConfirmText.value = ''
    await fetchVolume()
  } catch (e: unknown) {
    clearError.value = e instanceof Error ? e.message : '清除失败'
  } finally {
    clearing.value = false
  }
}

// ── 工具函数 ──────────────────────────────────────────────────────────────

function formatFileSize(bytes: number | null): string {
  if (bytes == null) return '未知'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function backupStatusClass(st: string): string {
  switch (st) {
    case 'completed': return 'bg-green-100 text-green-700'
    case 'failed': return 'bg-red-100 text-red-700'
    default: return 'bg-gray-100 text-gray-500'
  }
}

function backupStatusLabel(st: string): string {
  switch (st) {
    case 'completed': return '完成'
    case 'failed': return '失败'
    default: return st
  }
}

// ── 生命周期 ──────────────────────────────────────────────────────────────

onMounted(() => {
  fetchVolume()
  fetchExports()
  fetchBackups()
})
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
