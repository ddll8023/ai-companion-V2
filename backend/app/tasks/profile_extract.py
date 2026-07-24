"""画像提取后台任务。

从已确认记忆（confirmed/corrected）中提取用户画像特征。

处理器注册: @register_handler("profile.extract")

任务 payload:
{
    "memory_ids": [int, ...]      // 可选，指定提取哪些记忆；为空则提取全部
}
"""

from __future__ import annotations

import json

from sqlalchemy import desc, select

from app.core import api_key_cache
from app.core.database import get_background_db_session
from app.models.memory import Memory
from app.schemas.profile import PROFILE_CATEGORIES, ProfileCreate
from app.services import model_provider
from app.services import profile as services_profile
from app.tasks.registry import register_handler
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

_PROFILE_EXTRACT_SYSTEM_PROMPT = (
    "你是用户画像分析助手。请阅读以下「用户已确认的记忆」列表，\
从中提取用户的人物画像特征。\n\n"
    "提取要求：\n"
    "1. 只从给定的记忆内容中推断，禁止添加记忆未包含的信息\n"
    "2. 提取稳定的、对长期理解用户有帮助的特征\n"
    "3. 每条特征必须附带「evidence」（直接对应记忆原文）作为证据\n"
    "4. 避免过度泛化：单条临时情绪不构成习惯或偏好\n"
    "5. 用简洁明确的中文描述画像内容\n"
    "6. 如果没有可提取的画像特征，返回空列表\n\n"
    "可选类别：\n"
    "- communication_preference（沟通偏好：语气、格式、风格等）\n"
    "- work_habit（工作习惯：工作方式、工具偏好、时间安排等）\n"
    "- learning_preference（学习偏好：学习方式、知识领域等）\n"
    "- interest（兴趣方向：关注的话题、娱乐、爱好等）\n"
    "- decision_preference（决策偏好：选择倾向、权衡方式等）\n"
    "- time_habit（时间习惯：活跃时段、作息等）\n"
    "- long_term_goal（长期目标：事业、学习、生活目标等）\n"
    "- work_pattern（使用模式：常用应用、工作流程等）\n"
    "- other（其他无法归类的稳定特征）\n\n"
    "请以 JSON 格式返回，格式为：\n"
    '{"profiles": [{"category": "...", "content": "...", '
    '"confidence": 80, "evidence": "记忆原文..."}]}\n\n'
    "置信度规则：\n"
    "- 有 2 条以上独立记忆支持同一结论 → 60～80\n"
    "- 只有 1 条记忆支持 → 最高 50\n"
    "- 直觉推断但无直接记忆支持 → 最高 30\n"
    "- 超过 80 的置信度必须有至少 3 条独立记忆交叉支持\n\n"
    "只返回 JSON，不要包含其他说明文字。"
)


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

        # 从进程内存缓存获取 API Key（不经过前端/Renderer）
        api_key = api_key_cache.peek_global()
        if not api_key:
            logger.warning("画像提取: API Key 缓存未命中（请先进行一次对话）")
            return json.dumps({"extracted": 0, "error": "API Key 不可用（请先进行一次对话）"})

        # 获取已确认记忆（含 Memory 对象，用于提取 source_version）
        memories = _get_confirmed_memories(db, memory_ids)
        if not memories:
            logger.info("画像提取: 没有可用的已确认记忆")
            return json.dumps({"extracted": 0, "reason": "无可用的已确认记忆"})

        # 调用模型提取画像
        return _do_extract(db, memories, api_key)


# ── 辅助函数 ─────────────────────────────────────────────────────────────

"""辅助函数"""


def _get_confirmed_memories(
    db,
    memory_ids: list[int] | None = None,
    max_count: int = 50,
) -> list[Memory]:
    """获取已确认的记忆对象列表。

    Args:
        db: 数据库会话
        memory_ids: 指定记忆 ID 列表；为空则取全部已确认记忆
        max_count: 最大记忆条数

    Returns:
        Memory 对象列表（空列表表示无可用记忆）
    """
    stmt = select(Memory).where(
        Memory.status.in_(["confirmed", "corrected"]),
    )

    if memory_ids:
        stmt = stmt.where(Memory.id.in_(memory_ids))

    memories = db.scalars(
        stmt.order_by(desc(Memory.importance), desc(Memory.id))
        .limit(max_count)
    ).all()

    return list(memories)


