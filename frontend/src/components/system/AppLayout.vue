<template>
  <div class="min-h-screen flex bg-bg">
    <!-- 侧边栏 -->
    <AppSidebar />

    <!-- 主内容区 -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- 顶部区域 -->
      <header class="h-14 flex items-center px-6 bg-surface border-b border-border">
        <h2 class="text-base font-medium text-text">
          {{ pageTitle }}
        </h2>
      </header>

      <!-- 页面内容 -->
      <main class="flex-1 overflow-auto">
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
</script>
