/**
 * AI Companion — Electron 主进程
 *
 * 职责：
 * - 应用单实例管理
 * - 主窗口生命周期
 * - Python 本地服务进程管理（启动、健康检查、重启、清理）
 * - 安全通信（IPC 代理，Renderer 不持有端口和令牌）
 * - 操作系统安全存储（密钥管理）
 * - 数据目录管理
 */

import {
  app, BrowserWindow, ipcMain, safeStorage,
} from 'electron';
import { ChildProcess, spawn } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import * as net from 'net';
import * as crypto from 'crypto';
import * as http from 'http';
import { IPC_CHANNELS } from './constants/channels';
import {
  getPlatform,
  getPlatformCapabilities,
  PlatformCapabilitiesResponse,
  PermissionStatus,
  PermissionNames,
  PermissionState,
} from './constants/platform';
import {
  getActivityCaptureManager,
} from './services/activityCapture';

// ── 常量 ──────────────────────────────────────────────────────────────

const isDev = process.env.NODE_ENV === 'development';

/** 项目根目录路径（编译后 electron/dist/main.js → 根目录） */
const ROOT_DIR = isDev
  ? path.resolve(__dirname, '../..')
  : path.resolve(process.resourcesPath, 'app');

/** 后端 Python 项目路径 */
const BACKEND_DIR = path.join(ROOT_DIR, 'backend');

/** Electron 统一确定的数据目录 */
const DATA_DIR = path.join(app.getPath('userData'), 'data');

/** 安全存储文件路径 */
const SECURE_STORE_PATH = path.join(app.getPath('userData'), 'secure-store.enc');

// IPC_CHANNELS 定义在 src/constants/channels.ts 中，两处共享

// ── 全局状态 ─────────────────────────────────────────────────────────

let mainWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;
let backendPort = 0;
let authToken = '';
let isBackendReady = false;
let healthCheckTimer: ReturnType<typeof setInterval> | null = null;
let isQuitting = false;

// ── 单实例 ────────────────────────────────────────────────────────────

const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}

// ── 工具函数 ─────────────────────────────────────────────────────────

/** 查找可用端口（监听 127.0.0.1 回环地址） */
function findFreePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, '127.0.0.1', () => {
      const addr = server.address();
      if (addr && typeof addr === 'object') {
        const port = addr.port;
        server.close(() => resolve(port));
      } else {
        server.close(() => reject(new Error('无法获取端口')));
      }
    });
    server.on('error', reject);
  });
}

/** 生成随机认证令牌 */
function generateAuthToken(): string {
  return crypto.randomBytes(32).toString('hex');
}

/** 向 Renderer 发送后端状态 */
function sendBackendStatus(ready: boolean): void {
  isBackendReady = ready;
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send(IPC_CHANNELS.BACKEND_STATUS, { ready });
  }
}

/** 构建 HTTP 请求选项（含认证头） */
function buildRequestOptions(
  method: string,
  urlPath: string,
  body?: unknown,
) {
  const headers: Record<string, string> = {
    'Authorization': `Bearer ${authToken}`,
    'Content-Type': 'application/json',
  };
  return {
    hostname: '127.0.0.1',
    port: backendPort,
    path: urlPath,
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  };
}

/** 发送 HTTP 请求到本地 Python 服务 */
function apiRequest(method: string, urlPath: string, body?: unknown): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const opts = buildRequestOptions(method, urlPath, body);

    const req = http.request(
      {
        hostname: opts.hostname,
        port: opts.port,
        path: opts.path,
        method: opts.method,
        headers: opts.headers,
      },
      (res: any) => {
        let data = '';
        res.on('data', (chunk: string) => { data += chunk; });
        res.on('end', () => {
          try {
            resolve(JSON.parse(data));
          } catch {
            resolve({
              code: 5001,
              message: '本地服务返回了无效的响应格式',
            });
          }
        });
      },
    );

    req.on('error', (err) => {
      reject(new Error(`本地服务不可用: ${err.message}`));
    });

    if (opts.body) {
      req.write(opts.body);
    }
    req.end();
  });
}

// ── Python 进程管理 ────────────────────────────────────────────────

