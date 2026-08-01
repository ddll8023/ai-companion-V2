"""对话服务。

职责：
- 会话 CRUD
- 消息管理
- 流式对话编排

安全约束：
- API Key 仅在请求时传入，不持久化
- 日志中不记录完整消息正文
"""

from __future__ import annotations

import json
from typing import Any, Generator

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core import api_key_cache
from app.core.database import commit_or_rollback, get_background_db_session
from app.models.chat import ChatSession, Message
from app.models.conversation import ConversationTurn
from app.models.memory import MemoryReference
from app.prompts.chat import (
    DEFAULT_CHAT_SYSTEM_PROMPT,
    TITLE_GENERATION_SYSTEM_PROMPT,
    build_chat_system_prompt,
)
from app.schemas.chat import MessageResponse, SessionCreate, SessionResponse, SessionUpdate
from app.schemas.reference import MemoryReferenceResponse
from app.schemas.common import ErrorCode
from app.schemas.task import TaskCreate
from app.services import model_provider
from app.services import persona as services_persona
from app.services import retrieval
from app.services import task as services_task
from app.services.audit import record_audit
from app.utils.exception import ServiceException
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

DEFAULT_TITLE = "新对话"
# ── 会话 CRUD ──────────────────────────────────────────────────────────────


def create_session(db: Session, data: SessionCreate | None = None) -> SessionResponse:
    """创建新会话。"""
    session = ChatSession(title=data.title if data and data.title else DEFAULT_TITLE)
    db.add(session)
    commit_or_rollback(db)
    logger.info(f"创建会话: id={session.id}")
    return SessionResponse.model_validate(session)


def list_sessions(db: Session) -> list[SessionResponse]:
    """获取全部会话列表（按更新时间倒序，附带提取状态）。"""
    items = db.scalars(
        select(ChatSession).order_by(desc(ChatSession.updated_at))
    ).all()
    return [_build_session_response(db, item) for item in items]


def get_session(db: Session, session_id: int) -> SessionResponse:
    """获取单个会话详情（附带提取状态）。"""
    session = _get_session_or_error(db, session_id)
    return _build_session_response(db, session)


def update_session(db: Session, session_id: int, data: SessionUpdate) -> SessionResponse:
    """更新会话（重命名等）。"""
    session = _get_session_or_error(db, session_id)
    session.title = data.title
    commit_or_rollback(db)
    logger.info(f"更新会话: id={session_id}")
    return SessionResponse.model_validate(session)


def delete_session(db: Session, session_id: int) -> None:
    """删除会话及其关联的消息（CASCADE）。"""
    session = _get_session_or_error(db, session_id)
    db.delete(session)
    commit_or_rollback(db)
    logger.info(f"删除会话: id={session_id}")

    record_audit(
        db=db,
        action="chat.session.delete",
        target_type="session",
        target_id=session_id,
        summary=f"删除会话: {session.title}",
    )


# ── 消息管理 ────────────────────────────────────────────────────────────────


def get_messages(db: Session, session_id: int) -> list[MessageResponse]:
    """获取指定会话的全部消息（按创建时间正序）。"""
    # 先验证会话存在
    _get_session_or_error(db, session_id)

    items = db.scalars(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.id)
    ).all()

    # 为每条助手消息加载记忆引用
    result = []
    for item in items:
        resp = MessageResponse.model_validate(item)
        if item.role == "assistant":
            refs = db.scalars(
                select(MemoryReference)
                .where(MemoryReference.message_id == item.id)
                .order_by(MemoryReference.rank)
            ).all()
            resp.memory_references = [MemoryReferenceResponse.model_validate(r) for r in refs]
        result.append(resp)
    return result


def _save_user_message(db: Session, session_id: int, content: str) -> Message:
    """保存用户消息。"""
    msg = Message(
        session_id=session_id,
        role="user",
        content=content,
        status="completed",
    )
    db.add(msg)
    commit_or_rollback(db)
    return msg


