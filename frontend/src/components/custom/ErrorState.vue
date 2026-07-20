<template>
  <div
    v-if="error"
    class="flex flex-col items-center justify-center py-16 text-center"
  >
    <font-awesome-icon
      :icon="['fas', 'circle-exclamation']"
      class="text-3xl text-error"
    />
    <p class="mt-3 text-sm text-text-secondary">
      {{ error }}
    </p>
    <button
      v-if="showRetry"
      class="mt-4 px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-dark transition-colors"
      @click="$emit('retry')"
    >
      重新尝试
    </button>
  </div>
  <slot v-else />
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    error?: string | null
    showRetry?: boolean
  }>(),
  {
    error: null,
    showRetry: false,
  },
)

defineEmits<{
  (e: 'retry'): void
}>()
</script>
