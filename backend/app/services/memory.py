"""记忆服务。

职责：
- 管理记忆 CRUD
- 处理用户审查操作（确认、纠正、否定、删除）
- 管理来源证据和修订历史
- 版本控制：接触来源已被修改或删除时跳过任务
"""

from __future__ import annotations

import math

from sqlalchemy import desc, func, select, text
from sqlalchemy.orm import Session

from app.core.database import commit_or_rollback
from app.models.chat import Message
from app.models.memory import Memory, MemoryReference, MemoryRevision, MemorySource
from app.schemas.common import ErrorCode, PaginatedResponse, PaginationInfo
from app.schemas.memory import (
    MemoryCorrect,
    MemoryCreate,
    MemoryDetailResponse,
    MemoryListQuery,
    MemoryResponse,
    MemoryRevisionResponse,
    MemorySourceResponse,
)
from app.services.audit import record_audit
from app.services.embedding import embed_text, serialize_embedding
from app.utils.exception import ServiceException
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)


# ── 公共入口函数 ────────────────────────────────────────────────────────────


def create_candidate_memory(
    db: Session,
    data: MemoryCreate,
) -> MemoryResponse:
    """创建候选记忆。

    Args:
        db: 数据库会话
        data: 创建记忆所需数据

    Returns:
        创建后的记忆响应
    """
    memory = Memory(
        content=data.content,
        type=data.type,
        importance=data.importance,
        status="candidate",
        session_id=data.session_id,
        version=1,
    )
    db.add(memory)
    commit_or_rollback(db)

    # 保存来源证据
    for index, source_id in enumerate(data.source_ids):
        evidence_text = (
            data.source_evidence_texts[index]
            if index < len(data.source_evidence_texts)
            else None
        )
        content_preview = data.content[:200]
        if data.source_type == "message":
            source_message = db.get(Message, source_id)
            if source_message is not None:
                content_preview = source_message.content[:200]
        source = MemorySource(
            memory_id=memory.id,
            source_type=data.source_type,
            source_id=source_id,
            content_preview=content_preview,
            evidence_text=evidence_text,
        )
        db.add(source)

    commit_or_rollback(db)
    logger.info(f"创建候选记忆: id={memory.id}, type={data.type}")

    return MemoryResponse.model_validate(memory)


def save_session_analysis(
    db: Session,
    session_id: int,
    from_message_id: int,
    to_message_id: int,
    summary_content: str,
    memories_data: list[dict],
) -> list[Memory]:
    """原子保存会话分析结果：候选记忆与会话摘要同一事务提交（摘要作为阶段完成标志）。"""
    from app.models.conversation import SessionSummary

    saved_memories: list[Memory] = []
    for item in memories_data:
        memory = Memory(
            content=item["content"],
            type=item["type"],
            importance=item["importance"],
            status="candidate",
            session_id=session_id,
            version=1,
        )
        db.add(memory)
        db.flush()

        source_message = db.get(Message, item["source_message_id"])
        db.add(MemorySource(
            memory_id=memory.id,
            source_type="message",
            source_id=item["source_message_id"],
            content_preview=(
                source_message.content[:200]
                if source_message is not None
                else item["content"][:200]
            ),
            evidence_text=item["evidence"][:512],
        ))
        saved_memories.append(memory)

    db.add(SessionSummary(
        session_id=session_id,
        from_message_id=from_message_id,
        to_message_id=to_message_id,
        content=summary_content,
    ))
    commit_or_rollback(db)
    logger.info(
        f"会话分析结果已保存: session_id={session_id}, "
        f"memories={len(saved_memories)}, range=[{from_message_id}, {to_message_id}]",
    )
    return saved_memories


def query_memories(
    db: Session,
    query: MemoryListQuery,
) -> PaginatedResponse[MemoryResponse]:
    """查询记忆列表。

    Args:
        db: 数据库会话
        query: 查询参数（支持按状态、类型、会话、关键词过滤）

    Returns:
        分页的记忆列表
    """
    base_stmt = select(Memory)

    if query.status:
        base_stmt = base_stmt.where(Memory.status == query.status)
    if query.type:
        base_stmt = base_stmt.where(Memory.type == query.type)
    if query.session_id:
        base_stmt = base_stmt.where(Memory.session_id == query.session_id)
    if query.keyword:
        base_stmt = base_stmt.where(Memory.content.contains(query.keyword))

    total = db.scalar(select(func.count()).select_from(base_stmt.subquery()))

    items = (
        db.scalars(
            base_stmt
            .order_by(desc(Memory.importance), desc(Memory.id))
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        ).all()
    )

    return PaginatedResponse(
        lists=[MemoryResponse.model_validate(item) for item in items],
        pagination=PaginationInfo(
            page=query.page,
            page_size=query.page_size,
            total=total or 0,
            total_pages=math.ceil((total or 0) / query.page_size),
        ),
    )


