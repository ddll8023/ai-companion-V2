<template>
  <div
    v-if="empty"
    class="flex flex-col items-center justify-center py-16 text-center"
  >
    <font-awesome-icon
      :icon="['fas', 'inbox']"
      class="text-3xl text-text-tertiary"
    />
    <p class="mt-3 text-sm text-text-secondary">
      {{ emptyText }}
    </p>
  </div>
  <slot v-else />
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    empty?: boolean
    emptyText?: string
  }>(),
  {
    empty: false,
    emptyText: '暂无数据',
  },
)
</script>
