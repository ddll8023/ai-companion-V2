<template>
  <div class="p-6 max-w-5xl">
    <!-- 页面标题 -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h2 class="text-xl font-semibold text-text">目标与任务</h2>
        <p class="mt-1 text-sm text-text-secondary">管理你的目标和任务，查看 AI 建议</p>
      </div>
      <button
        class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-dark transition-colors"
        @click="openCreateGoal"
      >
        <font-awesome-icon :icon="['fas', 'plus']" class="mr-1" />
        新建目标
      </button>
    </div>

    <!-- Tab 切换 -->
    <div class="mb-4 flex items-center gap-2">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="px-4 py-1.5 text-sm rounded-lg transition-colors"
        :class="activeTab === tab.key
          ? 'bg-primary text-white'
          : 'bg-surface border border-border text-text-secondary hover:bg-hover hover:text-text'
        "
        @click="switchTab(tab.key)"
      >
        <font-awesome-icon :icon="tab.icon" class="mr-1" />
        {{ tab.label }}
        <span v-if="tab.key === 'suggestions' && suggestionCount > 0" class="ml-1 text-xs bg-warning text-white px-1.5 py-0.5 rounded-full">
          {{ suggestionCount }}
        </span>
      </button>
    </div>

    <!-- 错误提示 -->
    <div
      v-if="error"
      class="mb-4 p-3 text-sm text-error bg-red-50 border border-red-200 rounded-lg flex items-center justify-between"
    >
      <span>{{ error }}</span>
      <button class="text-error underline text-xs" @click="refresh">重试</button>
    </div>

    <!-- ──── 目标列表 ──── -->
    <div v-if="activeTab === 'goals'">
      <LoadingState :loading="loading" loading-text="加载目标...">
        <EmptyState :empty="goals.length === 0" empty-text="暂无目标，点击右上角新建">

          <!-- 目标列表 -->
          <div class="space-y-4">
            <div
              v-for="goal in goals"
              :key="goal.id"
              class="bg-surface border border-border rounded-lg overflow-hidden"
            >
              <!-- 目标头部 -->
              <div class="p-5">
                <div class="flex items-start justify-between mb-3">
                  <div class="flex-1">
                    <div class="flex items-center gap-2 mb-1">
                      <h3 class="text-base font-medium text-text">{{ goal.title }}</h3>
                      <span
                        class="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded"
                        :class="goalStatusClass(goal.status)"
                      >
                        {{ goalStatusLabel(goal.status) }}
                      </span>
                    </div>
                    <p v-if="goal.description" class="text-sm text-text-secondary line-clamp-2">
                      {{ goal.description }}
                    </p>
                  </div>
                  <div class="flex items-center gap-2 ml-4">
                    <button
                      class="p-1.5 text-text-tertiary hover:text-text transition-colors"
                      :title="expandedGoalId === goal.id ? '收起' : '展开任务'"
                      @click="toggleGoalExpand(goal.id)"
                    >
                      <font-awesome-icon
                        :icon="['fas', expandedGoalId === goal.id ? 'chevron-up' : 'chevron-down']"
                      />
                    </button>
                    <button
                      class="p-1.5 text-text-tertiary hover:text-text transition-colors"
                      title="编辑目标"
                      @click="openEditGoal(goal)"
                    >
                      <font-awesome-icon :icon="['fas', 'pen']" />
                    </button>
                    <button
                      class="p-1.5 text-text-tertiary hover:text-error transition-colors"
                      title="删除目标"
                      @click="handleDeleteGoal(goal)"
                    >
                      <font-awesome-icon :icon="['fas', 'trash']" />
                    </button>
                  </div>
                </div>

                <!-- 进度条 -->
                <div class="flex items-center gap-3">
                  <div class="flex-1 h-2 bg-hover rounded-full overflow-hidden">
                    <div
                      class="h-full rounded-full transition-all duration-300"
                      :class="goal.progress === 100 ? 'bg-success' : 'bg-primary'"
                      :style="{ width: goal.progress + '%' }"
                    />
                  </div>
                  <span class="text-xs text-text-tertiary min-w-[3rem] text-right">{{ goal.progress }}%</span>
                </div>
              </div>

              <!-- 任务列表（展开时显示） -->
              <div v-if="expandedGoalId === goal.id" class="border-t border-border">
                <!-- 任务列表头部 -->
                <div class="px-5 py-2 flex items-center justify-between bg-hover/50">
                  <span class="text-xs font-medium text-text-tertiary">
                    任务
                    <span v-if="goalTasks.length > 0">({{ goalTasks.length }})</span>
                  </span>
                  <button
                    class="text-xs text-primary hover:underline"
                    @click="openCreateTask(goal.id)"
                  >
                    + 添加任务
                  </button>
                </div>

                <!-- 单个任务项 -->
                <div
                  v-for="task in goalTasks"
                  :key="task.id"
                  class="px-5 py-3 border-b border-border last:border-b-0 hover:bg-hover/30 transition-colors"
                >
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-3 flex-1">
                      <!-- 状态 checkbox -->
                      <button
                        class="w-4 h-4 rounded border-2 flex items-center justify-center transition-colors shrink-0"
                        :class="task.status === 2
                          ? 'bg-success border-success text-white'
                          : 'border-text-tertiary hover:border-primary'
                        "
                        @click="toggleTaskComplete(task)"
                      >
                        <font-awesome-icon
                          v-if="task.status === 2"
                          :icon="['fas', 'check']"
                          class="text-[10px]"
                        />
                      </button>
                      <!-- 任务标题 -->
                      <span
                        class="text-sm"
                        :class="task.status === 2
                          ? 'text-text-tertiary line-through'
                          : 'text-text'
                        "
                      >
                        {{ task.title }}
                      </span>
                      <!-- 优先级标签 -->
                      <span
                        class="inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded"
                        :class="taskPriorityClass(task.priority)"
                      >
                        {{ taskPriorityLabel(task.priority) }}
                      </span>
                    </div>
                    <div class="flex items-center gap-2 ml-3 shrink-0">
                      <button
                        class="p-1 text-text-tertiary hover:text-text transition-colors"
                        title="编辑任务"
                        @click="openEditTask(task)"
                      >
                        <font-awesome-icon :icon="['fas', 'pen']" class="text-xs" />
                      </button>
                      <button
                        class="p-1 text-text-tertiary hover:text-error transition-colors"
                        title="删除任务"
                        @click="handleDeleteTask(task)"
                      >
                        <font-awesome-icon :icon="['fas', 'trash']" class="text-xs" />
                      </button>
                    </div>
                  </div>
                  <p v-if="task.description" class="mt-1 text-xs text-text-secondary ml-7">
                    {{ task.description }}
                  </p>
                </div>

                <!-- 任务列表空状态 -->
                <div v-if="goalTasks.length === 0" class="px-5 py-6 text-center text-sm text-text-tertiary">
                  还没有关联的任务
                </div>
              </div>
            </div>
          </div>
        </EmptyState>
      </LoadingState>

      <!-- 加载更多 -->
      <div v-if="goals.length < goalTotal && !loading" class="mt-4 text-center">
        <button class="px-4 py-2 text-sm text-primary hover:underline" @click="loadMoreGoals">
          加载更多
        </button>
      </div>
    </div>

    <!-- ──── AI 建议列表 ──── -->
    <div v-if="activeTab === 'suggestions'">
      <LoadingState :loading="loading" loading-text="加载建议...">
        <EmptyState :empty="suggestions.length === 0" empty-text="暂无 AI 建议">

          <div class="space-y-3">
            <div
              v-for="suggestion in suggestions"
              :key="suggestion.id"
              class="p-4 bg-surface border border-warning/30 rounded-lg"
            >
              <div class="flex items-start justify-between mb-2">
                <div class="flex-1">
                  <div class="flex items-center gap-2 mb-1">
                    <span class="inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded bg-warning/10 text-warning-dark">
                      <font-awesome-icon :icon="['fas', 'lightbulb']" class="mr-1" />
                      AI 建议
                    </span>
                    <span
                      class="inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded"
                      :class="taskPriorityClass(suggestion.priority)"
                    >
                      {{ taskPriorityLabel(suggestion.priority) }}
                    </span>
                  </div>
                  <h4 class="text-sm font-medium text-text">{{ suggestion.title }}</h4>
                  <p v-if="suggestion.description" class="mt-1 text-xs text-text-secondary">
                    {{ suggestion.description }}
                  </p>
                </div>
              </div>

              <div class="flex items-center gap-2 pt-2 border-t border-border">
                <button
                  class="px-3 py-1.5 text-xs font-medium text-white bg-success rounded-lg hover:bg-success/90 transition-colors disabled:opacity-50"
                  :disabled="actionLoading === suggestion.id"
                  @click="handleAcceptSuggestion(suggestion)"
                >
                  <font-awesome-icon :icon="['fas', 'check']" class="mr-1" />
                  接受
                </button>
                <button
                  class="px-3 py-1.5 text-xs font-medium text-text-secondary bg-hover border border-border rounded-lg hover:bg-error/10 hover:text-error transition-colors disabled:opacity-50"
                  :disabled="actionLoading === suggestion.id"
                  @click="handleRejectSuggestion(suggestion)"
                >
                  <font-awesome-icon :icon="['fas', 'ban']" class="mr-1" />
                  拒绝
                </button>
              </div>
            </div>
          </div>
        </EmptyState>
      </LoadingState>
    </div>

    <!-- ──── 创建/编辑目标对话框 ──── -->
    <Transition name="fade">
      <div
        v-if="goalDialogVisible"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
        @click.self="closeGoalDialog"
      >
        <div class="w-[32rem] p-5 bg-surface rounded-xl border border-border shadow-lg">
          <h3 class="text-base font-medium text-text mb-4">
            {{ editingGoal ? '编辑目标' : '新建目标' }}
          </h3>

          <div class="mb-4">
            <label class="block text-sm font-medium text-text mb-1">标题</label>
            <input
              v-model="goalForm.title"
              class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text placeholder-text-tertiary focus:outline-none focus:border-primary"
              placeholder="输入目标标题"
            />
          </div>

          <div class="mb-4">
            <label class="block text-sm font-medium text-text mb-1">描述</label>
            <textarea
              v-model="goalForm.description"
              class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text placeholder-text-tertiary resize-none focus:outline-none focus:border-primary"
              rows="3"
              placeholder="输入目标描述（可选）"
            />
          </div>

          <div v-if="editingGoal" class="mb-4">
            <label class="block text-sm font-medium text-text mb-1">状态</label>
            <select
              v-model.number="goalForm.status"
              class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text focus:outline-none focus:border-primary"
            >
              <option :value="0">进行中</option>
              <option :value="1">已完成</option>
              <option :value="2">已放弃</option>
            </select>
          </div>

          <div class="flex items-center gap-3">
            <button
              class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-dark transition-colors disabled:opacity-50"
              :disabled="!goalForm.title || goalSaving"
              @click="handleSaveGoal"
            >
              {{ goalSaving ? '保存中...' : '保存' }}
            </button>
            <button
              class="px-4 py-2 text-sm font-medium text-text-secondary bg-hover rounded-lg hover:text-text transition-colors"
              @click="closeGoalDialog"
            >
              取消
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- ──── 创建/编辑任务对话框 ──── -->
    <Transition name="fade">
      <div
        v-if="taskDialogVisible"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
        @click.self="closeTaskDialog"
      >
        <div class="w-[32rem] p-5 bg-surface rounded-xl border border-border shadow-lg">
          <h3 class="text-base font-medium text-text mb-4">
            {{ editingTask ? '编辑任务' : '添加任务' }}
          </h3>

          <div class="mb-4">
            <label class="block text-sm font-medium text-text mb-1">标题</label>
            <input
              v-model="taskForm.title"
              class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text placeholder-text-tertiary focus:outline-none focus:border-primary"
              placeholder="输入任务标题"
            />
          </div>

          <div class="mb-4">
            <label class="block text-sm font-medium text-text mb-1">描述</label>
            <textarea
              v-model="taskForm.description"
              class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text placeholder-text-tertiary resize-none focus:outline-none focus:border-primary"
              rows="2"
              placeholder="输入任务描述（可选）"
            />
          </div>

          <div v-if="editingTask" class="mb-4">
            <label class="block text-sm font-medium text-text mb-1">状态</label>
            <select
              v-model.number="taskForm.status"
              class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text focus:outline-none focus:border-primary"
            >
              <option :value="0">待处理</option>
              <option :value="1">进行中</option>
              <option :value="2">已完成</option>
              <option :value="3">已放弃</option>
            </select>
          </div>

          <div class="mb-4">
            <label class="block text-sm font-medium text-text mb-1">优先级</label>
            <select
              v-model.number="taskForm.priority"
              class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text focus:outline-none focus:border-primary"
            >
              <option :value="0">无</option>
              <option :value="1">低</option>
              <option :value="2">中</option>
              <option :value="3">高</option>
              <option :value="4">紧急</option>
            </select>
          </div>

          <div class="flex items-center gap-3">
            <button
              class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-dark transition-colors disabled:opacity-50"
              :disabled="!taskForm.title || taskSaving"
              @click="handleSaveTask"
            >
              {{ taskSaving ? '保存中...' : '保存' }}
            </button>
            <button
              class="px-4 py-2 text-sm font-medium text-text-secondary bg-hover rounded-lg hover:text-text transition-colors"
              @click="closeTaskDialog"
            >
              取消
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- ──── 删除确认对话框 ──── -->
    <ConfirmDialog
      :visible="showDeleteGoalDialog"
      title="确认删除目标"
      :message="deleteGoalTarget ? `确定删除目标「${deleteGoalTarget.title}」吗？关联任务将变为独立任务。` : ''"
      confirm-text="删除"
      cancel-text="取消"
      :danger="true"
      @confirm="confirmDeleteGoal"
      @cancel="showDeleteGoalDialog = false"
    />
    <ConfirmDialog
      :visible="showDeleteTaskDialog"
      title="确认删除任务"
      :message="deleteTaskTarget ? `确定删除任务「${deleteTaskTarget.title}」吗？` : ''"
      confirm-text="删除"
      cancel-text="取消"
      :danger="true"
      @confirm="confirmDeleteTask"
      @cancel="showDeleteTaskDialog = false"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { Goal, GoalDetail, Task, TaskWithGoal } from '@/types/api'
