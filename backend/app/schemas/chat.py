"""对话 Pydantic Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── 会话 Schema ────────────────────────────────────────────────────────────


class SessionCreate(BaseModel):
    """创建会话请求。"""

    title: str | None = Field(None, max_length=128, description="会话标题（可选，留空使用默认标题）")


class SessionUpdate(BaseModel):
    """更新会话请求。"""

    title: str = Field(..., max_length=128, description="会话标题")


class SessionResponse(BaseModel):
    """会话响应。"""

    id: int
    title: str
    model_name: str | None = None
    model_provider: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ── 消息 Schema ────────────────────────────────────────────────────────────


class MessageResponse(BaseModel):
    """消息响应。"""

    id: int
    session_id: int
    role: str
    content: str
    status: str
    error_message: str | None = None
    model_name: str | None = None
    model_provider: str | None = None
    token_count: int | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ── 对话请求 Schema ────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    """发送消息请求。"""

    content: str = Field(..., min_length=1, max_length=32000, description="消息内容")
    api_key: str | None = Field(None, description="API Key（浏览器模式需要传入）")


class ChatEvent(BaseModel):
    """流式事件。"""

    type: str = Field(..., description="事件类型: token/done/error")
    content: str | None = Field(None, description="token 内容（type=token 时）")
    message_id: int | None = Field(None, description="消息 ID（type=done 时）")
    message: str | None = Field(None, description="错误信息（type=error 时）")
