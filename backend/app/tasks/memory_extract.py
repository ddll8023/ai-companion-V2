"""记忆提取后台任务。

在对话完成后，从对话内容中识别重要信息，生成候选记忆。

处理器注册: @register_handler("memory.extract")

任务 payload:
{
    "session_id": int,
    "user_message_id": int,
    "assistant_message_id": int,
    "source_version": str | null
}
"""

from __future__ import annotations

import json

from app.core import api_key_cache
from app.core.database import get_background_db_session
from app.models.chat import Message
from app.prompts.memory import MEMORY_EXTRACTION_SYSTEM_PROMPT
from app.schemas.memory import MemoryCreate
from app.services import memory as services_memory
from app.services import model_provider
from app.services import task as services_task
from app.tasks.registry import register_handler
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

@register_handler("memory.extract")
def handle_memory_extract(payload: dict | None) -> str | None:
    """处理记忆提取任务。

    Args:
        payload: 任务参数，包含 session_id、消息 ID 等

    Returns:
        任务执行结果 JSON 字符串
    """
    if payload is None:
        logger.warning("记忆提取任务 payload 为空")
        return json.dumps({"extracted": 0, "error": "payload 为空"})

    with get_background_db_session() as db:
        session_id = payload.get("session_id")
        user_message_id = payload.get("user_message_id")
        assistant_message_id = payload.get("assistant_message_id")
        source_version = payload.get("source_version")

        if not session_id:
            logger.warning("记忆提取任务缺少 session_id")
            return json.dumps({"extracted": 0, "error": "缺少 session_id"})

        # 从内存缓存获取 API Key（不持久化到 SQLite）
        api_key_cache_key = f"chat_{assistant_message_id}"
        api_key = api_key_cache.peek(api_key_cache_key)
        if not api_key:
            logger.warning(f"记忆提取: API Key 缓存未命中, session_id={session_id}")
            return json.dumps({"extracted": 0, "error": "API Key 不可用（可能已过期）"})

        # 检查来源是否仍然有效
        # 用户消息是唯一可用于生成用户事实的来源。助手消息仅用于 API Key 缓存定位，
        # 不能作为长期记忆或画像的证据。
        source_ids = [user_message_id] if user_message_id else []

        if not services_memory.check_source_valid(db, session_id, source_version, source_ids):
            logger.info(f"记忆提取跳过: 来源内容已变更或删除, session_id={session_id}")
            return json.dumps({"extracted": 0, "reason": "来源内容已变更或删除"})

        # 仅处理当前轮的用户消息，避免重复扫描历史及助手内容污染用户事实。
        user_message = _get_user_message_for_extraction(
            db, session_id, user_message_id,
        )
        if user_message is None:
            logger.info(f"记忆提取: 没有可用的用户消息, session_id={session_id}")
            return json.dumps({"extracted": 0, "reason": "无可用的用户消息"})

        # 调用模型提取记忆
        return _do_extract(
            db, session_id, user_message, user_message_id,
            source_version, api_key,
        )


def _get_user_message_for_extraction(
    db,
    session_id: int,
    message_id: int | None,
) -> Message | None:
    """获取当前轮可作为用户事实来源的用户消息。"""
    if not message_id:
        return None
    message = db.get(Message, message_id)
    if (
        message is None
        or message.session_id != session_id
        or message.role != "user"
        or message.status != "completed"
    ):
        return None
    return message


def _do_extract(
    db,
    session_id: int,
    user_message: Message,
    user_message_id: int,
    source_version: str | None,
    api_key: str | None = None,
) -> str | None:
    """调用模型提取记忆并保存候选记忆。"""
    try:
        active_config = model_provider.get_active_config(db)
        if active_config is None:
            logger.warning("记忆提取: 无激活的模型配置")
            return json.dumps({"extracted": 0, "error": "无激活的模型配置"})

        # 调用模型获取结构化输出
        result_text = model_provider.chat_sync(
            provider=active_config.provider,
            model_name=active_config.model_name,
            api_key=api_key,
            api_base=active_config.api_base,
            system_prompt=MEMORY_EXTRACTION_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"source_message_id: {user_message_id}\n"
                    f"用户消息：{user_message.content}"
                ),
            }],
        )

        if not result_text:
            return json.dumps({"extracted": 0, "reason": "模型返回为空"})

        # 解析 JSON
        result = _parse_extraction_result(result_text)
        if result is None:
            return json.dumps({"extracted": 0, "error": "模型返回格式异常"})

        memories_data = result.get("memories", [])
        if not memories_data:
            return json.dumps({"extracted": 0, "reason": "未提取到有效记忆"})

        # 保存候选记忆
        extracted_count = 0
        for mem in memories_data:
            content = mem.get("content", "").strip()
            evidence = mem.get("evidence", "").strip()
            candidate_source_id = mem.get("source_message_id")
            if (
                not content
                or not evidence
                or candidate_source_id != user_message_id
                or evidence not in user_message.content
            ):
                logger.info(
                    "记忆提取跳过: 缺少可验证的用户原文证据, session_id=%s",
                    session_id,
                )
                continue

            mem_type = mem.get("type", "fact")
            importance = min(max(mem.get("importance", 0), 0), 10)

            create_data = MemoryCreate(
                content=content,
                type=mem_type,
                importance=importance,
                session_id=session_id,
                source_version=source_version,
                source_type="message",
                source_ids=[user_message_id],
                source_evidence_texts=[evidence],
            )

            try:
                services_memory.create_candidate_memory(db, create_data)
                extracted_count += 1
            except Exception as e:
                logger.warning(f"保存候选记忆失败: {e!s}")
                continue

        logger.info(f"记忆提取完成: session_id={session_id}, 提取 {extracted_count} 条")
        return json.dumps({"extracted": extracted_count})

    except Exception as e:
        logger.error(f"记忆提取模型调用异常: {e!s}", exc_info=True)
        return json.dumps({"extracted": 0, "error": str(e)[:200]})


def _parse_extraction_result(text: str) -> dict | None:
    """解析模型返回的 JSON 结果。

    尝试直接解析，失败时尝试从代码块中提取。
    """
    text = text.strip()

    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试从 ```json ... ``` 代码块中提取
    if "```" in text:
        import re

        matches = re.findall(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

    # 尝试找到第一个 { 和最后一个 }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None
