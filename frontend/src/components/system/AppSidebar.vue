<template>
  <aside
    class="
      w-60 min-h-screen flex flex-col
      bg-surface border-r border-border
    "
  >
    <!-- 应用标题 -->
    <div class="h-14 flex items-center px-5 border-b border-border">
      <h1 class="text-base font-semibold text-text">AI Companion</h1>
      <!-- 后端状态指示灯 -->
      <span
        class="ml-3 inline-block w-2 h-2 rounded-full"
        :class="appStore.backendReady ? 'bg-success' : 'bg-error'"
        :title="appStore.backendReady ? '服务运行中' : '服务不可用'"
      />
    </div>

    <!-- 导航菜单 -->
    <nav class="flex-1 py-4 px-3 space-y-1">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="
          flex items-center gap-3 px-3 py-2 rounded-lg text-sm
          transition-colors
        "
        :class="isActive(item.path)
          ? 'bg-primary-light text-primary-dark font-medium'
          : 'text-text-secondary hover:bg-hover hover:text-text'"
      >
        <font-awesome-icon
          :icon="['fas', item.icon]"
          class="w-5 text-center"
        />
        <span>{{ item.label }}</span>
      </router-link>
    </nav>

    <!-- 底部：后端状态 + 版本信息 -->
    <div class="px-5 py-3 border-t border-border space-y-1">
      <div class="flex items-center gap-2 text-xs">
        <span
          class="inline-block w-1.5 h-1.5 rounded-full"
          :class="appStore.backendReady ? 'bg-success' : 'bg-error'"
        />
        <span class="text-text-tertiary">
          {{ appStore.backendReady ? '服务运行中' : '服务不可用' }}
        </span>
      </div>
      <span class="text-xs text-text-tertiary">v0.1.0</span>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'

const route = useRoute()
const appStore = useAppStore()

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
  return route.path.startsWith(path)
}
</script>
