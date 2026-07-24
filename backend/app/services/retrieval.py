"""记忆检索服务。

职责：
- FTS5 全文搜索已确认记忆
- 多信号融合排序（FTS5 相关度 + 重要性 + 时间新鲜度）
- 上下文组装（将记忆注入系统提示词）
- 降级能力：FTS5 不可用时返回空结果，不阻塞对话

检索原则：
- 只检索状态为 confirmed 和 corrected 的记忆
- 遵循最小必要上下文原则
- 检索失败不能伪装成"没有记忆"
- FTS5 不可用时保留基础对话
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import numpy as np
from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.schemas.retrieval import MemoryContext, RetrievedMemory
from app.services.embedding import (
    cosine_similarity,
    deserialize_embedding,
    embed_text,
)
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

# ── 配置常量 ────────────────────────────────────────────────────────────────

# 每次检索最大返回条数
_DEFAULT_MAX_RESULTS = 5

# 记忆上下文预算（估计 token 数），防止上下文过长
_MAX_MEMORY_TOKENS = 1500

# 每条记忆平均 token 系数（粗略估计：按中文字符数 * 1.5）
_AVG_TOKEN_PER_CHAR = 1.5

# 新鲜度半衰期（天）：超过此天数的记忆新鲜度降为 50%
_FRESHNESS_HALF_LIFE_DAYS = 30

# ── 向量检索配置 ──────────────────────────────────────────────────────────

# 向量检索返回的候选数（RRF 融合前各自取 Top N）
_VECTOR_CANDIDATES = 20

# 向量检索全表扫描安全上限（超出此数量时记录警告但不截断）
_VECTOR_SCAN_LIMIT = 5000

# RRF 融合常数（标准值 60）
_RRF_K = 60

# ── 公共入口函数 ────────────────────────────────────────────────────────────


def retrieve_memories(
    db: Session,
    query_text: str,
    max_results: int = _DEFAULT_MAX_RESULTS,
    max_tokens: int = _MAX_MEMORY_TOKENS,
) -> MemoryContext:
    """检索与用户消息相关的已确认记忆。

    执行多信号检索：
    1. FTS5 全文搜索匹配
    2. 时间新鲜度计算
    3. 重要性加权
    4. 综合排序

    Args:
        db: 数据库会话
        query_text: 用户消息内容，作为搜索关键词
        max_results: 最多返回的记忆条数
        max_tokens: 记忆上下文最大 token 预算

    Returns:
        包含检索结果和元信息的 MemoryContext
        检索失败或无可检索记忆时返回空结果（enabled=False）
    """
    if not query_text or not query_text.strip():
        logger.debug("检索跳过: 空查询文本")
        return MemoryContext(enabled=False)

    try:
        memories = _search_memories(db, query_text)
    except Exception as exc:
        logger.warning(f"记忆检索失败（降级）: {exc}")
        return MemoryContext(enabled=False)

    if not memories:
        return MemoryContext(enabled=False)

    # 多信号排序
    scored = _multi_signal_rank(memories, query_text)

    # 按 token 预算筛选
    selected = _select_with_budget(scored, max_results, max_tokens)

    # 构建结果
    retrieved = [
        RetrievedMemory(
            id=m["id"],
            content=m.get("content", "")[:500],
            type=m.get("type", "fact"),
            importance=m.get("importance", 0),
            status=m.get("status", ""),
            created_at=str(m.get("created_at")) if m.get("created_at") else None,
            relevance_score=min(100, s["score"]),
            fts_score=s.get("fts_score", 0.0),
            freshness_score=s.get("freshness_score", 0),
            vector_score=s.get("vector_score", None),
        )
        for m, s in selected
    ]

    total_tokens = sum(
        len(m.get("content", "")) * _AVG_TOKEN_PER_CHAR for m, _ in selected
    )

    logger.info(
        f"检索完成: query=({query_text[:50]}...) "
        f"found={len(scored)} selected={len(retrieved)} "
        f"tokens_est={int(total_tokens)}"
    )

    return MemoryContext(
        enabled=True,
        memory_count=len(retrieved),
        total_tokens_est=int(total_tokens),
        memories=retrieved,
    )


# ── 搜索 ────────────────────────────────────────────────────────────────────


def _search_memories(
    db: Session,
    query_text: str,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """搜索已确认的记忆。

    使用混合检索策略：
    1. FTS5 全文搜索（英文精确匹配） → Top 20
    2. 向量语义搜索（中文语义匹配） → Top 20
    3. RRF 融合排序 → 合并去重结果
    4. 中文 LIKE 搜索作为 FTS5 降级补充

    Args:
        db: 数据库会话
        query_text: 搜索关键词
        limit: 最终返回的最大候选数量

    Returns:
        搜索结果列表（含 fts_rank、rrf_score、vector_score 等信号字段）
    """
    if not query_text or not query_text.strip():
        return []

    # 提取关键词（用于 FTS5 和 LIKE 降级）
    cjk_chars, eng_tokens = _extract_tokens(query_text)

    # ── 第 1 步：FTS5 搜索 → 最多 _VECTOR_CANDIDATES 条 ──────────────
    fts_results: list[dict[str, Any]] = []
    if eng_tokens:
        try:
            fts_results = _search_english_fts(db, eng_tokens, _VECTOR_CANDIDATES)
        except Exception as exc:
            logger.warning("FTS5 英文搜索失败: %s", exc)

    # ── 第 2 步：向量语义搜索 → 最多 _VECTOR_CANDIDATES 条 ──────────────
    vec_results: list[dict[str, Any]] = []
    query_emb = embed_text(query_text)
    if query_emb is not None:
        try:
            vec_results = _search_vector(db, query_emb, _VECTOR_CANDIDATES)
        except Exception as exc:
            logger.warning("向量语义搜索失败（可降级）: %s", exc)

    # ── 第 3 步：RRF 融合 ────────────────────────────────────────────────
    if vec_results:
        merged = _rrf_merge(fts_results, vec_results, k=_RRF_K)
    else:
        # 向量不可用时，直接用 FTS 结果
        merged = fts_results

    # ── 第 4 步：中文 LIKE 降级补充 ──────────────────────────────────────
    # 当 FTS5 和向量都结果不足时，用 LIKE 补充（与原有逻辑一致）
    if not merged and cjk_chars:
        try:
            cjk_results = _search_chinese_like(db, cjk_chars, limit)
            merged.extend(cjk_results)
        except Exception as exc:
            logger.warning("LIKE 中文搜索失败: %s", exc)

    return merged[:limit]


def _extract_tokens(
    text: str,
) -> tuple[list[str], list[str]]:
    """从查询文本中提取中文重要字符和英文词。

    Returns:
        (cjk重要字符列表, 英文词列表)
    """
    # 中文停用字
    _CJK_STOP_CHARS = set(
        "的了是在有就和都而及与着或把被从以到让对向跟"
        "比我你他她它我们你们他们谁什么哪这那怎怎"
        "吗呢吧啊哦嗯呀哈么罢了而已哟"
        "个只种些次回趟遍"
    )

    cjk_chars = []
    eng_tokens = []
    current_eng = []

    for ch in text.strip():
        if '一' <= ch <= '鿿':
            if current_eng:
                eng_tokens.append("".join(current_eng))
                current_eng = []
            if ch not in _CJK_STOP_CHARS:
                cjk_chars.append(ch)
        elif ch.isalpha() or ch.isdigit():
            current_eng.append(ch)
        else:
            if current_eng:
                eng_tokens.append("".join(current_eng))
                current_eng = []

    if current_eng:
        eng_tokens.append("".join(current_eng))

    return cjk_chars, eng_tokens


def _search_english_fts(
    db: Session,
    eng_tokens: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    """使用 FTS5 搜索英文关键词。"""
    # 构建 FTS5 查询：前缀匹配
    parts = []
    for token in eng_tokens:
        if len(token) >= 2:
            parts.append(f"{token}*")
        elif token:
            parts.append(token)

    if not parts:
        return []

    fts_query = " OR ".join(parts)

    try:
        result = db.execute(
            text(
                "SELECT m.id, m.content, m.type, m.importance, m.status, "
                "       m.created_at, m.updated_at, "
                "       fts.rank AS bm25_rank "
                "FROM memories_fts fts "
                "JOIN memories m ON m.id = fts.memory_id "
                "WHERE memories_fts MATCH :query "
                "  AND m.status IN ('confirmed', 'corrected') "
                "ORDER BY bm25_rank "
                "LIMIT :limit"
            ),
            {"query": fts_query, "limit": limit},
        )
        rows = result.fetchall()
        return [
            {
                "id": r.id,
                "content": r.content,
                "type": r.type,
                "importance": r.importance,
                "status": r.status,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "fts_rank": r.bm25_rank if hasattr(r, 'bm25_rank') else 0,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning(f"FTS5 查询执行失败: {exc}")
        return []


def _search_chinese_like(
    db: Session,
    cjk_chars: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    """使用 SQL LIKE 搜索中文记忆。

    对每个有语义的中文字符用 OR 组合逐字匹配。
    """
    if not cjk_chars:
        return []

    from app.models.memory import Memory

    # 构建 LIKE 条件：每个字符一个 content LIKE '%ch%' 条件
    conditions = [Memory.content.contains(ch) for ch in cjk_chars]

    # 使用 OR 组合所有字符条件
    filter_condition = conditions[0]
    for cond in conditions[1:]:
        filter_condition = or_(filter_condition, cond)

    items = (
        db.scalars(
            select(Memory)
            .where(
                Memory.status.in_(["confirmed", "corrected"]),
                filter_condition,
            )
            .order_by(Memory.importance.desc(), Memory.id.desc())
            .limit(limit)
        ).all()
    )

    # 计算匹配分数（用于排序）
    results = []
    for item in items:
        content = item.content or ""
        # 匹配字符数占所有重要字符的比例
        match_count = sum(1 for ch in cjk_chars if ch in content)
        match_ratio = match_count / max(len(cjk_chars), 1)
        # BM25 模拟：匹配越多得分越低（与 FTS5 rank 语义一致）
        simulated_rank = 100 - (match_ratio * 100)

        results.append({
            "id": item.id,
            "content": content,
            "type": item.type,
            "importance": item.importance,
            "status": item.status,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "fts_rank": simulated_rank,
        })

    # 按匹配比例降序排列
    results.sort(key=lambda r: r.get("fts_rank", 0))
    return results[:limit]


# ── 向量搜索 ────────────────────────────────────────────────────────────────


def _search_vector(
    db: Session,
    query_embedding: np.ndarray,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """向量语义搜索：余弦相似度 + Top N。

    扫描数据库中所有已确认（confirmed/corrected）且有嵌入向量的记忆，
    逐一计算余弦相似度，返回得分最高的 N 条。

    该实现为精确搜索（全表扫描），适用于记忆数量处于可控范围。
    （后续可引入 sqlite-vec 或 HNSW 近似索引加速。）

    Args:
        db: 数据库会话
        query_embedding: 查询文本的嵌入向量（L2 归一化）
        limit: 返回的最大条数

    Returns:
        按余弦相似度降序的搜索结果列表
    """
    from app.models.memory import Memory

    items = db.scalars(
        select(Memory)
        .where(
            Memory.status.in_(["confirmed", "corrected"]),
            Memory.embedding.isnot(None),
        )
        .limit(_VECTOR_SCAN_LIMIT)
    ).all()

    scored: list[tuple[Memory, float]] = []
    for item in items:
        vec = deserialize_embedding(item.embedding)
        if vec is None:
            continue
        sim = cosine_similarity(query_embedding, vec)
        if sim < 0.1:
            # 相似度过低等同于不相关，跳过以减少噪音
            continue
        scored.append((item, sim))

    scored.sort(key=lambda x: x[1], reverse=True)
    scored = scored[:limit]

    results = []
    for item, sim in scored:
        results.append({
            "id": item.id,
            "content": item.content,
            "type": item.type,
            "importance": item.importance,
            "status": item.status,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "fts_rank": 0,  # 无 FTS BM25 得分，RRF 中作为底分
            "vector_score": round(sim, 6),
        })

    logger.debug(
        "向量检索完成: candidates=%d, vector_hits=%d, selected=%d",
        len(items), len(scored), len(results),
    )
    return results


# ── RRF 融合 ────────────────────────────────────────────────────────────────


def _rrf_merge(
    fts_results: list[dict[str, Any]],
    vec_results: list[dict[str, Any]],
    k: int = 60,
) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion：融合两路检索结果。

    RRF 得分 = sum(1 / (k + rank))，其中 rank 从 1 开始计数。
    属于同一记忆的结果合并，取各信号的最佳值。

    Args:
        fts_results: FTS5 搜索结果（按相关度降序）
        vec_results: 向量搜索结果（按相似度降序）
        k: RRF 常数，控制两路融合时的平滑程度

    Returns:
        按 RRF 得分降序排列的唯一结果列表
    """
    merged: dict[int, dict[str, Any]] = {}

    # 融合 FTS 路
    for rank, r in enumerate(fts_results, start=1):
        mem_id = r["id"]
        if mem_id not in merged:
            entry = dict(r)
            entry["rrf_score"] = 0.0
            entry["vector_score"] = None  # FTS 结果无向量得分
            merged[mem_id] = entry
        merged[mem_id]["rrf_score"] += 1.0 / (k + rank)

    # 融合向量路
    for rank, r in enumerate(vec_results, start=1):
        mem_id = r["id"]
        if mem_id not in merged:
            entry = dict(r)
            entry["rrf_score"] = 0.0
            entry["fts_rank"] = 0
            merged[mem_id] = entry
        merged[mem_id]["rrf_score"] += 1.0 / (k + rank)
        # 保留最高向量得分（同一条记忆可能在 FTS 路也出现过）
        vec_s = r.get("vector_score", 0) or 0
        existing = merged[mem_id].get("vector_score", None)
        if existing is None or vec_s > existing:
            merged[mem_id]["vector_score"] = vec_s

    # 按 RRF 得分降序
    sorted_items = sorted(merged.values(), key=lambda x: x["rrf_score"], reverse=True)

    logger.debug("RRF 融合: fts=%d, vec=%d, merged=%d", len(fts_results), len(vec_results), len(sorted_items))
    return sorted_items


