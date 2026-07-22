/**
 * IPC 通道名称常量。
 *
 * 在 main.ts 和 preload.ts 之间共享，确保通道名称一致。
 * 增加通道时只需修改此文件一处。
 */
export const IPC_CHANNELS = {
  API_GET: 'api:get',
  API_POST: 'api:post',
  API_PUT: 'api:put',
  API_DELETE: 'api:delete',
  KEYSTORE_SET: 'keystore:set',
  KEYSTORE_GET: 'keystore:get',
  KEYSTORE_DELETE: 'keystore:delete',
  KEYSTORE_HAS: 'keystore:has',
  BACKEND_STATUS: 'backend-status',
  GET_PLATFORM: 'get-platform',
  GET_APP_VERSION: 'get-app-version',
  /** 获取平台各能力状态 */
  GET_PLATFORM_CAPABILITIES: 'get-platform-capabilities',
  // 注意：不暴露 GET_DATA_DIR，Renderer 不得获得数据库路径
} as const;