/** 启动 Python 本地服务 */
async function startPythonBackend(): Promise<void> {
  backendPort = await findFreePort();
  authToken = generateAuthToken();

  // 确保数据目录存在
  fs.mkdirSync(DATA_DIR, { recursive: true });

  console.log(`[Main] 启动本地服务 → 端口: ${backendPort}, 数据目录: ${DATA_DIR}`);

  // 检测 Python 运行时：优先使用 .venv 下的 Python
  const venvPython = path.join(BACKEND_DIR, '.venv', 'bin', 'python3');
  let useDirectPython = false;
  let pythonExecutable = '';

  if (fs.existsSync(venvPython)) {
    pythonExecutable = venvPython;
    useDirectPython = true;
  }

  const pythonEnv = {
    ...process.env,
    PORT: String(backendPort),
    DATA_DIR: DATA_DIR,
    AUTH_TOKEN: authToken,
  };

  if (useDirectPython) {
    // 直接使用 .venv 下的 Python
    console.log(`[Main] 使用 .venv Python: ${pythonExecutable}`);
    pythonProcess = spawn(
      pythonExecutable,
      ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(backendPort)],
      {
        cwd: BACKEND_DIR,
        env: pythonEnv,
        stdio: ['ignore', 'pipe', 'pipe'],
      },
    );
  } else {
    // 使用 uv 运行
    console.log('[Main] 使用 uv 运行 Python 服务');
    pythonProcess = spawn(
      'uv',
      ['run', '--directory', BACKEND_DIR, 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(backendPort)],
      {
        cwd: BACKEND_DIR,
        env: pythonEnv,
        stdio: ['ignore', 'pipe', 'pipe'],
      },
    );
  }

  // 日志输出
  if (pythonProcess.stdout) {
    pythonProcess.stdout.on('data', (data: Buffer) => {
      const text = data.toString().trim();
      if (text) console.log(`[Python] ${text}`);
    });
  }
  if (pythonProcess.stderr) {
    pythonProcess.stderr.on('data', (data: Buffer) => {
      const text = data.toString().trim();
      if (text) console.log(`[Python] ${text}`);
    });
  }

  // 进程退出处理
  pythonProcess.on('exit', (code: number | null, signal: string | null) => {
    console.log(`[Main] Python 进程退出: code=${code}, signal=${signal}`);
    pythonProcess = null;
    if (!isQuitting) {
      sendBackendStatus(false);
    }
  });

  // 轮询健康检查，等待服务就绪
  await waitForBackendHealth();
}

/** 轮询等待后端服务就绪 */
async function waitForBackendHealth(maxRetries = 60, interval = 1000): Promise<void> {
  console.log('[Main] 等待本地服务就绪...');

  for (let i = 0; i < maxRetries; i++) {
    if (isQuitting) return;
    try {
      const result = await new Promise<boolean>((resolve) => {
        const req = http.get(
          `http://127.0.0.1:${backendPort}/health`,
          (res: any) => {
            let data = '';
            res.on('data', (chunk: string) => { data += chunk; });
            res.on('end', () => {
              try {
                resolve(JSON.parse(data).code === 0);
              } catch {
                resolve(false);
              }
            });
          },
        );
        req.on('error', () => resolve(false));
        req.end();
      });

      if (result) {
        console.log('[Main] 本地服务已就绪');
        sendBackendStatus(true);
        return;
      }
    } catch {
      // 服务未就绪，继续等待
    }
    await new Promise((r) => setTimeout(r, interval));
  }

  console.error('[Main] 本地服务启动超时');
  sendBackendStatus(false);
  throw new Error('本地服务启动超时');
}

/** 启动后端健康检查定时器 */
function startHealthCheck(): void {
  if (healthCheckTimer) {
    clearInterval(healthCheckTimer);
  }

  healthCheckTimer = setInterval(async () => {
    if (isQuitting) return;
    try {
      const result = await new Promise<boolean>((resolve) => {
        const req = http.get(
          `http://127.0.0.1:${backendPort}/health`,
          (res: any) => {
            let data = '';
            res.on('data', (chunk: string) => { data += chunk; });
            res.on('end', () => {
              try {
                resolve(JSON.parse(data).code === 0);
              } catch {
                resolve(false);
              }
            });
          },
        );
        req.on('error', () => resolve(false));
        req.end();
      });

      if (result !== isBackendReady) {
        sendBackendStatus(result);
      }
    } catch {
      if (isBackendReady) {
        sendBackendStatus(false);
      }
    }
  }, 10000); // 每 10 秒检查一次
}

