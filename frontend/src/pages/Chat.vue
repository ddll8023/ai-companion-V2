<template>
  <div class="flex h-full overflow-hidden">
    <!-- 会话列表侧栏 -->
    <aside
      class="w-60 flex-shrink-0 flex flex-col border-r border-border bg-surface/50"
    >
      <!-- 新建对话按钮 -->
      <div class="p-3">
        <button
          class="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-dark transition-colors"
          :disabled="!canChat"
          @click="handleNewSession"
        >
          <font-awesome-icon :icon="['fas', 'plus']" />
          新建对话
        </button>
      </div>

      <!-- 配置提示 -->
      <p
        v-if="!activeConfig && !loadingSessions"
        class="px-4 py-2 text-xs text-text-tertiary leading-relaxed"
      >
        请先前往
        <router-link to="/settings" class="text-primary underline">设置</router-link>
        配置模型
      </p>

      <!-- 加载状态 -->
      <LoadingState :loading="loadingSessions" loading-text="加载对话列表...">
        <div class="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
          <button
            v-for="sess in sessions"
            :key="sess.id"
            class="w-full text-left px-3 py-2 rounded-lg text-sm transition-colors truncate"
            :class="currentSessionId === sess.id
              ? 'bg-primary-light text-primary-dark font-medium'
              : 'text-text-secondary hover:bg-hover hover:text-text'
            "
            @click="switchSession(sess.id)"
          >
            <div class="flex items-center gap-2">
              <font-awesome-icon
                :icon="['fas', 'message']"
                class="text-xs flex-shrink-0"
                :class="currentSessionId === sess.id ? 'text-primary' : 'text-text-tertiary'"
              />
              <span class="truncate">{{ sess.title }}</span>
            </div>
          </button>

          <!-- 空状态 -->
          <EmptyState
            :empty="sessions.length === 0 && !loadingSessions"
            empty-text="暂无对话"
          />
        </div>
      </LoadingState>
    </aside>

    <!-- 消息区域 -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- 当前会话标题 -->
      <div
        v-if="currentSession"
        class="flex items-center gap-3 px-6 py-3 border-b border-border"
      >
        <font-awesome-icon :icon="['fas', 'comments']" class="text-text-tertiary text-sm" />
        <span class="text-sm font-medium text-text truncate">
          {{ currentSession.title }}
        </span>
        <span v-if="currentSession.model_name" class="text-xs text-text-tertiary flex-shrink-0">
          {{ currentSession.model_name }}
        </span>
      </div>

      <!-- 欢迎/没有会话时 -->
      <div
        v-if="!currentSessionId"
        class="flex-1 flex flex-col items-center justify-center text-center px-6"
      >
        <font-awesome-icon
          :icon="['fas', 'comments']"
          class="text-5xl text-text-tertiary/30 mb-4"
        />
        <h3 class="text-lg font-medium text-text mb-2">AI Companion 对话</h3>
        <p class="text-sm text-text-secondary max-w-md">
          点击左侧「新建对话」开始新的对话，或选择一个已有会话继续。
        </p>
        <!-- 配置提示 -->
        <p
          v-if="!activeConfig"
          class="mt-4 text-sm text-text-tertiary"
        >
          开始之前，请先在
          <router-link to="/settings" class="text-primary underline">模型设置</router-link>
          中配置并激活一个模型。
        </p>
      </div>

      <!-- 消息列表 + 输入框 -->
      <template v-else>
        <!-- 消息显示区 -->
        <div
          ref="messagesContainer"
          class="flex-1 overflow-y-auto px-4 md:px-8 py-4 space-y-4"
        >
          <LoadingState :loading="loadingMessages" loading-text="加载消息...">
            <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full text-center">
              <font-awesome-icon :icon="['fas', 'comment-dots']" class="text-3xl text-text-tertiary/30 mb-3" />
              <p class="text-sm text-text-tertiary">输入消息开始对话</p>
            </div>

            <div
              v-for="msg in messages"
              :key="msg.id"
              class="flex"
              :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
            >
              <div
                class="max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words"
                :class="msg.role === 'user'
                  ? 'bg-primary text-white rounded-br-md'
                  : 'bg-surface border border-border text-text rounded-bl-md'
                "
              >
                {{ msg.content }}
                <!-- 生成中的动画 -->
                <span
                  v-if="msg.status === 'generating'"
                  class="inline-block w-1.5 h-4 ml-0.5 bg-current rounded-sm animate-pulse"
                />
                <!-- 失败状态 -->
                <p
                  v-if="msg.status === 'failed' && msg.error_message"
                  class="mt-1 text-xs text-error"
                >
                  {{ msg.error_message }}
                </p>
                <!-- 已中止 -->
                <p
                  v-if="msg.status === 'aborted'"
                  class="mt-1 text-xs text-text-tertiary"
                >
                  已中止
                </p>
              </div>
            </div>

            <!-- 流式传输中的助手消息 -->
            <div
              v-if="streamingContent !== ''"
              class="flex justify-start"
            >
              <div
                class="max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words bg-surface border border-border text-text rounded-bl-md"
              >
                {{ streamingContent }}
                <span class="inline-block w-1.5 h-4 ml-0.5 bg-current rounded-sm animate-pulse" />
              </div>
            </div>
          </LoadingState>
        </div>

        <!-- 输入区 -->
        <div class="flex-shrink-0 border-t border-border p-4">
          <div class="max-w-4xl mx-auto">
            <div class="flex items-end gap-3">
              <textarea
                ref="inputRef"
                v-model="inputText"
                class="flex-1 min-h-[44px] max-h-32 px-4 py-2.5 text-sm border border-border rounded-xl bg-surface text-text placeholder-text-tertiary resize-none focus:outline-none focus:border-primary transition-colors"
                placeholder="输入消息..."
                rows="1"
                :disabled="isGenerating"
                @keydown.enter.exact="handleSend"
                @input="autoResizeInput"
              />
              <!-- 发送按钮 -->
              <button
                v-if="!isGenerating"
                class="flex-shrink-0 w-10 h-10 flex items-center justify-center rounded-xl bg-primary text-white hover:bg-primary-dark transition-colors disabled:opacity-50"
                :disabled="!canSend || !canChat"
                :title="canChat ? '发送' : '请先配置模型'"
                @click="handleSend"
              >
                <font-awesome-icon :icon="['fas', 'paper-plane']" class="text-sm" />
              </button>
              <!-- 停止按钮 -->
              <button
                v-else
                class="flex-shrink-0 w-10 h-10 flex items-center justify-center rounded-xl bg-error text-white hover:bg-error/90 transition-colors"
                title="停止生成"
                @click="handleStop"
              >
                <font-awesome-icon :icon="['fas', 'stop']" class="text-sm" />
              </button>
            </div>
            <p v-if="errorMessage" class="mt-2 text-xs text-error">{{ errorMessage }}</p>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed, nextTick } from 'vue'
