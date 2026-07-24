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

import hashlib
import json
from typing import Any, Generator

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core import api_key_cache
from app.core.database import commit_or_rollback, get_background_db_session
from app.models.chat import ChatSession, Message
from app.schemas.chat import MessageResponse, SessionCreate, SessionResponse, SessionUpdate
from app.schemas.common import ErrorCode
from app.schemas.task import TaskCreate
from app.services import model_provider
from app.services import retrieval
from app.services import task as services_task
from app.services.audit import record_audit
from app.utils.exception import ServiceException
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

DEFAULT_TITLE = "新对话"
_DEFAULT_SYSTEM_PROMPT = "你是一个有用的 AI 助手。请使用中文回复用户，除非用户使用其他语言提问。"


# ── 会话 CRUD ──────────────────────────────────────────────────────────────


def create_session(db: Session, data: SessionCreate | None = None) -> SessionResponse:
    """创建新会话。"""
    session = ChatSession(title=data.title if data and data.title else DEFAULT_TITLE)
    db.add(session)
    commit_or_rollback(db)
    logger.info(f"创建会话: id={session.id}")
    return SessionResponse.model_validate(session)


def list_sessions(db: Session) -> list[SessionResponse]:
    """获取全部会话列表（按更新时间倒序）。"""
    items = db.scalars(
        select(ChatSession).order_by(desc(ChatSession.updated_at))
    ).all()
    return [SessionResponse.model_validate(item) for item in items]


def get_session(db: Session, session_id: int) -> SessionResponse:
    """获取单个会话详情。"""
    session = _get_session_or_error(db, session_id)
    return SessionResponse.model_validate(session)


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
    return [MessageResponse.model_validate(item) for item in items]


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


def _complete_assistant_message(db: Session, message_id: int, content: str) -> None:
    """助手消息完成，保存完整内容并更新状态。"""
    msg = db.get(Message, message_id)
    if msg is None:
        logger.warning(f"助手消息不存在: id={message_id}")
        return
    msg.content = content
    msg.status = "completed"
    commit_or_rollback(db)


def _abort_assistant_message(db: Session, message_id: int, content: str) -> None:
    """中止助手消息，保存已生成内容并标记为已中止。"""
    msg = db.get(Message, message_id)
    if msg is None:
        return
    msg.content = content
    msg.status = "aborted"
    commit_or_rollback(db)


def _fail_assistant_message(db: Session, message_id: int, error_message: str) -> None:
    """助手消息失败，标记状态。"""
    msg = db.get(Message, message_id)
    if msg is None:
        return
    msg.status = "failed"
    msg.error_message = error_message[:256]
    commit_or_rollback(db)


# ── 流式对话编排 ────────────────────────────────────────────────────────────


def initialize_chat_stream(
    db: Session,
    session_id: int,
    user_content: str,
    api_key: str | None,
) -> dict[str, Any]:
    """流式对话初始化（在注入的 db session 中快速执行，不 hold session）。

    验证会话、检查并发、保存用户消息、获取模型配置、创建占位消息。

    Args:
        db: 数据库会话（由 Depends 注入，本函数返回后释放）
        session_id: 会话 ID
        user_content: 用户消息内容
        api_key: API Key

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

    # 构造系统提示词（包含检索到的记忆）
    if memory_context and memory_context.enabled:
        system_prompt = retrieval.build_system_prompt_with_context(
            base_prompt=_DEFAULT_SYSTEM_PROMPT,
            memory_context=memory_context,
        )
    else:
        system_prompt = _DEFAULT_SYSTEM_PROMPT

    # 尝试自动更新会话标题（首次对话时）
    _try_auto_title(db, session_id, user_content, history_messages)

    return {
        "user_message_id": user_msg.id,
        "assistant_message_id": assistant_msg.id,
        "active_config": {
            "provider": active_config.provider,
            "model_name": active_config.model_name,
            "api_base": active_config.api_base,
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
        - {"type": "done", "message_id": 123} — 完成
        - {"type": "error", "message": "..."} — 错误
    """
    collected_content = ""

    # 将 API Key 存入进程内存缓存（供后台任务使用），不持久化到 SQLite
    api_key_cache_key = f"chat_{assistant_msg_id}"
    if api_key:
        api_key_cache.store(api_key_cache_key, api_key)
        # 同时写入全局缓存（供画像提取等后台任务使用）
        api_key_cache.store_global(api_key)

    try:
        for token in model_provider.chat_stream(
            provider=active_config["provider"],
            model_name=active_config["model_name"],
            api_key=api_key,
            api_base=active_config.get("api_base"),
            messages=model_messages,
            system_prompt=system_prompt or _DEFAULT_SYSTEM_PROMPT,
        ):
            collected_content += token
            yield {"type": "token", "content": token}

        # 完成：使用独立 session 持久化
        with get_background_db_session() as db:
            # 第1步：保存完整回复（关键路径，优先提交）
            _complete_assistant_message(db, assistant_msg_id, collected_content)

        with get_background_db_session() as db:
            # 第2步：创建候选记忆提取后台任务
            _try_create_memory_extract_task(
                db, session_id, assistant_msg_id, collected_content,
            )

            # 第3步：保存记忆引用记录（与第2步在同一 session 中）
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
                _abort_assistant_message(db, assistant_msg_id, collected_content)
            else:
                _fail_assistant_message(db, assistant_msg_id, "用户中止")
        # 清理 API Key 缓存
        api_key_cache.pop(api_key_cache_key)
        raise

    except ServiceException as e:
        with get_background_db_session() as db:
            if collected_content:
                _abort_assistant_message(db, assistant_msg_id, collected_content)
            else:
                _fail_assistant_message(db, assistant_msg_id, e.message)
        api_key_cache.pop(api_key_cache_key)
        yield {"type": "error", "message": e.message}
    except Exception as e:
        logger.error(f"对话流式调用异常: {e}", exc_info=True)
        with get_background_db_session() as db:
            if collected_content:
                _abort_assistant_message(db, assistant_msg_id, collected_content)
            else:
                _fail_assistant_message(db, assistant_msg_id, str(e))
        api_key_cache.pop(api_key_cache_key)
        yield {"type": "error", "message": f"对话生成失败: {e!s}"}


