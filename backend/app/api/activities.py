"""活动记录和隐私规则 API 路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.activity import (
    ActivityEvent,
    ActivityListQuery,
    ActivityResponse,
    ActivityStats,
    BatchActivityEvent,
    PrivacyEvaluateRequest,
    PrivacyEvaluateResult,
    PrivacyRuleCreate,
    PrivacyRuleListQuery,
    PrivacyRuleResponse,
    PrivacyRuleUpdate,
)
from app.schemas.common import ApiResponse, ErrorCode, PaginatedResponse
from app.schemas.response import error, success
from app.services import activity as services_activity
from app.utils.exception import ServiceException

router = APIRouter(prefix="/api/v1/activities", tags=["活动"])

# ── 活动事件 ─────────────────────────────────────────────────────────────────


@router.post("/events", response_model=ApiResponse[int])
def submit_events(
    body: BatchActivityEvent,
    db: Annotated[Session, Depends(get_db)],
):
    """批量提交活动事件（Electron 采集端上报）。"""
    try:
        count = services_activity.submit_activity_events(db, body.events)
        return success(data=count, message=f"已保存 {count} 条活动记录")
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/list", response_model=ApiResponse[PaginatedResponse[ActivityResponse]])
def list_activities(
    body: ActivityListQuery,
    db: Annotated[Session, Depends(get_db)],
):
    """查询活动记录列表（支持按应用、平台、时间、关键词筛选）。"""
    try:
        result = services_activity.query_activities(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.get("/stats", response_model=ApiResponse[ActivityStats])
def get_stats(
    db: Annotated[Session, Depends(get_db)],
):
    """获取活动统计信息（总记录数、今日记录数、今日应用数）。"""
    try:
        stats = services_activity.get_activity_stats(db)
        return success(data=stats)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.get("/{activity_id}", response_model=ApiResponse[ActivityResponse])
def get_activity(
    activity_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """获取单条活动记录详情。"""
    try:
        result = services_activity.get_activity(db, activity_id)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.delete("/{activity_id}", response_model=ApiResponse[None])
def delete_activity(
    activity_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """删除单条活动记录。"""
    try:
        services_activity.delete_activity(db, activity_id)
        return success(message="活动记录已删除")
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/clear", response_model=ApiResponse[int])
def clear_activities(
    db: Annotated[Session, Depends(get_db)],
):
    """清空所有活动记录（危险操作，需要二次确认）。"""
    try:
        count = services_activity.clear_activities(db)
        return success(data=count, message=f"已清空 {count} 条活动记录")
    except ServiceException as e:
        return error(code=e.code, message=e.message)


# ── 隐私规则 ────────────────────────────────────────────────────────────────────


@router.post("/privacy/evaluate", response_model=ApiResponse[PrivacyEvaluateResult])
def evaluate_privacy(
    body: PrivacyEvaluateRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """评估给定场景是否允许采集（Electron 预检查用）。"""
    result = services_activity.evaluate_privacy(db, body)
    return success(data=result)


@router.post("/privacy-rules", response_model=ApiResponse[PrivacyRuleResponse])
def create_privacy_rule(
    body: PrivacyRuleCreate,
    db: Annotated[Session, Depends(get_db)],
):
    """创建隐私规则。"""
    try:
        result = services_activity.create_privacy_rule(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post(
    "/privacy-rules/list",
    response_model=ApiResponse[PaginatedResponse[PrivacyRuleResponse]],
)
def list_privacy_rules(
    body: PrivacyRuleListQuery,
    db: Annotated[Session, Depends(get_db)],
):
    """查询隐私规则列表。"""
    try:
        result = services_activity.query_privacy_rules(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.get("/privacy-rules/{rule_id}", response_model=ApiResponse[PrivacyRuleResponse])
def get_privacy_rule(
    rule_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """获取单条隐私规则。"""
    try:
        result = services_activity.get_privacy_rule(db, rule_id)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.put("/privacy-rules/{rule_id}", response_model=ApiResponse[PrivacyRuleResponse])
def update_privacy_rule(
    rule_id: int,
    body: PrivacyRuleUpdate,
    db: Annotated[Session, Depends(get_db)],
):
    """更新隐私规则。"""
    try:
        result = services_activity.update_privacy_rule(db, rule_id, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.delete("/privacy-rules/{rule_id}", response_model=ApiResponse[None])
def delete_privacy_rule(
    rule_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """删除隐私规则。"""
    try:
        services_activity.delete_privacy_rule(db, rule_id)
        return success(message="隐私规则已删除")
    except ServiceException as e:
        return error(code=e.code, message=e.message)
