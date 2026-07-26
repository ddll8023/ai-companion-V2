import { getAdapter } from '@/composables/useApi'
import type {
  ApiResponse,
  BackgroundTaskInfo,
  ChatStreamEvent,
  Message,
  Session,
  SessionCreate,
  SessionExtractResult,
  SessionUpdate,
} from '@/types/api'

const adapter = getAdapter()

// ── 会话 API ──────────────────────────────────────────────────────────────

/** 获取全部会话列表 */
export async function listSessions() {
  return adapter.get<Session[]>('/api/v1/chat/sessions')
}

/** 创建新会话 */
export async function createSession(data?: SessionCreate) {
  return adapter.post<Session>('/api/v1/chat/sessions', data || {})
}

/** 获取单个会话详情 */
export async function getSession(id: number) {
  return adapter.get<Session>(`/api/v1/chat/sessions/${id}`)
}

/** 更新会话（重命名） */
export async function updateSession(id: number, data: SessionUpdate) {
  return adapter.put<Session>(`/api/v1/chat/sessions/${id}`, data)
}

/** 删除会话 */
export async function deleteSession(id: number) {
  return adapter.delete(`/api/v1/chat/sessions/${id}`)
}

// ── 会话提取 API ──────────────────────────────────────────────────────────

/** 触发会话级记忆与画像提取（异步后台任务） */
export async function extractSession(sessionId: number, apiKey?: string) {
  return adapter.post<SessionExtractResult>(
    `/api/v1/chat/sessions/${sessionId}/extract`,
    { api_key: apiKey || undefined },
  )
}

/** 查询提取任务状态（轮询用） */
export async function getExtractTask(taskId: number) {
  return adapter.get<BackgroundTaskInfo>(`/api/v1/tasks/${taskId}`)
}

// ── 消息 API ──────────────────────────────────────────────────────────────

/** 获取指定会话的全部消息 */
export async function getMessages(sessionId: number) {
  return adapter.get<Message[]>(`/api/v1/chat/sessions/${sessionId}/messages`)
}

// ── 流式对话 ──────────────────────────────────────────────────────────────

/**
 * 发送消息并通过 SSE 接收流式回复。
 *
 * 安全设计：
 * - Electron 模式：通过专用 IPC 通道（chat:stream）发送，API Key 由主进程从 keystore
 *   读取并注入 HTTP 请求，Renderer 不接触密钥明文
 * - 浏览器模式：使用 fetch + SSE（密钥在请求体中，仅用于开发环境）
 *
 * @param configId 模型配置 ID（Electron 模式：主进程据此从 keystore 获取密钥）
 * @param signal 可选 AbortSignal，用于主动中止请求
 */
export async function streamChat(
  sessionId: number,
  content: string,
  configId: number,
  onEvent: (event: ChatStreamEvent) => void,
  onError: (error: Error) => void,
  signal?: AbortSignal,
): Promise<void> {
  // ── Electron 模式：通过 IPC 逐 token 推送 ──
  if (typeof window !== 'undefined' && window.electronAPI) {
    try {
      const cleanup = window.electronAPI.streamChat(
        { sessionId, content, configId },
        {
          onToken: (token: string) => {
            onEvent({ type: 'token', content: token })
          },
          onReasoning: (token: string) => {
            onEvent({ type: 'reasoning_token', content: token })
          },
          onDone: (messageId: number | null) => {
            onEvent({ type: 'done', message_id: messageId ?? undefined })
          },
          onError: (message: string) => {
            onEvent({ type: 'error', message })
            onError(new Error(message))
          },
        },
      )

      // 注册中止清理
      if (signal) {
        signal.addEventListener('abort', () => { cleanup() })
      }
      return
    } catch (e) {
      onError(e instanceof Error ? e : new Error(String(e)))
      return
    }
  }

  // ── 浏览器开发模式：使用 fetch + SSE ──
  // 密钥通过请求体传递，仅用于开发环境
  let apiKey: string | undefined
  try {
    // 浏览器模式：从 localStorage 读取（仅限 DEV）
    if (import.meta.env.DEV) {
      apiKey = localStorage.getItem(`model_key_${configId}`) || undefined
    }
  } catch {
    // localStorage 不可用时忽略
  }

  try {
    const response = await fetch(`/api/v1/chat/sessions/${sessionId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, api_key: apiKey || undefined }),
      signal,
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('响应体不可读')
    }

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // 解析 SSE 事件：data: {...}\n\n
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || '' // 最后一段可能不完整，保留到下次

      for (const part of parts) {
        for (const line of part.split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const event = JSON.parse(line.slice(6)) as ChatStreamEvent
              onEvent(event)
            } catch {
              // 跳过解析失败的 event
            }
          }
        }
      }
    }

    // 处理 buffer 中可能残留的数据
    if (buffer.startsWith('data: ')) {
      try {
        const event = JSON.parse(buffer.slice(6)) as ChatStreamEvent
        onEvent(event)
      } catch {
        // ignore
      }
    }
  } catch (e) {
    // 用户主动中止（AbortController）不触发错误回调
    if (e instanceof DOMException && e.name === 'AbortError') {
      return
    }
    onError(e instanceof Error ? e : new Error(String(e)))
  }
}
