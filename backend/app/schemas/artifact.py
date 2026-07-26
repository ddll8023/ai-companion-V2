from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class AiArtifactCreate(BaseModel):
    session_id: int
    assistant_message_id: int
    title: str | None = Field(None, max_length=128)

class AiArtifactResponse(BaseModel):
    id: int
    session_id: int
    assistant_message_id: int
    title: str
    content: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)