import * as goalApi from '@/api/goal'
import LoadingState from '@/components/custom/LoadingState.vue'
import EmptyState from '@/components/custom/EmptyState.vue'
import ConfirmDialog from '@/components/custom/ConfirmDialog.vue'

// ── Tab 切换 ──
interface TabItem {
  key: 'goals' | 'suggestions'
  label: string
  icon: string[]
}

const tabs: TabItem[] = [
  { key: 'goals', label: '目标', icon: ['fas', 'bullseye'] },
  { key: 'suggestions', label: '建议', icon: ['fas', 'lightbulb'] },
]

const activeTab = ref<'goals' | 'suggestions'>('goals')
const suggestionCount = ref(0)

function switchTab(tab: 'goals' | 'suggestions') {
  activeTab.value = tab
  page.value = 1
  refresh()
}

// ── 数据状态 ──
const loading = ref(false)
const error = ref<string | null>(null)
const actionLoading = ref<number | null>(null)
const page = ref(1)
const pageSize = 20

// ── 目标数据 ──
const goals = ref<Goal[]>([])
const goalTotal = ref(0)
const expandedGoalId = ref<number | null>(null)
const goalTasks = ref<Task[]>([])

// ── 建议数据 ──
const suggestions = ref<TaskWithGoal[]>([])

