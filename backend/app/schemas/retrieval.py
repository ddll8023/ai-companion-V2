"""记忆检索 Pydantic Schema。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RetrievedMemory(BaseModel):
    """检索到的记忆结果。"""

    id: int
    content: str
    type: str
    importance: int
    status: str
    created_at: str | None = None

    # 检索信号
    relevance_score: int = Field(0, ge=0, le=100, description="综合相关度 0-100")
    fts_score: float = Field(0.0, description="FTS5 BM25 得分")
    freshness_score: int = Field(0, ge=0, le=100, description="时间新鲜度 0-100")

    model_config = ConfigDict(from_attributes=True)


class MemoryContext(BaseModel):
    """注入对话上下文的记忆信息。"""

    enabled: bool = Field(False, description="是否启用了个性化上下文")
    memory_count: int = Field(0, description="注入的记忆条数")
    total_tokens_est: int = Field(0, description="估计占用的 token 数")
    memories: list[RetrievedMemory] = Field(default_factory=list)


class Fts5Status(BaseModel):
    """FTS5 检索状态。"""

    available: bool = Field(False, description="FTS5 是否可用")
    memory_count: int = Field(0, description="索引中的记忆数量")
    error: str | None = Field(None, description="错误信息（可选）")
