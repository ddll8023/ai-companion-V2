from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.artifact import AiArtifactCreate, AiArtifactResponse
from app.schemas.common import ApiResponse
from app.schemas.memory import MemoryResponse
from app.schemas.response import success, error
from app.services import artifact as service
from app.utils.exception import ServiceException

router = APIRouter(prefix="/api/v1/ai-artifacts", tags=["AI 内容"])

@router.post("", response_model=ApiResponse[AiArtifactResponse])
def save(body: AiArtifactCreate, db: Annotated[Session, Depends(get_db)]):
    try: return success(data=service.save_artifact(db, body))
    except ServiceException as exc: return error(code=exc.code, message=exc.message)

@router.post("/{artifact_id}/remember", response_model=ApiResponse[MemoryResponse])
def remember(artifact_id: int, db: Annotated[Session, Depends(get_db)]):
    try: return success(data=service.adopt_as_memory(db, artifact_id))
    except ServiceException as exc: return error(code=exc.code, message=exc.message)
