"""系统状态和审计查询 API 路由。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.response import error, success
from app.services import system as services_system
from app.utils.exception import ServiceException
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

router = APIRouter(prefix="/api/v1/system", tags=["系统状态"])

# ── 全局状态标记（由 main.py 导入设置） ─────────────────────────────
_db_ready: bool = False
_db_migration_completed: bool = False


def set_db_ready(val: bool):
    """设置数据库就绪状态。"""
    global _db_ready
    _db_ready = val


def set_db_migration_completed(val: bool):
    """设置数据库迁移完成状态。"""
    global _db_migration_completed
    _db_migration_completed = val


@router.get("/status", response_model=ApiResponse)
def get_system_status(
    db: Annotated[Session, Depends(get_db)],
):
    """获取聚合系统状态。"""
    try:
        result = services_system.get_system_status(
            db=db,
            db_ready=_db_ready,
            db_migration_completed=_db_migration_completed,
        )
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)
    except Exception as exc:
        logger.error(f"获取系统状态失败: {exc}", exc_info=True)
        return error(message="获取系统状态失败")