# ── 多信号排序 ──────────────────────────────────────────────────────────────


def _multi_signal_rank(
    results: list[dict[str, Any]],
    query_text: str,
) -> list[tuple[dict[str, Any], dict[str, float]]]:
    """多信号融合排序。

    三种信号：
    1. 检索得分（权重 0.5）— RRF 得分（混合）或 FTS5 BM25（降级）
    2. 重要性（权重 0.3）
    3. 时间新鲜度（权重 0.2）

    当结果包含 rrf_score 时使用 RRF 归一化得分替代 FTS5 BM25。

    Args:
        results: 搜索结果列表（可能经 RRF 融合或纯 FTS5 降级）
        query_text: 原始查询文本

    Returns:
        按综合得分降序排列的 (记忆对象, 信号字典) 列表
    """
    if not results:
        return []

    has_rrf = "rrf_score" in results[0]

    # 找出各信号的极值用于归一化
    max_importance = max((r.get("importance", 0) for r in results), default=1)
    if max_importance == 0:
        max_importance = 1

    # BM25 rank 归一化（仅用于 FTS-only 降级路径）
    if not has_rrf:
        min_rank = min(r.get("fts_rank", 0) for r in results)
        max_rank = max(r.get("fts_rank", 0) for r in results)
        rank_range = max_rank - min_rank if max_rank > min_rank else 1.0

    now = datetime.now(tz=timezone.utc)

    scored = []
    for r in results:
        # 1. 检索得分 (0-100)
        if has_rrf:
            # RRF 得分归一化：0~1/k 范围，映射到 0-100
            raw_rrf = r.get("rrf_score", 0)
            rank_score = min(100, raw_rrf * _RRF_K * 20)  # 经验映射因子
        else:
            raw_rank = r.get("fts_rank", 0)
            rank_score = max(0, 100 * (1 - (raw_rank - min_rank) / rank_range))

        # 2. 重要性得分 (0-100)
        importance_score = (r.get("importance", 0) / max_importance) * 100

        # 3. 时间新鲜度得分 (0-100)
        freshness_score = _calc_freshness(r.get("created_at"))

        # 综合得分
        combined = (
            rank_score * 0.5 + importance_score * 0.3 + freshness_score * 0.2
        )

        # 取最大向量得分用于结果展示
        vec_s = r.get("vector_score", None)

        scored.append((
            r,
            {
                "score": int(combined),
                "fts_score": round(rank_score, 1),
                "freshness_score": int(freshness_score),
                "importance_score": int(importance_score),
                "vector_score": vec_s,
            },
        ))

    # 按综合得分降序排列
    scored.sort(key=lambda x: x[1]["score"], reverse=True)
    return scored