// ── 目标对话框 ──
const goalDialogVisible = ref(false)
const editingGoal = ref<Goal | null>(null)
const goalSaving = ref(false)
const goalForm = ref({
  title: '',
  description: '',
  status: 0,
})

// ── 任务对话框 ──
const taskDialogVisible = ref(false)
const editingTask = ref<Task | null>(null)
const taskSaving = ref(false)
const taskForm = ref({
  title: '',
  description: '',
  status: 0,
  priority: 0,
})
const taskGoalId = ref<number | null>(null)

// ── 删除确认 ──
const showDeleteGoalDialog = ref(false)
const deleteGoalTarget = ref<Goal | null>(null)
const showDeleteTaskDialog = ref(false)
const deleteTaskTarget = ref<Task | null>(null)

// ── 数据加载 ──
async function fetchGoals() {
  loading.value = true
  error.value = null
  try {
    const res = await goalApi.listGoals({
      page: page.value,
      page_size: pageSize,
    })
    if (page.value === 1) {
      goals.value = res.data?.lists || []
    } else {
      goals.value = [...goals.value, ...(res.data?.lists || [])]
    }
    goalTotal.value = res.data?.pagination?.total || 0
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载目标失败'
  } finally {
    loading.value = false
  }
}

async function fetchSuggestions() {
  loading.value = true
  error.value = null
  try {
    const res = await goalApi.listTasks({
      suggestion_status: 1,
      page: page.value,
      page_size: pageSize,
    })
    if (page.value === 1) {
      suggestions.value = res.data?.lists || []
    } else {
      suggestions.value = [...suggestions.value, ...(res.data?.lists || [])]
    }
    suggestionCount.value = res.data?.pagination?.total || 0
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载建议失败'
  } finally {
    loading.value = false
  }
}