import type { Message, Session, ChatStreamEvent } from '@/types/api'
import * as chatApi from '@/api/chat'
import * as modelApi from '@/api/model'
import LoadingState from '@/components/custom/LoadingState.vue'
import EmptyState from '@/components/custom/EmptyState.vue'

// ── 状态 ──────────────────────────────────────────────────────────────────

const sessions = ref<Session[]>([])
const currentSessionId = ref<number | null>(null)
const messages = ref<Message[]>([])
const activeConfig = ref<{ id: number; provider: string; model_name: string; api_base: string | null } | null>(null)

const loadingSessions = ref(false)
const loadingMessages = ref(false)
const errorMessage = ref<string | null>(null)

const inputText = ref('')
const isGenerating = ref(false)
const streamingContent = ref('')
const abortController = ref<AbortController | null>(null)

const messagesContainer = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)

// ── 计算属性 ──────────────────────────────────────────────────────────────

const currentSession = computed(() => {
  if (!currentSessionId.value) return null
  return sessions.value.find(s => s.id === currentSessionId.value) || null
})

const canChat = computed(() => {
  return activeConfig.value !== null && activeConfig.value !== undefined
})

const canSend = computed(() => {
  return inputText.value.trim().length > 0 && !isGenerating.value
})

// ── 生命周期 ──────────────────────────────────────────────────────────────

onMounted(async () => {
  await Promise.all([fetchSessions(), fetchActiveConfig()])
  // 如果存在会话，默认选中第一个
  if (sessions.value.length > 0) {
    currentSessionId.value = sessions.value[0].id
    await fetchMessages()
  }
})

// ── 数据加载 ──────────────────────────────────────────────────────────────

async function fetchSessions() {
  loadingSessions.value = true
  try {
    const res = await chatApi.listSessions()
    sessions.value = res.data || []
  } catch (e: unknown) {
    errorMessage.value = e instanceof Error ? e.message : '加载会话列表失败'
  } finally {
    loadingSessions.value = false
  }
}

async function fetchActiveConfig() {
  try {
    const res = await modelApi.getActiveConfig()
    activeConfig.value = res.data
  } catch {
    activeConfig.value = null
  }
}

async function fetchMessages() {
  if (!currentSessionId.value) return
  loadingMessages.value = true
  try {
    const res = await chatApi.getMessages(currentSessionId.value)
    messages.value = res.data || []
    await nextTick()
    scrollToBottom()
  } catch (e: unknown) {
    errorMessage.value = e instanceof Error ? e.message : '加载消息失败'
  } finally {
    loadingMessages.value = false
  }
}

// ── 会话操作 ──────────────────────────────────────────────────────────────

