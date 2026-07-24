<template>
  <div class="p-6 max-w-5xl">
    <!-- 页面标题 -->
    <div class="mb-6">
      <h2 class="text-xl font-semibold text-text">长期记忆</h2>
      <p class="mt-1 text-sm text-text-secondary">审查和管理 AI 从对话中提取的候选记忆</p>
    </div>

    <!-- 搜索栏 -->
    <div class="mb-4">
      <div class="relative">
        <font-awesome-icon
          :icon="['fas', 'search']"
          class="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary text-sm"
        />
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索记忆内容..."
          class="w-full pl-9 pr-3 py-2 text-sm border border-border rounded-lg bg-bg text-text placeholder-text-tertiary focus:outline-none focus:border-primary transition-colors"
          @input="onSearchInput"
        />
        <button
          v-if="searchQuery"
          class="absolute right-2 top-1/2 -translate-y-1/2 text-text-tertiary hover:text-text text-sm px-1"
          @click="clearSearch"
        >
          <font-awesome-icon :icon="['fas', 'times']" />
        </button>
      </div>
    </div>

    <!-- 状态筛选标签栏 -->
    <div class="mb-4 flex items-center gap-2 flex-wrap">
      <button
        v-for="tab in statusTabs"
        :key="tab.value"
        class="px-3 py-1.5 text-sm rounded-lg transition-colors"
        :class="selectedStatus === tab.value
          ? 'bg-primary text-white'
          : 'bg-surface border border-border text-text-secondary hover:bg-hover hover:text-text'
        "
        @click="switchStatus(tab.value)"
      >
        {{ tab.label }}
        <span class="ml-1 text-xs opacity-70">({{ tab.count }})</span>
      </button>
    </div>

    <!-- 加载状态 -->
    <LoadingState :loading="loading" loading-text="加载记忆...">
      <!-- 空状态 -->
      <EmptyState :empty="memories.length === 0" empty-text="暂无记忆">

        <!-- 记忆列表 -->
        <div class="space-y-4">
          <div
            v-for="memory in memories"
            :key="memory.id"
            class="p-5 bg-surface border border-border rounded-lg"
          >
            <!-- 记忆头部 -->
            <div class="flex items-start justify-between mb-3">
              <div class="flex items-center gap-2 flex-wrap">
                <!-- 状态标签 -->
                <span
                  class="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded"
                  :class="statusClass(memory.status)"
                >
                  {{ statusLabel(memory.status) }}
                </span>
                <!-- 类型标签 -->
                <span class="inline-flex items-center px-2 py-0.5 text-xs text-text-tertiary bg-hover rounded">
                  {{ typeLabel(memory.type) }}
                </span>
                <!-- 重要性 -->
                <span class="text-xs text-text-tertiary">
                  重要性: {{ memory.importance }}/10
                </span>
                <!-- 版本 -->
                <span v-if="memory.version > 1" class="text-xs text-text-tertiary">
                  v{{ memory.version }}
                </span>
              </div>
            </div>

            <!-- 记忆正文 -->
            <p class="text-sm text-text leading-relaxed whitespace-pre-wrap break-words mb-3">
              {{ memory.content }}
            </p>

            <!-- 错误信息 -->
            <p v-if="memory.error_message" class="mb-3 text-xs text-error">
              {{ memory.error_message }}
            </p>

            <!-- 来源信息 -->
            <div v-if="memory.session_id" class="mb-3 text-xs text-text-tertiary">
              来源: 会话 #{{ memory.session_id }}
            </div>

            <!-- 操作按钮 -->
            <div class="flex items-center gap-2 flex-wrap pt-3 border-t border-border">
              <!-- 确认（仅候选） -->
              <button
                v-if="memory.status === 'candidate'"
                class="px-3 py-1.5 text-xs font-medium text-white bg-success rounded-lg hover:bg-success/90 transition-colors"
                :disabled="actionLoading === memory.id"
                @click="handleConfirm(memory)"
              >
                <font-awesome-icon :icon="['fas', 'check']" class="mr-1" />
                确认
              </button>

              <!-- 纠正 -->
              <button
                v-if="memory.status !== 'deleted' && memory.status !== 'rejected'"
                class="px-3 py-1.5 text-xs font-medium text-text-secondary bg-hover border border-border rounded-lg hover:bg-primary/10 hover:text-primary transition-colors"
                :disabled="actionLoading === memory.id"
                @click="openCorrect(memory)"
              >
                <font-awesome-icon :icon="['fas', 'pen']" class="mr-1" />
                纠正
              </button>

              <!-- 否定（仅候选） -->
              <button
                v-if="memory.status === 'candidate'"
                class="px-3 py-1.5 text-xs font-medium text-text-secondary bg-hover border border-border rounded-lg hover:bg-error/10 hover:text-error transition-colors"
                :disabled="actionLoading === memory.id"
                @click="handleReject(memory)"
              >
                <font-awesome-icon :icon="['fas', 'ban']" class="mr-1" />
                否定
              </button>

              <!-- 删除（仅已确认/已纠正/已否定） -->
              <button
                v-if="memory.status !== 'candidate' && memory.status !== 'deleted'"
                class="px-3 py-1.5 text-xs font-medium text-error bg-hover border border-border rounded-lg hover:bg-error hover:text-white transition-colors"
                :disabled="actionLoading === memory.id"
                @click="handleDelete(memory)"
              >
                <font-awesome-icon :icon="['fas', 'trash']" class="mr-1" />
                删除
              </button>

              <!-- 查看详情 -->
              <button
                class="px-3 py-1.5 text-xs font-medium text-primary bg-primary-light rounded-lg hover:bg-primary/20 transition-colors ml-auto"
                @click="openDetail(memory)"
              >
                详情
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
      共 {{ total }} 条记忆，当前第 {{ page }} 页
    </div>

    <!-- 错误状态 -->
    <ErrorState :error="error" :show-retry="true" @retry="fetchMemories" />

    <!-- 纠正对话框 -->
    <Transition name="fade">
      <div
        v-if="correctDialogVisible"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
        @click.self="closeCorrectDialog"
      >
        <div class="w-[32rem] p-5 bg-surface rounded-xl border border-border shadow-lg">
          <h3 class="text-base font-medium text-text mb-4">纠正记忆</h3>

          <div class="mb-4">
            <label class="block text-sm font-medium text-text mb-1">记忆内容</label>
            <textarea
              v-model="correctForm.content"
              class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text placeholder-text-tertiary resize-none focus:outline-none focus:border-primary"
              rows="4"
              placeholder="输入纠正后的记忆内容"
            />
          </div>

          <div class="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label class="block text-sm font-medium text-text mb-1">类型</label>
              <select
                v-model="correctForm.type"
                class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text focus:outline-none focus:border-primary"
              >
                <option value="fact">事实</option>
                <option value="preference">偏好</option>
                <option value="event">事件</option>
                <option value="goal">目标</option>
                <option value="habit">习惯</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-text mb-1">重要性 (1-10)</label>
              <input
                v-model.number="correctForm.importance"
                type="number"
                min="1"
                max="10"
                class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text focus:outline-none focus:border-primary"
              />
            </div>
          </div>

          <div class="flex items-center gap-3">
            <button
              class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-dark transition-colors disabled:opacity-50"
              :disabled="!correctForm.content || correctSaving"
              @click="handleCorrect"
            >
              {{ correctSaving ? '保存中...' : '保存' }}
            </button>
            <button
              class="px-4 py-2 text-sm font-medium text-text-secondary bg-hover rounded-lg hover:text-text transition-colors"
              @click="closeCorrectDialog"
            >
              取消
            </button>
            <span v-if="correctError" class="text-sm text-error">{{ correctError }}</span>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 详情对话框 -->
    <Transition name="fade">
      <div
        v-if="detailVisible"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
        @click.self="closeDetail"
      >
        <div class="w-[36rem] max-h-[80vh] overflow-y-auto p-5 bg-surface rounded-xl border border-border shadow-lg">
          <h3 class="text-base font-medium text-text mb-4">记忆详情</h3>

          <div v-if="detailData" class="space-y-4">
            <!-- 基本信息 -->
            <div class="grid grid-cols-2 gap-3 text-sm">
              <div>
                <span class="text-text-tertiary">状态：</span>
                <span class="text-text">{{ statusLabel(detailData.memory.status) }}</span>
              </div>
              <div>
                <span class="text-text-tertiary">类型：</span>
                <span class="text-text">{{ typeLabel(detailData.memory.type) }}</span>
              </div>
              <div>
                <span class="text-text-tertiary">重要性：</span>
                <span class="text-text">{{ detailData.memory.importance }}/10</span>
              </div>
              <div>
                <span class="text-text-tertiary">版本：</span>
                <span class="text-text">v{{ detailData.memory.version }}</span>
              </div>
            </div>

            <!-- 记忆内容 -->
            <div>
              <h4 class="text-sm font-medium text-text mb-1">记忆内容</h4>
              <p class="text-sm text-text bg-bg p-3 rounded-lg whitespace-pre-wrap break-words">
                {{ detailData.memory.content }}
              </p>
            </div>

            <!-- 来源 -->
            <div v-if="detailData.sources.length > 0">
              <h4 class="text-sm font-medium text-text mb-2">
                来源证据 ({{ detailData.sources.length }})
              </h4>
              <div class="space-y-2">
                <div
                  v-for="source in detailData.sources"
                  :key="source.id"
                  class="p-3 bg-bg rounded-lg"
                >
                  <div class="text-xs text-text-tertiary mb-1">
                    来源: {{ source.source_type }} #{{ source.source_id }}
                  </div>
                  <p v-if="source.content_preview" class="text-xs text-text-secondary">
                    {{ source.content_preview }}
                  </p>
                </div>
              </div>
            </div>

            <!-- 修订历史 -->
            <div v-if="detailData.revisions.length > 0">
              <h4 class="text-sm font-medium text-text mb-2">
                修订历史 ({{ detailData.revisions.length }})
              </h4>
              <div class="space-y-2">
                <div
                  v-for="rev in detailData.revisions"
                  :key="rev.id"
                  class="p-3 bg-bg rounded-lg"
                >
                  <div class="text-xs text-text-tertiary mb-1">
                    由 {{ rev.changed_by }} 修改
                  </div>
                  <p class="text-xs text-text-secondary whitespace-pre-wrap break-words">
                    {{ rev.previous_content }}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div class="mt-4 flex justify-end">
            <button
              class="px-4 py-2 text-sm font-medium text-text-secondary bg-hover rounded-lg hover:text-text transition-colors"
              @click="closeDetail"
            >
              关闭
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 删除确认对话框 -->
    <ConfirmDialog
      :visible="showDeleteDialog"
      title="确认删除记忆"
      :message="deleteTarget ? `确定删除这条记忆吗？删除后不可恢复。` : ''"
      confirm-text="删除"
      cancel-text="取消"
      :danger="true"
      @confirm="confirmDelete"
      @cancel="showDeleteDialog = false"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import type { Memory, MemoryDetail } from '@/types/api'
