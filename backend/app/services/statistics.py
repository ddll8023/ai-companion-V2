"""行为统计服务。

职责：
- 活跃时段分布（按小时）
- 应用使用分布（Top 10）
- 对话活跃度（按日期）

说明：
行为统计从旧版画像模块（已被删除）中独立出来，不依赖人物理解体系。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.chat import Message
from app.schemas.statistics import BehaviorStatsResponse
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)


def get_behavior_stats(db: Session, days: int) -> BehaviorStatsResponse:
    """获取行为统计数据。

    聚合查询 activities 和 messages 表，不支持缓存。
    """
    since = datetime.now() - timedelta(days=days)

    active_hours = _query_active_hours(db, since)
    app_usage = _query_app_usage(db, since)
    chat_activity = _query_chat_activity(db, since)

    return BehaviorStatsResponse(
        active_hours=active_hours,
        app_usage=app_usage,
        chat_activity=chat_activity,
    )


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
    """查询用户对话活跃度（按日期聚合用户主动发送次数）。"""
    rows = db.execute(
        select(
            func.date(Message.created_at).label("date"),
            func.count().label("count"),
        )
        .where(
            Message.created_at >= since,
            Message.status == "completed",
            Message.role == "user",
        )
        .group_by(func.date(Message.created_at))
        .order_by(func.date(Message.created_at))
    ).all()

    return [
        {"date": str(r[0]), "message_count": r[1]}
        for r in rows
    ]
