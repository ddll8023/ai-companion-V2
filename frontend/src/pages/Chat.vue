<template>
  <div class="flex h-full min-h-0 overflow-hidden">
    <!-- 会话列表侧栏 -->
    <aside
      class="w-60 flex-shrink-0 flex flex-col min-h-0 border-r border-border bg-surface/50"
    >
      <!-- 新建对话按钮 -->
      <div class="p-3 space-y-2">
        <button
          class="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-dark transition-colors"
          :disabled="!canChat"
          @click="handleNewSession"
        >
          <font-awesome-icon :icon="['fas', 'plus']" />
          新建对话
        </button>
        <!-- 批量提取按钮：存在待提取会话时显示 -->
        <button
          v-if="extractableSessions.length > 0"
          class="w-full flex items-center justify-center gap-2 px-4 py-1.5 text-xs font-medium rounded-lg border border-border text-text-secondary hover:text-primary hover:border-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="hasActiveExtracts"
          :title="hasActiveExtracts ? '正在提取中' : '对全部有新消息的会话提取记忆与人物理解'"
          @click="handleExtractAll"
        >
          <font-awesome-icon
            :icon="['fas', hasActiveExtracts ? 'spinner' : 'wand-magic-sparkles']"
            :class="hasActiveExtracts ? 'animate-spin' : ''"
            class="text-xs"
          />
          {{ hasActiveExtracts ? '提取中…' : `提取全部 (${extractableSessions.length})` }}
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

      <!-- 会话搜索 -->
      <div v-if="sessions.length > 0" class="px-3 pb-1.5">
        <div class="relative">
          <font-awesome-icon
            :icon="['fas', 'search']"
            class="absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-text-tertiary"
          />
          <input
            v-model="sessionSearch"
            type="text"
            placeholder="搜索会话..."
            class="w-full pl-7 pr-7 py-1.5 text-xs border border-border rounded-lg bg-surface text-text placeholder-text-tertiary focus:outline-none focus:border-primary transition-colors"
          />
          <button
            v-if="sessionSearch"
            class="absolute right-2 top-1/2 -translate-y-1/2 text-text-tertiary hover:text-text text-xs"
            title="清除搜索"
            @click="sessionSearch = ''"
          >
            <font-awesome-icon :icon="['fas', 'xmark']" />
          </button>
        </div>
      </div>

      <!-- 加载状态 -->
      <LoadingState :loading="loadingSessions" loading-text="加载对话列表...">
        <div class="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
          <template v-for="group in sessionGroups" :key="group.key">
            <p
              v-if="group.items.length > 0"
              class="px-3 pt-2.5 pb-0.5 text-[10px] font-medium text-text-tertiary/70"
            >
              {{ group.label }}
            </p>
            <div
              v-for="sess in group.items"
              :key="sess.id"
            class="group flex items-center gap-1 rounded-lg text-sm transition-colors"
            :class="currentSessionId === sess.id
              ? 'bg-primary-light text-primary-dark font-medium'
              : 'text-text-secondary hover:bg-hover hover:text-text'
            "
          >
            <button
              class="min-w-0 flex-1 flex items-center gap-2 px-3 py-2 text-left"
              @click="switchSession(sess.id)"
            >
              <font-awesome-icon
                :icon="['fas', 'message']"
                class="text-xs flex-shrink-0"
                :class="currentSessionId === sess.id ? 'text-primary' : 'text-text-tertiary'"
              />
              <span class="truncate">{{ sess.title }}</span>
              <!-- 提取状态：提取中转圈 / 待提取数量徽标 -->
              <font-awesome-icon
                v-if="sessionExtracting(sess)"
                :icon="['fas', 'spinner']"
                class="ml-auto flex-shrink-0 text-xs text-primary animate-spin"
                title="正在提取记忆与人物理解"
              />
              <span
                v-else-if="(sess.extractable_message_count ?? 0) > 0"
                class="ml-auto flex-shrink-0 min-w-4 h-4 px-1 flex items-center justify-center rounded-full bg-primary/15 text-primary text-[10px] font-medium"
                :title="`${sess.extractable_message_count} 条新消息待提取`"
              >
                {{ sess.extractable_message_count }}
              </span>
            </button>
            <!-- 快捷提取按钮（hover 显示） -->
            <button
              v-if="(sess.extractable_message_count ?? 0) > 0 && !sessionExtracting(sess)"
              class="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded text-text-tertiary opacity-100 md:opacity-0 md:group-hover:opacity-100 hover:bg-primary/10 hover:text-primary focus:opacity-100 transition-all disabled:cursor-not-allowed"
              :disabled="isGenerating && currentSessionId === sess.id"
              :title="isGenerating && currentSessionId === sess.id ? '生成中不能提取' : '提取记忆与人物理解'"
              @click.stop="requestExtract(sess.id)"
            >
              <font-awesome-icon :icon="['fas', 'wand-magic-sparkles']" class="text-xs" />
            </button>
            <button
              class="mr-1 flex-shrink-0 w-7 h-7 flex items-center justify-center rounded text-text-tertiary opacity-100 md:opacity-0 md:group-hover:opacity-100 hover:bg-error/10 hover:text-error focus:opacity-100 transition-all disabled:cursor-not-allowed"
              :disabled="isGenerating"
              :title="isGenerating ? '生成中不能删除会话' : '删除对话'"
              @click.stop="requestDeleteSession(sess)"
            >
              <font-awesome-icon :icon="['fas', 'trash']" class="text-xs" />
            </button>
            </div>
          </template>

          <!-- 空状态 -->
          <EmptyState
            :empty="sessions.length === 0 && !loadingSessions"
            empty-text="暂无对话"
          />
          <p
            v-if="sessions.length > 0 && sessionGroups.length === 0"
            class="px-3 py-8 text-center text-xs text-text-tertiary"
          >
            没有匹配的会话
          </p>
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
        <!-- 会话提取按钮 -->
        <button
          class="ml-auto flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-border text-text-secondary hover:text-primary hover:border-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:text-text-secondary disabled:hover:border-border"
          :disabled="!canExtract"
          :title="extractButtonTitle"
          @click="handleExtract"
        >
          <font-awesome-icon
            :icon="['fas', extractInProgress ? 'spinner' : 'wand-magic-sparkles']"
            :class="extractInProgress ? 'animate-spin' : ''"
            class="text-xs"
          />
          {{ extractInProgress ? '提取中…' : '提取记忆与人物理解' }}
        </button>
      </div>

      <!-- 提取结果提示条 -->
      <div
        v-if="extractNotice"
        class="flex items-center gap-2 px-6 py-2 text-xs border-b border-border"
        :class="extractNotice.type === 'success' ? 'text-success bg-success/5' : 'text-error bg-error/5'"
      >
        <font-awesome-icon
          :icon="['fas', extractNotice.type === 'success' ? 'circle-check' : 'circle-exclamation']"
        />
        <span class="flex-1">{{ extractNotice.text }}</span>
        <button
          class="text-text-tertiary hover:text-text transition-colors"
          title="关闭提示"
          @click="extractNotice = null"
        >
          <font-awesome-icon :icon="['fas', 'xmark']" />
        </button>
      </div>

      <!-- 欢迎/没有会话时 -->
      <div
        v-if="!currentSessionId"
        class="flex-1 flex flex-col items-center justify-center text-center px-6 py-10"
      >
        <font-awesome-icon
          :icon="['fas', 'comments']"
          class="text-5xl text-primary/20 mb-5"
        />
        <h3 class="text-lg font-medium text-text mb-2">AI Companion 对话</h3>
        <p class="text-sm text-text-secondary max-w-md mb-8">
          开始一段对话，AI 会结合你的记忆与人物侧写给出个性化回应
        </p>

        <!-- 示例问题（点击即新建会话并发送） -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-2xl mb-6">
          <button
            v-for="prompt in suggestedPrompts"
            :key="prompt.text"
            class="group p-4 bg-surface border border-border rounded-xl text-left hover:border-primary/50 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="!canChat"
            @click="handleSuggestedPrompt(prompt.text)"
          >
            <font-awesome-icon :icon="['fas', prompt.icon]" class="text-primary/70 text-base mb-2" />
            <p class="text-sm text-text leading-relaxed">{{ prompt.text }}</p>
          </button>
        </div>

        <!-- 快捷入口 -->
        <div class="flex items-center gap-4 text-xs text-text-tertiary">
          <router-link to="/memories" class="hover:text-primary transition-colors">
            <font-awesome-icon :icon="['fas', 'book-open']" class="mr-1" />长期记忆
          </router-link>
          <router-link to="/understanding" class="hover:text-primary transition-colors">
            <font-awesome-icon :icon="['fas', 'user-astronaut']" class="mr-1" />人物理解
          </router-link>
        </div>

        <!-- 配置提示 -->
        <p
          v-if="!activeConfig"
          class="mt-6 text-sm text-text-tertiary"
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
          class="relative flex-1 overflow-y-auto px-4 md:px-8 py-4"
          @scroll="onMessagesScroll"
        >
          <LoadingState :loading="loadingMessages" loading-text="加载消息...">
            <TransitionGroup name="msg" tag="div" class="h-full space-y-4">
            <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full text-center">
              <font-awesome-icon :icon="['fas', 'comment-dots']" class="text-3xl text-text-tertiary/30 mb-3" />
              <p class="text-sm text-text-tertiary">输入消息开始对话</p>
            </div>

            <template v-for="row in messageRows" :key="row.key">
              <!-- 日期分隔线 -->
              <div v-if="row.type === 'divider'" class="flex items-center gap-3 my-1 select-none">
                <div class="flex-1 h-px bg-border" />
                <span class="text-[11px] text-text-tertiary/80">{{ row.label }}</span>
                <div class="flex-1 h-px bg-border" />
              </div>

              <!-- 消息行 -->
              <div
                v-else
                class="flex items-end gap-2.5 group"
                :class="row.msg!.role === 'user' ? 'justify-end' : 'justify-start'"
              >
                <!-- AI 头像（助手在左） -->
                <div v-if="row.msg!.role === 'assistant'" class="w-8 flex-shrink-0 flex flex-col items-center gap-1">
                  <div class="w-8 h-8 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center">
                    <font-awesome-icon :icon="['fas', 'brain']" class="text-primary text-sm" />
                  </div>
                  <span class="text-[10px] leading-none text-text-tertiary opacity-0 group-hover:opacity-80 transition-opacity">{{ row.timeLabel }}</span>
                </div>

                <div
                  class="max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words"
                  :class="row.msg!.role === 'user'
                    ? 'bg-primary text-white rounded-br-md'
                    : 'bg-surface border border-border text-text rounded-bl-md'
                  "
                >
                <!-- 推理过程（已完成/已中止的助手消息） -->
                <div
                  v-if="row.msg!.role === 'assistant' && row.msg!.reasoning_content"
                  class="mb-3"
                >
                  <details class="group">
                    <summary class="cursor-pointer text-[#8b7d6b] text-xs font-medium select-none flex items-center gap-1.5 hover:text-[#6b5d4b] transition-colors">
                      <font-awesome-icon :icon="['fas', 'brain']" class="text-xs" />
                      推理过程
                      <font-awesome-icon :icon="['fas', 'chevron-down']" class="ml-1 text-[10px] transition-transform group-open:rotate-180" />
                    </summary>
                    <div class="mt-2 p-3 bg-[#f8f6f0] border border-[#e8e0d0] rounded-lg text-xs leading-relaxed text-[#6b5d4b] whitespace-pre-wrap">
                      {{ row.msg!.reasoning_content }}
                    </div>
                  </details>
                </div>

                <MarkdownRenderer v-if="row.msg!.content" :content="row.msg!.content" />
                <!-- 生成中的动画 -->
                <span
                  v-if="row.msg!.status === 'generating'"
                  class="inline-block w-1.5 h-4 ml-0.5 bg-current rounded-sm animate-pulse"
                />
                <!-- 失败状态 -->
                <p
                  v-if="row.msg!.status === 'failed' && row.msg!.error_message"
                  class="mt-1 text-xs text-error"
                >
                  {{ row.msg!.error_message }}
                </p>
                <!-- 已中止 -->
                <p
                  v-if="row.msg!.status === 'aborted'"
                  class="mt-1 text-xs text-text-tertiary"
                >
                  已中止
                </p>

                <!-- 记忆引用（仅助手已完成消息） -->
                <div
                  v-if="row.msg!.role === 'assistant' && row.msg!.status === 'completed' && row.msg!.memory_references && row.msg!.memory_references.length > 0"
                  class="mt-3 pt-2 border-t border-border/50"
                >
                  <p class="text-xs text-text-tertiary mb-1.5 flex items-center gap-1">
                    <font-awesome-icon :icon="['fas', 'book-open']" class="text-xs" />
                    来自记忆
                  </p>
                  <div class="space-y-1">
                    <div
                      v-for="ref in row.msg!.memory_references"
                      :key="ref.id"
                      class="flex items-start gap-1.5 px-1 -mx-1 rounded cursor-pointer transition-colors hover:bg-hover"
                      :title="ref.memory_id ? '查看该记忆' : undefined"
                      @click="openMemoryRef(ref)"
                    >
                      <font-awesome-icon
                        :icon="['fas', 'quote-left']"
                        class="mt-0.5 text-text-tertiary/50 text-xs flex-shrink-0"
                      />
                      <span class="text-xs text-text-tertiary leading-relaxed">
                        {{ ref.memory_content_preview || '(内容不可用)' }}
                        <span v-if="ref.relevance_score" class="ml-1 opacity-60">
                          相关度: {{ ref.relevance_score }}
                        </span>
                      </span>
                    </div>
                  </div>
                </div>

                <!-- 操作按钮组（hover 显现；重新生成对已完成/中止/失败消息可用） -->
                <div
                  v-if="row.msg!.role === 'assistant' && row.msg!.status !== 'generating' && (row.msg!.status !== 'completed' || !!row.msg!.content)"
                  class="mt-3 pt-2 border-t border-border/50 flex items-center gap-0.5"
                >
                  <template v-if="row.msg!.status === 'completed' && row.msg!.content">
                    <button class="p-1.5 rounded-md text-text-tertiary hover:text-primary hover:bg-primary/10 transition-colors" title="复制回复" @click="copyMessageContent(row.msg!)">
                      <font-awesome-icon :icon="['fas', 'copy']" class="text-xs" />
                    </button>
                    <button class="p-1.5 rounded-md text-text-tertiary hover:text-primary hover:bg-primary/10 transition-colors" title="收藏回复" @click="saveAiContent(row.msg!)">
                      <font-awesome-icon :icon="['fas', 'bookmark']" class="text-xs" />
                    </button>
                    <button class="p-1.5 rounded-md text-text-tertiary hover:text-primary hover:bg-primary/10 transition-colors" title="采纳为候选记忆" @click="rememberAiContent(row.msg!)">
                      <font-awesome-icon :icon="['fas', 'brain']" class="text-xs" />
                    </button>
                  </template>
                  <button
                    class="ml-auto p-1.5 rounded-md text-text-tertiary hover:text-primary hover:bg-primary/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                    title="重新生成回复"
                    :disabled="isGenerating"
                    @click="handleRegenerate(row.msg!)"
                  >
                    <font-awesome-icon :icon="['fas', 'rotate-right']" class="text-xs" />
                  </button>
                </div>
              </div>

              <!-- 用户头像（右侧） -->
              <div v-if="row.msg!.role === 'user'" class="w-8 flex-shrink-0 flex flex-col items-center gap-1">
                <div class="w-8 h-8 rounded-full bg-primary flex items-center justify-center">
                  <font-awesome-icon :icon="['fas', 'user']" class="text-white text-sm" />
                </div>
                <span class="text-[10px] leading-none text-text-tertiary opacity-0 group-hover:opacity-80 transition-opacity">{{ row.timeLabel }}</span>
              </div>
            </div>
            </template>

            <!-- 流式传输中的助手消息。发送后立即显示，避免首个 token 到达前没有反馈。 -->
            <div
              v-if="isGenerating"
              key="streaming"
              class="flex justify-start items-end gap-2.5"
            >
              <div class="w-8 h-8 flex-shrink-0 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center">
                <font-awesome-icon :icon="['fas', 'brain']" class="text-primary text-sm animate-pulse" />
              </div>
              <div
                class="max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words bg-surface border border-border text-text rounded-bl-md"
              >
                <!-- 流式推理过程 -->
                <div
                  v-if="streamingReasoning !== ''"
                  class="mb-3"
                >
                  <details open class="group">
                    <summary class="cursor-pointer text-[#8b7d6b] text-xs font-medium select-none flex items-center gap-1.5 hover:text-[#6b5d4b] transition-colors">
                      <font-awesome-icon :icon="['fas', 'brain']" class="text-xs" />
                      推理过程
                      <font-awesome-icon :icon="['fas', 'chevron-down']" class="ml-1 text-[10px] transition-transform group-open:rotate-180" />
                    </summary>
                    <div class="mt-2 p-3 bg-[#f8f6f0] border border-[#e8e0d0] rounded-lg text-xs leading-relaxed text-[#6b5d4b] whitespace-pre-wrap">
                      {{ streamingReasoning }}
                    </div>
                  </details>
                </div>

                <template v-if="streamingContent !== ''">
                  <MarkdownRenderer :content="renderedStreaming || streamingContent" />
                  <span class="inline-block w-1.5 h-4 ml-0.5 bg-current rounded-sm animate-pulse" />
                </template>
                <!-- 首响应前的上下文检索反馈 -->
                <div
                  v-else-if="streamingReasoning === ''"
                  class="flex items-center gap-2 text-text-secondary"
                  aria-live="polite"
                >
                  <font-awesome-icon :icon="['fas', 'magnifying-glass']" class="text-primary animate-pulse" />
                  <span>正在检索记忆与人物侧写…</span>
                  <span class="flex gap-1" aria-hidden="true">
                    <i class="w-1.5 h-1.5 rounded-full bg-current animate-bounce" />
                    <i class="w-1.5 h-1.5 rounded-full bg-current animate-bounce [animation-delay:150ms]" />
                    <i class="w-1.5 h-1.5 rounded-full bg-current animate-bounce [animation-delay:300ms]" />
                  </span>
                </div>
              </div>
            </div>
            </TransitionGroup>
          </LoadingState>

          <!-- 回到底部按钮 -->
          <button
            v-if="!atBottom"
            class="absolute bottom-4 right-4 w-9 h-9 flex items-center justify-center rounded-full bg-primary text-white shadow-lg hover:bg-primary-dark hover:shadow-xl transition-all"
            title="回到底部"
            @click="jumpToBottom"
          >
            <font-awesome-icon :icon="['fas', 'arrow-down']" class="text-sm" />
            <span
              v-if="unreadCount > 0"
              class="absolute -top-1 -right-1 min-w-4 h-4 px-1 flex items-center justify-center rounded-full bg-error text-white text-[10px] font-medium"
            >
              {{ unreadCount > 99 ? '99+' : unreadCount }}
            </span>
          </button>
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
            </div>
            <p v-if="errorMessage" class="mt-2 text-xs text-error">{{ errorMessage }}</p>
            <p class="mt-1.5 text-[11px] text-text-tertiary/70">Enter 发送 · Shift+Enter 换行</p>
          </div>
        </div>
      </template>
    </div>

    <ConfirmDialog
      :visible="showDeleteDialog"
      title="删除对话"
      :message="deleteTarget ? `确定删除对话「${deleteTarget.title}」吗？其中的全部消息也会被删除，且无法恢复。` : ''"
      confirm-text="删除"
      cancel-text="取消"
      :danger="true"
      @confirm="confirmDeleteSession"
      @cancel="showDeleteDialog = false"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { MemoryReference, Message, Session, ChatStreamEvent } from '@/types/api'
