<template>
  <div class="p-6 max-w-4xl">
    <!-- 页面标题 -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h2 class="text-xl font-semibold text-text">用户理解</h2>
        <p class="mt-1 text-sm text-text-secondary">管理 AI 对你的人物画像理解和行为统计</p>
      </div>
      <button
        class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50"
        :disabled="extracting"
        @click="handleExtract"
      >
        <font-awesome-icon v-if="extracting" :icon="['fas', 'spinner']" class="mr-1 animate-spin" />
        <font-awesome-icon v-else :icon="['fas', 'wand-magic-sparkles']" class="mr-1" />
        {{ extracting ? '提取中...' : '提取画像' }}
      </button>
    </div>

    <!-- ── 行为统计概览 ──────────────────────────────────────────── -->
    <div class="mb-6 space-y-4">
      <h3 class="text-sm font-medium text-text">行为模式（近 {{ statsDays }} 天）</h3>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <!-- 活跃时段 -->
        <div class="p-4 bg-surface border border-border rounded-lg">
          <h4 class="text-xs font-medium text-text-secondary mb-3">活跃时段分布</h4>
          <div v-if="statsLoading" class="text-xs text-text-tertiary text-center py-4">加载中...</div>
          <div v-else-if="statsData.active_hours.length === 0" class="text-xs text-text-tertiary text-center py-4">暂无数据</div>
          <div v-else class="space-y-1">
            <div
              v-for="item in statsData.active_hours"
              :key="item.hour"
              class="flex items-center gap-2 text-xs"
            >
              <span class="w-8 text-right text-text-tertiary">{{ item.hour }}时</span>
              <div class="flex-1 h-3 bg-hover rounded-full overflow-hidden">
                <div
                  class="h-full bg-primary/60 rounded-full transition-all"
                  :style="{ width: (maxHourCount > 0 ? (item.count / maxHourCount * 100) : 0) + '%' }"
                />
              </div>
              <span class="w-8 text-right text-text-tertiary">{{ item.count }}</span>
            </div>
          </div>
        </div>

        <!-- 常用应用 -->
        <div class="p-4 bg-surface border border-border rounded-lg">
          <h4 class="text-xs font-medium text-text-secondary mb-3">常用应用（Top 10）</h4>
          <div v-if="statsLoading" class="text-xs text-text-tertiary text-center py-4">加载中...</div>
          <div v-else-if="statsData.app_usage.length === 0" class="text-xs text-text-tertiary text-center py-4">暂无数据</div>
          <div v-else class="space-y-1">
            <div
              v-for="app in statsData.app_usage"
              :key="app.app_name"
              class="flex items-center gap-2 text-xs"
            >
              <span class="flex-1 truncate text-text">{{ app.app_name }}</span>
              <div class="w-20 h-2.5 bg-hover rounded-full overflow-hidden">
                <div
                  class="h-full bg-primary/60 rounded-full"
                  :style="{ width: app.percentage + '%' }"
                />
              </div>
              <span class="w-12 text-right text-text-tertiary">{{ app.percentage }}%</span>
            </div>
          </div>
        </div>

        <!-- 对话活跃度 -->
        <div class="p-4 bg-surface border border-border rounded-lg">
          <h4 class="text-xs font-medium text-text-secondary mb-3">用户对话活跃度</h4>
          <div v-if="statsLoading" class="text-xs text-text-tertiary text-center py-4">加载中...</div>
          <div v-else-if="statsData.chat_activity.length === 0" class="text-xs text-text-tertiary text-center py-4">暂无数据</div>
          <div v-else class="space-y-1">
            <div
              v-for="day in statsData.chat_activity.slice(-7).reverse()"
              :key="day.date"
              class="flex items-center gap-2 text-xs"
            >
              <span class="w-16 text-right text-text-tertiary">{{ day.date.slice(5) }}</span>
              <div class="flex-1 h-2.5 bg-hover rounded-full overflow-hidden">
                <div
                  class="h-full bg-primary/60 rounded-full"
                  :style="{ width: (maxChatCount > 0 ? (day.message_count / maxChatCount * 100) : 0) + '%' }"
                />
              </div>
              <span class="w-6 text-right text-text-tertiary">{{ day.message_count }}</span>
            </div>
          </div>
          <div class="mt-2 text-right">
            <select
              v-model="statsDays"
              class="text-xs text-text-tertiary bg-transparent border border-border rounded px-1 py-0.5"
              @change="fetchStats"
            >
              <option :value="1">近 1 天</option>
              <option :value="7">近 7 天</option>
              <option :value="14">近 14 天</option>
              <option :value="30">近 30 天</option>
            </select>
          </div>
        </div>
      </div>

      <!-- 行为统计加载失败提示 -->
      <div
        v-if="statsError"
        class="text-xs text-error flex items-center gap-1"
      >
        <font-awesome-icon :icon="['fas', 'triangle-exclamation']" />
        <span>{{ statsError }}</span>
        <button
          class="ml-1 underline hover:text-error/80"
          @click="fetchStats"
        >
          重试
        </button>
      </div>
    </div>

    <!-- ── 画像特征 ──────────────────────────────────────────────── -->
    <div class="mb-4 flex items-center justify-between">
      <h3 class="text-sm font-medium text-text">画像特征</h3>
    </div>

    <!-- 类别筛选 -->
    <div class="flex flex-wrap gap-2 mb-4">
      <button
        v-for="cat in categoryList"
        :key="cat.value"
        class="px-3 py-1 text-xs rounded-lg border transition-colors"
        :class="filterCategory === cat.value
          ? 'bg-primary text-white border-primary'
          : 'bg-surface text-text-secondary border-border hover:border-primary/40'"
        @click="toggleCategory(cat.value)"
      >
        {{ cat.label }}
      </button>
    </div>

    <!-- 加载状态 -->
    <LoadingState :loading="loading" loading-text="加载画像...">
      <!-- 空状态 -->
      <EmptyState :empty="profiles.length === 0" empty-text="暂无画像特征，点击上方「提取画像」从记忆中生成">
        <!-- 画像列表 -->
        <div class="space-y-3">
          <div
            v-for="item in profiles"
            :key="item.id"
            class="p-4 bg-surface border border-border rounded-lg"
          >
            <div class="flex items-start justify-between">
              <div class="flex-1 min-w-0">
                <!-- 标签行 -->
                <div class="flex items-center gap-2 mb-1.5">
                  <span
                    class="inline-flex items-center px-1.5 py-0.5 text-xs rounded font-medium"
                    :class="categoryClass(item.category)"
                  >
                    {{ categoryLabel(item.category) }}
                  </span>
                  <span
                    class="inline-flex items-center px-1.5 py-0.5 text-xs rounded"
                    :class="statusClass(item.status)"
                  >
                    {{ statusLabel(item.status) }}
                  </span>
                  <span class="text-xs text-text-tertiary">
                    可信度 {{ item.confidence }}%
                  </span>
                  <span v-if="item.is_auto_extracted" class="text-xs text-text-tertiary">
                    · 自动提取
                  </span>
                </div>
                <!-- 画像正文 -->
                <p class="text-sm text-text leading-relaxed">{{ item.content }}</p>
                <!-- 时间 -->
                <p class="mt-1 text-xs text-text-tertiary">
                  更新于 {{ formatTime(item.updated_at) }}
                </p>
              </div>
              <!-- 操作按钮 -->
              <div class="flex items-center gap-1 ml-3 shrink-0">
                <template v-if="item.status === 'candidate' || item.status === 'corrected'">
                  <button
                    class="p-1.5 text-xs text-success hover:bg-success/10 rounded transition-colors"
                    title="确认"
                    @click="handleConfirm(item)"
                  >
                    <font-awesome-icon :icon="['fas', 'check']" />
                  </button>
                </template>
                <button
                  class="p-1.5 text-xs text-text-tertiary hover:text-primary rounded hover:bg-primary/10 transition-colors"
                  title="纠正"
                  @click="openCorrectDialog(item)"
                >
                  <font-awesome-icon :icon="['fas', 'pen']" />
                </button>
                <button
                  class="p-1.5 text-xs text-text-tertiary hover:text-error rounded hover:bg-error/10 transition-colors"
                  :title="item.status === 'candidate' ? '否定' : '删除'"
                  @click="handleRejectOrDelete(item)"
                >
                  <font-awesome-icon :icon="['fas', 'xmark']" />
                </button>
                <button
                  class="p-1.5 text-xs text-text-tertiary hover:text-primary rounded hover:bg-primary/10 transition-colors"
                  title="详情"
                  @click="openDetail(item)"
                >
                  <font-awesome-icon :icon="['fas', 'info-circle']" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </EmptyState>
    </LoadingState>

    <!-- 错误状态 -->
    <ErrorState :error="error" :show-retry="true" @retry="fetchProfiles" />

    <!-- ── 纠正对话框 ──────────────────────────────────────────── -->
    <Transition name="fade">
      <div
        v-if="correctDialogVisible"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
        @click.self="correctDialogVisible = false"
      >
        <div class="w-[32rem] p-5 bg-surface rounded-xl border border-border shadow-lg">
          <h3 class="text-base font-medium text-text mb-4">纠正画像</h3>

          <div class="mb-4">
            <label class="block text-sm font-medium text-text mb-1">类别</label>
            <select
              v-model="correctForm.category"
              class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text focus:outline-none focus:border-primary"
            >
              <option v-for="cat in categoryList" :key="cat.value" :value="cat.value">
                {{ cat.label }}
              </option>
            </select>
          </div>

          <div class="mb-4">
            <label class="block text-sm font-medium text-text mb-1">内容</label>
            <textarea
              v-model="correctForm.content"
              class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text placeholder-text-tertiary resize-none focus:outline-none focus:border-primary"
              rows="4"
            />
          </div>

          <div class="mb-4">
            <label class="block text-sm font-medium text-text mb-1">可信度 (0-100)</label>
            <input
              v-model.number="correctForm.confidence"
              type="number"
              min="0"
              max="100"
              class="w-24 px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text focus:outline-none focus:border-primary"
            />
          </div>

          <div class="flex justify-end gap-2">
            <button
              class="px-4 py-1.5 text-sm text-text-secondary bg-hover border border-border rounded-lg hover:bg-surface transition-colors"
              @click="correctDialogVisible = false"
            >
              取消
            </button>
            <button
              class="px-4 py-1.5 text-sm text-white bg-primary rounded-lg hover:bg-primary/90 transition-colors"
              :disabled="actionLoading"
              @click="handleCorrect"
            >
              保存
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- ── 详情对话框 ──────────────────────────────────────────── -->
    <Transition name="fade">
      <div
        v-if="detailVisible"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
        @click.self="detailVisible = false"
      >
        <div class="w-[36rem] max-h-[80vh] p-5 bg-surface rounded-xl border border-border shadow-lg overflow-y-auto">
          <h3 class="text-base font-medium text-text mb-4">画像详情</h3>

          <div v-if="detailData" class="space-y-4">
            <!-- 基本信息 -->
            <div>
              <span class="text-xs text-text-tertiary block mb-1">基本信息</span>
              <div class="p-3 bg-bg rounded-lg space-y-1 text-sm">
                <div class="flex justify-between">
                  <span class="text-text-tertiary">类别</span>
                  <span class="text-text">{{ categoryLabel(detailData.profile.category) }}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-text-tertiary">状态</span>
                  <span class="text-text">{{ statusLabel(detailData.profile.status) }}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-text-tertiary">可信度</span>
                  <span class="text-text">{{ detailData.profile.confidence }}%</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-text-tertiary">版本</span>
                  <span class="text-text">v{{ detailData.profile.version }}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-text-tertiary">自动提取</span>
                  <span class="text-text">{{ detailData.profile.is_auto_extracted ? '是' : '否' }}</span>
                </div>
              </div>
            </div>

            <!-- 画像正文 -->
            <div>
              <span class="text-xs text-text-tertiary block mb-1">画像正文</span>
              <div class="p-3 bg-bg rounded-lg">
                <p class="text-sm text-text">{{ detailData.profile.content }}</p>
              </div>
            </div>

            <!-- 来源证据 -->
            <div v-if="detailData.sources.length > 0">
              <span class="text-xs text-text-tertiary block mb-1">来源证据（{{ detailData.sources.length }}）</span>
              <div class="space-y-2">
                <div
                  v-for="src in detailData.sources"
                  :key="src.id"
                  class="p-2 bg-bg rounded-lg text-xs space-y-1"
                >
                  <div class="flex justify-between">
                    <span class="text-text-tertiary">{{ sourceTypeLabel(src.source_type) }}</span>
                    <span v-if="src.memory_id" class="text-text-tertiary">记忆 ID: {{ src.memory_id }}</span>
                  </div>
                  <p v-if="src.evidence_text" class="text-text-secondary italic">
                    "{{ src.evidence_text }}"
                  </p>
                  <p v-if="src.content_preview" class="text-text-tertiary">
                    {{ src.content_preview }}
                  </p>
                </div>
              </div>
            </div>
            <div v-else>
              <span class="text-xs text-text-tertiary block mb-1">来源证据</span>
              <p class="text-xs text-text-tertiary italic">无来源信息</p>
            </div>

            <!-- 修订历史 -->
            <div v-if="detailData.revisions.length > 0">
              <span class="text-xs text-text-tertiary block mb-1">修订历史（{{ detailData.revisions.length }}）</span>
              <div class="space-y-1">
                <div
                  v-for="rev in detailData.revisions"
                  :key="rev.id"
                  class="p-2 bg-bg rounded-lg text-xs text-text-tertiary"
                >
                  <p>旧内容: {{ rev.previous_content }}</p>
                  <p class="mt-0.5">{{ formatTime(rev.created_at) }} · {{ rev.changed_by === 'user' ? '用户修改' : '系统' }}</p>
                </div>
              </div>
            </div>
          </div>

          <div class="mt-4 flex justify-end">
            <button
              class="px-4 py-1.5 text-sm text-text-secondary bg-hover border border-border rounded-lg hover:bg-surface transition-colors"
              @click="detailVisible = false"
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
import { computed, onMounted, reactive, ref } from 'vue'
import LoadingState from '@/components/custom/LoadingState.vue'
import EmptyState from '@/components/custom/EmptyState.vue'
import ErrorState from '@/components/custom/ErrorState.vue'
import { formatTime } from '@/utils/format'
import {
  confirmProfile,
  correctProfile,
  deleteProfile,
  extractProfiles,
  getBehaviorStats,
  getProfile,
  listProfiles,
  rejectProfile,
} from '@/api/profile'
import type { BehaviorStatsResponse, Profile, ProfileDetail } from '@/types/api'

