"""记忆引用 Pydantic Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MemoryReferenceCreate(BaseModel):
    """创建记忆引用请求。"""

    message_id: int
    memory_id: int
    memory_content_preview: str | None = None
    relevance_score: int | None = None
    rank: int | None = None


class MemoryReferenceResponse(BaseModel):
    """记忆引用响应。"""

    id: int
    message_id: int
    memory_id: int | None = None
    memory_content_preview: str | None = None
    relevance_score: int | None = None
    rank: int | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
