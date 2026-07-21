"""后台任务 API 路由。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import ApiResponse, ErrorCode, PaginatedResponse
from app.schemas.task import TaskCreate, TaskQueryRequest, TaskResponse
from app.schemas.response import error, success
from app.services import task as services_task
from app.utils.exception import ServiceException

router = APIRouter(prefix="/api/v1/tasks", tags=["后台任务"])


# ── 以下特定路径必须定义在参数化路径之前 ──────────────────────────────


@router.get("/stats/pending-count", response_model=ApiResponse[dict])
def get_pending_count(
    db: Annotated[Session, Depends(get_db)],
):
    """获取待处理任务的积压数量。"""
    try:
        count = services_task.get_pending_count(db)
        return success(data={"pending_count": count})
    except ServiceException as e:
        return error(code=e.code, message=e.message)


# ── 任务 CRUD ──────────────────────────────────────────────────────────


@router.post("", response_model=ApiResponse[TaskResponse])
def create_task(
    body: TaskCreate,
    db: Annotated[Session, Depends(get_db)],
):
    """创建后台任务（支持去重）。"""
    try:
        result = services_task.create_task(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/list", response_model=ApiResponse[PaginatedResponse[TaskResponse]])
def list_tasks(
    body: TaskQueryRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """查询任务列表（支持按类型和状态过滤）。"""
    try:
        result = services_task.query_tasks(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.get("/{task_id}", response_model=ApiResponse[TaskResponse])
def get_task(
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """获取单个任务详情。"""
    try:
        result = services_task.get_task(db, task_id)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/{task_id}/cancel", response_model=ApiResponse[TaskResponse])
def cancel_task(
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """取消任务（仅可取消 pending 或 retrying 状态的任务）。"""
    try:
        result = services_task.cancel_task(db, task_id)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)
