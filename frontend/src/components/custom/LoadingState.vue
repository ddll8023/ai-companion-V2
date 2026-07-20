<template>
  <div
    v-if="loading"
    class="flex flex-col items-center justify-center py-16 text-center"
  >
    <font-awesome-icon
      :icon="['fas', 'spinner']"
      class="fa-spin text-2xl text-primary"
    />
    <p class="mt-3 text-sm text-text-secondary">
      {{ loadingText }}
    </p>
  </div>
  <slot v-else />
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    loading?: boolean
    loadingText?: string
  }>(),
  {
    loading: false,
    loadingText: '加载中...',
  },
)
</script>