def _create_assistant_placeholder(
    db: Session,
    session_id: int,
    model_name: str | None,
    model_provider: str | None = None,
) -> Message:
    """创建助手占位消息（初始状态为 generating）。"""
    msg = Message(
        session_id=session_id,
        role="assistant",
        content="",
        status="generating",
        model_name=model_name,
        model_provider=model_provider,
    )
    db.add(msg)
    commit_or_rollback(db)
    return msg


def _complete_assistant_message(
    db: Session,
    message_id: int,
    content: str,
    reasoning_content: str | None = None,
) -> None:
    """助手消息完成，保存完整内容并更新状态。"""
    msg = db.get(Message, message_id)
    if msg is None:
        logger.warning(f"助手消息不存在: id={message_id}")
        return
    msg.content = content
    msg.reasoning_content = reasoning_content
    msg.status = "completed"
    _set_turn_status(db, message_id, "completed")
    commit_or_rollback(db)


def _abort_assistant_message(
    db: Session,
    message_id: int,
    content: str,
    reasoning_content: str | None = None,
) -> None:
    """中止助手消息，保存已生成内容并标记为已中止。"""
    msg = db.get(Message, message_id)
    if msg is None:
        return
    msg.content = content
    msg.reasoning_content = reasoning_content
    msg.status = "aborted"
    _set_turn_status(db, message_id, "aborted")
    commit_or_rollback(db)


def _fail_assistant_message(db: Session, message_id: int, error_message: str) -> None:
    """助手消息失败，标记状态。"""
    msg = db.get(Message, message_id)
    if msg is None:
        return
    msg.status = "failed"
    msg.error_message = error_message[:256]
    _set_turn_status(db, message_id, "failed")
    commit_or_rollback(db)


def _set_turn_status(db: Session, assistant_message_id: int, status: str) -> None:
    turn = db.scalar(select(ConversationTurn).where(
        ConversationTurn.assistant_message_id == assistant_message_id,
    ).limit(1))
    if turn is not None:
        turn.status = status


# ── 流式对话编排 ────────────────────────────────────────────────────────────


