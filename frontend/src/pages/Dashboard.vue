<template>
  <div class="p-6 max-w-5xl">
    <div class="mb-6">
      <h2 class="text-xl font-semibold text-text">今日概览</h2>
      <p class="mt-1 text-sm text-text-secondary">查看系统状态和待办事项</p>
    </div>

    <!-- 首次启动引导 -->
    <div
      v-if="showWelcome"
      class="mb-6 p-5 bg-gradient-to-br from-primary/5 to-primary/10 border border-primary/20 rounded-xl"
    >
      <h3 class="text-base font-medium text-primary-dark mb-3">
        <font-awesome-icon :icon="['fas', 'magic']" class="mr-2" />
        欢迎使用 AI Companion
      </h3>
      <p class="text-sm text-text-secondary mb-4">
        完成以下步骤，开始你的个性化 AI 体验：
      </p>
      <div class="space-y-3">
        <!-- 步骤1 -->
        <div
          class="flex items-center gap-3 p-3 bg-white/50 rounded-lg"
          :class="{ 'opacity-50': steps.modelConfigured }"
        >
          <div
            class="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-sm font-medium"
            :class="steps.modelConfigured
              ? 'bg-success text-white'
              : 'bg-primary text-white'"
          >
            <font-awesome-icon v-if="steps.modelConfigured" :icon="['fas', 'check']" class="text-xs" />
            <span v-else>1</span>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-text">配置模型</p>
            <p class="text-xs text-text-tertiary">添加 API Key 并激活模型</p>
          </div>
          <router-link
            v-if="!steps.modelConfigured"
            to="/settings"
          >
            去配置
          </router-link>
        </div>

        <!-- 步骤2 -->
        <div
          class="flex items-center gap-3 p-3 bg-white/50 rounded-lg"
          :class="{ 'opacity-50': !steps.modelConfigured || steps.sessionCreated }"
        >
          <div
            class="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-sm font-medium"
            :class="!steps.modelConfigured
              ? 'bg-hover text-text-tertiary'
              : steps.sessionCreated
                ? 'bg-success text-white'
                : 'bg-primary text-white'"
          >
            <font-awesome-icon v-if="steps.sessionCreated" :icon="['fas', 'check']" class="text-xs" />
            <span v-else>2</span>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-text">开始对话</p>
            <p class="text-xs text-text-tertiary">创建首个会话，与 AI 交流</p>
          </div>
          <router-link
            v-if="steps.modelConfigured && !steps.sessionCreated"
            to="/chat"
            class="flex-shrink-0 px-3 py-1.5 text-xs font-medium text-white bg-primary rounded-lg hover:bg-primary-dark transition-colors"
          >
            去对话
          </router-link>
        </div>

        <!-- 步骤3 -->
        <div
          class="flex items-center gap-3 p-3 bg-white/50 rounded-lg"
          :class="{ 'opacity-50': !steps.sessionCreated || steps.privacyConfigured }"
        >
          <div
            class="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-sm font-medium"
            :class="!steps.sessionCreated
              ? 'bg-hover text-text-tertiary'
              : steps.privacyConfigured
                ? 'bg-success text-white'
                : 'bg-primary text-white'"
          >
            <font-awesome-icon v-if="steps.privacyConfigured" :icon="['fas', 'check']" class="text-xs" />
            <span v-else>3</span>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-text">设置隐私规则</p>
            <p class="text-xs text-text-tertiary">配置活动采集和隐私保护</p>
          </div>
          <router-link
            v-if="steps.sessionCreated && !steps.privacyConfigured"
            to="/settings-privacy"
            class="flex-shrink-0 px-3 py-1.5 text-xs font-medium text-white bg-primary rounded-lg hover:bg-primary-dark transition-colors"
          >
            去设置
          </router-link>
        </div>
      </div>

      <button
        class="mt-4 text-xs text-text-tertiary hover:text-text transition-colors"
        @click="dismissWelcome"
      >
        <font-awesome-icon :icon="['fas', 'times']" class="mr-1" />
        不再显示
      </button>
    </div>

    <!-- 待办事项卡片 -->
    <div v-if="!showWelcome && hasPendingTasks" class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      <!-- 待确认记忆 -->
      <router-link
        v-if="pendingMemories > 0"
        to="/memories"
        class="p-4 bg-surface rounded-lg border border-border hover:border-primary/30 hover:shadow-sm transition-all"
      >
        <div class="flex items-center gap-2 text-sm text-text-secondary mb-2">
          <font-awesome-icon :icon="['fas', 'brain']" class="text-primary" />
          <span>待确认记忆</span>
        </div>
        <p class="text-2xl font-bold text-primary">{{ pendingMemories }}</p>
        <p class="text-xs text-text-tertiary mt-1">点击查看</p>
      </router-link>

      <!-- 待完成任务 -->
      <router-link
        v-if="pendingTasks > 0"
        to="/goals"
        class="p-4 bg-surface rounded-lg border border-border hover:border-primary/30 hover:shadow-sm transition-all"
      >
        <div class="flex items-center gap-2 text-sm text-text-secondary mb-2">
          <font-awesome-icon :icon="['fas', 'tasks']" class="text-warning" />
          <span>待办事宜</span>
        </div>
        <p class="text-2xl font-bold text-warning">{{ pendingTasks }}</p>
        <p class="text-xs text-text-tertiary mt-1">点击查看</p>
      </router-link>

      <!-- 今日活动 -->
      <router-link
        to="/activities"
        class="p-4 bg-surface rounded-lg border border-border hover:border-primary/30 hover:shadow-sm transition-all"
      >
        <div class="flex items-center gap-2 text-sm text-text-secondary mb-2">
          <font-awesome-icon :icon="['fas', 'clock']" class="text-info" />
          <span>今日活动</span>
        </div>
        <p class="text-2xl font-bold text-info">{{ todayActivities }}</p>
        <p class="text-xs text-text-tertiary mt-1">点击查看</p>
      </router-link>
    </div>

    <!-- 关键功能状态提示 -->
    <div v-if="modelConfigurationLoaded && !steps.modelConfigured && !showWelcome" class="mb-6 p-4 bg-warning/10 border border-warning/20 rounded-lg">
      <div class="flex items-center gap-3">
        <font-awesome-icon :icon="['fas', 'exclamation-triangle']" class="text-warning" />
        <div>
          <p class="text-sm font-medium text-text">模型未配置</p>
          <p class="text-xs text-text-tertiary">请先到<router-link to="/settings" class="text-primary hover:underline">模型设置</router-link>中配置并激活一个模型，然后才能开始对话。</p>
        </div>
        <router-link
          to="/settings"
          class="ml-auto flex-shrink-0 px-3 py-1.5 text-xs font-medium text-white bg-primary rounded-lg hover:bg-primary-dark transition-colors"
        >
          立即配置
        </router-link>
      </div>
    </div>

    <!-- 系统状态卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div class="p-4 bg-surface rounded-lg border border-border">
        <div class="flex items-center gap-2 text-sm text-text-secondary">
          <font-awesome-icon :icon="['fas', 'server']" />
          <span>服务状态</span>
        </div>
        <p
          class="mt-2 text-lg font-semibold"
          :class="appStore.healthData?.status === 'running' ? 'text-success' : 'text-error'"
        >
          {{ appStore.healthData?.status === 'running' ? '运行中' : '异常' }}
        </p>
      </div>

      <div class="p-4 bg-surface rounded-lg border border-border">
        <div class="flex items-center gap-2 text-sm text-text-secondary">
          <font-awesome-icon :icon="['fas', 'database']" />
          <span>数据库</span>
        </div>
        <p
          class="mt-2 text-lg font-semibold"
          :class="appStore.healthData?.database?.ready ? 'text-success' : 'text-error'"
        >
          {{ appStore.healthData?.database?.ready ? '就绪' : '不可用' }}
        </p>
      </div>

      <div class="p-4 bg-surface rounded-lg border border-border">
        <div class="flex items-center gap-2 text-sm text-text-secondary">
          <font-awesome-icon :icon="['fas', 'cog']" />
          <span>模型配置</span>
        </div>
        <p
          class="mt-2 text-lg font-semibold"
          :class="modelConfigured ? 'text-success' : 'text-text-tertiary'"
        >
          {{ modelConfigured ? '已配置' : '未配置' }}
        </p>
      </div>
    </div>

    <ErrorState
      :error="error"
      :show-retry="true"
      @retry="initDashboard"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, reactive, watch } from 'vue'
