"""模型配置服务。

职责：
- 模型配置 CRUD
- 连接测试
- 激活/停用配置

API Key 不存储在 SQLite。密钥由 Electron 安全存储管理，前端通过 IPC 读写。
"""

from __future__ import annotations

import json
from typing import Generator

import httpx
from sqlalchemy import select, desc, update as sa_update
from sqlalchemy.orm import Session

from app.core.database import commit_or_rollback
from app.models.system import ModelConfig
from app.schemas.common import ErrorCode
from app.schemas.model import ModelConfigCreate, ModelConfigResponse, ModelConfigUpdate
from app.services.audit import record_audit
from app.utils.exception import ServiceException
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)


# ── 支持的供应商列表 ────────────────────────────────────────────────────

SUPPORTED_PROVIDERS = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "openai-compatible": "兼容 OpenAI 格式",
}


# ── 同步调用超时配置（秒）────────────────────────────────────────────────
# 非流式请求在模型生成完毕前不会返回任何字节，读超时必须覆盖"完整生成耗时"，
# 因此按输出规模分档：标题类短输出用默认档，后台提取类长输出用长档。

_SYNC_CONNECT_TIMEOUT = 10.0    # 建连/连接池等待
_SYNC_WRITE_TIMEOUT = 30.0      # 请求体写入
SYNC_TIMEOUT_DEFAULT = 60.0     # 默认读超时
SYNC_TIMEOUT_SHORT = 20.0       # 在线路径短输出（会话标题）
SYNC_TIMEOUT_BACKGROUND = 180.0  # 后台长输出（会话分析、人物理解反思与侧写汇编）


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
        enable_reasoning=data.enable_reasoning,
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
    if data.enable_reasoning is not None:
        config.enable_reasoning = data.enable_reasoning
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

    if not config.has_key:
        raise ServiceException(
            ErrorCode.MODEL_CONFIG_ERROR,
            "请先配置 API Key 后激活",
        )

    # 取消全部激活状态
    db.execute(sa_update(ModelConfig).values(is_active=0))
    # 激活目标配置
    config.is_active = 1
    config.status = "active"
    commit_or_rollback(db)
    logger.info(f"激活模型配置: id={config_id}")

    record_audit(
        db=db,
        action="model.config.activate",
        target_type="model_config",
        target_id=config_id,
        summary=f"激活模型配置: provider={config.provider} model={config.model_name}",
    )
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

    record_audit(
        db=db,
        action="model.test_connection",
        target_type="model_config",
        target_id=config_id,
        summary=f"测试模型连接: provider={config.provider} model={config.model_name}",
        result=0 if success else 1,
    )

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


def _get_active_config(db: Session) -> ModelConfig:
    """获取当前激活的配置，不存在时抛出异常。"""
    config = db.scalar(
        select(ModelConfig).where(ModelConfig.is_active == 1).limit(1)
    )
    if config is None:
        raise ServiceException(ErrorCode.MODEL_CONFIG_ERROR, "未配置模型，请在设置中完成模型配置")
    if not config.has_key:
        raise ServiceException(ErrorCode.MODEL_CONFIG_ERROR, "当前模型尚未配置 API Key")
    return config


# ── 流式对话 ────────────────────────────────────────────────────────────────


def chat_stream(
    provider: str,
    model_name: str,
    api_key: str,
    api_base: str | None,
    messages: list[dict[str, str]],
    system_prompt: str | None = None,
    include_reasoning: bool = False,
) -> Generator[tuple[str, str], None, None]:
    """流式对话，逐 token 生成回复内容。

    Args:
        provider: 模型供应商
        model_name: 模型名称
        api_key: API Key
        api_base: API 地址
        messages: 历史消息列表，格式 [{"role": "user", "content": "..."}, ...]
        system_prompt: 系统提示词（可选）

    Yields:
        (type, content) 元组，type 为 "text" 或 "reasoning"
    """
    if provider in ("openai", "openai-compatible"):
        yield from _chat_stream_openai(
            model_name, api_key, api_base, messages, system_prompt, include_reasoning,
        )
    elif provider == "anthropic":
        yield from _chat_stream_anthropic(
            model_name, api_key, api_base, messages, system_prompt, include_reasoning,
        )
    else:
        raise ServiceException(ErrorCode.MODEL_CONFIG_ERROR, f"不支持的供应商类型: {provider}")


