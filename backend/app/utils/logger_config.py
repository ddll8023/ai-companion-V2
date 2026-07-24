"""统一日志配置模块。

支持控制台输出和文件日志（自动轮转）。
文件日志路径由 DATA_DIR 配置决定。
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings

_FORMATTER = logging.Formatter(
    "%(asctime)s [%(levelname)-5s] %(name)s.%(funcName)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_handlers_initialized = False


def _ensure_handlers():
    """创建并注册全局 handler（单次初始化）。"""
    global _handlers_initialized
    if _handlers_initialized:
        return
    _handlers_initialized = True

    # 控制台 handler（所有环境）
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(_FORMATTER)
    logging.root.addHandler(console)

    # 文件 handler（仅 DATA_DIR 可写时启用）
    try:
        data_dir = Path(settings.resolved_data_dir) if settings.DATA_DIR else None
        if data_dir:
            data_dir.mkdir(parents=True, exist_ok=True)
            log_file = data_dir / "app.log"
            file_handler = RotatingFileHandler(
                str(log_file),
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setFormatter(_FORMATTER)
            logging.root.addHandler(file_handler)
    except (OSError, PermissionError):
        pass  # 文件日志不是强依赖，失败不阻止应用运行

    logging.root.setLevel(logging.INFO)


def setup_logger(name: str) -> logging.Logger:
    """获取统一格式的日志记录器。

    Args:
        name: 日志器名称，通常传 __name__

    Returns:
        配置好的 Logger 实例
    """
    _ensure_handlers()

    logger = logging.getLogger(name)

    # 按配置调整级别
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    # 避免日志重复（propagate 到 root，root 已有 handler）
    logger.propagate = True

    return logger