/** 停止 Python 本地服务 */
function stopPythonBackend(): void {
  if (healthCheckTimer) {
    clearInterval(healthCheckTimer);
    healthCheckTimer = null;
  }

  if (pythonProcess) {
    console.log('[Main] 正在停止本地服务...');
    // 先发 SIGTERM，优雅关闭
    pythonProcess.kill('SIGTERM');

    // 5 秒后强制关闭
    const forceKillTimer = setTimeout(() => {
      if (pythonProcess) {
        pythonProcess.kill('SIGKILL');
        pythonProcess = null;
      }
    }, 5000);
    forceKillTimer.unref(); // 不阻止 Node 进程退出
  }
}

// ── 安全存储 ──────────────────────────────────────────────────────────

/** 从加密文件加载安全存储 */
function loadSecureStore(): Record<string, string> {
  try {
    if (!fs.existsSync(SECURE_STORE_PATH)) {
      return {};
    }
    const raw = fs.readFileSync(SECURE_STORE_PATH, 'utf-8');
    const encryptedStore = JSON.parse(raw) as Record<string, string>;

    // 解密所有值
    const store: Record<string, string> = {};
    for (const [key, encryptedHex] of Object.entries(encryptedStore)) {
      try {
        store[key] = safeStorage.decryptString(Buffer.from(encryptedHex, 'hex'));
      } catch {
        console.warn(`[Main] 安全存储: 密钥 "${key}" 解密失败，已跳过（系统加密环境可能已变更）`);
      }
    }
    return store;
  } catch {
    return {};
  }
}

/** 保存安全存储到加密文件 */
function saveSecureStore(store: Record<string, string>): void {
  try {
    if (!safeStorage.isEncryptionAvailable()) {
      console.warn('[Main] 当前系统不支持安全存储');
      return;
    }

    // 加密所有值
    const encryptedStore: Record<string, string> = {};
    for (const [key, value] of Object.entries(store)) {
      encryptedStore[key] = safeStorage.encryptString(value).toString('hex');
    }

    const dir = path.dirname(SECURE_STORE_PATH);
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(SECURE_STORE_PATH, JSON.stringify(encryptedStore), 'utf-8');
  } catch (err) {
    console.error('[Main] 保存安全存储失败:', err);
  }
}

// ── IPC 处理器 ───────────────────────────────────────────────────────

/** API 访问控制规则。
 *
 * blockedPaths: 按路径段前缀阻断（自动处理 URL 编码，只匹配独立路径段）。
 * 使用 /api/v1/data/clear-all 阻断 clear-all，不误阻 clear-all?type=xxx 等参数化请求。
 */
const API_ACCESS_RULES = {
  /** 只读 GET */
  read: {
    // 阻断管理性接口
    blockedPathPrefixes: ['/api/v1/data/clear-all', '/api/v1/data/backup', '/api/v1/data/restore'],
  },
  /** 写入 POST/PUT */
  write: {
    // 阻断全局数据操作和备份恢复等高危接口
    // 不阻断单条数据修改（如 POST /api/v1/activities/privacy-rules 是合法规则创建）
    blockedPathPrefixes: [
      '/api/v1/data/clear-all',
      '/api/v1/data/clear',
      '/api/v1/data/backup',
      '/api/v1/data/restore',
    ],
  },
  /** 删除 DELETE */
  delete: {
    // 只阻断全局清除，允许单条导出/备份记录的删除
    blockedPathPrefixes: ['/api/v1/data/clear-all', '/api/v1/data/clear'],
  },
};

/** 检查 URL 路径是否被允许通过 IPC 代理。

 * 使用路径段前缀精确比较（而非子串匹配），避免误阻合法请求。
 * 同时做 URL 解码防止编码绕过。
 */
function isApiPathAllowed(urlPath: string, accessLevel: 'read' | 'write' | 'delete'): boolean {
  const rules = API_ACCESS_RULES[accessLevel];
  // URL 解码，防止百分比编码绕过
  const decoded = decodeURIComponent(urlPath);
  // 规范化：去除末尾斜杠
  const normalized = decoded.replace(/\/+$/, '');
  // 路径段前缀检查：检查是否以任何阻断路径段开头
  const isBlocked = rules.blockedPathPrefixes.some((prefix) => {
    return normalized === prefix || normalized.startsWith(prefix + '/') || normalized.startsWith(prefix + '?');
  });
  return !isBlocked;
}

