"""嵌入向量生成服务。

使用 FastEmbed + ONNX Runtime CPU 本地生成文本嵌入向量。
默认模型：BAAI/bge-small-zh-v1.5（512 维，L2 归一化）。

设计原则：
- 延迟初始化：首次调用时加载模型，避免启动时阻塞
- 完全离线：模型首次下载后不再需要联网
- 线程安全：FastEmbed 内部管理推理会话，全局单例
- 降级友好：模型加载失败或推理异常时返回 None，不抛异常

依赖：fastembed (TextEmbedding), numpy
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Sequence

import numpy as np

logger = logging.getLogger(__name__)

# ── 配置常量 ────────────────────────────────────────────────────────────────

_DEFAULT_MODEL_NAME: str = "BAAI/bge-small-zh-v1.5"
_EMBEDDING_DIMENSION: int = 512

# 模型缓存目录（项目本地，不依赖 ~/.cache）
# 解析路径: backend/app/services/embedding.py → backend/data/models/
_MODEL_CACHE_DIR: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "models",
)

# ── 全局单例（延迟初始化，线程安全） ────────────────────────────────────────

_model = None
_model_lock = threading.Lock()


# ── 公共 API ────────────────────────────────────────────────────────────────


def get_embedding_dimension() -> int:
    """返回当前嵌入向量的维度（固定 512）。"""
    return _EMBEDDING_DIMENSION


def embed_text(text: str) -> np.ndarray | None:
    """生成单条文本的嵌入向量。

    Args:
        text: 待嵌入的文本

    Returns:
        512 维 float32 numpy 数组（L2 归一化），
        模型未加载或推理失败时返回 None
    """
    if not text or not text.strip():
        return None
    if not _ensure_model():
        return None

    try:
        # fastembed.embed() 返回生成器，取第一个结果
        vec = next(_model.embed(text, normalize_embeddings=True))
        return np.array(vec, dtype=np.float32)
    except Exception as exc:
        logger.warning("嵌入向量生成失败（降级）: %s", exc)
        return None


def embed_texts(texts: Sequence[str]) -> list[np.ndarray | None]:
    """批量生成文本的嵌入向量。

    相比逐条调用 embed_text 性能更好（ONNX 批量推理优化）。
    返回列表与输入等长，失败的条目对应位置为 None。

    Args:
        texts: 待嵌入的文本列表

    Returns:
        与输入等长的向量列表
    """
    if not texts:
        return []

    valid_texts = [t for t in texts if t and t.strip()]
    if not valid_texts:
        return [None] * len(texts)
    if not _ensure_model():
        return [None] * len(texts)

    try:
        embeddings = list(_model.embed(valid_texts, normalize_embeddings=True))
        result: list[np.ndarray | None] = []
        idx = 0
        for t in texts:
            if t and t.strip():
                result.append(np.array(embeddings[idx], dtype=np.float32))
                idx += 1
            else:
                result.append(None)
        return result
    except Exception as exc:
        logger.warning("批量嵌入向量生成失败（降级）: %s", exc)
        return [None] * len(texts)


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """计算两个 L2 归一化向量的余弦相似度。

    向量已归一化时，点积等价于余弦相似度，取值 [-1, 1]。
    高维向量点积通常不会接近 ±1，bge 小模型典型值在 0.3-0.8 之间。

    Args:
        vec_a: 归一化向量 A
        vec_b: 归一化向量 B

    Returns:
        余弦相似度，异常或形状不匹配时返回 0.0
    """
    try:
        return float(np.dot(vec_a, vec_b))
    except Exception as exc:
        logger.warning("余弦相似度计算失败: %s", exc)
        return 0.0


def serialize_embedding(vec: np.ndarray | None) -> bytes | None:
    """将 numpy 向量序列化为 BLOB。

    Args:
        vec: numpy float32 向量，或 None

    Returns:
        bytes（.tobytes() 结果），vec 为 None 时返回 None

    Raises:
        ValueError: 向量维度与配置不匹配或 dtype 不是 float32
    """
    if vec is None:
        return None
    if not isinstance(vec, np.ndarray):
        raise ValueError(f"期望 numpy 数组，实际类型: {type(vec)}")
    if vec.dtype != np.float32:
        raise ValueError(f"期望 float32，实际 dtype: {vec.dtype}")
    if vec.shape[0] != _EMBEDDING_DIMENSION:
        raise ValueError(
            f"向量维度不匹配: 期望 {_EMBEDDING_DIMENSION}，实际 {vec.shape[0]}"
        )
    return vec.tobytes()


def deserialize_embedding(blob: bytes | None) -> np.ndarray | None:
    """从 BLOB 反序列化为 numpy 向量。

    Args:
        blob: 序列化的向量字节

    Returns:
        (512,) float32 numpy 数组，blob 为空或解析失败时返回 None
    """
    if blob is None:
        return None
    try:
        arr = np.frombuffer(blob, dtype=np.float32)
        if arr.shape[0] != _EMBEDDING_DIMENSION:
            logger.warning(
                "嵌入向量维度不匹配: 期望 %d, 实际 %d",
                _EMBEDDING_DIMENSION,
                arr.shape[0],
            )
            return None
        return arr
    except Exception as exc:
        logger.warning("嵌入向量反序列化失败: %s", exc)
        return None


# ── 内部方法 ────────────────────────────────────────────────────────────────


def _ensure_model() -> bool:
    """延迟初始化嵌入模型（全局单例，首次调用时加载，线程安全）。

    Returns:
        True 表示模型可用，False 表示加载失败
    """
    global _model
    if _model is not None:
        return True

    with _model_lock:
        # 双重检查锁定：获取锁后重新检查，避免重复初始化
        if _model is not None:
            return True
        try:
            from fastembed import TextEmbedding

            # 确保缓存目录存在
            os.makedirs(_MODEL_CACHE_DIR, exist_ok=True)
            _model = TextEmbedding(model_name=_DEFAULT_MODEL_NAME, cache_dir=_MODEL_CACHE_DIR)
            logger.info("嵌入模型加载完成: %s （缓存: %s）", _DEFAULT_MODEL_NAME, _MODEL_CACHE_DIR)
            return True
        except ImportError:
            logger.error("fastembed 未安装，嵌入功能不可用")
            _model = None
            return False
        except Exception as exc:
            logger.error("嵌入模型加载失败: %s", exc)
            _model = None
            return False