def _calc_freshness(created_at: Any) -> float:
    """根据创建时间计算新鲜度得分。

    时间越近得分越高，使用指数衰减。
    """
    if created_at is None:
        return 50  # 无时间信息时取中间值

    try:
        if isinstance(created_at, str):
            dt = datetime.fromisoformat(created_at)
        else:
            dt = created_at

        now = datetime.now(tz=timezone.utc) if hasattr(datetime, "timezone") else datetime.now()

        # 确保时区一致
        if hasattr(dt, "tzinfo") and dt.tzinfo is None:
            # dt 无时区，now 有时区 → 剥离 now 的时区
            now = now.replace(tzinfo=None)
        elif hasattr(now, "tzinfo") and now.tzinfo is None and hasattr(dt, "tzinfo") and dt.tzinfo is not None:
            # dt 有时区，now 无时区 → 剥离 dt 的时区
            dt = dt.replace(tzinfo=None)

        days_diff = (now - dt).days
        if days_diff < 0:
            return 100  # 未来的时间（不太可能，但兼容）

        # 指数衰减：score = 100 * 0.5^(days / half_life)
        score = 100 * (0.5 ** (days_diff / _FRESHNESS_HALF_LIFE_DAYS))
        return min(100, max(0, score))
    except Exception:
        return 50


