"""模型配置 Pydantic Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ModelConfigCreate(BaseModel):
    """创建模型配置请求。"""

    name: str = Field(..., max_length=64, description="配置名称")
    provider: str = Field(..., max_length=32, description="模型供应商: openai/anthropic/openai-compatible")
    model_name: str = Field(..., max_length=128, description="模型名称")
    api_base: str | None = Field(None, max_length=256, description="API 地址（可选）")
    enable_reasoning: bool = Field(False, description="是否展示并保存模型推理过程")


class ModelConfigUpdate(BaseModel):
    """更新模型配置请求。"""

    name: str | None = Field(None, max_length=64, description="配置名称")
    provider: str | None = Field(None, max_length=32, description="模型供应商")
    model_name: str | None = Field(None, max_length=128, description="模型名称")
    api_base: str | None = Field(None, max_length=256, description="API 地址")
    enable_reasoning: bool | None = Field(None, description="是否展示并保存模型推理过程")
    has_key: bool | None = Field(None, description="密钥是否已配置")


class ModelConfigResponse(BaseModel):
    """模型配置响应（不含 API Key）。"""

    id: int
    name: str
    provider: str
    model_name: str
    api_base: str | None = None
    enable_reasoning: bool = False
    is_active: bool
    has_key: bool
    status: str
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ModelConfigTestRequest(BaseModel):
    """模型连接测试请求。"""

    api_key: str = Field(..., description="API Key（仅在测试时传入，不持久化）")