def _chat_stream_openai(
    model_name: str,
    api_key: str,
    api_base: str | None,
    messages: list[dict[str, str]],
    system_prompt: str | None = None,
    include_reasoning: bool = False,
) -> Generator[tuple[str, str], None, None]:
    """OpenAI 兼容格式流式对话。"""
    base_url = (api_base or "https://api.openai.com/v1").rstrip("/")
    url = f"{base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload_messages = []
    if system_prompt:
        payload_messages.append({"role": "system", "content": system_prompt})
    payload_messages.extend(messages)

    payload = {
        "model": model_name,
        "messages": payload_messages,
        "stream": True,
    }

    with httpx.Client(timeout=120) as client:
        with client.stream("POST", url, json=payload, headers=headers) as response:
            if response.status_code != 200:
                err_msg = _extract_error(response)
                raise ServiceException(ErrorCode.AI_SERVICE_ERROR, f"模型调用失败: {err_msg}")

            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    # 部分 OpenAI 兼容服务会发送 choices 为空列表的 chunk（如仅含 usage 的收尾帧）
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})

                    # 推理 token（o1/o3/DeepSeek-R1 等推理模型）
                    reasoning = delta.get("reasoning_content", "")
                    if reasoning and include_reasoning:
                        yield ("reasoning", reasoning)

                    # 文本 token
                    content = delta.get("content", "")
                    if content:
                        yield ("text", content)
                except json.JSONDecodeError:
                    logger.warning(f"解析流式响应失败: {data_str[:100]}")
                    continue


def _chat_stream_anthropic(
    model_name: str,
    api_key: str,
    api_base: str | None,
    messages: list[dict[str, str]],
    system_prompt: str | None = None,
    include_reasoning: bool = False,
) -> Generator[tuple[str, str], None, None]:
    """Anthropic 格式流式对话。"""
    base_url = (api_base or "https://api.anthropic.com/v1").rstrip("/")
    url = f"{base_url}/messages"

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    # Anthropic 的 system prompt 是顶层参数，不在 messages 数组中
    payload_messages = [m for m in messages if m["role"] != "system"]

    payload: dict = {
        "model": model_name,
        "max_tokens": 4096,
        "messages": payload_messages,
        "stream": True,
    }
    if system_prompt:
        payload["system"] = system_prompt

    with httpx.Client(timeout=120) as client:
        with client.stream("POST", url, json=payload, headers=headers) as response:
            if response.status_code != 200:
                err_msg = _extract_error(response)
                raise ServiceException(ErrorCode.AI_SERVICE_ERROR, f"模型调用失败: {err_msg}")

            for line in response.iter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    try:
                        event = json.loads(data_str)
                        event_type = event.get("type", "")

                        if event_type == "content_block_start":
                            block = event.get("content_block", {})
                            if block.get("type") == "thinking":
                                thinking = block.get("thinking", "")
                                if thinking and include_reasoning:
                                    yield ("reasoning", thinking)

                        elif event_type == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "thinking_delta":
                                thinking = delta.get("thinking", "")
                                if thinking and include_reasoning:
                                    yield ("reasoning", thinking)
                            elif delta.get("type") == "text_delta":
                                content = delta.get("text", "")
                                if content:
                                    yield ("text", content)
                    except json.JSONDecodeError:
                        logger.warning(f"解析 Anthropic 流式响应失败: {data_str[:100]}")
                        continue


def chat_sync(
    provider: str,
    model_name: str,
    api_key: str | None,
    api_base: str | None,
    system_prompt: str | None = None,
    messages: list[dict[str, str]] | None = None,
    timeout: float = SYNC_TIMEOUT_DEFAULT,
) -> str:
    """同步对话（非流式），完整回复一次性返回，用于后台任务等场景。

    Args:
        provider: 模型供应商
        model_name: 模型名称
        api_key: API Key
        api_base: API 地址
        system_prompt: 系统提示词
        messages: 消息列表
        timeout: 等待模型完整生成的读超时（秒），长输出场景应放大

    Returns:
        完整回复文本

    Raises:
        ServiceException: 缺少 Key、供应商不支持、调用超时/失败或返回内容为空
    """
    if not api_key:
        raise ServiceException(ErrorCode.PARAM_ERROR, "缺少 API Key")

    if provider in ("openai", "openai-compatible"):
        return _chat_sync_openai(model_name, api_key, api_base, messages, system_prompt, timeout)
    elif provider == "anthropic":
        return _chat_sync_anthropic(model_name, api_key, api_base, messages, system_prompt, timeout)
    else:
        raise ServiceException(ErrorCode.PARAM_ERROR, f"不支持的供应商: {provider}")


