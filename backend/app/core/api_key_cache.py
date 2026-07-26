"""API Key 进程内全局内存缓存。

仅用于后台任务场景（会话提取、画像演化），避免 API Key 持久化写入 SQLite。

设计：
- 单一全局键，值为 API Key（str）
- TTL 600 秒（10 分钟），过期后读取返回 None
- threading.Lock 保证线程安全

安全约束：
- API Key 仅在进程内存中存在
- 不写入任何持久化存储
"""

from __future__ import annotations

import threading
import time

from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

# TTL: 10 分钟，足够后台任务完成
_TTL_SECONDS = 600

# 缓存结构: (api_key, expire_at)，None 表示未缓存
_entry: tuple[str, float] | None = None
_lock = threading.Lock()


def store_global(api_key: str, ttl: int = _TTL_SECONDS) -> None:
    """存储 API Key 到全局缓存（供后台任务重复读取）。"""
    global _entry
    with _lock:
        _entry = (api_key, time.time() + ttl)
    logger.debug(f"API Key 已缓存: ttl={ttl}s")


def peek_global() -> str | None:
    """查看全局缓存的 API Key（只读不删，重试时仍可获取），不存在或已过期时返回 None。"""
    with _lock:
        if _entry is None:
            return None
        api_key, expire_at = _entry
        if time.time() > expire_at:
            return None
        return api_key