async function loadMoreGoals() {
  page.value++
  await fetchGoals()
}

async function refresh() {
  page.value = 1
  if (activeTab.value === 'goals') {
    await fetchGoals()
  } else {
    await fetchSuggestions()
  }
}

// ── 目标展开/收起 ──
async function toggleGoalExpand(goalId: number) {
  if (expandedGoalId.value === goalId) {
    expandedGoalId.value = null
    goalTasks.value = []
    return
  }
  expandedGoalId.value = goalId
  try {
    const res = await goalApi.getGoal(goalId)
    goalTasks.value = res.data?.tasks || []
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载任务失败'
    goalTasks.value = []
  }
}

// ── 目标 CRUD ──
function openCreateGoal() {
  editingGoal.value = null
  goalForm.value = { title: '', description: '', status: 0 }
  goalDialogVisible.value = true
}

function openEditGoal(goal: Goal) {
  editingGoal.value = goal
  goalForm.value = {
    title: goal.title,
    description: goal.description || '',
    status: goal.status,
  }
  goalDialogVisible.value = true
}

function closeGoalDialog() {
  goalDialogVisible.value = false
  editingGoal.value = null
}

async function handleSaveGoal() {
  goalSaving.value = true
  try {
    if (editingGoal.value) {
      await goalApi.updateGoal(editingGoal.value.id, {
        title: goalForm.value.title,
        description: goalForm.value.description || undefined,
        status: goalForm.value.status,
      })
    } else {
      await goalApi.createGoal({
        title: goalForm.value.title,
        description: goalForm.value.description || undefined,
      })
    }
    closeGoalDialog()
    await fetchGoals()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '保存目标失败'
  } finally {
    goalSaving.value = false
  }
}

