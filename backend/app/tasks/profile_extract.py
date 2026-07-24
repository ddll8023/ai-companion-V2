"""画像提取后台任务。

从已确认记忆（confirmed/corrected）中提取用户画像特征。
处理器注册: @register_handler("profile.extract")

任务 payload:
{
    "memory_ids": [int, ...]      // 可选，指定提取哪些记忆；为空则提取全部
}

使用 Service 层的 sync_extract_profiles 方法实现提取逻辑，
此文件只做任务调度层的适配（payload 解析、API Key 获取、JSON 序列化）。
"""

from __future__ import annotations

import json

from app.core import api_key_cache
from app.core.database import get_background_db_session
from app.services import profile as services_profile
from app.tasks.registry import register_handler
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)


@register_handler("profile.extract")
def handle_profile_extract(payload: dict | None) -> str | None:
    """处理画像提取任务。

    API Key 从进程内存缓存获取（由 chat 服务在对话时缓存），
    不再通过 payload 或前端传递。

    Args:
        payload: 任务参数，可包含 memory_ids 列表
    """
    if payload is None:
        logger.warning("画像提取任务 payload 为空")
        return json.dumps({"extracted": 0, "error": "payload 为空"})

    with get_background_db_session() as db:
        memory_ids = payload.get("memory_ids")

        # 从进程内存缓存获取 API Key
        api_key = api_key_cache.peek_global()
        if not api_key:
            logger.warning("画像提取: API Key 缓存未命中（请先进行一次对话）")
            return json.dumps({"extracted": 0, "error": "API Key 不可用（请先进行一次对话）"})

        # 调用 Service 层提取逻辑
        result = services_profile.sync_extract_profiles(
            db, api_key=api_key, memory_ids=memory_ids,
        )
        return json.dumps(result)