def get_memory(db: Session, memory_id: int) -> MemoryDetailResponse:
    """获取单个记忆详情（含来源和修订历史）。"""
    memory = _get_memory_or_error(db, memory_id)

    sources = db.scalars(
        select(MemorySource)
        .where(MemorySource.memory_id == memory_id)
        .order_by(MemorySource.id)
    ).all()

    revisions = db.scalars(
        select(MemoryRevision)
        .where(MemoryRevision.memory_id == memory_id)
        .order_by(desc(MemoryRevision.id))
    ).all()

    return MemoryDetailResponse(
        memory=MemoryResponse.model_validate(memory),
        sources=[MemorySourceResponse.model_validate(s) for s in sources],
        revisions=[MemoryRevisionResponse.model_validate(r) for r in revisions],
    )


def confirm_memory(db: Session, memory_id: int) -> MemoryResponse:
    """确认候选记忆。

    将记忆状态更新为 confirmed，使其进入检索索引。
    """
    memory = _get_memory_or_error(db, memory_id)

    if memory.status != "candidate":
        raise ServiceException(
            ErrorCode.PARAM_ERROR,
            f"仅可确认候选状态的记忆，当前状态: {memory.status}",
        )

    memory.status = "confirmed"
    # 同步 FTS5 索引和嵌入向量（在同一事务中，确保崩溃后一致性）
    _sync_memory_to_fts(db, memory)
    _sync_memory_embedding(memory)
    commit_or_rollback(db)
    logger.info(f"确认记忆: id={memory_id}")

    record_audit(
        db=db,
        action="memory.confirm",
        target_type="memory",
        target_id=memory_id,
        summary=f"确认记忆: {memory.content[:100]}",
    )

    return MemoryResponse.model_validate(memory)


def correct_memory(db: Session, memory_id: int, data: MemoryCorrect) -> MemoryResponse:
    """纠正记忆。

    用户纠正记忆内容，旧版本保存到 revisions 表。
    """
    memory = _get_memory_or_error(db, memory_id)

    if memory.status in ("deleted",):
        raise ServiceException(
            ErrorCode.PARAM_ERROR,
            f"已删除的记忆不可纠正，当前状态: {memory.status}",
        )

    # 保存旧版本到修订历史
    revision = MemoryRevision(
        memory_id=memory_id,
        previous_content=memory.content,
        previous_type=memory.type,
        previous_importance=memory.importance,
        changed_by="user",
    )
    db.add(revision)

    # 更新为新内容
    memory.content = data.content
    memory.type = data.type
    memory.importance = data.importance
    memory.version += 1

    if memory.status != "confirmed":
        memory.status = "confirmed"

    # 同步 FTS5 索引和嵌入向量（在同一事务中，确保崩溃后一致性）
    _sync_memory_to_fts(db, memory)
    _sync_memory_embedding(memory)
    commit_or_rollback(db)
    logger.info(f"纠正记忆: id={memory_id}, version={memory.version}")

    record_audit(
        db=db,
        action="memory.correct",
        target_type="memory",
        target_id=memory_id,
        summary=f"纠正记忆 (v{memory.version})",
    )

    return MemoryResponse.model_validate(memory)


def reject_memory(db: Session, memory_id: int) -> MemoryResponse:
    """否定记忆。

    标记为 rejected 状态，保留否定标识以防止系统再次使用。
    """
    memory = _get_memory_or_error(db, memory_id)

    if memory.status != "candidate":
        raise ServiceException(
            ErrorCode.PARAM_ERROR,
            f"仅可否定候选状态的记忆，当前状态: {memory.status}",
        )

    memory.status = "rejected"
    # 从 FTS5 索引和嵌入向量中移除
    _sync_memory_to_fts(db, memory)
    _sync_memory_embedding(memory)
    commit_or_rollback(db)
    logger.info(f"否定记忆: id={memory_id}")

    record_audit(
        db=db,
        action="memory.reject",
        target_type="memory",
        target_id=memory_id,
        summary=f"否定记忆: {memory.content[:100]}",
    )

    return MemoryResponse.model_validate(memory)


