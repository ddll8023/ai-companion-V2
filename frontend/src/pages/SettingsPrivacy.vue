<template>
  <div class="p-6 max-w-4xl">
    <!-- 页面标题 -->
    <div class="mb-6">
      <h2 class="text-xl font-semibold text-text">隐私设置</h2>
      <p class="mt-1 text-sm text-text-secondary">管理活动采集的隐私规则</p>
    </div>

    <!-- 新建规则按钮 -->
    <div class="mb-4">
      <button
        class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary/90 transition-colors"
        @click="openCreateDialog"
      >
        <font-awesome-icon :icon="['fas', 'plus']" class="mr-1" />
        添加规则
      </button>
    </div>

    <!-- 规则类型说明卡 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      <div
        v-for="info in ruleTypeInfo"
        :key="info.type"
        class="p-3 bg-surface border border-border rounded-lg text-center cursor-pointer hover:border-primary/40 transition-colors"
        :class="{ 'border-primary': filterType === info.type }"
        @click="toggleTypeFilter(info.type)"
      >
        <p class="text-xs font-medium text-text">{{ info.label }}</p>
        <p class="mt-0.5 text-lg font-semibold text-text">{{ typeCounts[info.type] || 0 }}</p>
      </div>
    </div>

    <!-- 加载状态 -->
    <LoadingState :loading="loading" loading-text="加载隐私规则...">
      <!-- 空状态 -->
      <EmptyState :empty="rules.length === 0" empty-text="暂无隐私规则，点击上方按钮添加">

        <!-- 规则列表 -->
        <div class="space-y-3">
          <div
            v-for="rule in rules"
            :key="rule.id"
            class="p-4 bg-surface border border-border rounded-lg"
          >
            <div class="flex items-start justify-between">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <span class="text-sm font-medium text-text">{{ ruleTypeLabel(rule.rule_type) }}</span>
                  <span
                    class="inline-flex items-center px-1.5 py-0.5 text-xs rounded"
                    :class="rule.is_active
                      ? 'bg-green-100 text-green-700'
                      : 'bg-gray-100 text-gray-500'"
                  >
                    {{ rule.is_active ? '启用' : '禁用' }}
                  </span>
                  <span class="text-xs text-text-tertiary">优先级: {{ rule.priority }}</span>
                </div>
                <p class="text-xs text-text-secondary break-all font-mono bg-bg p-2 rounded mt-1">
                  {{ rule.rule_value }}
                </p>
                <p v-if="rule.description" class="mt-1 text-xs text-text-tertiary">
                  {{ rule.description }}
                </p>
                <p class="mt-1 text-xs text-text-tertiary">
                  更新于 {{ formatTime(rule.updated_at) }}
                </p>
              </div>
              <!-- 操作按钮 -->
              <div class="flex items-center gap-1 ml-3">
                <button
                  class="p-1.5 text-text-tertiary hover:text-primary transition-colors rounded hover:bg-primary/10"
                  title="编辑"
                  @click="openEditDialog(rule)"
                >
                  <font-awesome-icon :icon="['fas', 'pen']" class="text-xs" />
                </button>
                <button
                  class="p-1.5 text-text-tertiary hover:text-error transition-colors rounded hover:bg-error/10"
                  title="删除"
                  @click="handleDelete(rule)"
                >
                  <font-awesome-icon :icon="['fas', 'trash']" class="text-xs" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </EmptyState>
    </LoadingState>

    <!-- 错误状态 -->
    <ErrorState :error="error" :show-retry="true" @retry="fetchRules" />

    <!-- 创建/编辑对话框 -->
    <Transition name="fade">
      <div
        v-if="dialogVisible"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
        @click.self="dialogVisible = false"
      >
        <div class="w-[32rem] p-5 bg-surface rounded-xl border border-border shadow-lg">
          <h3 class="text-base font-medium text-text mb-4">
            {{ editingRule ? '编辑规则' : '添加规则' }}
          </h3>

          <div class="mb-4">
            <label class="block text-sm font-medium text-text mb-1">规则类型</label>
            <select
              v-model="form.rule_type"
              class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text focus:outline-none focus:border-primary"
              :disabled="!!editingRule"
            >
              <option value="global_pause">全局暂停</option>
              <option value="app_blacklist">应用黑名单</option>
              <option value="app_whitelist">应用白名单</option>
              <option value="title_keyword">窗口标题关键字阻断</option>
              <option value="time_based">特定时段暂停</option>
              <option value="content_masking">内容脱敏</option>
              <option value="temp_pause">单次临时暂停</option>
            </select>
          </div>

          <!-- 不同类型的帮助提示 -->
          <div class="mb-3 p-2 bg-blue-50 text-blue-700 text-xs rounded-lg">
            {{ ruleTypeHint(form.rule_type) }}
          </div>

          <div class="mb-4">
            <label class="block text-sm font-medium text-text mb-1">规则值</label>
            <textarea
              v-model="form.rule_value"
              class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text placeholder-text-tertiary resize-none focus:outline-none focus:border-primary"
              rows="3"
              :placeholder="rulePlaceholder(form.rule_type)"
            />
          </div>

          <div class="mb-4">
            <label class="block text-sm font-medium text-text mb-1">描述（可选）</label>
            <input
              v-model="form.description"
              type="text"
              class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text placeholder-text-tertiary focus:outline-none focus:border-primary"
              placeholder="简单说明此规则的作用"
            />
          </div>

          <div class="mb-4">
            <label class="block text-sm font-medium text-text mb-1">优先级</label>
            <input
              v-model.number="form.priority"
              type="number"
              min="0"
              max="100"
              class="w-24 px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text focus:outline-none focus:border-primary"
            />
            <span class="ml-2 text-xs text-text-tertiary">数值越高越优先</span>
          </div>

          <div class="flex justify-end gap-2">
            <button
              class="px-4 py-1.5 text-sm text-text-secondary bg-hover border border-border rounded-lg hover:bg-surface transition-colors"
              @click="dialogVisible = false"
            >
              取消
            </button>
            <button
              class="px-4 py-1.5 text-sm text-white bg-primary rounded-lg hover:bg-primary/90 transition-colors"
              :disabled="actionLoading"
              @click="handleSave"
            >
              {{ editingRule ? '保存' : '创建' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 删除确认对话框 -->
    <Transition name="fade">
      <div
        v-if="deleteDialogVisible"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
        @click.self="deleteDialogVisible = false"
      >
        <div class="w-96 p-5 bg-surface rounded-xl border border-border shadow-lg">
          <h3 class="text-base font-medium text-text mb-2">确认删除</h3>
          <p class="text-sm text-text-secondary mb-4">
            确定要删除此隐私规则吗？
          </p>
          <div class="flex justify-end gap-2">
            <button
              class="px-4 py-1.5 text-sm text-text-secondary bg-hover border border-border rounded-lg hover:bg-surface transition-colors"
              @click="deleteDialogVisible = false"
            >
              取消
            </button>
            <button
              class="px-4 py-1.5 text-sm text-white bg-error rounded-lg hover:bg-error/90 transition-colors"
              :disabled="actionLoading"
              @click="confirmDelete"
            >
              确认删除
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
  listPrivacyRules,
  createPrivacyRule,
  updatePrivacyRule,
  deletePrivacyRule,
} from '@/api/activity'
import type { PrivacyRule } from '@/types/api'

// ── 状态 ──────────────────────────────────────────────────────────────────

const loading = ref(false)
const actionLoading = ref(false)
const error = ref<string | null>(null)
const rules = ref<PrivacyRule[]>([])
const dialogVisible = ref(false)
const deleteDialogVisible = ref(false)
const editingRule = ref<PrivacyRule | null>(null)
const deletingRule = ref<PrivacyRule | null>(null)
const filterType = ref('')

const form = reactive({
  rule_type: 'app_blacklist',
  rule_value: '',
  description: '',
  priority: 0,
})

// 各类型的提示信息和占位符
const ruleTypeInfo = [
  { type: 'global_pause', label: '全局暂停' },
  { type: 'app_blacklist', label: '应用黑名单' },
  { type: 'title_keyword', label: '关键字阻断' },
  { type: 'content_masking', label: '内容脱敏' },
]

const typeCounts = reactive<Record<string, number>>({})

// ── 数据获取 ──────────────────────────────────────────────────────────────

async function fetchRules() {
  loading.value = true
  error.value = null
  try {
    const query: { rule_type?: string; page: number; page_size: number } = {
      page: 1,
      page_size: 100,
    }
    if (filterType.value) {
      query.rule_type = filterType.value
    }
    const res = await listPrivacyRules(query)
    rules.value = res.data.lists
    // 统计各类规则数量
    const counts: Record<string, number> = {}
    for (const r of res.data.lists) {
      counts[r.rule_type] = (counts[r.rule_type] || 0) + 1
    }
    Object.assign(typeCounts, counts)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function toggleTypeFilter(type: string) {
  filterType.value = filterType.value === type ? '' : type
  fetchRules()
}

// ── 创建/编辑 ──────────────────────────────────────────────────────────────

function openCreateDialog() {
  editingRule.value = null
  form.rule_type = 'app_blacklist'
  form.rule_value = ''
  form.description = ''
  form.priority = 0
  dialogVisible.value = true
}

function openEditDialog(rule: PrivacyRule) {
  editingRule.value = rule
  form.rule_type = rule.rule_type
  form.rule_value = rule.rule_value
  form.description = rule.description || ''
  form.priority = rule.priority
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.rule_value.trim()) return
  actionLoading.value = true
  try {
    if (editingRule.value) {
      await updatePrivacyRule(editingRule.value.id, {
        rule_value: form.rule_value,
        description: form.description || undefined,
        is_active: undefined,
        priority: form.priority,
      })
    } else {
      await createPrivacyRule({
        rule_type: form.rule_type,
        rule_value: form.rule_value,
        description: form.description || undefined,
        priority: form.priority,
      })
    }
    dialogVisible.value = false
    fetchRules()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    actionLoading.value = false
  }
}

// ── 删除 ──────────────────────────────────────────────────────────────────

function handleDelete(rule: PrivacyRule) {
  deletingRule.value = rule
  deleteDialogVisible.value = true
}

async function confirmDelete() {
  if (!deletingRule.value) return
  actionLoading.value = true
  try {
    await deletePrivacyRule(deletingRule.value.id)
    deleteDialogVisible.value = false
    deletingRule.value = null
    fetchRules()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '删除失败'
  } finally {
    actionLoading.value = false
  }
}

// ── 工具函数 ──────────────────────────────────────────────────────────────

function ruleTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    global_pause: '全局暂停',
    app_blacklist: '应用黑名单',
    app_whitelist: '应用白名单',
    title_keyword: '窗口标题关键字阻断',
    time_based: '特定时段暂停',
    content_masking: '内容脱敏',
    temp_pause: '单次临时暂停',
  }
  return labels[type] || type
}