function handleDeleteGoal(goal: Goal) {
  deleteGoalTarget.value = goal
  showDeleteGoalDialog.value = true
}

async function confirmDeleteGoal() {
  if (!deleteGoalTarget.value) return
  actionLoading.value = deleteGoalTarget.value.id
  try {
    await goalApi.deleteGoal(deleteGoalTarget.value.id, 'unlink')
    await fetchGoals()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '删除目标失败'
  } finally {
    actionLoading.value = null
    showDeleteGoalDialog.value = false
    deleteGoalTarget.value = null
  }
}

// ── 任务 CRUD ──
function openCreateTask(goalId: number) {
  editingTask.value = null
  taskGoalId.value = goalId
  taskForm.value = { title: '', description: '', status: 0, priority: 0 }
  taskDialogVisible.value = true
}

function openEditTask(task: Task) {
  editingTask.value = task
  taskGoalId.value = task.goal_id
  taskForm.value = {
    title: task.title,
    description: task.description || '',
    status: task.status,
    priority: task.priority,
  }
  taskDialogVisible.value = true
}

function closeTaskDialog() {
  taskDialogVisible.value = false
  editingTask.value = null
  taskGoalId.value = null
}

async function handleSaveTask() {
  taskSaving.value = true
  try {
    if (editingTask.value) {
      await goalApi.updateTask(editingTask.value.id, {
        title: taskForm.value.title,
        description: taskForm.value.description || undefined,
        status: taskForm.value.status,
        priority: taskForm.value.priority,
      })
    } else {
      await goalApi.createTask({
        goal_id: taskGoalId.value,
        title: taskForm.value.title,
        description: taskForm.value.description || undefined,
        priority: taskForm.value.priority,
      })
    }
    closeTaskDialog()
    // 刷新当前展开的目标的任务列表
    if (expandedGoalId.value) {
      await toggleGoalExpand(expandedGoalId.value)
    }
    await fetchGoals()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '保存任务失败'
  } finally {
    taskSaving.value = false
  }
}