def delete_memory(db: Session, memory_id: int) -> None:
    """删除记忆（领域删除）。

    清理记忆正文、来源、修订数据。
    关联的 sources 和 revisions 通过 CASCADE 自动清理。
    """
    memory = _get_memory_or_error(db, memory_id)

    # 清理嵌入向量
    memory.embedding = None

    # 先删除 FTS5 索引，后删除主表（在同一事务中，确保崩溃后一致性）
    try:
        db.execute(
            text("DELETE FROM memories_fts WHERE memory_id = :mid"),
            {"mid": memory_id},
        )
    except Exception as exc:
        logger.warning(f"FTS5 索引删除失败: memory_id={memory_id}, error={exc}")

    # 记录审计（不含完整正文）
    record_audit(
        db=db,
        action="memory.delete",
        target_type="memory",
        target_id=memory_id,
        summary=f"删除记忆 (id={memory_id})",
    )

    db.delete(memory)
    commit_or_rollback(db)
    logger.info(f"删除记忆: id={memory_id}")


# ── FTS5 索引同步 ────────────────────────────────────────────────────────────


def _sync_memory_to_fts(db: Session, memory: Memory) -> None:
    """同步单条记忆到 FTS5 索引。

    先删除再插入，保证索引与记忆状态一致。
    仅 confirmed/corrected 状态的记忆才会进入索引。

    注意：不执行 db.commit()，由调用方统一提交事务。
    调用方应在执行此函数后统一 commit_or_rollback(db)。

    Args:
        db: 数据库会话
        memory: 记忆实体
    """
    try:
        # 先删除旧索引
        db.execute(
            text("DELETE FROM memories_fts WHERE memory_id = :mid"),
            {"mid": memory.id},
        )

        # 如果是 active 状态，插入新索引
        if memory.status in ("confirmed", "corrected"):
            db.execute(
                text(
                    "INSERT INTO memories_fts (content, memory_id, type) "
                    "VALUES (:content, :mid, :type)"
                ),
                {
                    "content": memory.content,
                    "mid": memory.id,
                    "type": memory.type,
                },
            )
    except Exception as exc:
        logger.warning(f"FTS5 索引同步失败（不影响主操作）: memory_id={memory.id}, error={exc}")


def sync_memory_to_fts(db: Session, memory_id: int) -> None:
    """同步记忆到 FTS5 索引的公共入口。

    在确认、纠正、否定、删除记忆后调用。

    Args:
        db: 数据库会话
        memory_id: 记忆 ID
    """
    memory = db.get(Memory, memory_id)
    if memory is None:
        return
    _sync_memory_to_fts(db, memory)


# ── 嵌入向量同步 ──────────────────────────────────────────────────────────────


def _sync_memory_embedding(memory: Memory) -> None:
    """同步单条记忆的嵌入向量。

    仅 confirmed/corrected 状态的记忆才生成嵌入向量。
    其他状态（rejected、deleted、candidate）清除向量。

    注意：
    - 此操作不依赖数据库事务，直接修改 memory 对象的字段
    - 调用方需确保在 commit_or_rollback(db) 之前调用

    Args:
        memory: 记忆实体（需包含最新 content 和 status）
    """
    try:
        if memory.status in ("confirmed", "corrected"):
            vec = embed_text(memory.content)
            memory.embedding = serialize_embedding(vec)
        else:
            memory.embedding = None
    except Exception as exc:
        logger.warning(
            "嵌入向量同步失败（不影响主操作）: memory_id=%d, error=%s",
            memory.id, exc,
        )


# ── 记忆引用跟踪 ─────────────────────────────────────────────────────────────


def save_memory_references(
    db: Session,
    message_id: int,
    memory_context,
) -> int:
    """保存助手消息引用的记忆记录。

    在对话生成完成后调用，记录实际为对话上下文提供的记忆。

    Args:
        db: 数据库会话
        message_id: 助手消息 ID
        memory_context: 检索模块返回的 MemoryContext 对象

    Returns:
        保存的引用数量
    """
    if not memory_context or not memory_context.enabled:
        return 0

    count = 0
    for i, mem in enumerate(memory_context.memories, start=1):
        ref = MemoryReference(
            message_id=message_id,
            memory_id=mem.id,
            memory_content_preview=mem.content[:200],
            relevance_score=mem.relevance_score,
            rank=i,
        )
        db.add(ref)
        count += 1

    if count > 0:
        commit_or_rollback(db)
        logger.info(f"保存记忆引用: message_id={message_id}, count={count}")

    return count


# ── 内部方法 ────────────────────────────────────────────────────────────────


def _get_memory_or_error(db: Session, memory_id: int) -> Memory:
    """获取记忆实体，不存在时抛出异常。"""
    memory = db.get(Memory, memory_id)
    if memory is None:
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, f"记忆不存在: {memory_id}")
    return memory
