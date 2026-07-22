"""记忆检索 API 路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.response import error, success
from app.schemas.retrieval import Fts5Status, MemoryContext
from app.services import retrieval as services_retrieval
from app.utils.exception import ServiceException

router = APIRouter(prefix="/api/v1/retrieval", tags=["检索"])


@router.get("/status", response_model=ApiResponse[Fts5Status])
def get_fts5_status(
    db: Annotated[Session, Depends(get_db)],
):
    """获取 FTS5 检索状态。

    用于前端系统状态页面展示 FTS5 索引状态。
    """
    try:
        status = services_retrieval.check_fts5_available(db)
        return success(data=status)
    except ServiceException as e:
        return error(message=e.message)