async function handleNewSession() {
  errorMessage.value = null
  try {
    const res = await chatApi.createSession()
    sessions.value.unshift(res.data!)
    currentSessionId.value = res.data!.id
    messages.value = []
    streamingContent.value = ''
    await nextTick()
    focusInput()
  } catch (e: unknown) {
    errorMessage.value = e instanceof Error ? e.message : '创建会话失败'
  }
}

async function switchSession(sessionId: number) {
  if (isGenerating.value) return // 生成中不允许切换
  currentSessionId.value = sessionId
  streamingContent.value = ''
  await fetchMessages()
  await nextTick()
  focusInput()
}

// ── 发送消息 / 流式对话 ──────────────────────────────────────────────────

async function handleSend() {
  if (!canSend.value || !canChat.value || !currentSessionId.value) return

  const content = inputText.value.trim()
  inputText.value = ''
  resetInputHeight()
  errorMessage.value = null

  // 添加用户消息到本地
  const newUserMessage: Message = {
    id: Date.now(), // 临时 ID
    session_id: currentSessionId.value,
    role: 'user',
    content,
    status: 'completed',
    error_message: null,
    model_name: null,
    token_count: null,
    created_at: null,
  }
  messages.value.push(newUserMessage)
  scrollToBottom()

  isGenerating.value = true
  streamingContent.value = ''

  // 清理旧生成消息：将已有 status=generating 的消息标记为已中止
  // 异常恢复场景下可能残存未结束的占位消息
  messages.value = messages.value.map(m =>
    m.role === 'assistant' && m.status === 'generating'
      ? { ...m, status: 'aborted' }
      : m,
  )

  // 创建 AbortController 用于中止
  abortController.value = new AbortController()

  await chatApi.streamChat(
    currentSessionId.value,
    content,
    activeConfig.value?.id || 0,
    handleStreamEvent,
    handleStreamError,
    abortController.value.signal,
  )
}

function handleStreamEvent(event: ChatStreamEvent) {
  switch (event.type) {
    case 'token':
      streamingContent.value += event.content || ''
      scrollToBottom()
      break

    case 'done':
      // 完成：添加完整的助手消息
      if (streamingContent.value) {
        const newAssistantMessage: Message = {
          id: event.message_id || Date.now(),
          session_id: currentSessionId.value!,
          role: 'assistant',
          content: streamingContent.value,
          status: 'completed',
          error_message: null,
          model_name: activeConfig.value?.model_name || null,
          token_count: null,
          created_at: null,
        }
        messages.value.push(newAssistantMessage)
      }
      streamingContent.value = ''
      isGenerating.value = false
      scrollToBottom()
      focusInput()
      break

    case 'error':
      // 如果已有流式内容，作为已中止消息添加
      if (streamingContent.value) {
        const partialMessage: Message = {
          id: Date.now(),
          session_id: currentSessionId.value!,
          role: 'assistant',
          content: streamingContent.value,
          status: 'aborted',
          error_message: null,
          model_name: activeConfig.value?.model_name || null,
          token_count: null,
          created_at: null,
        }
        messages.value.push(partialMessage)
      } else {
        // 无内容时显示错误
        const errorMsg = event.message || '生成失败'
        // 更新最后一条助手消息或显示错误
        errorMessage.value = errorMsg
      }
      streamingContent.value = ''
      isGenerating.value = false
      scrollToBottom()
      break

    case 'user_saved':
      // 用户消息已保存到后端，更新其实际 ID
      break
  }
}

function handleStreamError(err: Error) {
  errorMessage.value = err.message || '对话请求失败'
  isGenerating.value = false
  streamingContent.value = ''
}

function handleStop() {
  // 中止 SSE 连接 → 触发后端 GeneratorExit → 后端标记为 aborted
  abortController.value?.abort()

  // 已有流式内容作为已中止消息保留
  if (streamingContent.value) {
    const partialMessage: Message = {
      id: Date.now(),
      session_id: currentSessionId.value!,
      role: 'assistant',
      content: streamingContent.value,
      status: 'aborted',
      error_message: null,
      model_name: activeConfig.value?.model_name || null,
      token_count: null,
      created_at: null,
    }
    messages.value.push(partialMessage)
  }
  streamingContent.value = ''
  isGenerating.value = false
  errorMessage.value = null
  focusInput()
}

// ── 辅助函数 ──────────────────────────────────────────────────────────────

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

function focusInput() {
  nextTick(() => {
    inputRef.value?.focus()
  })
}

function autoResizeInput() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 128) + 'px'
}

function resetInputHeight() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
}

// 快捷键 Ctrl+Enter 也触发发送
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && !isGenerating.value) {
    handleSend()
  }
}

// ── 监听器 ────────────────────────────────────────────────────────────────

// ── DOM 事件绑定 ─────────────────────────────────────────────────────────

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
/* 消息区平滑滚动 */
.messages-container {
  scroll-behavior: smooth;
}
</style>