def _chat_sync_openai(
    model_name: str,
    api_key: str,
    api_base: str | None,
    messages: list[dict[str, str]] | None,
    system_prompt: str | None = None,
    timeout: float = SYNC_TIMEOUT_DEFAULT,
) -> str:
    """OpenAI 格式同步对话。"""
    base_url = (api_base or "https://api.openai.com/v1").rstrip("/")
    url = f"{base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload_messages = []
    if system_prompt:
        payload_messages.append({"role": "system", "content": system_prompt})
    if messages:
        payload_messages.extend(messages)

    payload = {
        "model": model_name,
        "messages": payload_messages,
        "stream": False,
    }

    with httpx.Client(timeout=_build_sync_timeout(timeout)) as client:
        result = _post_sync(client, url, payload, headers, timeout, "OpenAI").json()

    choices = result.get("choices") or []
    if not choices:
        logger.warning("chat_sync OpenAI 响应缺少 choices")
        raise ServiceException(ErrorCode.AI_SERVICE_ERROR, "模型返回内容为空")

    content = choices[0].get("message", {}).get("content") or ""
    if not content.strip():
        raise ServiceException(ErrorCode.AI_SERVICE_ERROR, "模型返回内容为空")
    return content


def _chat_sync_anthropic(
    model_name: str,
    api_key: str,
    api_base: str | None,
    messages: list[dict[str, str]] | None,
    system_prompt: str | None = None,
    timeout: float = SYNC_TIMEOUT_DEFAULT,
) -> str:
    """Anthropic 格式同步对话。"""
    base_url = (api_base or "https://api.anthropic.com/v1").rstrip("/")
    url = f"{base_url}/messages"

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    payload_messages = []
    if messages:
        payload_messages = [m for m in messages if m.get("role") != "system"]

    payload: dict = {
        "model": model_name,
        "max_tokens": 4096,
        "messages": payload_messages,
    }
    if system_prompt:
        payload["system"] = system_prompt

    with httpx.Client(timeout=_build_sync_timeout(timeout)) as client:
        result = _post_sync(client, url, payload, headers, timeout, "Anthropic").json()

    full_text = ""
    for block in result.get("content", []):
        if block.get("type") == "text":
            full_text += block.get("text", "")

    if not full_text.strip():
        raise ServiceException(ErrorCode.AI_SERVICE_ERROR, "模型返回内容为空")
    return full_text


def _build_sync_timeout(read_timeout: float) -> httpx.Timeout:
    """构造同步调用的分项超时（读超时单独放大，覆盖模型完整生成耗时）。"""
    return httpx.Timeout(
        connect=_SYNC_CONNECT_TIMEOUT,
        read=read_timeout,
        write=_SYNC_WRITE_TIMEOUT,
        pool=_SYNC_CONNECT_TIMEOUT,
    )


def _post_sync(
    client: httpx.Client,
    url: str,
    payload: dict,
    headers: dict[str, str],
    timeout: float,
    provider_label: str,
) -> httpx.Response:
    """发送同步对话请求，把网络层与 HTTP 错误统一转为 ServiceException。"""
    try:
        response = client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        # 非流式请求在模型生成完成前不返回任何字节，读超时即"生成太慢"
        logger.error(f"chat_sync {provider_label} 超时: timeout={timeout:.0f}s url={url}")
        raise ServiceException(
            ErrorCode.AI_SERVICE_ERROR,
            f"模型调用超时（等待 {timeout:.0f} 秒未返回）",
        ) from exc
    except Exception as exc:
        logger.error(f"chat_sync {provider_label} 请求异常: {exc!s}", exc_info=True)
        raise ServiceException(ErrorCode.AI_SERVICE_ERROR, "模型服务连接失败") from exc

    if response.status_code != 200:
        err_msg = _extract_error(response)
        logger.warning(f"chat_sync {provider_label} 调用失败: {err_msg}")
        raise ServiceException(
            ErrorCode.AI_SERVICE_ERROR,
            f"模型调用失败（HTTP {response.status_code}）",
        )

    return response


def _extract_error(response: httpx.Response) -> str:
    """从模型 API 错误响应中提取错误消息。"""
    try:
        body = response.json()
        if "error" in body:
            err = body["error"]
            if isinstance(err, dict):
                return err.get("message", str(response.status_code))
            return str(err)
        return str(response.status_code)
    except Exception:
        return f"HTTP {response.status_code}"


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


def _test_http_api(
    url: str,
    headers: dict[str, str],
    payload: dict,
    timeout: int = 15,
) -> tuple[bool, str]:
    """发送 HTTP POST 请求测试模型连接。"""
    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
        if response.status_code == 200:
            return True, "连接成功"
        else:
            err_body = response.json()
            err_msg = err_body.get("error", {}).get("message", str(response.status_code))
            return False, f"连接失败: {err_msg}"
    except httpx.TimeoutException:
        return False, "连接超时（超过 15 秒）"
    except httpx.ConnectError:
        return False, f"无法连接到 {url}"
    except Exception as exc:
        return False, f"连接失败: {exc!s}"


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

    return _test_http_api(url, headers, payload)


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

    return _test_http_api(url, headers, payload)
