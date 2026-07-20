<template>
  <div class="p-6">
    <div class="flex flex-col items-center justify-center py-20 text-center">
      <font-awesome-icon
        :icon="['fas', icon]"
        class="text-4xl text-text-tertiary mb-4"
      />
      <h3 class="text-lg font-medium text-text">{{ title }}</h3>
      <p class="mt-2 text-sm text-text-secondary">{{ description }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    description?: string
    icon?: string
  }>(),
  {
    description: '功能开发中，敬请期待',
    icon: 'hammer',
  },
)
</script>
