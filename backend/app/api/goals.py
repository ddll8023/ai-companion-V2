"""目标和任务 API 路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import ApiResponse, ErrorCode, PaginatedResponse
from app.schemas.goal import (
    GoalCreate,
    GoalDeleteRequest,
    GoalDetailResponse,
    GoalListQuery,
    GoalResponse,
    GoalUpdate,
    TaskCreate,
    TaskListQuery,
    TaskResponse,
    TaskSuggestionCreate,
    TaskUpdate,
    TaskWithGoalResponse,
)
from app.schemas.response import error, success
from app.services import goal as services_goal
from app.utils.exception import ServiceException

router = APIRouter(prefix="/api/v1/goals", tags=["目标与任务"])


# ── 目标 CRUD ─────────────────────────────────────────────────────────────────


@router.post("", response_model=ApiResponse[GoalResponse])
def create_goal(
    body: GoalCreate,
    db: Annotated[Session, Depends(get_db)],
):
    """创建目标。"""
    try:
        result = services_goal.create_goal(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/list", response_model=ApiResponse[PaginatedResponse[GoalResponse]])
def list_goals(
    body: GoalListQuery,
    db: Annotated[Session, Depends(get_db)],
):
    """查询目标列表（支持按状态、关键词筛选）。"""
    try:
        result = services_goal.query_goals(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.get("/{goal_id}", response_model=ApiResponse[GoalDetailResponse])
def get_goal(
    goal_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """获取目标详情（含关联任务）。"""
    try:
        result = services_goal.get_goal(db, goal_id)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.put("/{goal_id}", response_model=ApiResponse[GoalResponse])
def update_goal(
    goal_id: int,
    body: GoalUpdate,
    db: Annotated[Session, Depends(get_db)],
):
    """更新目标。"""
    try:
        result = services_goal.update_goal(db, goal_id, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.delete("/{goal_id}", response_model=ApiResponse[dict])
def delete_goal(
    goal_id: int,
    task_action: str = Query("unlink", description="关联任务处理方式: unlink=解除关联, cascade=级联删除"),
    db: Annotated[Session, Depends(get_db)],
):
    """删除目标。"""
    try:
        result = services_goal.delete_goal(db, goal_id, GoalDeleteRequest(task_action=task_action))
        return success(data=result, message="目标已删除")
    except ServiceException as e:
        return error(code=e.code, message=e.message)


# ── 任务 CRUD ─────────────────────────────────────────────────────────────────


@router.post("/tasks", response_model=ApiResponse[TaskResponse])
def create_task(
    body: TaskCreate,
    db: Annotated[Session, Depends(get_db)],
):
    """创建任务。"""
    try:
        result = services_goal.create_task(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/tasks/list", response_model=ApiResponse[PaginatedResponse[TaskWithGoalResponse]])
def list_tasks(
    body: TaskListQuery,
    db: Annotated[Session, Depends(get_db)],
):
    """查询任务列表（支持按目标、状态、建议状态筛选）。"""
    try:
        result = services_goal.query_tasks(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.get("/tasks/{task_id}", response_model=ApiResponse[TaskWithGoalResponse])
def get_task(
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """获取任务详情。"""
    try:
        result = services_goal.get_task(db, task_id)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.put("/tasks/{task_id}", response_model=ApiResponse[TaskResponse])
def update_task(
    task_id: int,
    body: TaskUpdate,
    db: Annotated[Session, Depends(get_db)],
):
    """更新任务。"""
    try:
        result = services_goal.update_task(db, task_id, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.delete("/tasks/{task_id}", response_model=ApiResponse[dict])
def delete_task(
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """删除任务。"""
    try:
        result = services_goal.delete_task(db, task_id)
        return success(data=result, message="任务已删除")
    except ServiceException as e:
        return error(code=e.code, message=e.message)


# ── AI 建议管理 ──────────────────────────────────────────────────────────────


@router.post("/suggestions", response_model=ApiResponse[TaskResponse])
def create_suggestion(
    body: TaskSuggestionCreate,
    db: Annotated[Session, Depends(get_db)],
):
    """创建 AI 建议任务。"""
    try:
        result = services_goal.create_suggestion(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/tasks/{task_id}/accept-suggestion", response_model=ApiResponse[TaskResponse])
def accept_suggestion(
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """接受 AI 建议任务。"""
    try:
        result = services_goal.accept_suggestion(db, task_id)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/tasks/{task_id}/reject-suggestion", response_model=ApiResponse[TaskResponse])
def reject_suggestion(
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """拒绝 AI 建议任务。"""
    try:
        result = services_goal.reject_suggestion(db, task_id)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)