import * as memoryApi from '@/api/memory'
import LoadingState from '@/components/custom/LoadingState.vue'
import EmptyState from '@/components/custom/EmptyState.vue'
import ErrorState from '@/components/custom/ErrorState.vue'
import ConfirmDialog from '@/components/custom/ConfirmDialog.vue'

// ── 状态筛选 ──
type StatusFilter = string | undefined

const statusTabs = ref([
  { value: undefined, label: '全部', count: 0 },
  { value: 'candidate', label: '候选', count: 0 },
  { value: 'confirmed', label: '已确认', count: 0 },
  { value: 'corrected', label: '已纠正', count: 0 },
  { value: 'rejected', label: '已否定', count: 0 },
])

const selectedStatus = ref<StatusFilter>(undefined)

function switchStatus(status: StatusFilter) {
  selectedStatus.value = status
  resetAndFetch()
}

// ── 搜索 ──
const searchQuery = ref('')
let searchTimer: ReturnType<typeof setTimeout> | null = null

function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    resetAndFetch()
  }, 350) // 350ms 防抖，用户停止输入后才发起请求
}

function clearSearch() {
  searchQuery.value = ''
  resetAndFetch()
}

/** 重置分页并刷新 */
function resetAndFetch() {
  page.value = 1
  memories.value = []
  fetchMemories()
}