def _format_memories_for_prompt(memories: list[Memory]) -> str:
    """将记忆对象列表格式化为模型的输入文本。"""
    parts = []
    for mem in memories:
        parts.append(
            f"[类型: {mem.type} | 重要性: {mem.importance}]\n{mem.content}",
        )
    return "\n\n---\n\n".join(parts)


def _do_extract(
    db,
    memories: list[Memory],
    api_key: str,
) -> str | None:
    """调用模型提取画像并保存候选画像。

    Args:
        db: 数据库会话
        memories: 已确认记忆对象列表
        api_key: API Key

    Returns:
        JSON 结果字符串
    """
    try:
        active_config = model_provider.get_active_config(db)
        if active_config is None:
            logger.warning("画像提取: 无激活的模型配置")
            return json.dumps({"extracted": 0, "error": "无激活的模型配置"})

        # 格式化记忆文本并计算来源版本
        memories_text = _format_memories_for_prompt(memories)
        memory_ids = sorted([m.id for m in memories])
        source_version = f"memories_{'_'.join(str(i) for i in memory_ids[:20])}"

        # 调用模型获取结构化输出
        result_text = model_provider.chat_sync(
            provider=active_config.provider,
            model_name=active_config.model_name,
            api_key=api_key,
            api_base=active_config.api_base,
            system_prompt=_PROFILE_EXTRACT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": memories_text}],
        )

        if not result_text:
            return json.dumps({"extracted": 0, "reason": "模型返回为空"})

        # 解析 JSON
        result = _parse_extraction_result(result_text)
        if result is None:
            return json.dumps({"extracted": 0, "error": "模型返回格式异常"})

        profiles_data = result.get("profiles", [])
        if not profiles_data:
            return json.dumps({"extracted": 0, "reason": "未提取到有效画像"})

        # 保存候选画像（去重）
        extracted_count = 0
        skipped_count = 0

        for prof in profiles_data:
            category = prof.get("category", "other")
            content = (prof.get("content", "") or "").strip()
            confidence = prof.get("confidence", 50)
            evidence = (prof.get("evidence", "") or "").strip()

            # 校验类别
            if category not in PROFILE_CATEGORIES:
                category = "other"

            # 校验内容
            if not content or len(content) < 5:
                continue

            # 限制置信度
            confidence = min(max(confidence, 0), 60)  # 自动提取上限 60
            if evidence and len(evidence) > 10:
                # 有证据可放宽到 80
                confidence = min(max(confidence, 0), 80)

            # 去重检查
            if services_profile.check_duplicate_profile(db, category, content):
                skipped_count += 1
                continue

            # 创建候选画像（携带来源版本信息）
            create_data = ProfileCreate(
                category=category,
                content=content,
                confidence=confidence,
                is_auto_extracted=1,
                source_version=source_version,
                memory_ids=[],
                evidence_texts=[evidence] if evidence else [],
            )

            try:
                services_profile.create_candidate_profile(db, create_data)
                extracted_count += 1
            except Exception as e:
                logger.warning(f"保存候选画像失败: {e!s}")
                continue

        logger.info(
            f"画像提取完成: 提取 {extracted_count} 条, "
            f"跳过 {skipped_count} 条重复",
        )
        return json.dumps({
            "extracted": extracted_count,
            "skipped": skipped_count,
        })

    except Exception as e:
        logger.error(f"画像提取模型调用异常: {e!s}", exc_info=True)
        return json.dumps({"extracted": 0, "error": str(e)[:200]})


def _parse_extraction_result(text: str) -> dict | None:
    """解析模型返回的 JSON 结果。"""
    text = text.strip()

    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试从 ```json ... ``` 代码块提取
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