def _try_auto_title(
    db: Session,
    session_id: int,
    user_content: str,
    history: list[MessageResponse],
) -> None:
    """首次对话时自动设置会话标题（使用用户消息前 N 字）。"""
    session = _get_session_or_error(db, session_id)

    # 只有标题为默认值时且这是第一条用户消息时才设置
    if session.title == DEFAULT_TITLE and len([m for m in history if m.role == "user"]) <= 1:
        # 使用用户消息的前 30 个字符作为标题
        new_title = user_content[:30]
        if len(user_content) > 30:
            new_title += "…"
        session.title = new_title
        commit_or_rollback(db)


# ── 内部方法 ────────────────────────────────────────────────────────────────


def _try_create_memory_extract_task(
    db: Session,
    session_id: int,
    assistant_message_id: int,
    assistant_content: str,
) -> None:
    """对话完成后创建候选记忆提取后台任务。

    这是一个非阻塞操作。任务创建失败不影响对话主流程。

    Args:
        db: 数据库会话
        session_id: 会话 ID
        assistant_message_id: 助手消息 ID
        assistant_content: 助手回复内容（用于生成 source_version 版本校验）
    """
    try:
        # 查找该会话最新的一条用户消息作为来源
        user_msg = db.scalar(
            select(Message)
            .where(
                Message.session_id == session_id,
                Message.role == "user",
                Message.status == "completed",
            )
            .order_by(desc(Message.id))
            .limit(1)
        )
        if user_msg is None:
            logger.warning(f"记忆提取任务创建: 未找到用户消息, session_id={session_id}")
            return

        # 使用消息内容的 MD5 作为 source_version，用于执行时校验来源是否变更
        content_md5 = hashlib.md5(
            f"{user_msg.content}|{assistant_content}".encode("utf-8")
        ).hexdigest()

        payload = {
            "session_id": session_id,
            "user_message_id": user_msg.id,
            "assistant_message_id": assistant_message_id,
            "source_version": f"md5_{content_md5}",
        }

        task_data = TaskCreate(
            task_type="memory.extract",
            payload=json.dumps(payload),
            dedup_key=f"memory.extract:session:{session_id}:msg:{assistant_message_id}",
            priority=0,
            source_version=f"md5_{content_md5}",
        )
        services_task.create_task(db, task_data)
        logger.info(f"创建记忆提取任务: session_id={session_id}")
    except Exception as e:
        # 任务创建失败不影响对话主流程
        logger.warning(f"创建记忆提取任务失败: {e!s}")


# ── 内部方法 ────────────────────────────────────────────────────────────────


def _get_session_or_error(db: Session, session_id: int) -> ChatSession:
    """获取会话，不存在时抛出异常。"""
    session = db.get(ChatSession, session_id)
    if session is None:
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, f"会话不存在: {session_id}")
    return session
