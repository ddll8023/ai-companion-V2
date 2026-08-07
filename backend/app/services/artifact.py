from __future__ import annotations
from sqlalchemy.orm import Session
from app.core.database import commit_or_rollback
from app.models.chat import Message
from app.models.conversation import AiArtifact
from app.models.memory import MemorySource
from app.schemas.artifact import AiArtifactCreate, AiArtifactResponse
from app.schemas.memory import MemoryCreate
from app.services import memory as memory_service
from app.services.audit import record_audit
from app.utils.exception import ServiceException
from app.schemas.common import ErrorCode

def save_artifact(db: Session, data: AiArtifactCreate) -> AiArtifactResponse:
    existing = db.query(AiArtifact).filter(AiArtifact.assistant_message_id == data.assistant_message_id).first()
    if existing:
        return AiArtifactResponse.model_validate(existing)
    message = db.get(Message, data.assistant_message_id)
    if not message or message.role != "assistant" or message.session_id != data.session_id or message.status != "completed":
        raise ServiceException(ErrorCode.PARAM_ERROR, "只能收藏已完成的本会话助手回复")
    artifact = AiArtifact(session_id=data.session_id, assistant_message_id=message.id, title=data.title or message.content[:40] or "AI 内容", content=message.content)
    db.add(artifact)
    commit_or_rollback(db)
    record_audit(db, "ai_artifact.save", "ai_artifact", artifact.id, summary="收藏 AI 内容")
    return AiArtifactResponse.model_validate(artifact)

def adopt_as_memory(db: Session, artifact_id: int):
    artifact = _get(db, artifact_id)
    artifact.status = "adopted"
    existing_source = db.query(MemorySource).filter(
        MemorySource.source_type == "user_adopted_ai",
        MemorySource.source_id == artifact.id,
    ).first()
    if existing_source is not None:
        return memory_service.get_memory(db, existing_source.memory_id).memory
    memory = memory_service.create_candidate_memory(db, MemoryCreate(
        content=artifact.content, type="fact", importance=5, session_id=artifact.session_id,
        source_type="user_adopted_ai", source_ids=[artifact.id],
    ))
    commit_or_rollback(db)
    record_audit(db, "ai_artifact.remember", "ai_artifact", artifact.id, summary="用户采纳 AI 内容为候选记忆")
    return memory

def _get(db: Session, artifact_id: int) -> AiArtifact:
    artifact = db.get(AiArtifact, artifact_id)
    if not artifact:
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, "AI 内容不存在")
    return artifact