// ── 状态 ─────────────────────────────────────────────────────────────────

const loading = ref(false)
const extracting = ref(false)
const statsLoading = ref(false)
const actionLoading = ref(false)
const error = ref<string | null>(null)
const statsError = ref<string | null>(null)
const profiles = ref<Profile[]>([])
const detailData = ref<ProfileDetail | null>(null)
const detailVisible = ref(false)
const filterCategory = ref('')
const statsDays = ref(7)

const statsData = reactive<BehaviorStatsResponse>({
  active_hours: [],
  app_usage: [],
  chat_activity: [],
})

// 纠正对话框
const correctDialogVisible = ref(false)
const editingProfile = ref<Profile | null>(null)
const correctForm = reactive({
  category: 'other',
  content: '',
  confidence: 50,
})

// 类别列表
const categoryList = [
  { value: '', label: '全部' },
  { value: 'communication_preference', label: '沟通偏好' },
  { value: 'work_habit', label: '工作习惯' },
  { value: 'learning_preference', label: '学习偏好' },
  { value: 'interest', label: '兴趣方向' },
  { value: 'decision_preference', label: '决策偏好' },
  { value: 'time_habit', label: '时间习惯' },
  { value: 'long_term_goal', label: '长期目标' },
  { value: 'work_pattern', label: '工作模式' },
  { value: 'other', label: '其他' },
]

