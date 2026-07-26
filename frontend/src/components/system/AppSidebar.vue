<template>
  <aside
    class="h-full flex-shrink-0 flex flex-col bg-surface border-r border-border transition-[width] duration-200"
    :class="isCollapsed ? 'w-16' : 'w-60'"
  >
    <!-- 应用标题 -->
    <div class="h-14 flex items-center border-b border-border" :class="isCollapsed ? 'justify-center px-2' : 'px-5'">
      <font-awesome-icon
        v-if="isCollapsed"
        :icon="['fas', 'robot']"
        class="text-primary"
        title="AI Companion"
      />
      <h1 v-else class="text-base font-semibold text-text whitespace-nowrap">AI Companion</h1>
      <!-- 后端状态指示灯 -->
      <span
        class="inline-block w-2 h-2 rounded-full"
        :class="[appStore.backendReady ? 'bg-success' : 'bg-error', isCollapsed ? 'ml-1.5' : 'ml-3']"
        :title="appStore.backendReady ? '服务运行中' : '服务不可用'"
      />
      <button
        class="ml-auto w-7 h-7 flex items-center justify-center rounded text-text-tertiary hover:bg-hover hover:text-text transition-colors"
        :class="isCollapsed ? 'hidden' : ''"
        title="收起侧边栏"
        aria-label="收起侧边栏"
        @click="toggleCollapsed"
      >
        <font-awesome-icon :icon="['fas', 'angles-left']" />
      </button>
    </div>

    <button
      v-if="isCollapsed"
      class="mx-auto mt-2 w-9 h-8 flex items-center justify-center rounded text-text-tertiary hover:bg-hover hover:text-text transition-colors"
      title="展开侧边栏"
      aria-label="展开侧边栏"
      @click="toggleCollapsed"
    >
      <font-awesome-icon :icon="['fas', 'angles-right']" />
    </button>

    <!-- 导航菜单 -->
    <nav class="flex-1 py-4 space-y-1" :class="isCollapsed ? 'px-2' : 'px-3'">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="
          flex items-center rounded-lg text-sm
          transition-colors
        "
        :class="[
          isCollapsed ? 'justify-center px-2 py-2.5' : 'gap-3 px-3 py-2',
          isActive(item.path)
            ? 'bg-primary-light text-primary-dark font-medium'
            : 'text-text-secondary hover:bg-hover hover:text-text',
        ]"
        :title="isCollapsed ? item.label : undefined"
      >
        <font-awesome-icon
          :icon="['fas', item.icon]"
          class="w-5 text-center"
        />
        <span v-if="!isCollapsed" class="whitespace-nowrap">{{ item.label }}</span>
      </router-link>
    </nav>

    <!-- 底部：后端状态 + 版本信息 -->
    <div class="border-t border-border" :class="isCollapsed ? 'px-2 py-3' : 'px-5 py-3 space-y-1'">
      <div class="flex items-center gap-2 text-xs">
        <span
          class="inline-block w-1.5 h-1.5 rounded-full"
          :class="appStore.backendReady ? 'bg-success' : 'bg-error'"
        />
        <span v-if="!isCollapsed" class="text-text-tertiary">
          {{ appStore.backendReady ? '服务运行中' : '服务不可用' }}
        </span>
      </div>
      <span v-if="!isCollapsed" class="text-xs text-text-tertiary">v0.1.0</span>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'

const route = useRoute()
const appStore = useAppStore()
const isCollapsed = ref(false)
const SIDEBAR_COLLAPSED_KEY = 'ai_companion_sidebar_collapsed'

interface NavItem {
  path: string
  label: string
  icon: string
}

const navItems: NavItem[] = [
  { path: '/', label: '概览', icon: 'house' },
  { path: '/chat', label: '对话', icon: 'comments' },
  { path: '/memories', label: '记忆', icon: 'brain' },
  { path: '/goals', label: '目标', icon: 'bullseye' },
  { path: '/understanding', label: '用户理解', icon: 'user' },
  { path: '/activities', label: '活动', icon: 'clock' },
  { path: '/settings', label: '设置', icon: 'gear' },
  { path: '/settings/data', label: '数据管理', icon: 'database' },
  { path: '/settings/status', label: '系统状态', icon: 'heart-pulse' },
]

function isActive(path: string): boolean {
  if (path === '/') {
    return route.path === '/'
  }
  return route.path === path
}

function toggleCollapsed() {
  isCollapsed.value = !isCollapsed.value
  localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(isCollapsed.value))
}

onMounted(() => {
  isCollapsed.value = localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true'
})
</script>
