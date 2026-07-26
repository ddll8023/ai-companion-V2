<template>
  <div class="h-screen overflow-hidden flex bg-bg">
    <!-- 侧边栏 -->
    <AppSidebar />

    <!-- 主内容区 -->
    <div class="flex-1 flex flex-col min-w-0 min-h-0">
      <!-- 顶部区域 -->
      <header class="h-14 flex items-center px-6 bg-surface border-b border-border">
        <h2 class="text-base font-medium text-text">
          {{ pageTitle }}
        </h2>
      </header>

      <!-- 页面内容 -->
      <main
        class="flex-1 min-h-0"
        :class="isChatPage ? 'overflow-hidden' : 'overflow-auto'"
      >
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from '@/components/system/AppSidebar.vue'

const route = useRoute()

const pageTitle = computed(() => {
  return (route.meta?.title as string) ?? ''
})

// 对话页自行管理消息区域滚动；其他页面仍由主内容区滚动。
const isChatPage = computed(() => route.name === 'Chat')
</script>
