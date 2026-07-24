"""对话 API 路由。

路由说明：
- 会话 CRUD 使用常规 REST API
- 对话流式输出使用 Server-Sent Events (SSE)
- SSE 响应使用 text/event-stream 格式
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.chat import ChatRequest, MessageResponse, SessionCreate, SessionResponse, SessionUpdate
from app.schemas.common import ApiResponse, ErrorCode
from app.schemas.response import error, success
from app.services import chat as services_chat
from app.utils.exception import ServiceException
from app.utils.logger_config import setup_logger

import json

logger = setup_logger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["对话"])


# ── 会话 CRUD ──────────────────────────────────────────────────────────────


@router.get("/sessions", response_model=ApiResponse[list[SessionResponse]])
def list_sessions(
    db: Annotated[Session, Depends(get_db)],
):
    """获取全部会话列表。"""
    try:
        result = services_chat.list_sessions(db)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/sessions", response_model=ApiResponse[SessionResponse])
def create_session(
    db: Annotated[Session, Depends(get_db)],
    body: SessionCreate | None = None,
):
    """创建新会话。"""
    try:
        result = services_chat.create_session(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.get("/sessions/{session_id}", response_model=ApiResponse[SessionResponse])
def get_session(
    session_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """获取单个会话详情。"""
    try:
        result = services_chat.get_session(db, session_id)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.put("/sessions/{session_id}", response_model=ApiResponse[SessionResponse])
def update_session(
    session_id: int,
    body: SessionUpdate,
    db: Annotated[Session, Depends(get_db)],
):
    """更新会话（重命名）。"""
    try:
        result = services_chat.update_session(db, session_id, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.delete("/sessions/{session_id}", response_model=ApiResponse)
def delete_session(
    session_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """删除会话及关联消息。"""
    try:
        services_chat.delete_session(db, session_id)
        return success(message="会话已删除")
    except ServiceException as e:
        return error(code=e.code, message=e.message)


# ── 消息 ────────────────────────────────────────────────────────────────────


@router.get("/sessions/{session_id}/messages", response_model=ApiResponse[list[MessageResponse]])
def get_messages(
    session_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """获取指定会话的全部消息。"""
    try:
        result = services_chat.get_messages(db, session_id)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


# ── 流式对话 ────────────────────────────────────────────────────────────────


@router.post("/sessions/{session_id}/chat")
def chat_stream(
    session_id: int,
    body: ChatRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """发送消息并接收流式回复（SSE）。

    分两阶段执行：
    1. 初始化阶段 — 验证、保存用户消息、创建占位消息（使用注入的 db session）
    2. 流式生成阶段 — 模型对话（使用独立 db session，不 hold 连接池）

    返回 Server-Sent Events 流：
    - data: {"type": "token", "content": "..."}
    - data: {"type": "done", "message_id": 2}
    - data: {"type": "error", "message": "..."}
    """
    # 阶段 1：初始化（快速完成，释放注入的 db session）
    init_result = services_chat.initialize_chat_stream(
        db=db,
        session_id=session_id,
        user_content=body.content,
        api_key=body.api_key,
    )
    if init_result.get("error"):
        return JSONResponse(
            status_code=400,
            content=error(message=init_result["error"]),
        )

    assistant_msg_id = init_result["assistant_message_id"]
    active_config = init_result["active_config"]
    model_messages = init_result["model_messages"]
    api_key = init_result["api_key"]
    system_prompt = init_result.get("system_prompt")
    memory_context = init_result.get("memory_context")

    # 阶段 2：流式生成（使用独立 session）
    def event_generator():
        for event in services_chat.run_chat_stream(
            session_id=session_id,
            assistant_msg_id=assistant_msg_id,
            active_config=active_config,
            model_messages=model_messages,
            api_key=api_key,
            system_prompt=system_prompt,
            memory_context=memory_context,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