def initialize_chat_stream(
    db: Session,
    session_id: int,
    user_content: str,
    api_key: str | None,
    regenerate_message_id: int | None = None,
) -> dict[str, Any]:
    """流式对话初始化（在注入的 db session 中快速执行，不 hold session）。

    验证会话、检查并发、保存用户消息、获取模型配置、创建占位消息。

    Args:
        db: 数据库会话（由 Depends 注入，本函数返回后释放）
        session_id: 会话 ID
        user_content: 用户消息内容（重新生成模式下可传空，将复用目标消息对应的用户消息）
        api_key: API Key
        regenerate_message_id: 重新生成模式：指定要替换的助手消息 ID。
            删除该消息并从其上一条用户消息重新生成，不新增用户消息。

    Returns:
        成功时返回包含生成所需全部信息的 dict；错误时返回 {"error": "..."}
    """
    # 验证会话存在
    try:
        _get_session_or_error(db, session_id)
    except ServiceException as e:
        return {"error": e.message}

    # 检查并发：同一会话同一时间只允许一个生成任务
    existing_generating = db.scalar(
        select(Message).where(
            Message.session_id == session_id,
            Message.status == "generating",
        ).limit(1)
    )
    if existing_generating is not None:
        return {"error": "当前会话已有正在生成的回复，请等待完成或中止后重试"}

    # 重新生成模式：校验目标消息并删除，复用其对应的用户消息
    if regenerate_message_id is not None:
        target_msg = db.get(Message, regenerate_message_id)
        if (
            target_msg is None
            or target_msg.session_id != session_id
            or target_msg.role != "assistant"
        ):
            return {"error": "目标回复不存在"}
        user_msg = db.scalar(
            select(Message).where(
                Message.session_id == session_id,
                Message.role == "user",
                Message.id < target_msg.id,
            ).order_by(Message.id.desc()).limit(1)
        )
        if user_msg is None:
            return {"error": "未找到对应的用户消息，无法重新生成"}
        # 删除旧回复（memory_references 级联删除，conversation_turns 置空）
        db.delete(target_msg)
        db.flush()
        user_content = user_msg.content
    else:
        # 保存用户消息
        user_msg = _save_user_message(db, session_id, user_content)

    # 获取激活的模型配置
    try:
        active_config = model_provider.get_active_config(db)
        if active_config is None:
            return {"error": "未配置模型，请在设置中完成模型配置"}
    except ServiceException as e:
        return {"error": e.message}

    # 获取 API Key
    resolved_key = api_key
    if not resolved_key:
        return {"error": "缺少 API Key"}

    # 创建助手占位消息
    assistant_msg = _create_assistant_placeholder(db, session_id, active_config.model_name, active_config.provider)
    db.add(ConversationTurn(
        session_id=session_id,
        user_message_id=user_msg.id,
        assistant_message_id=assistant_msg.id,
        status="generating",
    ))
    commit_or_rollback(db)

    # 获取历史消息并构造模型调用消息列表（过滤掉占位消息）
    history_messages = get_messages(db, session_id)
    model_messages = [
        {"role": msg.role, "content": msg.content}
        for msg in history_messages
        if msg.status != "generating"
    ]

    # 检索相关长期记忆（个性化上下文）
    memory_context = retrieval.retrieve_memories(
        db=db,
        query_text=user_content,
    )

    # 构造系统提示词（人物理解段落在前，检索记忆段落在后）
    base_system_prompt = build_chat_system_prompt(active_config.enable_reasoning)
    persona_context = services_persona.build_persona_context(db)
    if persona_context:
        base_system_prompt = f"{base_system_prompt}\n\n{persona_context}"
    if memory_context and memory_context.enabled:
        system_prompt = retrieval.build_system_prompt_with_context(
            base_prompt=base_system_prompt,
            memory_context=memory_context,
        )
    else:
        system_prompt = base_system_prompt

    # 尝试自动更新会话标题（首次对话时）
    _try_auto_title(db, session_id, user_content, history_messages, resolved_key)

    return {
        "user_message_id": user_msg.id,
        "assistant_message_id": assistant_msg.id,
        "active_config": {
            "provider": active_config.provider,
            "model_name": active_config.model_name,
            "api_base": active_config.api_base,
            "enable_reasoning": active_config.enable_reasoning,
        },
        "model_messages": model_messages,
        "api_key": resolved_key,
        "system_prompt": system_prompt,  # 个性化系统提示词
        "memory_context": memory_context,  # 检索到的记忆（用于引用记录）
    }


