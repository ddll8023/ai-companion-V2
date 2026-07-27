"""人物理解 API。"""

from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import api_key_cache
from app.core.database import get_db
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.persona import *
from app.schemas.response import error, success
from app.services import persona as services_persona
from app.services import task as services_task
from app.schemas.task import TaskCreate
from app.utils.exception import ServiceException

router = APIRouter(prefix="/api/v1/persona", tags=["人物理解"])


@router.post("/observations/list", response_model=ApiResponse[PaginatedResponse[ObservationResponse]])
def list_observations(body: ObservationListQuery, db: Annotated[Session, Depends(get_db)]):
    """查询观察列表。"""
    try:
        return success(data=services_persona.list_observations(db, body))
    except ServiceException as exc:
        return error(code=exc.code, message=exc.message)


@router.delete("/observations/{observation_id}", response_model=ApiResponse[None])
def delete_observation(observation_id: int, db: Annotated[Session, Depends(get_db)]):
    """删除观察。"""
    try:
        services_persona.delete_observation(db, observation_id)
        return success(message="观察已删除")
    except ServiceException as exc:
        return error(code=exc.code, message=exc.message)


@router.post("/insights/list", response_model=ApiResponse[PaginatedResponse[InsightResponse]])
def list_insights(body: InsightListQuery, db: Annotated[Session, Depends(get_db)]):
    """查询洞见列表。"""
    try:
        return success(data=services_persona.list_insights(db, body))
    except ServiceException as exc:
        return error(code=exc.code, message=exc.message)


@router.post("/insights/{insight_id}/correct", response_model=ApiResponse[InsightResponse])
def correct_insight(insight_id: int, body: InsightCorrection, db: Annotated[Session, Depends(get_db)]):
    """纠正洞见。"""
    try:
        return success(data=services_persona.correct_insight(db, insight_id, body))
    except ServiceException as exc:
        return error(code=exc.code, message=exc.message)


@router.post("/insights/{insight_id}/reject", response_model=ApiResponse[InsightResponse])
def reject_insight(insight_id: int, db: Annotated[Session, Depends(get_db)]):
    """否定洞见。"""
    try:
        return success(data=services_persona.reject_insight(db, insight_id))
    except ServiceException as exc:
        return error(code=exc.code, message=exc.message)


@router.get("/document", response_model=ApiResponse[PersonaDocumentResponse | None])
def get_document(db: Annotated[Session, Depends(get_db)]):
    """获取当前人物侧写。"""
    return success(data=services_persona.get_active_document(db))


@router.post("/document/edit", response_model=ApiResponse[PersonaDocumentResponse])
def edit_document(body: PersonaDocumentEdit, db: Annotated[Session, Depends(get_db)]):
    """编辑人物侧写。"""
    try:
        return success(data=services_persona.edit_document(db, body))
    except ServiceException as exc:
        return error(code=exc.code, message=exc.message)


@router.post("/reflect", response_model=ApiResponse[dict])
def reflect(db: Annotated[Session, Depends(get_db)]):
    """手动触发人物反思任务。"""
    if not api_key_cache.peek_global():
        return error(message="API Key 不可用（请先进行一次对话）")
    task = services_task.create_task(db, TaskCreate(task_type="persona.reflect", payload="{}", dedup_key="persona.reflect:manual", priority=1))
    return success(data={"task_id": task.id})
