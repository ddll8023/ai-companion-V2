"""模型配置服务。

职责：
- 模型配置 CRUD
- 连接测试
- 激活/停用配置

API Key 不存储在 SQLite。密钥由 Electron 安全存储管理，前端通过 IPC 读写。
"""

from __future__ import annotations

import httpx
from sqlalchemy import select, desc, update as sa_update
from sqlalchemy.orm import Session

from app.core.database import commit_or_rollback
from app.models.system import ModelConfig
from app.schemas.common import ErrorCode
from app.schemas.model import ModelConfigCreate, ModelConfigResponse, ModelConfigUpdate
from app.utils.exception import ServiceException
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)


# ── 支持的供应商列表 ────────────────────────────────────────────────────

SUPPORTED_PROVIDERS = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "openai-compatible": "兼容 OpenAI 格式",
}


def get_supported_providers() -> dict[str, str]:
    """返回支持的供应商列表。"""
    return dict(SUPPORTED_PROVIDERS)


# ── 配置 CRUD ──────────────────────────────────────────────────────────


def create_config(db: Session, data: ModelConfigCreate) -> ModelConfigResponse:
    """创建模型配置。"""
    config = ModelConfig(
        name=data.name,
        provider=data.provider,
        model_name=data.model_name,
        api_base=data.api_base,
    )
    db.add(config)
    commit_or_rollback(db)
    logger.info(f"创建模型配置: id={config.id} name={config.name} provider={config.provider}")
    return ModelConfigResponse.model_validate(config)


def update_config(db: Session, config_id: int, data: ModelConfigUpdate) -> ModelConfigResponse:
    """更新模型配置。"""
    config = _get_config_or_error(db, config_id)

    if data.name is not None:
        config.name = data.name
    if data.provider is not None:
        config.provider = data.provider
    if data.model_name is not None:
        config.model_name = data.model_name
    if data.api_base is not None:
        config.api_base = data.api_base
    if data.has_key is not None:
        config.has_key = 1 if data.has_key else 0

    commit_or_rollback(db)
    logger.info(f"更新模型配置: id={config.id}")
    return ModelConfigResponse.model_validate(config)


def delete_config(db: Session, config_id: int) -> None:
    """删除模型配置。"""
    config = _get_config_or_error(db, config_id)
    db.delete(config)
    commit_or_rollback(db)
    logger.info(f"删除模型配置: id={config_id}")


def get_config(db: Session, config_id: int) -> ModelConfigResponse:
    """获取单个配置详情。"""
    config = _get_config_or_error(db, config_id)
    return ModelConfigResponse.model_validate(config)


def list_configs(db: Session) -> list[ModelConfigResponse]:
    """获取全部模型配置列表。"""
    items = db.scalars(
        select(ModelConfig).order_by(desc(ModelConfig.updated_at))
    ).all()
    return [ModelConfigResponse.model_validate(item) for item in items]


def get_active_config(db: Session) -> ModelConfigResponse | None:
    """获取当前激活的配置。"""
    config = db.scalar(
        select(ModelConfig).where(ModelConfig.is_active == 1).limit(1)
    )
    if config is None:
        return None
    return ModelConfigResponse.model_validate(config)


# ── 激活 ────────────────────────────────────────────────────────────────


def activate_config(db: Session, config_id: int) -> ModelConfigResponse:
    """激活指定配置（先取消其他配置的激活状态）。"""
    config = _get_config_or_error(db, config_id)

    # 取消全部激活状态
    db.execute(sa_update(ModelConfig).values(is_active=0))
    # 激活目标配置
    config.is_active = 1
    config.status = "active"
    commit_or_rollback(db)
    logger.info(f"激活模型配置: id={config_id}")
    return ModelConfigResponse.model_validate(config)


# ── 连接测试 ────────────────────────────────────────────────────────────


def test_connection(
    config_id: int,
    api_key: str,
    db: Session,
) -> tuple[bool, str]:
    """测试模型连接。

    API Key 仅在测试时传入，不持久化。
    测试完成后，Python 进程内存中不保留密钥。

    Args:
        config_id: 配置 ID
        api_key: API Key
        db: 数据库会话

    Returns:
        (成功/失败, 消息)
    """
    config = _get_config_or_error(db, config_id)

    provider = config.provider
    model_name = config.model_name
    api_base = config.api_base

    logger.info(f"测试模型连接: id={config_id} provider={provider} model={model_name}")

    success, message = _do_test(provider, model_name, api_key, api_base)

    # 更新配置状态
    if success:
        config.status = "active"
        config.error_message = None
    else:
        config.status = "error"
        config.error_message = message[:256]
    commit_or_rollback(db)

    return success, message


def test_connection_with_data(
    provider: str,
    model_name: str,
    api_key: str,
    api_base: str | None,
) -> tuple[bool, str]:
    """使用传入的配置数据测试模型连接（不依赖已保存的配置）。

    仅用于新建配置时的快速测试。

    Returns:
        (成功/失败, 消息)
    """
    return _do_test(provider, model_name, api_key, api_base)


# ── 内部方法 ────────────────────────────────────────────────────────────


def _get_config_or_error(db: Session, config_id: int) -> ModelConfig:
    """获取配置，不存在时抛出异常。"""
    config = db.get(ModelConfig, config_id)
    if config is None:
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, f"模型配置不存在: {config_id}")
    return config


def _do_test(
    provider: str,
    model_name: str,
    api_key: str,
    api_base: str | None,
) -> tuple[bool, str]:
    """执行实际的连接测试。"""
    if provider in ("openai", "openai-compatible"):
        return _test_openai(model_name, api_key, api_base)
    elif provider == "anthropic":
        return _test_anthropic(model_name, api_key, api_base)
    else:
        return False, f"不支持的供应商类型: {provider}"


def _test_openai(
    model_name: str,
    api_key: str,
    api_base: str | None,
) -> tuple[bool, str]:
    """测试 OpenAI 兼容格式的连接。"""
    base_url = (api_base or "https://api.openai.com/v1").rstrip("/")
    url = f"{base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "test"}],
        "max_tokens": 1,
    }

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            return True, "连接成功"
        else:
            err_body = response.json()
            err_msg = err_body.get("error", {}).get("message", str(response.status_code))
            return False, f"连接失败: {err_msg}"
    except httpx.TimeoutException:
        return False, "连接超时（超过 15 秒）"
    except httpx.ConnectError:
        return False, f"无法连接到 {api_base or 'https://api.openai.com/v1'}"
    except Exception as exc:
        return False, f"连接失败: {exc!s}"


def _test_anthropic(
    model_name: str,
    api_key: str,
    api_base: str | None,
) -> tuple[bool, str]:
    """测试 Anthropic 连接。"""
    base_url = (api_base or "https://api.anthropic.com/v1").rstrip("/")
    url = f"{base_url}/messages"

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "test"}],
    }

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            return True, "连接成功"
        else:
            err_body = response.json()
            err_msg = err_body.get("error", {}).get("message", str(response.status_code))
            return False, f"连接失败: {err_msg}"
    except httpx.TimeoutException:
        return False, "连接超时（超过 15 秒）"
    except httpx.ConnectError:
        return False, f"无法连接到 {api_base or 'https://api.anthropic.com/v1'}"
    except Exception as exc:
        return False, f"连接失败: {exc!s}"
