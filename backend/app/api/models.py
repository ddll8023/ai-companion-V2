"""模型配置 API 路由。

安全约束：
- API Key 不写入 SQLite
- API Key 不返回 Renderer
- 连接测试时 Key 仅传入请求体，不持久化
- 密钥存储由 Electron keystore 管理

路由顺序说明：特定路径（如 /configs/active/info）必须定义在
参数化路径（如 /configs/{config_id}）之前，避免路径冲突。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import ApiResponse, ErrorCode
from app.schemas.model import (
    ModelConfigCreate,
    ModelConfigResponse,
    ModelConfigTestRequest,
    ModelConfigUpdate,
)
from app.schemas.response import error, success
from app.services import model_provider as services_model
from app.utils.exception import ServiceException

router = APIRouter(prefix="/api/v1/models", tags=["模型配置"])


@router.get("/providers", response_model=ApiResponse[dict[str, str]])
def get_providers():
    """获取支持的供应商列表。"""
    return success(data=services_model.get_supported_providers())


# ── 以下特定路径必须定义在参数化路径之前 ──────────────────────────────


@router.get("/configs/active/info", response_model=ApiResponse[ModelConfigResponse | None])
def get_active_config(
    db: Annotated[Session, Depends(get_db)],
):
    """获取当前激活的模型配置（不含 API Key）。"""
    try:
        result = services_model.get_active_config(db)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


# ── 配置 CRUD ──────────────────────────────────────────────────────────


@router.post("/configs", response_model=ApiResponse[ModelConfigResponse])
def create_config(
    body: ModelConfigCreate,
    db: Annotated[Session, Depends(get_db)],
):
    """创建模型配置（仅非敏感信息，API Key 请在创建后单独通过 keystore 保存）。"""
    try:
        result = services_model.create_config(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.get("/configs", response_model=ApiResponse[list[ModelConfigResponse]])
def list_configs(
    db: Annotated[Session, Depends(get_db)],
):
    """获取全部模型配置列表。"""
    try:
        result = services_model.list_configs(db)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.get("/configs/{config_id}", response_model=ApiResponse[ModelConfigResponse])
def get_config(
    config_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """获取单个模型配置详情（不含 API Key）。"""
    try:
        result = services_model.get_config(db, config_id)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.put("/configs/{config_id}", response_model=ApiResponse[ModelConfigResponse])
def update_config(
    config_id: int,
    body: ModelConfigUpdate,
    db: Annotated[Session, Depends(get_db)],
):
    """更新模型配置。has_key 字段由前端在操作 keystore 后同步更新。"""
    try:
        result = services_model.update_config(db, config_id, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.delete("/configs/{config_id}", response_model=ApiResponse)
def delete_config(
    config_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """删除模型配置（请同时删除 keystore 中对应的密钥）。"""
    try:
        services_model.delete_config(db, config_id)
        return success(message="配置已删除")
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/configs/{config_id}/activate", response_model=ApiResponse[ModelConfigResponse])
def activate_config(
    config_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """激活指定配置。"""
    try:
        result = services_model.activate_config(db, config_id)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/configs/{config_id}/test", response_model=ApiResponse)
def test_config_connection(
    config_id: int,
    body: ModelConfigTestRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """测试模型连接。

    请求体中需传入 API Key（测试完成后不持久化）。
    密钥仅在本次请求的内存中使用，测试结束后释放。
    """
    try:
        success_flag, message = services_model.test_connection(
            config_id=config_id,
            api_key=body.api_key,
            db=db,
        )
        if success_flag:
            return success(message=message)
        return error(code=ErrorCode.MODEL_CONNECTION_ERROR, message=message)
    except ServiceException as e:
        return error(code=e.code, message=e.message)
