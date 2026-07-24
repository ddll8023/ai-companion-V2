"""系统状态和审计查询 API 路由。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.app_state import app_state
from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.response import error, success
from app.services import system as services_system
from app.utils.exception import ServiceException
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

router = APIRouter(prefix="/api/v1/system", tags=["系统状态"])


@router.get("/status", response_model=ApiResponse)
def get_system_status(
    db: Annotated[Session, Depends(get_db)],
):
    """获取聚合系统状态。"""
    try:
        result = services_system.get_system_status(
            db=db,
            db_ready=app_state.db_ready,
            db_migration_completed=app_state.db_migration_completed,
        )
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)
    except Exception as exc:
        logger.error(f"获取系统状态失败: {exc}", exc_info=True)
        return error(message="获取系统状态失败")
