<template>
  <div class="p-6 max-w-4xl">
    <!-- 页面标题 -->
    <div class="mb-6">
      <h2 class="text-xl font-semibold text-text">数据管理</h2>
      <p class="mt-1 text-sm text-text-secondary">管理数据导出、备份恢复、保留策略和数据清理</p>
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

    <!-- ── 保留策略 ──────────────────────────────────────── -->
    <div class="p-4 bg-surface border border-border rounded-lg mb-6">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h3 class="text-sm font-medium text-text">数据保留策略</h3>
          <p class="mt-0.5 text-xs text-text-tertiary">设置各类数据的自动清理期限</p>
        </div>
        <div class="flex items-center gap-2">
          <button
            class="px-3 py-1 text-xs text-text-secondary bg-hover border border-border rounded-lg hover:bg-surface transition-colors"
            @click="handleRunCleanup"
          >
            立即清理
          </button>
          <button
            class="px-3 py-1 text-xs text-white bg-primary rounded-lg hover:bg-primary/90 transition-colors"
            @click="openAddPolicy"
          >
            <font-awesome-icon :icon="['fas', 'plus']" class="mr-1" />
            添加策略
          </button>
        </div>
      </div>

      <!-- 加载状态 -->
      <LoadingState :loading="policiesLoading" loading-text="加载保留策略...">
        <EmptyState :empty="policies.length === 0" empty-text="暂无保留策略，点击上方添加">
          <!-- 策略列表 -->
          <div class="space-y-2">
            <div
              v-for="policy in policies"
              :key="policy.id"
              class="flex items-center justify-between p-3 bg-bg rounded-lg"
            >
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-medium text-text">{{ targetTypeLabel(policy.target_type) }}</span>
                  <span
                    class="inline-flex items-center px-1.5 py-0.5 text-xs rounded"
                    :class="policy.is_enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
                  >
                    {{ policy.is_enabled ? '已启用' : '已禁用' }}
                  </span>
                </div>
                <p class="mt-0.5 text-xs text-text-tertiary">
                  保留 {{ policy.retention_days }} 天
                  <template v-if="policy.description"> · {{ policy.description }}</template>
                </p>
              </div>
              <div class="flex items-center gap-1 ml-3 shrink-0">
                <button
                  class="p-1.5 text-xs text-text-tertiary hover:text-primary rounded hover:bg-primary/10 transition-colors"
                  title="编辑"
                  @click="openEditPolicy(policy)"
                >
                  <font-awesome-icon :icon="['fas', 'pen']" />
                </button>
                <button
                  class="p-1.5 text-xs text-text-tertiary hover:text-error rounded hover:bg-error/10 transition-colors"
                  title="删除"
                  @click="handleDeletePolicy(policy)"
                >
                  <font-awesome-icon :icon="['fas', 'trash-can']" />
                </button>
              </div>
            </div>
          </div>
        </EmptyState>
      </LoadingState>
      <ErrorState :error="policiesError" :show-retry="true" @retry="fetchPolicies" />
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
        <p class="text-xs text-text-tertiary mb-4">创建和恢复数据库备份</p>

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
                  <span v-if="b.backup_type === 'auto'" class="text-xs text-text-tertiary">自动</span>
                </div>
                <p class="mt-0.5 text-xs text-text-tertiary">
                  {{ formatFileSize(b.file_size_bytes) }}
                  <template v-if="b.restored_at"> · 已用于恢复: {{ formatTime(b.restored_at) }}</template>
                </p>
              </div>
              <div class="flex items-center gap-1 ml-3 shrink-0">
                <button
                  class="px-3 py-1 text-xs text-primary border border-primary/30 rounded-lg hover:bg-primary/10 transition-colors disabled:opacity-50"
                  :disabled="restoring"
                  @click="handleRestore(b)"
                >
                  {{ restoring ? '恢复中...' : '恢复' }}
                </button>
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
        此操作将清除所有本地数据，包括对话、记忆、活动记录和目标任务。此操作不可逆。
      </p>

      <div class="space-y-3">
        <div v-if="!showClearConfirm" class="flex items-center gap-2">
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

    <!-- ── 策略编辑对话框 ──────────────────────────────────── -->
    <Transition name="fade">
      <div
        v-if="policyDialogVisible"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
        @click.self="policyDialogVisible = false"
      >
        <div class="w-[28rem] p-5 bg-surface rounded-xl border border-border shadow-lg">
          <h3 class="text-base font-medium text-text mb-4">
            {{ editingPolicy ? '编辑保留策略' : '添加保留策略' }}
          </h3>

          <div class="mb-4">
            <label class="block text-sm font-medium text-text mb-1">目标数据</label>
            <select
              v-model="policyForm.target_type"
              class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text focus:outline-none focus:border-primary"
              :disabled="!!editingPolicy"
            >
              <option
                v-for="opt in targetTypeOptions"
                :key="opt.value"
                :value="opt.value"
                :disabled="usedTargetTypes.includes(opt.value) && !editingPolicy"
              >
                {{ opt.label }}
              </option>
            </select>
          </div>

          <div class="mb-4">
            <label class="block text-sm font-medium text-text mb-1">保留天数</label>
            <input
              v-model.number="policyForm.retention_days"
              type="number"
              min="1"
              max="3650"
              class="w-24 px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text focus:outline-none focus:border-primary"
            />
          </div>

          <div class="mb-4">
            <label class="block text-sm font-medium text-text mb-1">描述（可选）</label>
            <input
              v-model="policyForm.description"
              type="text"
              class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text placeholder-text-tertiary focus:outline-none focus:border-primary"
              placeholder="策略说明"
            />
          </div>

          <div class="mb-4 flex items-center gap-2">
            <input
              v-model="policyForm.is_enabled"
              type="checkbox"
              class="w-4 h-4 rounded border-border"
            />
            <label class="text-sm text-text">启用</label>
          </div>

          <div class="flex justify-end gap-2">
            <button
              class="px-4 py-1.5 text-sm text-text-secondary bg-hover border border-border rounded-lg hover:bg-surface transition-colors"
              @click="policyDialogVisible = false"
            >
              取消
            </button>
            <button
              class="px-4 py-1.5 text-sm text-white bg-primary rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50"
              :disabled="!policyForm.target_type || policyForm.retention_days < 1"
              @click="handleSavePolicy"
            >
              保存
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- ── 恢复确认对话框 ──────────────────────────────────── -->
    <Transition name="fade">
      <div
        v-if="restoreConfirmVisible"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
        @click.self="restoreConfirmVisible = false"
      >
        <div class="w-[32rem] p-5 bg-surface rounded-xl border border-border shadow-lg">
          <h3 class="text-base font-medium text-error mb-2">确认恢复</h3>
          <p class="text-sm text-text mb-2">
            从以下备份恢复数据库：
          </p>
          <p class="text-xs text-text-tertiary mb-4">
            备份时间: {{ restoreTarget ? formatTime(restoreTarget.created_at) : '' }}<br />
            文件大小: {{ restoreTarget ? formatFileSize(restoreTarget.file_size_bytes) : '' }}
          </p>
          <p class="text-sm text-text-secondary mb-2">
            恢复后，当前所有数据将被备份文件中的数据替换。系统会在恢复前自动保护当前数据库。
          </p>
          <p class="text-xs text-warning">此操作需要重启服务后才能完全生效。</p>

          <div class="mt-4 flex justify-end gap-2">
            <button
              class="px-4 py-1.5 text-sm text-text-secondary bg-hover border border-border rounded-lg hover:bg-surface transition-colors"
              @click="restoreConfirmVisible = false"
            >
              取消
            </button>
            <button
              class="px-4 py-1.5 text-sm text-white bg-error rounded-lg hover:bg-error/90 transition-colors disabled:opacity-50"
              :disabled="restoring"
              @click="confirmRestore"
            >
              {{ restoring ? '恢复中...' : '确认恢复' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- ── 恢复结果对话框 ──────────────────────────────────── -->
    <Transition name="fade">
      <div
        v-if="restoreResultVisible"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
        @click.self="restoreResultVisible = false"
      >
        <div class="w-[32rem] p-5 bg-surface rounded-xl border border-border shadow-lg">
          <h3 class="text-base font-medium text-text mb-2">恢复结果</h3>
          <p class="text-sm text-text-secondary">{{ restoreResultMsg }}</p>
          <div class="mt-4 flex justify-end">
            <button
              class="px-4 py-1.5 text-sm text-white bg-primary rounded-lg hover:bg-primary/90 transition-colors"
              @click="restoreResultVisible = false"
            >
              关闭
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, computed } from 'vue'
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
  restoreFromBackup,
  deleteBackup,
  listRetentionPolicies,
  createRetentionPolicy,
  updateRetentionPolicy,
  deleteRetentionPolicy,
  runRetentionCleanup,
  clearAllData,
} from '@/api/data'
import type {
  DataExportResponse,
  BackupResponse,
  RetentionPolicyResponse,
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
  { key: 'goals', label: '目标' },
  { key: 'tasks', label: '任务' },
  { key: 'profiles', label: '画像' },
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

// ── 保留策略 ───────────────────────────────────────────────────────────────

const policies = ref<RetentionPolicyResponse[]>([])
const policiesLoading = ref(false)
const policiesError = ref<string | null>(null)

const policyDialogVisible = ref(false)
const editingPolicy = ref<RetentionPolicyResponse | null>(null)
const policyForm = reactive({
  target_type: '',
  retention_days: 90,
  is_enabled: true,
  description: '',
})

const targetTypeOptions = [
  { value: 'activities', label: '活动记录' },
  { value: 'messages', label: '消息记录' },
  { value: 'memories', label: '记忆数据' },
  { value: 'profiles', label: '画像数据' },
  { value: 'audit_logs', label: '审计日志' },
  { value: 'backups', label: '备份记录' },
]

const usedTargetTypes = computed(() =>
  policies.value.map((p) => p.target_type),
)

async function fetchPolicies() {
  policiesLoading.value = true
  policiesError.value = null
  try {
    const res = await listRetentionPolicies()
    policies.value = res.data
  } catch (e: unknown) {
    policiesError.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    policiesLoading.value = false
  }
}

function openAddPolicy() {
  editingPolicy.value = null
  policyForm.target_type = ''
  policyForm.retention_days = 90
  policyForm.is_enabled = true
  policyForm.description = ''
  policyDialogVisible.value = true
}

function openEditPolicy(policy: RetentionPolicyResponse) {
  editingPolicy.value = policy
  policyForm.target_type = policy.target_type
  policyForm.retention_days = policy.retention_days
  policyForm.is_enabled = policy.is_enabled
  policyForm.description = policy.description ?? ''
  policyDialogVisible.value = true
}

async function handleSavePolicy() {
  try {
    if (editingPolicy.value) {
      await updateRetentionPolicy(editingPolicy.value.id, {
        retention_days: policyForm.retention_days,
        is_enabled: policyForm.is_enabled,
        description: policyForm.description || undefined,
      })
    } else {
      await createRetentionPolicy({
        target_type: policyForm.target_type,
        retention_days: policyForm.retention_days,
        is_enabled: policyForm.is_enabled,
        description: policyForm.description || undefined,
      })
    }
    policyDialogVisible.value = false
    await fetchPolicies()
  } catch (e: unknown) {
    policiesError.value = e instanceof Error ? e.message : '保存失败'
  }
}

async function handleDeletePolicy(policy: RetentionPolicyResponse) {
  try {
    await deleteRetentionPolicy(policy.id)
    await fetchPolicies()
  } catch (e: unknown) {
    policiesError.value = e instanceof Error ? e.message : '删除失败'
  }
}

async function handleRunCleanup() {
  try {
    await runRetentionCleanup()
    await fetchPolicies()
    await fetchVolume()
  } catch (e: unknown) {
    policiesError.value = e instanceof Error ? e.message : '清理失败'
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

const restoring = ref(false)
const restoreConfirmVisible = ref(false)
const restoreTarget = ref<BackupResponse | null>(null)
const restoreResultVisible = ref(false)
const restoreResultMsg = ref('')

async function handleCreateBackup() {
  if (backingUp.value) return
  backingUp.value = true
  backupError.value = null
  backupResult.value = null
  try {
    const res = await createBackup({ backup_type: 'manual' })
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

function handleRestore(backup: BackupResponse) {
  restoreTarget.value = backup
  restoreConfirmVisible.value = true
}

async function confirmRestore() {
  if (!restoreTarget.value) return
  restoring.value = true
  try {
    const res = await restoreFromBackup({ backup_id: restoreTarget.value.id })
    restoreResultMsg.value = res.data.message || '恢复成功'
    restoreConfirmVisible.value = false
    restoreResultVisible.value = true
    await fetchBackups()
    await fetchVolume()
  } catch (e: unknown) {
    restoreResultMsg.value = e instanceof Error ? e.message : '恢复失败'
    restoreConfirmVisible.value = false
    restoreResultVisible.value = true
  } finally {
    restoring.value = false
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

const showClearConfirm = ref(false)
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

function targetTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    activities: '活动记录',
    messages: '消息记录',
    memories: '记忆数据',
    profiles: '画像数据',
    audit_logs: '审计日志',
    backups: '备份记录',
  }
  return labels[type] || type
}

function formatFileSize(bytes: number | null): string {
  if (bytes == null) return '未知'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function backupStatusClass(st: string): string {
  switch (st) {
    case 'completed': return 'bg-green-100 text-green-700'
    case 'restored': return 'bg-blue-100 text-blue-700'
    case 'restoring': return 'bg-yellow-100 text-yellow-700'
    case 'failed': return 'bg-red-100 text-red-700'
    default: return 'bg-gray-100 text-gray-500'
  }
}

function backupStatusLabel(st: string): string {
  switch (st) {
    case 'completed': return '完成'
    case 'restored': return '已恢复'
    case 'restoring': return '恢复中'
    case 'failed': return '失败'
    default: return st
  }
}

// ── 生命周期 ──────────────────────────────────────────────────────────────

onMounted(() => {
  fetchVolume()
  fetchPolicies()
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