def run_chat_stream(
    session_id: int,
    assistant_msg_id: int,
    active_config: dict[str, Any],
    model_messages: list[dict[str, str]],
    api_key: str,
    system_prompt: str | None = None,
    memory_context=None,
) -> Generator[dict[str, Any], None, None]:
    """流式对话生成（使用独立 db session，不阻塞连接池）。

    Args:
        session_id: 会话 ID
        assistant_msg_id: 助手占位消息 ID
        active_config: 模型配置信息 {provider, model_name, api_base}
        model_messages: 历史消息列表
        api_key: API Key
        system_prompt: 系统提示词（含个性化上下文，None 时使用默认值）
        memory_context: 检索到的记忆上下文（用于引用记录）

    Yields:
        流式事件字典:
        - {"type": "token", "content": "..."} — 内容 token
        - {"type": "reasoning_token", "content": "..."} — 推理 token
        - {"type": "done", "message_id": 123} — 完成
        - {"type": "error", "message": "..."} — 错误
    """
    collected_content = ""
    collected_reasoning = ""

    # 将 API Key 写入全局内存缓存（供会话提取等后台任务使用），不持久化到 SQLite
    if api_key:
        api_key_cache.store_global(api_key)

    try:
        for token_type, token in model_provider.chat_stream(
            provider=active_config["provider"],
            model_name=active_config["model_name"],
            api_key=api_key,
            api_base=active_config.get("api_base"),
            messages=model_messages,
            system_prompt=system_prompt or DEFAULT_CHAT_SYSTEM_PROMPT,
            include_reasoning=active_config.get("enable_reasoning", False),
        ):
            if token_type == "reasoning":
                collected_reasoning += token
                yield {"type": "reasoning_token", "content": token}
            else:
                collected_content += token
                yield {"type": "token", "content": token}

        # 完成：使用独立 session 持久化
        with get_background_db_session() as db:
            # 第1步：保存完整回复（关键路径，优先提交）
            _complete_assistant_message(
                db, assistant_msg_id, collected_content,
                reasoning_content=collected_reasoning or None,
            )

        with get_background_db_session() as db:
            # 第2步：保存记忆引用记录
            if memory_context and memory_context.enabled:
                try:
                    from app.services.memory import save_memory_references
                    save_memory_references(
                        db=db,
                        message_id=assistant_msg_id,
                        memory_context=memory_context,
                    )
                except Exception as exc:
                    logger.warning(f"保存记忆引用失败（不影响对话）: {exc}")
        yield {"type": "done", "message_id": assistant_msg_id}

    except GeneratorExit:
        # 客户端断开连接 → 中止生成
        logger.warning(f"客户端断开连接，生成中止: session_id={session_id}")
        with get_background_db_session() as db:
            if collected_content:
                _abort_assistant_message(
                    db, assistant_msg_id, collected_content,
                    reasoning_content=collected_reasoning or None,
                )
            else:
                _fail_assistant_message(db, assistant_msg_id, "用户中止")
        raise

    except ServiceException as e:
        with get_background_db_session() as db:
            if collected_content:
                _abort_assistant_message(
                    db, assistant_msg_id, collected_content,
                    reasoning_content=collected_reasoning or None,
                )
            else:
                _fail_assistant_message(db, assistant_msg_id, e.message)
        yield {"type": "error", "message": e.message}
    except Exception as e:
        logger.error(f"对话流式调用异常: {e}", exc_info=True)
        with get_background_db_session() as db:
            if collected_content:
                _abort_assistant_message(
                    db, assistant_msg_id, collected_content,
                    reasoning_content=collected_reasoning or None,
                )
            else:
                _fail_assistant_message(db, assistant_msg_id, str(e))
        yield {"type": "error", "message": f"对话生成失败: {e!s}"}


def _try_auto_title(
    db: Session,
    session_id: int,
    user_content: str,
    history: list[MessageResponse],
    api_key: str | None = None,
) -> None:
    """首次对话时自动设置会话标题。

    优先调用 LLM 生成摘要标题（需 API Key 和激活配置），
    失败时兜底使用用户消息前 30 字。
    """
    session = _get_session_or_error(db, session_id)

    # 只有标题为默认值时且这是第一条用户消息时才设置
    if session.title != DEFAULT_TITLE:
        return
    user_msgs = [m for m in history if m.role == "user"]
    if len(user_msgs) > 1:
        return

    # 优先尝试 LLM 摘要标题（需要 API Key + 激活配置）
    if api_key:
        try:
            active_config = model_provider.get_active_config(db)
            if active_config:
                summary = model_provider.chat_sync(
                    provider=active_config.provider,
                    model_name=active_config.model_name,
                    api_key=api_key,
                    api_base=active_config.api_base,
                    system_prompt=TITLE_GENERATION_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_content[:500]}],
                    timeout=model_provider.SYNC_TIMEOUT_SHORT,
                )
                if summary:
                    summary = summary.strip().strip('"').strip("'")
                    if len(summary) > 128:
                        summary = summary[:125] + "…"
                    session.title = summary
                    commit_or_rollback(db)
                    logger.info(f"AI 摘要标题: id={session_id} title='{summary[:30]}…'")
                    return
        except Exception:
            logger.debug("AI 摘要标题失败，使用截断标题兜底")

    # 兜底：使用用户消息的前 30 个字符作为标题
    new_title = user_content[:30]
    if len(user_content) > 30:
        new_title += "…"
    session.title = new_title
    commit_or_rollback(db)