# ── Token 预算筛选 ──────────────────────────────────────────────────────────


def _select_with_budget(
    scored_results: list[tuple[dict[str, Any], dict[str, float]]],
    max_results: int,
    max_tokens: int,
) -> list[tuple[dict[str, Any], dict[str, float]]]:
    """在 token 预算内选择最相关的记忆。

    按分数降序遍历，累计 token 消耗，超过预算时停止。

    Args:
        scored_results: 已排好序的 (记忆, 信号) 列表
        max_results: 最大条数限制
        max_tokens: 最大 token 预算

    Returns:
        预算内可用的记忆列表
    """
    selected = []
    tokens_used = 0

    for m, s in scored_results:
        token_est = len(m.get("content", "")) * _AVG_TOKEN_PER_CHAR
        if tokens_used + token_est > max_tokens and selected:
            # 至少返回一条，否则截断无意义
            break
        if len(selected) >= max_results:
            break
        selected.append((m, s))
        tokens_used += token_est

    return selected


# ── 系统提示词构造 ──────────────────────────────────────────────────────────


def build_system_prompt_with_context(
    base_prompt: str,
    memory_context: MemoryContext,
) -> str:
    """将检索到的记忆注入系统提示词。

    返回增强后的系统提示词，包含一段结构化的记忆上下文。
    如果 memory_context.enabled 为 False 或没有记忆，直接返回原提示词。

    Args:
        base_prompt: 原始系统提示词
        memory_context: 检索到的记忆上下文

    Returns:
        增强后的系统提示词
    """
    if not memory_context.enabled or not memory_context.memories:
        return base_prompt

    context_lines = []
    context_lines.append("")
    context_lines.append("以下是关于用户的已知信息（长期记忆），请你在回答时参考这些信息：")
    context_lines.append("")

    for i, mem in enumerate(memory_context.memories, start=1):
        # 根据类型添加标签
        type_label = {
            "fact": "事实",
            "preference": "偏好",
            "event": "事件",
            "goal": "目标",
            "habit": "习惯",
        }.get(mem.type, mem.type)

        line = f"{i}. [{type_label}] {mem.content}"
        if mem.relevance_score >= 70:
            line += "（相关度：高）"
        elif mem.relevance_score >= 40:
            line += "（相关度：中）"
        else:
            line += "（相关度：低）"

        context_lines.append(line)

    context_lines.append("")
    context_lines.append("--- 以上为长期记忆，以下为当前对话 ---")

    return base_prompt + "\n".join(context_lines)


# ── 状态检查 ─────────────────────────────────────────────────────────────────


def check_fts5_available(db: Session) -> dict:
    """检查 FTS5 虚拟表是否可用。

    Returns:
        {"available": bool, "memory_count": int, "error": str | None}
    """
    try:
        # 检查 memories_fts 表是否存在
        table_check = db.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='memories_fts'"
            )
        ).first()
        if not table_check:
            return {"available": False, "memory_count": 0, "error": "FTS5 表未创建"}

        # 查询索引中的记忆数量
        count = db.execute(
            text("SELECT COUNT(*) FROM memories_fts")
        ).scalar() or 0

        return {"available": True, "memory_count": count, "error": None}
    except Exception as exc:
        logger.warning(f"FTS5 状态检查失败: {exc}")
        return {"available": False, "memory_count": 0, "error": str(exc)[:200]}
