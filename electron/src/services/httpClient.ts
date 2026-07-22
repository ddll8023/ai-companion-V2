/**
 * HTTP 请求客户端（用于 Electron Main 进程向后端发送请求）。
 *
 * 与 main.ts 中的 apiRequest 功能类似，但提供独立模块供其他服务使用。
 * 通过端口和认证令牌直接发送 HTTP 请求。
 */

import * as http from 'http';

/**
 * 发送 HTTP 请求到本地 Python 后端服务。
 *
 * @param method - HTTP 方法
 * @param port - 后端端口
 * @param authToken - 认证令牌
 * @param urlPath - 请求路径
 * @param body - 请求体（可选）
 * @returns 解析后的响应 JSON
 */
export function httpRequest(
  method: string,
  port: number,
  authToken: string,
  urlPath: string,
  body?: unknown,
): Promise<any> {
  return new Promise((resolve, reject) => {
    const bodyStr = body ? JSON.stringify(body) : undefined;

    const options: http.RequestOptions = {
      hostname: '127.0.0.1',
      port,
      path: urlPath,
      method,
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json',
        ...(bodyStr ? { 'Content-Length': Buffer.byteLength(bodyStr).toString() } : {}),
      },
      timeout: 10000,
    };

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', (chunk: string) => {
        data += chunk;
      });
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch {
          reject(new Error(`无效响应 (${res.statusCode}): ${data.slice(0, 200)}`));
        }
      });
    });

    req.on('error', (err) => {
      reject(new Error(`请求失败: ${err.message}`));
    });

    req.on('timeout', () => {
      req.destroy();
      reject(new Error(`请求超时: ${method} ${urlPath}`));
    });

    if (bodyStr) {
      req.write(bodyStr);
    }
    req.end();
  });
}