// ── 数据获取 ─────────────────────────────────────────────────────────────

async function fetchProfiles() {
  loading.value = true
  error.value = null
  try {
    const query: Record<string, unknown> = { page: 1, page_size: 50 }
    if (filterCategory.value) {
      query.category = filterCategory.value
    }
    const res = await listProfiles(query)
    profiles.value = res.data.lists
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  statsLoading.value = true
  statsError.value = null
  try {
    const res = await getBehaviorStats({ days: statsDays.value })
    Object.assign(statsData, res.data)
  } catch (e: unknown) {
    statsError.value = e instanceof Error ? e.message : '行为统计加载失败'
  } finally {
    statsLoading.value = false
  }
}

async function handleExtract() {
  if (extracting.value) return
  extracting.value = true
  error.value = null
  try {
    // API Key 由后端进程缓存管理（对话时注入），浏览器和 Electron 均支持
    const res = await extractProfiles()
    const result = res.data?.result
    if (result?.error) {
      error.value = `画像提取失败：${result.error}`
    } else {
      await fetchProfiles()
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '画像提取失败'
  } finally {
    extracting.value = false
  }
}

// ── 操作处理 ─────────────────────────────────────────────────────────────

async function handleConfirm(item: Profile) {
  actionLoading.value = true
  try {
    await confirmProfile(item.id)
    await fetchProfiles()
  } catch (e: unknown) {
    error.value = e instanceof Error ? `确认失败: ${e.message}` : '确认失败'
  } finally {
    actionLoading.value = false
  }
}

function openCorrectDialog(item: Profile) {
  editingProfile.value = item
  correctForm.category = item.category as string
  correctForm.content = item.content
  correctForm.confidence = item.confidence
  correctDialogVisible.value = true
}

async function handleCorrect() {
  if (!editingProfile.value) return
  actionLoading.value = true
  try {
    await correctProfile(editingProfile.value.id, {
      category: correctForm.category as string,
      content: correctForm.content,
      confidence: correctForm.confidence,
    })
    correctDialogVisible.value = false
    await fetchProfiles()
  } catch (e: unknown) {
    error.value = e instanceof Error ? `纠正失败: ${e.message}` : '纠正失败'
  } finally {
    actionLoading.value = false
  }
}

async function handleRejectOrDelete(item: Profile) {
  actionLoading.value = true
  try {
    if (item.status === 'candidate') {
      await rejectProfile(item.id)
    } else {
      await deleteProfile(item.id)
    }
    await fetchProfiles()
  } catch (e: unknown) {
    error.value = e instanceof Error ? `操作失败: ${e.message}` : '操作失败'
  } finally {
    actionLoading.value = false
  }
}

function toggleCategory(cat: string) {
  filterCategory.value = filterCategory.value === cat ? '' : cat
  fetchProfiles()
}

// ── 详情 ─────────────────────────────────────────────────────────────────

async function openDetail(item: Profile) {
  try {
    const res = await getProfile(item.id)
    detailData.value = res.data
    detailVisible.value = true
  } catch (e: unknown) {
    error.value = e instanceof Error ? `获取详情失败: ${e.message}` : '获取详情失败'
  }
}

// ── 工具函数 ──────────────────────────────────────────────────────────────

function categoryClass(cat: string): string {
  const colors: Record<string, string> = {
    communication_preference: 'bg-blue-100 text-blue-700',
    work_habit: 'bg-green-100 text-green-700',
    learning_preference: 'bg-purple-100 text-purple-700',
    interest: 'bg-pink-100 text-pink-700',
    decision_preference: 'bg-orange-100 text-orange-700',
    time_habit: 'bg-cyan-100 text-cyan-700',
    long_term_goal: 'bg-indigo-100 text-indigo-700',
    work_pattern: 'bg-teal-100 text-teal-700',
  }
  return colors[cat] || 'bg-gray-100 text-gray-600'
}

function categoryLabel(cat: string): string {
  const labels: Record<string, string> = {
    communication_preference: '沟通偏好',
    work_habit: '工作习惯',
    learning_preference: '学习偏好',
    interest: '兴趣方向',
    decision_preference: '决策偏好',
    time_habit: '时间习惯',
    long_term_goal: '长期目标',
    work_pattern: '工作模式',
    other: '其他',
  }
  return labels[cat] || cat
}

function statusClass(st: string): string {
  switch (st) {
    case 'confirmed': return 'bg-green-100 text-green-700'
    case 'corrected': return 'bg-blue-100 text-blue-700'
    case 'candidate': return 'bg-yellow-100 text-yellow-700'
    case 'rejected': return 'bg-red-100 text-red-700'
    case 'deleted': return 'bg-gray-100 text-gray-500'
    default: return 'bg-gray-100 text-gray-500'
  }
}

function statusLabel(st: string): string {
  switch (st) {
    case 'confirmed': return '已确认'
    case 'corrected': return '已纠正'
    case 'candidate': return '候选'
    case 'rejected': return '已否定'
    case 'deleted': return '已删除'
    default: return st
  }
}

function sourceTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    memory: '记忆来源',
    extraction: '自动提取',
    user: '手动创建',
    activity: '活动来源',
  }
  return labels[type] || type
}

// 计算最大值的辅助属性（用于条形图比例）
const maxHourCount = computed(() => {
  if (statsData.active_hours.length === 0) return 0
  return Math.max(...statsData.active_hours.map((h) => h.count))
})

const maxChatCount = computed(() => {
  if (statsData.chat_activity.length === 0) return 0
  return Math.max(...statsData.chat_activity.map((d) => d.message_count))
})

// ── 生命周期 ──────────────────────────────────────────────────────────────

onMounted(() => {
  fetchProfiles()
  fetchStats()
})
</script>