# ── 会话级提取 ──────────────────────────────────────────────────────────────


def request_session_extract(db: Session, session_id: int, api_key: str | None) -> dict:
    """校验并创建会话级记忆与人物理解提取后台任务。"""
    session = _get_session_or_error(db, session_id)

    # API Key：优先请求传入，回退到全局缓存（Electron 模式对话后可用）
    resolved_key = api_key or api_key_cache.peek_global()
    if not resolved_key:
        raise ServiceException(
            ErrorCode.PARAM_ERROR,
            "缺少 API Key（请先进行一次对话或在请求中提供）",
        )

    # 生成中的会话不允许提取
    generating = db.scalar(
        select(Message).where(
            Message.session_id == session_id,
            Message.status == "generating",
        ).limit(1)
    )
    if generating is not None:
        raise ServiceException(
            ErrorCode.PARAM_ERROR, "会话正在生成回复，请等待完成后再提取",
        )

    # 同一会话同时只允许一个提取任务
    dedup_key = f"session.extract:session:{session_id}"
    active = services_task.find_active_task(db, "session.extract", dedup_key)
    if active is not None:
        raise ServiceException(ErrorCode.PARAM_ERROR, "该会话已有正在进行的提取任务")

    # 计算提取区间：水位线之后的 completed 消息
    watermark = session.last_extracted_message_id or 0
    range_row = db.execute(
        select(func.min(Message.id), func.max(Message.id)).where(
            Message.session_id == session_id,
            Message.id > watermark,
            Message.status == "completed",
            Message.role.in_(["user", "assistant"]),
        )
    ).first()
    from_message_id, to_message_id = range_row if range_row else (None, None)

    has_user_message = db.scalar(
        select(Message).where(
            Message.session_id == session_id,
            Message.id > watermark,
            Message.role == "user",
            Message.status == "completed",
        ).limit(1)
    )
    if from_message_id is None or has_user_message is None:
        raise ServiceException(ErrorCode.PARAM_ERROR, "没有可提取的新对话内容")

    # API Key 写入全局缓存供后台任务使用
    api_key_cache.store_global(resolved_key)

    task = services_task.create_task(db, TaskCreate(
        task_type="session.extract",
        payload=json.dumps({
            "session_id": session_id,
            "from_message_id": from_message_id,
            "to_message_id": to_message_id,
        }),
        dedup_key=dedup_key,
        priority=1,
    ))

    record_audit(
        db=db,
        action="chat.session.extract",
        target_type="session",
        target_id=session_id,
        summary=f"触发会话提取: 消息区间 [{from_message_id}, {to_message_id}]",
    )
    logger.info(f"创建会话提取任务: session_id={session_id}, task_id={task.id}")

    return {
        "task_id": task.id,
        "from_message_id": from_message_id,
        "to_message_id": to_message_id,
    }


# ── 内部方法 ────────────────────────────────────────────────────────────────


def _build_session_response(db: Session, session: ChatSession) -> SessionResponse:
    """构建会话响应，附带可提取消息数与提取任务状态。"""
    resp = SessionResponse.model_validate(session)

    watermark = session.last_extracted_message_id or 0
    resp.extractable_message_count = db.scalar(
        select(func.count()).select_from(
            select(Message).where(
                Message.session_id == session.id,
                Message.id > watermark,
                Message.role == "user",
                Message.status == "completed",
            ).subquery()
        )
    ) or 0

    resp.is_extracting = services_task.find_active_task(
        db, "session.extract", f"session.extract:session:{session.id}",
    ) is not None
    return resp


def _get_session_or_error(db: Session, session_id: int) -> ChatSession:
    """获取会话，不存在时抛出异常。"""
    session = db.get(ChatSession, session_id)
    if session is None:
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, f"会话不存在: {session_id}")
    return session
