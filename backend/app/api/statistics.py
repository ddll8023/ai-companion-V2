"""行为统计 API 路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.statistics import BehaviorStatsQuery, BehaviorStatsResponse
from app.schemas.response import error, success
from app.services import statistics as services_statistics
from app.utils.exception import ServiceException

router = APIRouter(prefix="/api/v1/statistics", tags=["行为统计"])


@router.post("/behavior", response_model=ApiResponse[BehaviorStatsResponse])
def behavior_stats(
    body: BehaviorStatsQuery,
    db: Annotated[Session, Depends(get_db)],
):
    """获取行为统计数据。

    聚合查询近 N 天的活动记录和对话记录，返回：
    - 活跃时段分布（按小时）
    - 应用使用分布（Top 10）
    - 对话活跃度（按日期）
    """
    try:
        result = services_statistics.get_behavior_stats(db, body.days)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)
