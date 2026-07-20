"""统一日志配置模块。"""

from __future__ import annotations

import logging
import sys

_formatter = logging.Formatter(
    "%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_handler: logging.Handler | None = None


def setup_logger(name: str) -> logging.Logger:
    """获取统一格式的日志记录器。"""
    global _handler

    if _handler is None:
        _handler = logging.StreamHandler(sys.stdout)
        _handler.setFormatter(_formatter)

    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(_handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

    return logger
