"""API Key 进程内内存缓存。

仅用于后台任务场景，避免 API Key 持久化写入 SQLite。

设计：
- 键为 assistant_message_id（int），值为 API Key（str）
- TTL 600 秒（10 分钟），过期自动清理
- 一次性取出（pop），取出后即从缓存删除
- threading.Lock 保证线程安全

安全约束：
- API Key 仅在进程内存中存在
- 不写入任何持久化存储
- 使用后立即释放
"""

from __future__ import annotations

import threading
import time

from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

# TTL: 10 分钟，足够后台任务完成
_TTL_SECONDS = 600

# 全局缓存的固定 key
_GLOBAL_CACHE_KEY = "__global__"

# 缓存结构: {key: (api_key, expire_time)}
_cache: dict[str, tuple[str, float]] = {}
_lock = threading.Lock()


def store(key: str, api_key: str, ttl: int = _TTL_SECONDS) -> None:
    """存储 API Key 到内存缓存。"""
    expire_at = time.time() + ttl
    with _lock:
        _cache[key] = (api_key, expire_at)
    logger.debug(f"API Key 已缓存: key={key}, ttl={ttl}s")


def pop(key: str) -> str | None:
    """取出 API Key（一次性，取出后删除）。

    返回 None 表示 key 不存在或已过期。
    """
    with _lock:
        entry = _cache.pop(key, None)
        if entry is None:
            logger.debug(f"API Key 缓存未命中: key={key}")
            return None
        api_key, expire_at = entry
        if time.time() > expire_at:
            logger.debug(f"API Key 缓存已过期: key={key}")
            return None
        return api_key


def cleanup() -> int:
    """清理过期缓存项。

    Returns:
        清理的条目数量
    """
    now = time.time()
    expired_keys: list[str] = []
    with _lock:
        for k, (_, expire_at) in _cache.items():
            if now > expire_at:
                expired_keys.append(k)
        for k in expired_keys:
            del _cache[k]
    if expired_keys:
        logger.debug(f"清理过期 API Key 缓存: count={len(expired_keys)}")
    return len(expired_keys)


def store_global(api_key: str, ttl: int = _TTL_SECONDS) -> None:
    """存储 API Key 到全局缓存。

    与 chat 级缓存不同，全局缓存不绑定特定会话，
    供画像提取等不需要会话上下文的后台任务使用。
    """
    store(_GLOBAL_CACHE_KEY, api_key, ttl)


def get_global() -> str | None:
    """获取全局缓存的 API Key（一次性取出，取出即删除）。

    Returns:
        API Key 字符串，不存在或已过期时返回 None
    """
    return pop(_GLOBAL_CACHE_KEY)
