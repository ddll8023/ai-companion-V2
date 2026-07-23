"""画像服务。

职责：
- 管理画像 CRUD
- 处理用户审查操作（确认、纠正、否定、删除）
- 管理来源证据和修订历史
- 画像去重校验
"""

from __future__ import annotations

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
