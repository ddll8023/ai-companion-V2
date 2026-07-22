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

from app.core.database import get_background_db_session
from app.models.chat import Message
from app.schemas.memory import MemoryCreate
from app.services import memory as services_memory
from app.services import model_provider
from app.services import task as services_task
from app.tasks.registry import register_handler
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

_MEMORY_EXTRACT_SYSTEM_PROMPT = (
    "你是一个记忆提取助手。请阅读以下对话内容，提取其中有长期价值的、关于用户的重要信息。\n\n"
    "提取要求：\n"
    "1. 只提取对长期理解用户有帮助的信息，如：用户提到的个人信息、偏好、习惯、重要事件、目标、观点等\n"
    "2. 每个记忆应当是一条独立的重要信息\n"
    "3. 用简洁明确的中文描述记忆内容\n"
    "4. 为每条记忆判断类型和重要性（1-10，越高越重要）\n"
    "5. 不要提取临时性、一次性或无关的信息\n"
    "6. 如果对话中没有值得提取的信息，返回空列表\n\n"
    "请以 JSON 格式返回，格式为：\n"
    '{"memories": [{"content": "...", "type": "fact|preference|event|goal|habit", "importance": 5}]}\n\n'
    "只返回 JSON，不要包含其他说明文字。"
)


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

    db = get_background_db_session()
    try:
        session_id = payload.get("session_id")
        user_message_id = payload.get("user_message_id")
        assistant_message_id = payload.get("assistant_message_id")
        source_version = payload.get("source_version")
        api_key = payload.get("api_key")

        if not session_id:
            logger.warning("记忆提取任务缺少 session_id")
            return json.dumps({"extracted": 0, "error": "缺少 session_id"})

        # 检查来源是否仍然有效
        source_ids = []
        for mid in [user_message_id, assistant_message_id]:
            if mid:
                source_ids.append(mid)

        if not services_memory.check_source_valid(db, session_id, source_version, source_ids):
            logger.info(f"记忆提取跳过: 来源内容已变更或删除, session_id={session_id}")
            return json.dumps({"extracted": 0, "reason": "来源内容已变更或删除"})

        # 获取对话内容
        messages = _get_conversation_messages(db, session_id, user_message_id, assistant_message_id)
        if not messages:
            logger.info(f"记忆提取: 没有可用的对话内容, session_id={session_id}")
            return json.dumps({"extracted": 0, "reason": "无可用的对话内容"})

        # 调用模型提取记忆
        return _do_extract(db, session_id, messages, source_ids, source_version, api_key)
    finally:
        db.close()


def _get_conversation_messages(
    db,
    session_id: int,
    user_message_id: int | None,
    assistant_message_id: int | None,
) -> str:
    """获取需要提取记忆的对话内容。"""
    query_ids = []
    if user_message_id:
        query_ids.append(user_message_id)
    if assistant_message_id:
        query_ids.append(assistant_message_id)

    if not query_ids:
        return ""

    messages = db.scalars(
        Message.__table__.select().where(Message.id.in_(query_ids))
    ).all()

    # 按 ID 排序以保证对话顺序
    messages.sort(key=lambda m: m.id)

    parts = []
    for msg in messages:
        role = "用户" if msg.role == "user" else "助手"
        # 截取内容防止过长
        content = msg.content[:2000] if msg.content else ""
        parts.append(f"{role}: {content}")

    return "\n\n".join(parts)


def _do_extract(
    db,
    session_id: int,
    conversation_text: str,
    source_ids: list[int],
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
            system_prompt=_MEMORY_EXTRACT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": conversation_text}],
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
            if not content:
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
                source_ids=source_ids,
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