function ruleTypeHint(type: string): string {
  const hints: Record<string, string> = {
    global_pause: '暂停后活动采集将完全停止。输入任意值即视为启用。建议优先级设为最高。',
    app_blacklist: '输入应用名称或 Bundle ID，匹配的应用将被阻断采集。例: "Google Chrome" 或 "com.google.Chrome"',
    app_whitelist: '输入允许采集的应用名称。白名单启用后，仅白名单中的应用会被记录。每行一个应用名。',
    title_keyword: '输入敏感关键词，含此关键词的窗口标题将被阻断采集。例: "密码"、"private"',
    time_based: 'JSON 格式，例: {"start_hour": 22, "end_hour": 7}，表示 22:00-07:00 暂停。',
    content_masking: '输入需要脱敏的关键词，匹配内容将被替换为 ***。例: "私人"',
    temp_pause: 'JSON 格式，例: {"pause_until": "2026-07-23T08:00:00"}。到期后自动恢复。',
  }
  return hints[type] || ''
}

function rulePlaceholder(type: string): string {
  const placeholders: Record<string, string> = {
    global_pause: '输入任意值即可启用全局暂停',
    app_blacklist: 'com.google.Chrome',
    app_whitelist: '每行一个应用名称',
    title_keyword: '密码',
    time_based: '{"start_hour": 22, "end_hour": 7}',
    content_masking: '私人',
    temp_pause: '{"pause_until": "2026-07-23T08:00:00"}',
  }
  return placeholders[type] || '输入规则值'
}

function formatTime(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleString()
  } catch {
    return dateStr
  }
}

// ── 生命周期 ──────────────────────────────────────────────────────────────

onMounted(() => {
  fetchRules()
})
</script>