import { useAppStore } from '@/stores/app'
import * as modelApi from '@/api/model'
import * as memoryApi from '@/api/memory'
import * as activityApi from '@/api/activity'
import * as goalApi from '@/api/goal'
import * as chatApi from '@/api/chat'
import ErrorState from '@/components/custom/ErrorState.vue'

const appStore = useAppStore()
const error = ref<string | null>(null)

// ── 首次启动引导 ──
const WELCOME_DISMISSED_KEY = 'ai_companion_welcome_dismissed'

const steps = reactive({
  modelConfigured: false,
  sessionCreated: false,
  privacyConfigured: false,
})

const modelConfigured = ref(false)
// 仅在成功取得模型状态后显示“未配置”提示，避免应用启动时后端尚未就绪造成误报。
const modelConfigurationLoaded = ref(false)
const pendingMemories = ref(0)
const pendingTasks = ref(0)
const todayActivities = ref(0)
const hasPendingTasks = ref(false)

// 首次启动引导是否已关闭（localStorage 持久化）
const showWelcome = ref(false)
let isInitializing = false

function dismissWelcome() {
  showWelcome.value = false
  try {
    localStorage.setItem(WELCOME_DISMISSED_KEY, 'true')
  } catch { /* ignore */ }
}

// ── 初始化 ──
async function initDashboard() {
  if (isInitializing) return
  isInitializing = true
  error.value = null
  try {
    // 并行查询关键状态
    const [activeConfigRes, sessionsRes, memoriesRes, tasksRes, activitiesRes] = await Promise.allSettled([
      modelApi.getActiveConfig(),
      chatApi.listSessions(),
      memoryApi.listMemories({ status: 'candidate', page: 1, page_size: 1 }),
      // 待完成任务（状态 0=待处理）
      goalApi.listTasks({ status: 0, page: 1, page_size: 1 }),
      activityApi.listActivities({ page: 1, page_size: 1 }),
    ])
    await appStore.fetchHealth()

    // 模型配置状态
    if (activeConfigRes.status === 'fulfilled') {
      const activeConfig = activeConfigRes.value.data
      // 与实际对话能力保持一致：必须存在已激活且已保存密钥的配置。
      modelConfigured.value = Boolean(activeConfig?.is_active && activeConfig.has_key)
      steps.modelConfigured = modelConfigured.value
      modelConfigurationLoaded.value = true
    }

    // 会话状态从持久化记录读取，而非只依赖本次运行时的 store。
    if (sessionsRes.status === 'fulfilled') {
      steps.sessionCreated = (sessionsRes.value.data?.length || 0) > 0
      appStore.hasSession = steps.sessionCreated
    }

    // 待确认记忆
    if (memoriesRes.status === 'fulfilled') {
      pendingMemories.value = memoriesRes.value.data?.pagination?.total || 0
    }

    // 待完成任务
    if (tasksRes.status === 'fulfilled') {
      pendingTasks.value = tasksRes.value.data?.pagination?.total || 0
    }

    // 今日活动
    if (activitiesRes.status === 'fulfilled') {
      todayActivities.value = activitiesRes.value.data?.pagination?.total || 0
    }

    hasPendingTasks.value = pendingMemories.value > 0 || pendingTasks.value > 0

    // 判断是否显示首次启动引导
    // 面板在所有步骤完成或用户手动关闭后才消失
    const dismissed = localStorage.getItem(WELCOME_DISMISSED_KEY)
    const allCoreStepsDone = steps.modelConfigured && steps.sessionCreated
    showWelcome.value = modelConfigurationLoaded.value && !allCoreStepsDone && dismissed !== 'true'
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载概览数据失败'
  } finally {
    isInitializing = false
  }
}

onMounted(() => {
  initDashboard()
})

// Electron 启动时 Dashboard 可能先于后端服务挂载。服务就绪后重新加载，
// 避免首次请求失败被错误地渲染为“模型未配置”。
watch(() => appStore.backendReady, (ready) => {
  if (ready && !modelConfigurationLoaded.value) {
    initDashboard()
  }
})
</script>