/** 静态能力定义（异步权限检测失败时的降级 fallback）。 */
function getStaticCapabilities(): PermissionState[] {
  const platform = getPlatform();

  return [
    {
      name: PermissionNames.ACTIVITY_CAPTURE,
      status: platform === 'macos' ? PermissionStatus.AVAILABLE : PermissionStatus.NOT_IMPLEMENTED,
      label: '活动采集',
      description: '采集前台应用和窗口信息',
    },
    {
      name: PermissionNames.ACCESSIBILITY,
      status: platform === 'macos' ? PermissionStatus.PENDING_AUTH : PermissionStatus.NOT_IMPLEMENTED,
      label: '辅助功能',
      description: '获取前台应用和窗口标题',
    },
    {
      name: PermissionNames.INPUT_MONITORING,
      status: PermissionStatus.NOT_IMPLEMENTED,
      label: '输入监控',
      description: '监控键盘输入事件',
    },
    {
      name: PermissionNames.SCREEN_RECORDING,
      status: PermissionStatus.NOT_IMPLEMENTED,
      label: '屏幕录制',
      description: '屏幕截图和录制',
    },
    {
      name: PermissionNames.NOTIFICATION,
      status: PermissionStatus.AVAILABLE,
      label: '系统通知',
      description: '发送桌面通知',
    },
    {
      name: PermissionNames.AUTOMATION,
      status: PermissionStatus.NOT_IMPLEMENTED,
      label: '自动化',
      description: '控制其他应用',
    },
  ];
}