// ── 记忆列表 ──
const memories = ref<Memory[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const page = ref(1)
const total = ref(0)
const pageSize = 20

const hasMore = computed(() => {
  return memories.value.length < total.value
})

// ── 操作状态 ──
const actionLoading = ref<number | null>(null)

// ── 纠正对话框 ──
const correctDialogVisible = ref(false)
const correctTarget = ref<Memory | null>(null)
const correctSaving = ref(false)
const correctError = ref<string | null>(null)
const correctForm = ref({
  content: '',
  type: 'fact',
  importance: 5,
})

function openCorrect(memory: Memory) {
  correctTarget.value = memory
  correctForm.value = {
    content: memory.content,
    type: memory.type,
    importance: memory.importance,
  }
  correctError.value = null
  correctDialogVisible.value = true
}

function closeCorrectDialog() {
  correctDialogVisible.value = false
  correctTarget.value = null
  correctError.value = null
}

// ── 详情对话框 ──
const detailVisible = ref(false)
const detailData = ref<MemoryDetail | null>(null)

async function openDetail(memory: Memory) {
  try {
    const res = await memoryApi.getMemory(memory.id)
    detailData.value = res.data
    detailVisible.value = true
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '获取记忆详情失败'
  }
}

function closeDetail() {
  detailVisible.value = false
  detailData.value = null
}

// ── 删除确认 ──
const showDeleteDialog = ref(false)
const deleteTarget = ref<Memory | null>(null)

// ── 数据加载 ──
async function fetchMemories() {
  loading.value = true
  error.value = null
  try {
    const query: Record<string, unknown> = {
      page: page.value,
      page_size: pageSize,
    }
    if (selectedStatus.value) {
      query.status = selectedStatus.value
    }
    if (searchQuery.value.trim()) {
      query.keyword = searchQuery.value.trim()
    }
    const res = await memoryApi.listMemories(query as any)
    if (page.value === 1) {
      memories.value = res.data?.lists || []
    } else {
      memories.value = [...memories.value, ...(res.data?.lists || [])]
    }
    total.value = res.data?.pagination?.total || 0
    updateTabCounts()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载记忆失败'
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  page.value++
  await fetchMemories()
}

async function updateTabCounts() {
  try {
    // 搜索时有确切的 total，无需额外请求
    if (searchQuery.value.trim()) return

    // 使用 Promise.all 并行查询各状态计数，避免 N+1 串行
    const promises = statusTabs.value.map(async (tab) => {
      if (!tab.value) {
        // 全部标签：查询全量计数（不传 status 参数）
        const res = await memoryApi.listMemories({ page: 1, page_size: 1 })
        tab.count = res.data?.pagination?.total || 0
      } else {
        const res = await memoryApi.listMemories({ status: tab.value, page: 1, page_size: 1 })
        tab.count = res.data?.pagination?.total || 0
      }
    })
    await Promise.all(promises)
  } catch {
    // 更新标签计数失败不影响主流程
  }
}

// ── 操作处理 ──
async function handleConfirm(memory: Memory) {
  actionLoading.value = memory.id
  try {
    await memoryApi.confirmMemory(memory.id)
    memory.status = 'confirmed'
    await fetchMemories()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '确认记忆失败'
  } finally {
    actionLoading.value = null
  }
}

async function handleCorrect() {
  if (!correctTarget.value || !correctForm.value.content) return
  correctSaving.value = true
  correctError.value = null
  try {
    await memoryApi.correctMemory(correctTarget.value.id, {
      content: correctForm.value.content,
      type: correctForm.value.type,
      importance: correctForm.value.importance,
    })
    closeCorrectDialog()
    await fetchMemories()
  } catch (e: unknown) {
    correctError.value = e instanceof Error ? e.message : '纠正记忆失败'
  } finally {
    correctSaving.value = false
  }
}

async function handleReject(memory: Memory) {
  actionLoading.value = memory.id
  try {
    await memoryApi.rejectMemory(memory.id)
    memory.status = 'rejected'
    await fetchMemories()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '否定记忆失败'
  } finally {
    actionLoading.value = null
  }
}

function handleDelete(memory: Memory) {
  deleteTarget.value = memory
  showDeleteDialog.value = true
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  actionLoading.value = deleteTarget.value.id
  try {
    await memoryApi.deleteMemory(deleteTarget.value.id)
    await fetchMemories()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '删除记忆失败'
  } finally {
    actionLoading.value = null
    showDeleteDialog.value = false
    deleteTarget.value = null
  }
}

// ── 辅助函数 ──
function statusLabel(status: string): string {
  const map: Record<string, string> = {
    candidate: '候选',
    confirmed: '已确认',
    corrected: '已纠正',
    rejected: '已否定',
    deleted: '已删除',
  }
  return map[status] || status
}

function statusClass(status: string): string {
  const map: Record<string, string> = {
    candidate: 'text-yellow-600 bg-yellow-50',
    confirmed: 'text-success bg-green-50',
    corrected: 'text-primary-dark bg-primary-light',
    rejected: 'text-text-tertiary bg-hover',
    deleted: 'text-error bg-red-50',
  }
  return map[status] || 'text-text-tertiary bg-hover'
}

function typeLabel(type: string): string {
  const map: Record<string, string> = {
    fact: '事实',
    preference: '偏好',
    event: '事件',
    goal: '目标',
    habit: '习惯',
  }
  return map[type] || type
}

// ── 生命周期 ──
onMounted(async () => {
  await fetchMemories()
})
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