import * as chatApi from '@/api/chat'
import * as modelApi from '@/api/model'
import * as artifactApi from '@/api/artifact'
import { useAppStore } from '@/stores/app'
import LoadingState from '@/components/custom/LoadingState.vue'
import EmptyState from '@/components/custom/EmptyState.vue'
import ConfirmDialog from '@/components/custom/ConfirmDialog.vue'
import MarkdownRenderer from '@/components/custom/MarkdownRenderer.vue'

// ── 状态 ──────────────────────────────────────────────────────────────────

const appStore = useAppStore()

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
const streamingReasoning = ref('')
const showDeleteDialog = ref(false)
const deleteTarget = ref<Session | null>(null)
const deletingSessionId = ref<number | null>(null)

// 提取任务监控：sessionId → taskId，多个会话的提取任务共用一个轮询定时器
const extractTasks = ref<Record<number, number>>({})
const extractNotice = ref<{ type: 'success' | 'error'; text: string } | null>(null)
let extractPollTimer: number | null = null
// 本轮批次的结果累计（全部任务完成后生成汇总提示）
let extractBatchStats = { sessions: 0, memories: 0, created: 0, errors: [] as string[] }

const messagesContainer = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)

// 会话搜索与分组
const sessionSearch = ref('')
// 消息区滚动：用户上滑阅读时暂停自动滚动，显示回到底部按钮
const atBottom = ref(true)
const unreadCount = ref(0)
const router = useRouter()

