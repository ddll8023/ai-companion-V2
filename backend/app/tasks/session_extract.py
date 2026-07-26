"""会话级提取后台任务。

两阶段流程：
- 阶段一 会话分析：区间内消息 → LLM → 摘要 + 候选记忆（原子保存，摘要作为幂等完成标志）
- 阶段二 画像演化：现有画像 + 摘要 + 新记忆 → LLM → CREATE/REINFORCE/REVISE 操作指令

处理器注册: @register_handler("session.extract")

任务 payload:
{
    "session_id": int,
    "from_message_id": int,   // 提取区间起始消息 ID（含）
    "to_message_id": int      // 提取区间结束消息 ID（含）
}
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app.core import api_key_cache
from app.core.database import commit_or_rollback, get_background_db_session
from app.models.chat import ChatSession, Message
from app.models.conversation import SessionSummary
from app.models.memory import Memory, MemorySource
from app.prompts.memory import SESSION_ANALYSIS_SYSTEM_PROMPT
from app.services import memory as services_memory
from app.services import model_provider
from app.services import profile as services_profile
from app.tasks.registry import register_handler
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

_VALID_MEMORY_TYPES = {"fact", "preference", "event", "goal", "habit"}

# 摘要正文长度上限
_SUMMARY_MAX_CHARS = 2000


@register_handler("session.extract")
def handle_session_extract(payload: dict | None) -> str | None:
    """处理会话级提取任务（阶段一会话分析 → 阶段二画像演化）。"""
    if payload is None:
        return json.dumps({"error": "payload 为空"})

    session_id = payload.get("session_id")
    from_message_id = payload.get("from_message_id")
    to_message_id = payload.get("to_message_id")
    if not session_id or not from_message_id or not to_message_id:
        return json.dumps({"error": "payload 缺少必要字段"})

    with get_background_db_session() as db:
        # 会话可能在任务排队期间被删除，属正常终态而非失败
        session = db.get(ChatSession, session_id)
        if session is None:
            logger.info(f"会话提取跳过: 会话已删除, session_id={session_id}")
            return json.dumps({"reason": "会话已删除"})

        api_key = api_key_cache.peek_global()
        if not api_key:
            return json.dumps({"error": "API Key 不可用（缓存已过期，请重新触发提取）"})

        active_config = model_provider.get_active_config(db)
        if active_config is None:
            return json.dumps({"error": "无激活的模型配置"})

        # ── 阶段一：会话分析（摘要存在 = 已完成，重试时跳过重新生成）──
        existing_summary = db.scalar(
            select(SessionSummary).where(
                SessionSummary.session_id == session_id,
                SessionSummary.from_message_id == from_message_id,
                SessionSummary.to_message_id == to_message_id,
            ).limit(1)
        )

        if existing_summary is not None:
            summary_content = existing_summary.content
            new_memories = _load_range_memories(
                db, session_id, from_message_id, to_message_id,
            )
            logger.info(f"阶段一已完成（重试恢复）: session_id={session_id}")
        else:
            analysis = _run_session_analysis(
                db, session_id, from_message_id, to_message_id,
                active_config, api_key,
            )
            if "error" in analysis:
                # 抛出异常交由执行器进入重试流程
                raise RuntimeError(analysis["error"])
            summary_content = analysis["summary"]
            new_memories = analysis["memories"]

        # ── 阶段二：画像演化 ──
        profile_stats = services_profile.evolve_profiles(
            db,
            api_key=api_key,
            new_summary=summary_content,
            new_memories=new_memories,
            source_session_id=session_id,
        )
        if "error" in profile_stats:
            raise RuntimeError(f"画像演化失败: {profile_stats['error']}")

        # ── 更新水位线（最后一步，全部成功后才推进）──
        session.last_extracted_message_id = to_message_id
        session.last_extracted_at = datetime.now()
        commit_or_rollback(db)

        result = {
            "memories_extracted": len(new_memories),
            "profile_ops": profile_stats,
        }
        logger.info(f"会话提取完成: session_id={session_id}, result={result}")
        return json.dumps(result, ensure_ascii=False)


"""辅助函数"""


def _run_session_analysis(
    db,
    session_id: int,
    from_message_id: int,
    to_message_id: int,
    active_config,
    api_key: str,
) -> dict:
    """执行阶段一：调用 LLM 生成摘要与候选记忆并原子保存。"""
    messages = db.scalars(
        select(Message).where(
            Message.session_id == session_id,
            Message.id >= from_message_id,
            Message.id <= to_message_id,
            Message.status == "completed",
            Message.role.in_(["user", "assistant"]),
        ).order_by(Message.id)
    ).all()

    user_messages = {m.id: m for m in messages if m.role == "user"}
    if not user_messages:
        # 区间内无用户消息（防御路径），无可分析内容
        return {"summary": None, "memories": []}

    # 前情摘要：该会话最近一份摘要，提供上下文连续性
    previous = db.scalar(
        select(SessionSummary)
        .where(SessionSummary.session_id == session_id)
        .order_by(SessionSummary.id.desc())
        .limit(1)
    )

    lines = []
    if previous is not None:
        lines.append(f"【前情摘要】\n{previous.content}\n")
    lines.append("【对话记录】")
    for m in messages:
        lines.append(f"[{m.role} #{m.id}] {m.content}")

    result_text = model_provider.chat_sync(
        provider=active_config.provider,
        model_name=active_config.model_name,
        api_key=api_key,
        api_base=active_config.api_base,
        system_prompt=SESSION_ANALYSIS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": "\n".join(lines)}],
    )
    if not result_text:
        return {"error": "会话分析模型返回为空"}

    parsed = _parse_json(result_text)
    if parsed is None:
        return {"error": "会话分析模型返回格式异常"}

    summary = str(parsed.get("summary") or "").strip()
    if not summary:
        return {"error": "会话分析未生成摘要"}

    validated = _validate_memories(parsed.get("memories"), user_messages, session_id)

    saved = services_memory.save_session_analysis(
        db,
        session_id=session_id,
        from_message_id=from_message_id,
        to_message_id=to_message_id,
        summary_content=summary[:_SUMMARY_MAX_CHARS],
        memories_data=validated,
    )
    return {"summary": summary, "memories": saved}


def _validate_memories(
    memories_data,
    user_messages: dict,
    session_id: int,
) -> list[dict]:
    """校验候选记忆：证据必须是区间内用户消息的逐字原文片段。"""
    validated = []
    for mem in memories_data or []:
        if not isinstance(mem, dict):
            continue
        content = str(mem.get("content") or "").strip()
        evidence = str(mem.get("evidence") or "").strip()
        source_id = mem.get("source_message_id")
        source_msg = user_messages.get(source_id) if isinstance(source_id, int) else None
        if (
            not content
            or not evidence
            or source_msg is None
            or evidence not in source_msg.content
        ):
            logger.info(
                f"候选记忆跳过: 缺少可验证的用户原文证据, session_id={session_id}",
            )
            continue

        mem_type = mem.get("type", "fact")
        if mem_type not in _VALID_MEMORY_TYPES:
            mem_type = "fact"
        importance = mem.get("importance", 0)
        if not isinstance(importance, int):
            importance = 0

        validated.append({
            "content": content,
            "type": mem_type,
            "importance": min(max(importance, 0), 10),
            "evidence": evidence,
            "source_message_id": source_id,
        })
    return validated


def _load_range_memories(
    db,
    session_id: int,
    from_message_id: int,
    to_message_id: int,
) -> list:
    """重试恢复：加载该区间此前已生成的候选记忆（供阶段二使用）。"""
    memory_ids_stmt = select(MemorySource.memory_id).where(
        MemorySource.source_type == "message",
        MemorySource.source_id >= from_message_id,
        MemorySource.source_id <= to_message_id,
    )
    return list(
        db.scalars(
            select(Memory).where(
                Memory.id.in_(memory_ids_stmt),
                Memory.session_id == session_id,
            )
        ).all()
    )


def _parse_json(text: str) -> dict | None:
    """宽松解析模型返回的 JSON（直接解析 → 代码块 → 花括号截取）。"""
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    if "```" in text:
        import re

        matches = re.findall(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start: end + 1])
        except json.JSONDecodeError:
            pass

    return None
