<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-50 flex items-center justify-center"
    >
      <!-- 遮罩层 -->
      <div
        class="absolute inset-0 bg-black/30 transition-opacity"
        @click="handleCancel"
      />

      <!-- 弹窗 -->
      <div class="relative w-full max-w-md mx-4 bg-surface rounded-xl shadow-lg">
        <div class="p-6">
          <!-- 标题 -->
          <h3 class="text-lg font-semibold text-text">
            {{ title }}
          </h3>

          <!-- 内容 -->
          <p v-if="message" class="mt-2 text-sm text-text-secondary">
            {{ message }}
          </p>

          <!-- 插槽 -->
          <slot />
        </div>

        <!-- 操作按钮 -->
        <div class="flex justify-end gap-3 px-6 pb-6">
          <button
            class="px-4 py-2 text-sm font-medium text-text-secondary bg-hover rounded-lg hover:bg-border transition-colors"
            @click="handleCancel"
          >
            {{ cancelText }}
          </button>
          <button
            class="px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors"
            :class="danger
              ? 'bg-error hover:bg-red-600'
              : 'bg-primary hover:bg-primary-dark'"
            @click="handleConfirm"
          >
            {{ confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    visible: boolean
    title?: string
    message?: string
    confirmText?: string
    cancelText?: string
    danger?: boolean
  }>(),
  {
    title: '确认操作',
    message: '',
    confirmText: '确认',
    cancelText: '取消',
    danger: false,
  },
)

const emit = defineEmits<{
  (e: 'confirm'): void
  (e: 'cancel'): void
  (e: 'update:visible', value: boolean): void
}>()

function handleConfirm() {
  emit('confirm')
  emit('update:visible', false)
}

function handleCancel() {
  emit('cancel')
  emit('update:visible', false)
}
</script>