// 流式 markdown：节流渲染，避免每个 token 都重解析
const renderedStreaming = ref('')
let streamRenderTimer: number | null = null
watch(streamingContent, (value) => {
  if (streamRenderTimer !== null) return
  streamRenderTimer = window.setTimeout(() => {
    streamRenderTimer = null
    renderedStreaming.value = streamingContent.value
  }, 80)
})

// 重新生成：标记正在替换的助手消息 ID，流结束后刷新消息列表
const regeneratingId = ref<number | null>(null)

/** 消息行展开：插入日期分隔线（今天/昨天/更早） */
interface MessageRow {
  key: string
  type: 'divider' | 'message'
  label?: string
  msg?: Message
  timeLabel: string
}

const messageRows = computed<MessageRow[]>(() => {
  const rows: MessageRow[] = []
  let lastDateKey = ''
  for (const msg of messages.value) {
    const d = msg.created_at ? new Date(msg.created_at) : null
    const dateKey = d ? `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}` : ''
    if (d && dateKey && dateKey !== lastDateKey) {
      rows.push({
        key: `divider-${dateKey}`,
        type: 'divider',
        label: dateLabel(d),
        timeLabel: '',
      })
      lastDateKey = dateKey
    }
    rows.push({
      key: `msg-${msg.id}`,
      type: 'message',
      msg,
      timeLabel: d
        ? `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
        : '',
    })
  }
  return rows
})

function dateLabel(d: Date): string {
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const startOfDay = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  if (startOfDay === startOfToday) return '今天'
  if (startOfDay === startOfToday - 86400000) return '昨天'
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

/** 欢迎页示例问题 */
const suggestedPrompts = [
  { icon: 'compass', text: '帮我梳理最近的思考，找出最值得推进的一件事' },
  { icon: 'chart-line', text: '总结我最近对话中提到的目标，并给出本周行动建议' },
  { icon: 'lightbulb', text: '根据你对我的了解，推荐一个适合我的学习计划' },
  { icon: 'clipboard-list', text: '整理我最近提到的待办和想法，生成任务清单' },
]

// ── 辅助函数 ──────────────────────────────────────────────────────────────

function buildAssistantMessage(opts: {
  id: number
  content: string
  reasoningContent?: string
  status: 'completed' | 'aborted'
}): Message {
  return {
    id: opts.id,
    session_id: currentSessionId.value!,
    role: 'assistant',
    content: opts.content,
    reasoning_content: opts.reasoningContent || null,
    status: opts.status,
    error_message: null,
    model_name: activeConfig.value?.model_name || null,
    token_count: null,
    created_at: null,
  }
}

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

/** 搜索过滤后的会话列表 */
const filteredSessions = computed(() => {
  const q = sessionSearch.value.trim().toLowerCase()
  if (!q) return sessions.value
  return sessions.value.filter((s) => (s.title || '').toLowerCase().includes(q))
})

/** 会话按活跃时间分组：今天 / 昨天 / 近 7 天 / 更早 */
const sessionGroups = computed(() => {
  const groups: { key: string; label: string; items: Session[] }[] = [
    { key: 'today', label: '今天', items: [] },
    { key: 'yesterday', label: '昨天', items: [] },
    { key: 'week', label: '近 7 天', items: [] },
    { key: 'older', label: '更早', items: [] },
  ]
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const startOfYesterday = startOfToday - 24 * 3600 * 1000
  const startOfWeek = startOfToday - 6 * 24 * 3600 * 1000
  for (const s of filteredSessions.value) {
    const t = new Date(s.updated_at || s.created_at || '').getTime()
    const index = !t || t < startOfWeek ? 3 : t < startOfYesterday ? 2 : t < startOfToday ? 1 : 0
    groups[index].items.push(s)
  }
  return groups.filter((g) => g.items.length > 0)
})

const extractInProgress = computed(() => {
  const sess = currentSession.value
  return sess ? sessionExtracting(sess) : false
})

const canExtract = computed(() => {
  const sess = currentSession.value
  if (!sess || isGenerating.value || extractInProgress.value) return false
  return (sess.extractable_message_count ?? 0) > 0
})

const extractableSessions = computed(() => {
  return sessions.value.filter(
    s => (s.extractable_message_count ?? 0) > 0 && !sessionExtracting(s),
  )
})

const hasActiveExtracts = computed(() => {
  return Object.keys(extractTasks.value).length > 0
    || sessions.value.some(s => s.is_extracting)
})

const extractButtonTitle = computed(() => {
  if (extractInProgress.value) return '正在提取记忆与人物理解'
  if ((currentSession.value?.extractable_message_count ?? 0) === 0) return '暂无可提取的新对话'
  return '对当前会话的新增对话提取记忆与人物理解'
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
    appStore.hasSession = sessions.value.length > 0
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
  } catch (e: unknown) {
    errorMessage.value = e instanceof Error ? e.message : '加载消息失败'
  } finally {
    loadingMessages.value = false
  }
  // 必须在 loading 关闭、消息 DOM 实际渲染后再滚动
  // （LoadingState 为 v-if/v-else 结构，loading 期间插槽内容不渲染）
  await nextTick()
  scrollToBottom()
}

// ── 会话操作 ──────────────────────────────────────────────────────────────

async function handleNewSession() {
  errorMessage.value = null
  try {
    const res = await chatApi.createSession()
    sessions.value.unshift(res.data!)
    currentSessionId.value = res.data!.id
    // 标记已创建会话（供 Dashboard 首次启动引导使用）
    try { appStore.hasSession = true } catch {}
    messages.value = []
    streamingContent.value = ''
    streamingReasoning.value = ''
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
  streamingReasoning.value = ''
  extractNotice.value = null
  await fetchMessages()
  await nextTick()
  focusInput()
}

function requestDeleteSession(session: Session) {
  if (isGenerating.value) return
  deleteTarget.value = session
  showDeleteDialog.value = true
}

async function confirmDeleteSession() {
  const target = deleteTarget.value
  if (!target || deletingSessionId.value !== null) return

  deletingSessionId.value = target.id
  errorMessage.value = null
  try {
    await chatApi.deleteSession(target.id)
    const deletedCurrentSession = currentSessionId.value === target.id
    sessions.value = sessions.value.filter(session => session.id !== target.id)
    appStore.hasSession = sessions.value.length > 0

    if (deletedCurrentSession) {
      const nextSession = sessions.value[0]
      currentSessionId.value = nextSession?.id ?? null
      messages.value = []
      streamingContent.value = ''
      streamingReasoning.value = ''
      if (nextSession) await fetchMessages()
    }
  } catch (e: unknown) {
    errorMessage.value = e instanceof Error ? e.message : '删除对话失败'
  } finally {
    deletingSessionId.value = null
    deleteTarget.value = null
    showDeleteDialog.value = false
  }
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
    reasoning_content: null,
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
  streamingReasoning.value = ''

  // 清理旧生成消息：将已有 status=generating 的消息标记为已中止
  // 异常恢复场景下可能残存未结束的占位消息
  messages.value = messages.value.map(m =>
    m.role === 'assistant' && m.status === 'generating'
      ? { ...m, status: 'aborted' }
      : m,
  )

  await chatApi.streamChat(
    currentSessionId.value,
    content,
    activeConfig.value?.id || 0,
    handleStreamEvent,
    handleStreamError,
  )
}

async function handleStreamEvent(event: ChatStreamEvent) {
  switch (event.type) {
    case 'token':
      streamingContent.value += event.content || ''
      scrollToBottomIfNeeded()
      break

    case 'reasoning_token':
      streamingReasoning.value += event.content || ''
      scrollToBottomIfNeeded()
      break

    case 'done':
      // 完成：添加完整的助手消息
      if (streamingContent.value || streamingReasoning.value) {
        const newAssistantMessage = buildAssistantMessage({
          id: event.message_id || Date.now(),
          content: streamingContent.value,
          reasoningContent: streamingReasoning.value,
          status: 'completed',
        })
        messages.value.push(newAssistantMessage)
      }
      streamingContent.value = ''
      streamingReasoning.value = ''
      isGenerating.value = false
      scrollToBottom()
      focusInput()
      // 重新生成模式：后端消息 ID 与本地不一致，全量刷新
      if (regeneratingId.value !== null) {
        regeneratingId.value = null
        await fetchMessages()
      }
      break

    case 'error':
      // 如果已有流式内容，作为已中止消息添加
      if (streamingContent.value || streamingReasoning.value) {
        const partialMessage = buildAssistantMessage({
          id: Date.now(),
          content: streamingContent.value,
          reasoningContent: streamingReasoning.value,
          status: 'aborted',
        })
        messages.value.push(partialMessage)
      } else {
        // 无内容时显示错误
        const errorMsg = event.message || '生成失败'
        // 更新最后一条助手消息或显示错误
        errorMessage.value = errorMsg
      }
      streamingContent.value = ''
      streamingReasoning.value = ''
      isGenerating.value = false
      scrollToBottom()
      // 重新生成失败：刷新以恢复被删除的旧回复
      if (regeneratingId.value !== null) {
        regeneratingId.value = null
        await fetchMessages()
      }
      break
  }
}

function handleStreamError(err: Error) {
  errorMessage.value = err.message || '对话请求失败'
  isGenerating.value = false
  streamingContent.value = ''
  streamingReasoning.value = ''
  // 重新生成失败：刷新以恢复被删除的旧回复
  if (regeneratingId.value !== null) {
    regeneratingId.value = null
    void fetchMessages()
  }
}

async function handleRegenerate(msg: Message) {
  if (isGenerating.value || !currentSessionId.value || !canChat.value) return
  // 本地移除旧回复，等待后端删除并重新生成
  messages.value = messages.value.filter((m) => m.id !== msg.id)
  regeneratingId.value = msg.id
  errorMessage.value = null
  streamingContent.value = ''
  streamingReasoning.value = ''
  isGenerating.value = true
  await chatApi.streamChat(
    currentSessionId.value,
    '', // 重新生成模式：后端复用该回复对应的用户消息
    activeConfig.value?.id || 0,
    handleStreamEvent,
    handleStreamError,
    msg.id,
  )
}

/** 复制整条助手回复内容 */
function copyMessageContent(msg: Message) {
  const text = msg.content || ''
  const fallback = () => {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    ta.remove()
  }
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text).catch(fallback)
  } else {
    fallback()
  }
}

/** 欢迎页示例问题：新建会话并直接发送 */
async function handleSuggestedPrompt(text: string) {
  if (!canChat.value) return
  inputText.value = text
  await handleNewSession()
  handleSend()
}

// ── 会话提取 ──────────────────────────────────────────────────────────────

function sessionExtracting(sess: Session): boolean {
  return extractTasks.value[sess.id] !== undefined || !!sess.is_extracting
}

function getDevApiKey(): string | undefined {
  // 浏览器开发模式随请求传入 API Key；Electron 模式由后端全局缓存回退
  try {
    if (import.meta.env.DEV && activeConfig.value) {
      return localStorage.getItem(`model_key_${activeConfig.value.id}`) || undefined
    }
  } catch {
    // localStorage 不可用时忽略
  }
  return undefined
}

function handleExtract() {
  if (!currentSessionId.value || !canExtract.value) return
  requestExtract(currentSessionId.value)
}

async function requestExtract(sessionId: number) {
  if (extractTasks.value[sessionId] !== undefined) return
  extractNotice.value = null
  try {
    const res = await chatApi.extractSession(sessionId, {
      apiKey: getDevApiKey(),
      configId: activeConfig.value?.id,
    })
    extractTasks.value = { ...extractTasks.value, [sessionId]: res.data!.task_id }
    ensureExtractPolling()
  } catch (e: unknown) {
    extractNotice.value = {
      type: 'error',
      text: e instanceof Error ? e.message : '提取任务创建失败',
    }
  }
}

async function handleExtractAll() {
  if (hasActiveExtracts.value) return
  extractNotice.value = null
  const targets = extractableSessions.value
  const results = await Promise.allSettled(
    targets.map(sess => chatApi.extractSession(sess.id, {
      apiKey: getDevApiKey(),
      configId: activeConfig.value?.id,
    })),
  )
  const tasks: Record<number, number> = { ...extractTasks.value }
  const failed: string[] = []
  results.forEach((result, index) => {
    if (result.status === 'fulfilled' && result.value.data) {
      tasks[targets[index].id] = result.value.data.task_id
    } else {
      const reason = result.status === 'rejected' && result.reason instanceof Error
        ? result.reason.message
        : '任务创建失败'
      failed.push(`「${targets[index].title}」${reason}`)
    }
  })
  extractTasks.value = tasks
  if (failed.length > 0) {
    extractBatchStats.errors.push(...failed)
  }
  if (Object.keys(tasks).length > 0) {
    ensureExtractPolling()
  } else {
    // 全部任务创建失败时立即提示，不等轮询周期
    finishExtractBatch()
  }
}

function ensureExtractPolling() {
  if (extractPollTimer !== null) return
  extractPollTimer = window.setInterval(pollExtractTasks, 2000)
}

async function pollExtractTasks() {
  const entries = Object.entries(extractTasks.value)
  if (entries.length === 0) {
    finishExtractBatch()
    return
  }

  for (const [sessionIdStr, taskId] of entries) {
    try {
      const res = await chatApi.getExtractTask(taskId)
      const task = res.data
      if (!task) continue
      if (task.status === 'completed') {
        accumulateExtractResult(task.result)
        removeExtractTask(Number(sessionIdStr))
      } else if (task.status === 'failed' || task.status === 'cancelled') {
        extractBatchStats.errors.push(task.error_message || '提取任务失败')
        removeExtractTask(Number(sessionIdStr))
      }
    } catch {
      // 单次轮询失败不中断，等待下一轮
    }
  }

  if (Object.keys(extractTasks.value).length === 0) {
    finishExtractBatch()
    await fetchSessions()
  }
}

function removeExtractTask(sessionId: number) {
  const tasks = { ...extractTasks.value }
  delete tasks[sessionId]
  extractTasks.value = tasks
}

function accumulateExtractResult(resultJson: string | null) {
  try {
    const result = JSON.parse(resultJson || '{}')
    if (result.error) {
      extractBatchStats.errors.push(String(result.error))
      return
    }
    extractBatchStats.sessions += 1
    extractBatchStats.memories += result.memories_extracted ?? 0
    const ops = result.persona_observations || {}
    extractBatchStats.created += ops.created ?? 0
  } catch {
    extractBatchStats.sessions += 1
  }
}

function finishExtractBatch() {
  stopExtractPolling()
  const stats = extractBatchStats
  extractBatchStats = { sessions: 0, memories: 0, created: 0, errors: [] }

  if (stats.sessions === 0 && stats.errors.length === 0) return

  if (stats.errors.length > 0 && stats.sessions === 0) {
    extractNotice.value = { type: 'error', text: `提取失败：${stats.errors.join('；')}` }
    return
  }

  let text = `完成 ${stats.sessions} 个会话提取：新增候选记忆 ${stats.memories} 条，` +
    `新增人物观察 ${stats.created} 条，可前往「长期记忆」和「用户理解」页面查看`
  if (stats.errors.length > 0) {
    text += `（${stats.errors.length} 个失败：${stats.errors.join('；')}）`
  }
  extractNotice.value = { type: 'success', text }
}

function stopExtractPolling() {
  if (extractPollTimer !== null) {
    clearInterval(extractPollTimer)
    extractPollTimer = null
  }
}

async function saveAiContent(message: Message) {
  try { await artifactApi.saveAiArtifact(message.session_id, message.id) }
  catch (e: unknown) { errorMessage.value = e instanceof Error ? e.message : '收藏 AI 内容失败' }
}

async function rememberAiContent(message: Message) {
  try {
    const artifact = await artifactApi.saveAiArtifact(message.session_id, message.id)
    await artifactApi.rememberAiArtifact(artifact.data!.id)
  } catch (e: unknown) { errorMessage.value = e instanceof Error ? e.message : '创建候选记忆失败' }
}

// ── 辅助函数 ──────────────────────────────────────────────────────────────

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
      atBottom.value = true
      unreadCount.value = 0
    }
  })
}

/** 流式输出时按需滚动：用户不在底部则不打扰，只累计未读提示 */
function scrollToBottomIfNeeded() {
  if (!atBottom.value) {
    unreadCount.value += 1
    return
  }
  scrollToBottom()
}

function jumpToBottom() {
  scrollToBottom()
}

function onMessagesScroll() {
  const el = messagesContainer.value
  if (!el) return
  const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  if (nearBottom) {
    if (!atBottom.value) {
      atBottom.value = true
      unreadCount.value = 0
    }
  } else {
    atBottom.value = false
  }
}

/** 点击记忆引用跳转到长期记忆页并定位高亮 */
function openMemoryRef(ref: MemoryReference) {
  if (!ref.memory_id) return
  router.push({ path: '/memories', query: { highlight: String(ref.memory_id) } })
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
  stopExtractPolling()
})
</script>

<style scoped>
/* 消息区平滑滚动 */
.messages-container {
  scroll-behavior: smooth;
}

/* 消息入场动画（只做进入，切换会话时避免旧列表淡出闪烁） */
.msg-enter-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.msg-enter-from {
  opacity: 0;
  transform: translateY(10px);
}
</style>