function setupIpcHandlers(): void {
  // API 代理：GET 请求（只读）
  ipcMain.handle(IPC_CHANNELS.API_GET, async (_event, url: string) => {
    if (!backendPort || !isBackendReady) {
      return { code: 5001, message: '本地服务尚未就绪' };
    }
    if (!isApiPathAllowed(url, 'read')) {
      return { code: 403, message: '权限不足：该 API 不允许通过 Renderer 访问' };
    }
    try {
      return await apiRequest('GET', url);
    } catch (e: any) {
      return { code: 5001, message: e.message || '本地服务不可用' };
    }
  });

  // API 代理：POST 请求（写入）
  ipcMain.handle(IPC_CHANNELS.API_POST, async (_event, url: string, data?: unknown) => {
    if (!backendPort || !isBackendReady) {
      return { code: 5001, message: '本地服务尚未就绪' };
    }
    if (!isApiPathAllowed(url, 'write')) {
      return { code: 403, message: '权限不足：该 API 不允许通过 Renderer 访问' };
    }
    try {
      return await apiRequest('POST', url, data);
    } catch (e: any) {
      return { code: 5001, message: e.message || '本地服务不可用' };
    }
  });

  // API 代理：PUT 请求（写入）
  ipcMain.handle(IPC_CHANNELS.API_PUT, async (_event, url: string, data?: unknown) => {
    if (!backendPort || !isBackendReady) {
      return { code: 5001, message: '本地服务尚未就绪' };
    }
    if (!isApiPathAllowed(url, 'write')) {
      return { code: 403, message: '权限不足：该 API 不允许通过 Renderer 访问' };
    }
    try {
      return await apiRequest('PUT', url, data);
    } catch (e: any) {
      return { code: 5001, message: e.message || '本地服务不可用' };
    }
  });

  // API 代理：DELETE 请求
  ipcMain.handle(IPC_CHANNELS.API_DELETE, async (_event, url: string) => {
    if (!backendPort || !isBackendReady) {
      return { code: 5001, message: '本地服务尚未就绪' };
    }
    if (!isApiPathAllowed(url, 'delete')) {
      return { code: 403, message: '权限不足：该 API 不允许通过 Renderer 访问' };
    }
    try {
      return await apiRequest('DELETE', url);
    } catch (e: any) {
      return { code: 5001, message: e.message || '本地服务不可用' };
    }
  });

  // 安全存储：设置密钥（只写通道，Renderer 不可读取密钥）
  ipcMain.handle(IPC_CHANNELS.KEYSTORE_SET, async (_event, key: string, value: string) => {
    if (!safeStorage.isEncryptionAvailable()) {
      return { success: false, error: '当前系统不支持安全存储' };
    }
    const store = loadSecureStore();
    store[key] = value;
    saveSecureStore(store);
    return { success: true };
  });

  // 安全存储：检查密钥是否存在
  ipcMain.handle(IPC_CHANNELS.KEYSTORE_HAS, async (_event, key: string) => {
    const store = loadSecureStore();
    return { success: true, has: key in store };
  });

  // ── 安全通信 IPC（密钥由主进程注入，Renderer 不接触密钥） ──

  // 获取平台信息
  ipcMain.handle(IPC_CHANNELS.GET_PLATFORM, () => {
    return process.platform;
  });

  // 获取应用版本
  ipcMain.handle(IPC_CHANNELS.GET_APP_VERSION, () => {
    return app.getVersion();
  });

  // 获取 Electron 运行时状态（不包含敏感路径信息）
  ipcMain.handle(IPC_CHANNELS.GET_APP_STATUS, () => {
    return {
      electronVersion: process.versions.electron,
      nodeVersion: process.versions.node,
      chromeVersion: process.versions.chrome,
      appVersion: app.getVersion(),
      pid: process.pid,
      platform: process.platform,
      uptime: Math.floor(process.uptime()),
    };
  });

  // 获取平台能力状态（异步检测 macOS 权限）
  ipcMain.handle(IPC_CHANNELS.GET_PLATFORM_CAPABILITIES, async () => {
    const platform = getPlatform();
    try {
      const capabilities = await getPlatformCapabilities();
      const result: PlatformCapabilitiesResponse = { platform, capabilities };
      return result;
    } catch {
      // 降级：返回静态默认能力
      const capabilities = getStaticCapabilities();
      const result: PlatformCapabilitiesResponse = { platform, capabilities };
      return result;
    }
  });

  // ── 活动采集 IPC 处理器 ─────────────────────────────────────────

  // 流式对话：Renderer 发送消息（不含密钥），主进程注入密钥后转发
  // 注意：不直接使用 apiRequest，因为后端 SSE 端点返回 "data: {...}\n\n" 格式
  // （非标准 JSON），需要使用原始 HTTP 请求逐段解析 SSE 事件。
  ipcMain.handle(IPC_CHANNELS.CHAT_STREAM, async (_event, data: {
    sessionId: number;
    content: string;
    configId: number;
  }) => {
    if (!backendPort || !isBackendReady) {
      return { code: 5001, message: '本地服务尚未就绪' };
    }
    try {
      // 从 keystore 读取 API Key（主进程内部操作，密钥不进入 Renderer）
      const store = loadSecureStore();
      const apiKey = store[`model_key_${data.configId}`];
      if (!apiKey) {
        return { code: 4001, message: 'API Key 未配置' };
      }

      // 原始 HTTP 请求：解析 SSE 格式的流式响应
      return await new Promise<{ code: number; message: string; data?: any }>((resolve) => {
        const body = JSON.stringify({
          content: data.content,
          api_key: apiKey,
        });

        const req = http.request(
          {
            hostname: '127.0.0.1',
            port: backendPort,
            path: `/api/v1/chat/sessions/${data.sessionId}/chat`,
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${authToken}`,
              'Content-Type': 'application/json',
              'Content-Length': Buffer.byteLength(body),
            },
          },
          (res: any) => {
            let collectedContent = '';
            let messageId: number | null = null;
            let errorMessage: string | null = null;
            let buffer = '';

            res.on('data', (chunk: string) => {
              buffer += chunk.toString();

              // 解析 SSE 事件块：data: {...}\n\n
              const parts = buffer.split('\n\n');
              // 最后一段可能不完整，保留到下次
              buffer = parts.pop() || '';

              for (const part of parts) {
                for (const line of part.split('\n')) {
                  if (line.startsWith('data: ')) {
                    try {
                      const event = JSON.parse(line.slice(6));
                      if (event.type === 'token' && event.content) {
                        collectedContent += event.content;
                      } else if (event.type === 'done') {
                        messageId = event.message_id;
                      } else if (event.type === 'error') {
                        errorMessage = event.message || '对话生成失败';
                      }
                    } catch {
                      // 跳过解析失败的单个 event
                    }
                  }
                }
              }
            });

            res.on('end', () => {
              if (errorMessage) {
                resolve({ code: 5001, message: errorMessage });
              } else {
                resolve({
                  code: 0,
                  message: 'ok',
                  data: {
                    content: collectedContent,
                    message_id: messageId,
                  },
                });
              }
            });

            res.on('error', (err: any) => {
              resolve({ code: 5001, message: `流式响应异常: ${err.message}` });
            });
          },
        );

        req.on('error', (err: any) => {
          resolve({ code: 5001, message: `本地服务不可用: ${err.message}` });
        });

        req.write(body);
        req.end();
      });
    } catch (e: any) {
      return { code: 5001, message: e.message || '对话生成失败' };
    }
  });

  // 模型连接测试：Renderer 发送 configId（不含密钥），主进程注入密钥后测试
  ipcMain.handle(IPC_CHANNELS.MODEL_TEST, async (_event, configId: number) => {
    if (!backendPort || !isBackendReady) {
      return { success: false, message: '本地服务尚未就绪' };
    }
    try {
      const store = loadSecureStore();
      const apiKey = store[`model_key_${configId}`];
      if (!apiKey) {
        return { success: false, message: '密钥已丢失' };
      }

      const result: any = await apiRequest(
        'POST',
        `/api/v1/models/configs/${configId}/test`,
        { api_key: apiKey },
      );

      if (result && result.code === 0) {
        return { success: true, message: result.message || '连接成功' };
      }
      return { success: false, message: (result && result.message) || '连接测试失败' };
    } catch (e: any) {
      return { success: false, message: e.message || '连接测试失败' };
    }
  });

  // 清除模型密钥：Renderer 通过 configId 发起，主进程从 keystore 删除
  ipcMain.handle(IPC_CHANNELS.MODEL_CLEAR_KEY, async (_event, configId: number) => {
    const store = loadSecureStore();
    delete store[`model_key_${configId}`];
    saveSecureStore(store);
    return { success: true };
  });
  // 活动采集由 Main 进程管理（通过 ActivityCaptureManager），
  // Renderer 只能通过受控 IPC 控制开关和查询状态。

  // 启动活动采集
  ipcMain.handle(IPC_CHANNELS.ACTIVITY_CAPTURE_START, async () => {
    const capture = getActivityCaptureManager();
    capture.setBackendInfo(backendPort, authToken);
    await capture.refreshPrivacyRules();
    const started = await capture.start();
    return { success: started };
  });

  // 停止活动采集
  ipcMain.handle(IPC_CHANNELS.ACTIVITY_CAPTURE_STOP, async () => {
    const capture = getActivityCaptureManager();
    await capture.stop();
    return { success: true };
  });

  // 查询活动采集状态
  ipcMain.handle(IPC_CHANNELS.ACTIVITY_CAPTURE_STATUS, () => {
    const capture = getActivityCaptureManager();
    return { success: true, status: capture.getStatus() };
  });
}

// ── 窗口管理 ─────────────────────────────────────────────────────────

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'AI Companion',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,  // 启用沙箱：Renderer 进程在 OS 级隔离中运行
    },
  });

  if (isDev) {
    mainWindow.loadURL('http://127.0.0.1:9753');
    mainWindow.webContents.openDevTools();
  } else {
    const frontendDist = path.join(ROOT_DIR, 'frontend', 'dist', 'index.html');
    if (fs.existsSync(frontendDist)) {
      mainWindow.loadFile(frontendDist);
    } else {
      console.error('[Main] 前端构建产物不存在:', frontendDist);
      mainWindow.loadURL('http://127.0.0.1:9753');
    }
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// ── 应用生命周期 ─────────────────────────────────────────────────────

app.whenReady().then(async () => {
  console.log('[Main] 应用启动');
  console.log(`[Main] 数据目录: ${DATA_DIR}`);

  // 确保数据目录存在
  fs.mkdirSync(DATA_DIR, { recursive: true });

  // 创建主窗口
  createWindow();

  // 注册 IPC 处理器
  setupIpcHandlers();

  // 启动 Python 本地服务
  try {
    await startPythonBackend();
    startHealthCheck();
  } catch (err) {
    console.error('[Main] 本地服务启动失败:', err);
    sendBackendStatus(false);
    // 即使后端启动失败，窗口仍然可用，展示不可用状态
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  isQuitting = true;
  // 同步停止活动采集（不等待缓冲区提交，退出时数据丢失可接受）
  try {
    const capture = getActivityCaptureManager();
    capture.stopSync();
  } catch {
    // 采集停止失败不影响退出
  }
  stopPythonBackend();
});

app.on('will-quit', () => {
  // 只清理定时器和引用，实际的 kill 操作已在 before-quit 中完成
  if (healthCheckTimer) {
    clearInterval(healthCheckTimer);
    healthCheckTimer = null;
  }
  pythonProcess = null;
});
