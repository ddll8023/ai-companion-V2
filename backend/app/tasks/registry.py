"""任务处理器注册表。

负责：
- 注册任务类型对应的处理器函数
- 根据任务类型查找对应的处理器
"""

from __future__ import annotations

from typing import Any, Callable

from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

# 注册表：task_type -> handler function
# handler 签名：handler(payload: dict | None) -> str | None
# 返回执行结果（JSON 字符串）或 None
_task_handlers: dict[str, Callable[[dict | None], str | None]] = {}


def register_handler(task_type: str):
    """注册任务处理器的装饰器。

    Args:
        task_type: 任务类型，如 'memory.extract'

    Returns:
        装饰器函数

    Usage:
        @register_handler("memory.extract")
        def handle_memory_extract(payload: dict | None) -> str | None:
            ...
    """

    def decorator(func: Callable[[dict | None], str | None]):
        _task_handlers[task_type] = func
        logger.info(f"注册任务处理器: {task_type} -> {func.__name__}")
        return func

    return decorator


def get_handler(task_type: str) -> Callable[[dict | None], str | None] | None:
    """根据任务类型获取对应的处理器。"""
    return _task_handlers.get(task_type)


def list_registered_types() -> list[str]:
    """获取所有已注册的任务类型。"""
    return list(_task_handlers.keys())