async function toggleTaskComplete(task: Task) {
  const newStatus = task.status === 2 ? 0 : 2
  try {
    await goalApi.updateTask(task.id, { status: newStatus })
    if (expandedGoalId.value) {
      await toggleGoalExpand(expandedGoalId.value)
    }
    await fetchGoals()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '更新任务失败'
  }
}

function handleDeleteTask(task: Task) {
  deleteTaskTarget.value = task
  showDeleteTaskDialog.value = true
}

async function confirmDeleteTask() {
  if (!deleteTaskTarget.value) return
  actionLoading.value = deleteTaskTarget.value.id
  try {
    await goalApi.deleteTask(deleteTaskTarget.value.id)
    await fetchGoals()
    if (expandedGoalId.value) {
      await toggleGoalExpand(expandedGoalId.value)
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '删除任务失败'
  } finally {
    actionLoading.value = null
    showDeleteTaskDialog.value = false
    deleteTaskTarget.value = null
  }
}

// ── AI 建议操作 ──
async function handleAcceptSuggestion(task: TaskWithGoal) {
  actionLoading.value = task.id
  try {
    await goalApi.acceptSuggestion(task.id)
    await fetchSuggestions()
    // 切换回目标标签显示新任务
    activeTab.value = 'goals'
    await fetchGoals()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '接受建议失败'
  } finally {
    actionLoading.value = null
  }
}

async function handleRejectSuggestion(task: TaskWithGoal) {
  actionLoading.value = task.id
  try {
    await goalApi.rejectSuggestion(task.id)
    await fetchSuggestions()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '拒绝建议失败'
  } finally {
    actionLoading.value = null
  }
}

// ── 辅助函数 ──
function goalStatusLabel(status: number): string {
  const map: Record<number, string> = {
    0: '进行中',
    1: '已完成',
    2: '已放弃',
  }
  return map[status] || '未知'
}

function goalStatusClass(status: number): string {
  const map: Record<number, string> = {
    0: 'text-primary bg-primary/10',
    1: 'text-success bg-green-50',
    2: 'text-text-tertiary bg-hover',
  }
  return map[status] || 'text-text-tertiary bg-hover'
}

function taskPriorityLabel(priority: number): string {
  const map: Record<number, string> = {
    0: '无',
    1: '低',
    2: '中',
    3: '高',
    4: '紧急',
  }
  return map[priority] || '无'
}

function taskPriorityClass(priority: number): string {
  const map: Record<number, string> = {
    0: 'text-text-tertiary bg-hover',
    1: 'text-blue-600 bg-blue-50',
    2: 'text-primary bg-primary/10',
    3: 'text-warning-dark bg-warning/10',
    4: 'text-error bg-red-50',
  }
  return map[priority] || 'text-text-tertiary bg-hover'
}

// ── 生命周期 ──
onMounted(async () => {
  await fetchGoals()
  // 异步更新建议计数
  try {
    const res = await goalApi.listTasks({ suggestion_status: 1, page: 1, page_size: 1 })
    suggestionCount.value = res.data?.pagination?.total || 0
  } catch {
    // 建议计数更新失败不影响主流程
  }
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
