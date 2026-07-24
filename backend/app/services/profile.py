"""画像服务。

职责：
- 管理画像 CRUD
- 处理用户审查操作（确认、纠正、否定、删除）
- 管理来源证据和修订历史
- 画像去重校验
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from app.core.database import commit_or_rollback
from app.models.activity import Activity
from app.models.chat import Message
from app.models.profile import Profile, ProfileRevision, ProfileSource
from app.schemas.common import ErrorCode, PaginatedResponse, PaginationInfo
from app.schemas.profile import (
    BehaviorStatsResponse,
    ProfileCorrect,
    ProfileCreate,
    ProfileDetailResponse,
    ProfileListQuery,
    ProfileResponse,
    ProfileRevisionResponse,
    ProfileSourceResponse,
)
from app.services.audit import record_audit
from app.utils.exception import ServiceException
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

# 候选画像过期天数
CANDIDATE_EXPIRE_DAYS = 7


# ========== 公共入口函数 ==========


def create_candidate_profile(
    db: Session,
    data: ProfileCreate,
) -> ProfileResponse:
    """创建候选画像。

    支持同时关联多条来源记忆和证据文本。
    """
    profile = Profile(
        category=data.category,
        content=data.content,
        confidence=data.confidence,
        status="candidate",
        is_auto_extracted=data.is_auto_extracted,
        source_version=data.source_version,
        version=1,
    )
    db.add(profile)
    commit_or_rollback(db)

    # 保存来源证据
    for idx, memory_id in enumerate(data.memory_ids):
        evidence = (
            data.evidence_texts[idx]
            if idx < len(data.evidence_texts)
            else None
        )
        source = ProfileSource(
            profile_id=profile.id,
            source_type="extraction" if data.is_auto_extracted else "memory",
            memory_id=memory_id,
            content_preview=data.content[:200],
            evidence_text=evidence,
        )
        db.add(source)

    commit_or_rollback(db)
    logger.info(
        f"创建候选画像: id={profile.id}, category={data.category}, "
        f"is_auto_extracted={data.is_auto_extracted}",
    )

    return ProfileResponse.model_validate(profile)


def query_profiles(
    db: Session,
    query: ProfileListQuery,
) -> PaginatedResponse[ProfileResponse]:
    """查询画像列表。

    支持按类别、状态、关键词、是否自动提取筛选。
    """
    base_stmt = select(Profile)

    if query.status:
        base_stmt = base_stmt.where(Profile.status == query.status)
    if query.category:
        base_stmt = base_stmt.where(Profile.category == query.category)
    if query.keyword:
        base_stmt = base_stmt.where(Profile.content.contains(query.keyword))
    if query.is_auto_extracted is not None:
        base_stmt = base_stmt.where(
            Profile.is_auto_extracted == query.is_auto_extracted,
        )

    total = db.scalar(select(func.count()).select_from(base_stmt.subquery()))

    items = (
        db.scalars(
            base_stmt
            .order_by(desc(Profile.confidence), desc(Profile.id))
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        ).all()
    )

    return PaginatedResponse(
        lists=[ProfileResponse.model_validate(item) for item in items],
        pagination=PaginationInfo(
            page=query.page,
            page_size=query.page_size,
            total=total or 0,
            total_pages=math.ceil((total or 0) / query.page_size),
        ),
    )


def get_profile(db: Session, profile_id: int) -> ProfileDetailResponse:
    """获取单个画像详情（含来源和修订历史）。"""
    profile = _get_profile_or_error(db, profile_id)

    sources = db.scalars(
        select(ProfileSource)
        .where(ProfileSource.profile_id == profile_id)
        .order_by(ProfileSource.id)
    ).all()

    revisions = db.scalars(
        select(ProfileRevision)
        .where(ProfileRevision.profile_id == profile_id)
        .order_by(desc(ProfileRevision.id))
    ).all()

    return ProfileDetailResponse(
        profile=ProfileResponse.model_validate(profile),
        sources=[ProfileSourceResponse.model_validate(s) for s in sources],
        revisions=[ProfileRevisionResponse.model_validate(r) for r in revisions],
    )


def confirm_profile(db: Session, profile_id: int) -> ProfileResponse:
    """确认候选画像。

    将状态更新为 confirmed。
    """
    profile = _get_profile_or_error(db, profile_id)

    if profile.status not in ("candidate", "corrected"):
        raise ServiceException(
            ErrorCode.PARAM_ERROR,
            f"仅可确认候选或已纠正状态的画像，当前状态: {profile.status}",
        )

    profile.status = "confirmed"
    commit_or_rollback(db)
    logger.info(f"确认画像: id={profile_id}")

    record_audit(
        db=db,
        action="profile.confirm",
        target_type="profile",
        target_id=profile_id,
        summary=f"确认画像: {profile.content[:100]}",
    )

    return ProfileResponse.model_validate(profile)


def correct_profile(
    db: Session,
    profile_id: int,
    data: ProfileCorrect,
) -> ProfileResponse:
    """纠正画像。

    用户纠正后，旧版本保存到 revisions 表，状态标记为 confirmed。
    """
    profile = _get_profile_or_error(db, profile_id)

    if profile.status in ("deleted",):
        raise ServiceException(
            ErrorCode.PARAM_ERROR,
            f"已删除的画像不可纠正，当前状态: {profile.status}",
        )

    # 保存旧版本到修订历史
    revision = ProfileRevision(
        profile_id=profile_id,
        previous_category=profile.category,
        previous_content=profile.content,
        previous_confidence=profile.confidence,
        previous_status=profile.status,
        changed_by="user",
    )
    db.add(revision)

    # 更新为新内容
    profile.category = data.category
    profile.content = data.content
    profile.confidence = data.confidence
    profile.version += 1

    if profile.status not in ("confirmed",):
        profile.status = "confirmed"

    commit_or_rollback(db)
    logger.info(f"纠正画像: id={profile_id}, version={profile.version}")

    record_audit(
        db=db,
        action="profile.correct",
        target_type="profile",
        target_id=profile_id,
        summary=f"纠正画像 (v{profile.version})",
    )

    return ProfileResponse.model_validate(profile)


def reject_profile(db: Session, profile_id: int) -> ProfileResponse:
    """否定画像（候选 → rejected）。

    保留否定标识，防止后续再次被自动提取。
    """
    profile = _get_profile_or_error(db, profile_id)

    if profile.status not in ("candidate", "confirmed", "corrected"):
        raise ServiceException(
            ErrorCode.PARAM_ERROR,
            f"当前状态不可否定: {profile.status}",
        )

    profile.status = "rejected"
    commit_or_rollback(db)
    logger.info(f"否定画像: id={profile_id}")

    record_audit(
        db=db,
        action="profile.reject",
        target_type="profile",
        target_id=profile_id,
        summary=f"否定画像: {profile.content[:100]}",
    )

    return ProfileResponse.model_validate(profile)


def delete_profile(db: Session, profile_id: int) -> None:
    """删除画像（逻辑删除）。

    标记 status='deleted'，保留来源和修订历史。
    关联的 sources 和 revisions 通过 CASCADE 自动清理。
    """
    profile = _get_profile_or_error(db, profile_id)

    record_audit(
        db=db,
        action="profile.delete",
        target_type="profile",
        target_id=profile_id,
        summary=f"删除画像 (id={profile_id})",
    )

    db.delete(profile)
    commit_or_rollback(db)
    logger.info(f"删除画像: id={profile_id}")


def expire_old_candidates(db: Session) -> int:
    """过期未确认的候选画像。

    超过 CANDIDATE_EXPIRE_DAYS 的候选画像自动转为 rejected。
    由后台定时任务调用。

    Returns:
        处理的记录数
    """
    cutoff = datetime.now() - timedelta(days=CANDIDATE_EXPIRE_DAYS)
    items = db.scalars(
        select(Profile).where(
            Profile.status == "candidate",
            Profile.created_at < cutoff,
        )
    ).all()

    count = 0
    for p in items:
        p.status = "rejected"
        count += 1

    if count:
        commit_or_rollback(db)
        logger.info(f"过期候选画像: {count} 条")

    return count


# ========== 行为统计 ==========


def get_behavior_stats(db: Session, days: int) -> BehaviorStatsResponse:
    """获取行为统计数据。

    聚合查询 activities 和 messages 表，不支持缓存。
    """
    since = datetime.now() - timedelta(days=days)

    # 1. 活跃时段：按小时聚合活动开始时间
    active_hours = _query_active_hours(db, since)

    # 2. 应用使用分布：按应用聚合使用时长
    app_usage = _query_app_usage(db, since)

    # 3. 对话活跃度：按日期聚合消息数
    chat_activity = _query_chat_activity(db, since)

    return BehaviorStatsResponse(
        active_hours=active_hours,
        app_usage=app_usage,
        chat_activity=chat_activity,
    )


# ========== 画笔去重校验 ==========


def check_duplicate_profile(
    db: Session,
    category: str,
    content: str,
) -> bool:
    """检查是否存在同类别下高度相似的画像。

    Args:
        db: 数据库会话
        category: 画像类别
        content: 画像正文

    Returns:
        True 表示存在重复
    """
    existing = db.scalars(
        select(Profile).where(
            Profile.category == category,
            Profile.status.notin_(["deleted", "rejected"]),
            Profile.content.contains(content[:50]),
        ).limit(3)
    ).all()

    if not existing:
        return False

    # 精确匹配
    for p in existing:
        if p.content == content:
            return True

    return False


# ========== 辅助函数 ==========

"""辅助函数"""


def sync_extract_profiles(
    db: Session,
    api_key: str,
    memory_ids: list[int] | None = None,
) -> dict:
    """从已确认记忆中同步提取画像特征并保存候选画像。

    这是 sync_extract_profiles 的纯业务方法，不涉及任务调度。
    API 路由和后台任务处理器都通过此方法调用同一份提取逻辑。

    Args:
        db: 数据库会话
        api_key: API Key
        memory_ids: 指定记忆 ID 列表；None 表示提取全部已确认记忆

    Returns:
        dict: 包含 extracted（提取数）和 skipped（重复跳过数）或 error 字段
    """
    try:
        # 1. 获取模型配置和记忆数据
        memories_data = _load_memories_for_extraction(db, memory_ids)
        if not isinstance(memories_data, dict):
            memories, source_version = memories_data
        else:
            return memories_data  # dict 即错误响应

        # 2. 组装 prompt 并调用模型
        result_text = _call_llm_for_extraction(db, api_key, memories, source_version)
        if result_text is None:
            return {"extracted": 0, "reason": "无激活的模型配置"}
        if not result_text:
            return {"extracted": 0, "reason": "模型返回为空"}

        # 3. 解析结果
        parsed = _parse_extraction_result(result_text)
        if parsed is None:
            return {"extracted": 0, "error": "模型返回格式异常"}
        profiles_data = parsed.get("profiles", [])
        if not profiles_data:
            return {"extracted": 0, "reason": "未提取到有效画像"}

        # 4. 保存候选画像（含去重）
        extracted, skipped = _save_extracted_profiles(
            db, profiles_data, source_version,
        )
        logger.info(
            f"画像提取完成: 提取 {extracted} 条, 跳过 {skipped} 条重复",
        )
        return {"extracted": extracted, "skipped": skipped}

    except Exception as exc:
        logger.error(f"画像提取模型调用异常: {exc}", exc_info=True)
        return {"extracted": 0, "error": str(exc)[:200]}


def _load_memories_for_extraction(
    db: Session, memory_ids: list[int] | None,
) -> tuple[list, str] | dict:
    """加载并格式化用于画像提取的记忆。返回 (memories列表, source_version) 或错误 dict。"""
    from app.models.memory import Memory
    from app.services import model_provider

    if not model_provider.get_active_config(db):
        return {"extracted": 0, "error": "无激活的模型配置"}

    stmt = select(Memory).where(
        Memory.status.in_(["confirmed", "corrected"]),
    )
    if memory_ids:
        stmt = stmt.where(Memory.id.in_(memory_ids))
    memories = list(
        db.scalars(
            stmt.order_by(desc(Memory.importance), desc(Memory.id))
            .limit(50)
        ).all()
    )
    if not memories:
        return {"extracted": 0, "reason": "无可用的已确认记忆"}

    memory_ids_sorted = sorted([m.id for m in memories])
    source_version = (
        f"memories_{'_'.join(str(i) for i in memory_ids_sorted[:20])}"
    )
    return memories, source_version


def _call_llm_for_extraction(
    db: Session, api_key: str,
    memories: list, source_version: str,
) -> str | None:
    """组装 prompt 并调用 LLM 进行画像提取。"""
    from app.schemas.profile import PROFILE_CATEGORIES
    from app.services import model_provider

    # 获取激活配置
    active_config = model_provider.get_active_config(db)
    if active_config is None:
        return None

    # 格式化记忆文本
    parts = []
    for mem in memories:
        parts.append(
            f"[类型: {mem.type} | 重要性: {mem.importance}]\n{mem.content}",
        )
    memories_text = "\n\n---\n\n".join(parts)

    system_prompt = _build_extraction_system_prompt()
    return model_provider.chat_sync(
        provider=active_config.provider,
        model_name=active_config.model_name,
        api_key=api_key,
        api_base=active_config.api_base,
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": memories_text}],
    )


def _build_extraction_system_prompt() -> str:
    """构造画像提取的系统提示词。"""
    return (
        "你是用户画像分析助手。请阅读以下「用户已确认的记忆」列表，"
        "从中提取用户的人物画像特征。\n\n"
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
        "- decision_preference（决策倾向：选择倾向、权衡方式等）\n"
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


def _save_extracted_profiles(
    db: Session,
    profiles_data: list[dict],
    source_version: str,
) -> tuple[int, int]:
    """保存提取到的画像，含去重和校验。返回 (extracted, skipped)。"""
    from app.schemas.profile import PROFILE_CATEGORIES, ProfileCreate

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

        # 限制置信度（有证据最高 80，否则最高 60）
        confidence = min(max(confidence, 0), 80 if (evidence and len(evidence) > 10) else 60)

        # 去重
        if check_duplicate_profile(db, category, content):
            skipped_count += 1
            continue

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
            create_candidate_profile(db, create_data)
            extracted_count += 1
        except Exception as exc:
            logger.warning(f"保存候选画像失败: {exc}")
            continue

    return extracted_count, skipped_count


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


def _get_profile_or_error(db: Session, profile_id: int) -> Profile:
    """获取画像实体，不存在时抛出异常。"""
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, f"画像不存在: {profile_id}")
    return profile


def _query_active_hours(db: Session, since: datetime) -> list[dict]:
    """查询活跃时段分布（按小时）。"""
    rows = db.execute(
        select(
            func.strftime("%H", Activity.started_at).label("hour"),
            func.count().label("count"),
        )
        .where(
            Activity.created_at >= since,
            Activity.privacy_action == "allowed",
        )
        .group_by("hour")
        .order_by("hour")
    ).all()

    # 补齐 24 小时，值为 0
    hour_counts = {int(r[0]): r[1] for r in rows}
    return [
        {"hour": h, "count": hour_counts.get(h, 0)} for h in range(24)
    ]


def _query_app_usage(db: Session, since: datetime) -> list[dict]:
    """查询应用使用分布（按应用聚合时长，取 Top 10）。"""
    rows = db.execute(
        select(
            Activity.app_name,
            func.sum(Activity.duration_seconds).label("total_seconds"),
        )
        .where(
            Activity.created_at >= since,
            Activity.privacy_action == "allowed",
            Activity.duration_seconds.isnot(None),
        )
        .group_by(Activity.app_name)
        .order_by(func.sum(Activity.duration_seconds).desc())
        .limit(10)
    ).all()

    if not rows:
        return []

    total_seconds = sum(r[1] or 0 for r in rows)
    if total_seconds == 0:
        return []

    result = []
    for r in rows:
        total_minutes = round((r[1] or 0) / 60, 1)
        percentage = round((r[1] or 0) / total_seconds * 100, 1)
        result.append({
            "app_name": r[0],
            "total_minutes": total_minutes,
            "percentage": percentage,
        })

    return result


def _query_chat_activity(db: Session, since: datetime) -> list[dict]:
    """查询对话活跃度（按日期聚合消息数）。"""
    rows = db.execute(
        select(
            func.date(Message.created_at).label("date"),
            func.count().label("count"),
        )
        .where(
            Message.created_at >= since,
            Message.status == "completed",
        )
        .group_by(func.date(Message.created_at))
        .order_by(func.date(Message.created_at))
    ).all()

    return [
        {"date": str(r[0]), "message_count": r[1]}
        for r in rows
    ]
