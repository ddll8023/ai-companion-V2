"""对话 Pydantic Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.reference import MemoryReferenceResponse


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
    last_extracted_message_id: int | None = None
    last_extracted_at: datetime | None = None
    extractable_message_count: int = Field(0, description="水位线之后可提取的用户消息数")
    is_extracting: bool = Field(False, description="是否存在进行中的提取任务")
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SessionExtractRequest(BaseModel):
    """会话提取请求。"""

    api_key: str | None = Field(None, description="API Key（浏览器模式需要传入，Electron 模式回退全局缓存）")


# ── 消息 Schema ────────────────────────────────────────────────────────────


class MessageResponse(BaseModel):
    """消息响应。"""

    id: int
    session_id: int
    role: str
    content: str
    reasoning_content: str | None = None
    status: str
    error_message: str | None = None
    model_name: str | None = None
    model_provider: str | None = None
    token_count: int | None = None
    memory_references: list[MemoryReferenceResponse] = Field(
        default_factory=list, description="该消息引用的记忆列表",
    )
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ── 对话请求 Schema ────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    """发送消息请求。"""

    content: str = Field(..., min_length=1, max_length=32000, description="消息内容")
    api_key: str | None = Field(None, description="API Key（浏览器模式需要传入）")


class ChatEvent(BaseModel):
    """流式事件。"""

    type: str = Field(..., description="事件类型: token/reasoning_token/done/error")
    content: str | None = Field(None, description="token 内容（type=token/reasoning_token 时）")
    message_id: int | None = Field(None, description="消息 ID（type=done 时）")
    message: str | None = Field(None, description="错误信息（type=error 时）")
