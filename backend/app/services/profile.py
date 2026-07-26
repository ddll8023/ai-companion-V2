"""画像服务。

职责：
- 管理画像 CRUD
- 处理用户审查操作（确认、纠正、否定、删除）
- 管理来源证据和修订历史
- 画像演化：执行 LLM 输出的 CREATE/REINFORCE/REVISE 操作指令
- 画像上下文组装（注入对话系统提示词）
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.database import commit_or_rollback
from app.models.activity import Activity
from app.models.chat import Message
from app.models.memory import Memory
from app.models.profile import Profile, ProfileRevision, ProfileSource
from app.prompts.profile import PROFILE_EVOLUTION_SYSTEM_PROMPT
from app.schemas.common import ErrorCode, PaginatedResponse, PaginationInfo
from app.schemas.profile import (
    PROFILE_CATEGORIES,
    BehaviorStatsResponse,
    ProfileCorrect,
    ProfileCreate,
    ProfileDetailResponse,
    ProfileListQuery,
    ProfileResponse,
    ProfileRevisionResponse,
    ProfileSourceResponse,
)
from app.services.audit import record_audit
from app.utils.exception import ServiceException
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

# 不同记忆批次中，模型常会用略有不同的措辞重复表达同一画像。
# 阈值保守设置，避免把同类但实际不同的偏好合并掉。
_CROSS_SOURCE_DUPLICATE_THRESHOLD = 0.88

# REINFORCE 操作的置信度步进与上限
_REINFORCE_STEP = 10
_REINFORCE_CAP = 95

# CREATE 操作的画像正文长度上限
_PROFILE_CONTENT_MAX_CHARS = 200

# 画像注入对话的 token 预算与字符换算系数（与检索模块保持一致）
_PROFILE_CONTEXT_TOKEN_BUDGET = 800
_AVG_TOKEN_PER_CHAR = 1.5

# 画像类别中文标签（注入对话与前端展示语义一致）
_CATEGORY_LABELS = {
    "communication_preference": "沟通偏好",
    "work_habit": "工作习惯",
    "learning_preference": "学习偏好",
    "interest": "兴趣方向",
    "decision_preference": "决策倾向",
    "time_habit": "时间习惯",
    "life_habit": "生活习惯",
    "long_term_goal": "长期目标",
    "work_pattern": "使用模式",
    "other": "其他特征",
}


# ========== 公共入口函数 ==========


def create_candidate_profile(
    db: Session,
    data: ProfileCreate,
) -> ProfileResponse:
    """创建候选画像。

    支持同时关联多条来源记忆和证据文本。
    """
    profile = Profile(
        category=data.category,
        content=data.content,
        confidence=data.confidence,
        status="candidate",
        is_auto_extracted=data.is_auto_extracted,
        supersedes_profile_id=data.supersedes_profile_id,
        version=1,
    )
    db.add(profile)
    commit_or_rollback(db)

    # 保存来源证据（无关联记忆时也保留证据文本，避免证据链丢失）
    source_count = max(len(data.memory_ids), len(data.evidence_texts))
    for idx in range(source_count):
        memory_id = data.memory_ids[idx] if idx < len(data.memory_ids) else None
        evidence = (
            data.evidence_texts[idx]
            if idx < len(data.evidence_texts)
            else None
        )
        source = ProfileSource(
            profile_id=profile.id,
            source_type="extraction" if data.is_auto_extracted else "memory",
            memory_id=memory_id,
            content_preview=data.content[:200],
            evidence_text=evidence,
        )
        db.add(source)

    commit_or_rollback(db)
    logger.info(
        f"创建候选画像: id={profile.id}, category={data.category}, "
        f"is_auto_extracted={data.is_auto_extracted}",
    )

    return ProfileResponse.model_validate(profile)


def query_profiles(
    db: Session,
    query: ProfileListQuery,
) -> PaginatedResponse[ProfileResponse]:
    """查询画像列表。

    支持按类别、状态、关键词、是否自动提取筛选。
    """
    base_stmt = select(Profile)

    if query.status:
        base_stmt = base_stmt.where(Profile.status == query.status)
    if query.category:
        base_stmt = base_stmt.where(Profile.category == query.category)
    if query.keyword:
        base_stmt = base_stmt.where(Profile.content.contains(query.keyword))
    if query.is_auto_extracted is not None:
        base_stmt = base_stmt.where(
            Profile.is_auto_extracted == query.is_auto_extracted,
        )

    total = db.scalar(select(func.count()).select_from(base_stmt.subquery()))

    items = (
        db.scalars(
            base_stmt
            .order_by(desc(Profile.confidence), desc(Profile.id))
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        ).all()
    )

    return PaginatedResponse(
        lists=[ProfileResponse.model_validate(item) for item in items],
        pagination=PaginationInfo(
            page=query.page,
            page_size=query.page_size,
            total=total or 0,
            total_pages=math.ceil((total or 0) / query.page_size),
        ),
    )


def get_profile(db: Session, profile_id: int) -> ProfileDetailResponse:
    """获取单个画像详情（含来源和修订历史）。"""
    profile = _get_profile_or_error(db, profile_id)

    sources = db.scalars(
        select(ProfileSource)
        .where(ProfileSource.profile_id == profile_id)
        .order_by(ProfileSource.id)
    ).all()

    revisions = db.scalars(
        select(ProfileRevision)
        .where(ProfileRevision.profile_id == profile_id)
        .order_by(desc(ProfileRevision.id))
    ).all()

    return ProfileDetailResponse(
        profile=ProfileResponse.model_validate(profile),
        sources=[ProfileSourceResponse.model_validate(s) for s in sources],
        revisions=[ProfileRevisionResponse.model_validate(r) for r in revisions],
    )


def confirm_profile(db: Session, profile_id: int) -> ProfileResponse:
    """确认候选画像。

    将状态更新为 confirmed。
    若该画像是候选修订版（supersedes_profile_id 非空），被修订的旧画像自动转为 rejected。
    """
    profile = _get_profile_or_error(db, profile_id)

    if profile.status not in ("candidate", "corrected"):
        raise ServiceException(
            ErrorCode.PARAM_ERROR,
            f"仅可确认候选或已纠正状态的画像，当前状态: {profile.status}",
        )

    profile.status = "confirmed"

    # 候选修订版被确认 → 旧画像自动否定，避免新旧两版并存注入对话
    if profile.supersedes_profile_id:
        old_profile = db.get(Profile, profile.supersedes_profile_id)
        if old_profile is not None and old_profile.status in (
            "candidate", "confirmed", "corrected",
        ):
            old_profile.status = "rejected"
            logger.info(
                f"确认修订版画像: id={profile_id}, "
                f"旧画像 id={old_profile.id} 已自动转 rejected",
            )

    commit_or_rollback(db)
    logger.info(f"确认画像: id={profile_id}")

    record_audit(
        db=db,
        action="profile.confirm",
        target_type="profile",
        target_id=profile_id,
        summary=f"确认画像: {profile.content[:100]}",
    )

    return ProfileResponse.model_validate(profile)


def correct_profile(
    db: Session,
    profile_id: int,
    data: ProfileCorrect,
) -> ProfileResponse:
    """纠正画像。

    用户纠正后，旧版本保存到 revisions 表，状态标记为 confirmed。
    """
    profile = _get_profile_or_error(db, profile_id)

    if profile.status in ("deleted",):
        raise ServiceException(
            ErrorCode.PARAM_ERROR,
            f"已删除的画像不可纠正，当前状态: {profile.status}",
        )

    # 保存旧版本到修订历史
    revision = ProfileRevision(
        profile_id=profile_id,
        previous_category=profile.category,
        previous_content=profile.content,
        previous_confidence=profile.confidence,
        previous_status=profile.status,
        changed_by="user",
    )
    db.add(revision)

    # 更新为新内容
    profile.category = data.category
    profile.content = data.content
    profile.confidence = data.confidence
    profile.version += 1

    if profile.status not in ("confirmed",):
        profile.status = "confirmed"

    commit_or_rollback(db)
    logger.info(f"纠正画像: id={profile_id}, version={profile.version}")

    record_audit(
        db=db,
        action="profile.correct",
        target_type="profile",
        target_id=profile_id,
        summary=f"纠正画像 (v{profile.version})",
    )

    return ProfileResponse.model_validate(profile)


def reject_profile(db: Session, profile_id: int) -> ProfileResponse:
    """否定画像（候选 → rejected）。

    保留否定标识，防止后续再次被自动提取。
    """
    profile = _get_profile_or_error(db, profile_id)

    if profile.status not in ("candidate", "confirmed", "corrected"):
        raise ServiceException(
            ErrorCode.PARAM_ERROR,
            f"当前状态不可否定: {profile.status}",
        )

    profile.status = "rejected"
    commit_or_rollback(db)
    logger.info(f"否定画像: id={profile_id}")

    record_audit(
        db=db,
        action="profile.reject",
        target_type="profile",
        target_id=profile_id,
        summary=f"否定画像: {profile.content[:100]}",
    )

    return ProfileResponse.model_validate(profile)


def delete_profile(db: Session, profile_id: int) -> None:
    """删除画像（逻辑删除）。

    标记 status='deleted'，保留来源和修订历史。
    关联的 sources 和 revisions 通过 CASCADE 自动清理。
    """
    profile = _get_profile_or_error(db, profile_id)

    record_audit(
        db=db,
        action="profile.delete",
        target_type="profile",
        target_id=profile_id,
        summary=f"删除画像 (id={profile_id})",
    )

    db.delete(profile)
    commit_or_rollback(db)
    logger.info(f"删除画像: id={profile_id}")


# ========== 行为统计 ==========


def get_behavior_stats(db: Session, days: int) -> BehaviorStatsResponse:
    """获取行为统计数据。

    聚合查询 activities 和 messages 表，不支持缓存。
    """
    since = datetime.now() - timedelta(days=days)

    # 1. 活跃时段：按小时聚合活动开始时间
    active_hours = _query_active_hours(db, since)

    # 2. 应用使用分布：按应用聚合使用时长
    app_usage = _query_app_usage(db, since)

    # 3. 对话活跃度：按日期聚合消息数
    chat_activity = _query_chat_activity(db, since)

    return BehaviorStatsResponse(
        active_hours=active_hours,
        app_usage=app_usage,
        chat_activity=chat_activity,
    )


# ========== 画像演化 ==========

# 单批操作指令数量上限（防止 LLM 输出失控）
_MAX_OPERATIONS_PER_BATCH = 20


def apply_profile_operations(
    db: Session,
    operations: list,
    evidence_memories: list | None = None,
    source_session_id: int | None = None,
) -> dict:
    """执行画像演化操作指令（CREATE/REINFORCE/REVISE），逐条独立校验，单条失败不中断。"""
    stats = {"created": 0, "reinforced": 0, "revised": 0, "skipped": 0}
    memories = evidence_memories or []

    if len(operations) > _MAX_OPERATIONS_PER_BATCH:
        logger.warning(
            f"画像操作数超过上限，截断处理: {len(operations)} -> {_MAX_OPERATIONS_PER_BATCH}",
        )
        operations = operations[:_MAX_OPERATIONS_PER_BATCH]

    for op_data in operations:
        if not isinstance(op_data, dict):
            stats["skipped"] += 1
            continue
        op = str(op_data.get("op", "")).upper()
        try:
            if op == "CREATE":
                ok = _apply_create(db, op_data, memories)
                stats["created" if ok else "skipped"] += 1
            elif op == "REINFORCE":
                ok = _apply_reinforce(db, op_data, memories, source_session_id)
                stats["reinforced" if ok else "skipped"] += 1
            elif op == "REVISE":
                ok = _apply_revise(db, op_data, memories)
                stats["revised" if ok else "skipped"] += 1
            else:
                stats["skipped"] += 1
        except Exception as exc:
            logger.warning(f"画像操作执行失败（跳过）: op={op}, error={exc}")
            stats["skipped"] += 1

    return stats


def evolve_profiles(
    db: Session,
    api_key: str,
    new_summary: str | None = None,
    new_memories: list | None = None,
    source_session_id: int | None = None,
) -> dict:
    """画像演化：现有画像对比新摘要/新记忆，调用 LLM 输出并执行增量操作指令。"""
    from app.services import model_provider

    memories = new_memories or []
    if not new_summary and not memories:
        return {"created": 0, "reinforced": 0, "revised": 0, "skipped": 0, "reason": "无新信息"}

    active_config = model_provider.get_active_config(db)
    if active_config is None:
        return {"error": "无激活的模型配置"}

    try:
        result_text = model_provider.chat_sync(
            provider=active_config.provider,
            model_name=active_config.model_name,
            api_key=api_key,
            api_base=active_config.api_base,
            system_prompt=PROFILE_EVOLUTION_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": _build_evolution_input(db, new_summary, memories)},
            ],
            timeout=model_provider.SYNC_TIMEOUT_BACKGROUND,
        )
    except ServiceException as exc:
        # 保留模型调用的真实失败原因（超时/连接失败/HTTP 错误），供任务错误信息使用
        return {"error": exc.message}

    parsed = _parse_extraction_result(result_text)
    if parsed is None:
        return {"error": "模型返回格式异常"}

    operations = parsed.get("operations", [])
    if not isinstance(operations, list) or not operations:
        return {"created": 0, "reinforced": 0, "revised": 0, "skipped": 0, "reason": "无可执行操作"}

    stats = apply_profile_operations(
        db, operations,
        evidence_memories=memories,
        source_session_id=source_session_id,
    )
    logger.info(f"画像演化完成: {stats}")
    return stats


def build_profile_context(db: Session) -> str | None:
    """组装已确认画像的系统提示词段落，无可用画像或异常时返回 None。"""
    try:
        items = db.scalars(
            select(Profile)
            .where(Profile.status.in_(["confirmed", "corrected"]))
            .order_by(desc(Profile.confidence), desc(Profile.id))
        ).all()
        if not items:
            return None

        # token 预算换算为字符预算，超出按置信度降序截断（至少保留一条）
        char_budget = int(_PROFILE_CONTEXT_TOKEN_BUDGET / _AVG_TOKEN_PER_CHAR)
        selected = []
        used = 0
        for p in items:
            cost = len(p.content)
            if selected and used + cost > char_budget:
                break
            selected.append(p)
            used += cost

        grouped: dict[str, list] = {}
        for p in selected:
            grouped.setdefault(p.category, []).append(p)

        lines = [
            "以下是用户的长期画像（经用户确认的稳定特征），"
            "请在回答内容和沟通方式上自然参考，无需向用户复述：",
        ]
        for category, profiles in grouped.items():
            label = _CATEGORY_LABELS.get(category, category)
            for p in profiles:
                lines.append(f"- [{label}] {p.content}")
        return "\n".join(lines)
    except Exception as exc:
        logger.warning(f"画像上下文组装失败（降级跳过）: {exc}")
        return None


def check_duplicate_profile(
    db: Session,
    category: str,
    content: str,
    exclude_profile_id: int | None = None,
) -> bool:
    """检查同类别下是否已存在相似的活跃画像（候选修订版可豁免与被修订画像的比对）。"""
    existing = db.scalars(
        select(Profile).where(
            Profile.category == category,
            Profile.status.in_(["candidate", "confirmed", "corrected"]),
        )
    ).all()

    normalized_content = _normalize_profile_content(content)
    for profile in existing:
        if exclude_profile_id is not None and profile.id == exclude_profile_id:
            continue
        if _is_similar_content(
            _normalize_profile_content(profile.content), normalized_content,
        ):
            return True

    return False


def matches_rejected_profile(db: Session, content: str) -> bool:
    """检查内容是否与用户已否定的画像相似（程序级兜底，禁止自动重建）。"""
    rejected = db.scalars(
        select(Profile).where(Profile.status == "rejected")
    ).all()

    normalized_content = _normalize_profile_content(content)
    for profile in rejected:
        if _is_similar_content(
            _normalize_profile_content(profile.content), normalized_content,
        ):
            return True

    return False


def _normalize_profile_content(content: str) -> str:
    """标准化画像文本，使标点、空格和大小写差异不影响重复判断。"""
    return re.sub(r"[\W_]+", "", content).casefold()


def sync_extract_profiles(
    db: Session,
    api_key: str,
    memory_ids: list[int] | None = None,
) -> dict:
    """从已确认记忆中演化画像（画像页手动触发入口）。"""
    try:
        stmt = select(Memory).where(
            Memory.status.in_(["confirmed", "corrected"]),
        )
        if memory_ids:
            stmt = stmt.where(Memory.id.in_(memory_ids))
        memories = list(
            db.scalars(
                stmt.order_by(desc(Memory.importance), desc(Memory.id))
                .limit(50)
            ).all()
        )
        if not memories:
            return {"created": 0, "reinforced": 0, "revised": 0, "skipped": 0,
                    "reason": "无可用的已确认记忆"}

        return evolve_profiles(db, api_key, new_summary=None, new_memories=memories)

    except Exception as exc:
        logger.error(f"画像演化异常: {exc}", exc_info=True)
        return {"error": str(exc)[:200]}


"""辅助函数"""


def _build_evolution_input(
    db: Session,
    new_summary: str | None,
    memories: list,
) -> str:
    """组装画像演化提示词的用户输入文本（现有画像 + 摘要 + 新记忆）。"""
    profiles = db.scalars(
        select(Profile)
        .where(Profile.status.in_(["candidate", "confirmed", "corrected", "rejected"]))
        .order_by(Profile.id)
    ).all()

    lines = ["【现有画像列表】"]
    if profiles:
        for p in profiles:
            status_note = (
                "（用户已否定，禁止重建相似内容）" if p.status == "rejected" else ""
            )
            lines.append(f"#{p.id} [{p.category} | {p.status}]{status_note} {p.content}")
    else:
        lines.append("（暂无画像）")

    lines.append("")
    lines.append("【本次会话摘要】")
    lines.append(new_summary if new_summary else "（无）")

    lines.append("")
    lines.append("【本次新记忆】")
    if memories:
        for mem in memories:
            lines.append(f"- [{mem.type} | 重要性 {mem.importance}] {mem.content}")
    else:
        lines.append("（无）")

    return "\n".join(lines)


def _apply_create(
    db: Session,
    op_data: dict,
    memories: list,
    supersedes_profile_id: int | None = None,
    forced_category: str | None = None,
    forced_confidence: int | None = None,
) -> bool:
    """执行 CREATE 操作：校验、去重、rejected 兜底后创建候选画像。"""
    category = forced_category or op_data.get("category", "other")
    if category not in PROFILE_CATEGORIES:
        category = "other"

    content = str(op_data.get("content") or op_data.get("new_content") or "").strip()
    if len(content) < 5:
        return False
    content = content[:_PROFILE_CONTENT_MAX_CHARS]

    evidence = str(op_data.get("evidence") or "").strip()[:512]

    if forced_confidence is not None:
        confidence = forced_confidence
    else:
        confidence = op_data.get("confidence", 50)
        if not isinstance(confidence, int):
            confidence = 50
        # 与演化提示词的置信度规则对齐：多证据最高 70，证据薄弱最高 30
        confidence = min(max(confidence, 0), 70 if len(evidence) > 10 else 30)

    # 程序级兜底：禁止自动重建用户已否定的画像（prompt 标注不可信）
    if matches_rejected_profile(db, content):
        logger.info("画像 CREATE 跳过: 与已否定画像相似")
        return False

    if check_duplicate_profile(
        db, category, content, exclude_profile_id=supersedes_profile_id,
    ):
        return False

    # 同一旧画像最多保留一个候选修订版
    if supersedes_profile_id is not None:
        existing_revision = db.scalar(
            select(Profile).where(
                Profile.supersedes_profile_id == supersedes_profile_id,
                Profile.status == "candidate",
            ).limit(1)
        )
        if existing_revision is not None:
            return False

    evidence_memory = _find_evidence_memory(evidence, memories)
    create_candidate_profile(db, ProfileCreate(
        category=category,
        content=content,
        confidence=confidence,
        is_auto_extracted=1,
        memory_ids=[evidence_memory.id] if evidence_memory else [],
        evidence_texts=[evidence] if evidence else [],
        supersedes_profile_id=supersedes_profile_id,
    ))
    return True


def _apply_reinforce(
    db: Session,
    op_data: dict,
    memories: list,
    source_session_id: int | None,
) -> bool:
    """执行 REINFORCE 操作：追加证据，按程序规则步进置信度。"""
    profile_id = op_data.get("profile_id")
    if not isinstance(profile_id, int):
        return False
    profile = db.get(Profile, profile_id)
    if profile is None or profile.status not in ("candidate", "confirmed", "corrected"):
        return False

    evidence = str(op_data.get("evidence") or "").strip()[:512]
    if not evidence:
        return False

    # 幂等保护：相同证据已存在则整体跳过（任务重试场景）
    duplicate_evidence = db.scalar(
        select(ProfileSource).where(
            ProfileSource.profile_id == profile_id,
            ProfileSource.evidence_text == evidence,
        ).limit(1)
    )
    if duplicate_evidence is not None:
        return False

    # 防刷分：同一会话来源最多贡献一次置信度提升
    session_already_counted = False
    if source_session_id is not None:
        session_already_counted = db.scalar(
            select(ProfileSource)
            .join(Memory, Memory.id == ProfileSource.memory_id)
            .where(
                ProfileSource.profile_id == profile_id,
                Memory.session_id == source_session_id,
            ).limit(1)
        ) is not None

    evidence_memory = _find_evidence_memory(evidence, memories)
    db.add(ProfileSource(
        profile_id=profile_id,
        source_type="extraction",
        memory_id=evidence_memory.id if evidence_memory else None,
        content_preview=evidence[:200],
        evidence_text=evidence,
    ))

    # corrected 画像的置信度由用户设定，系统只追加证据不覆盖
    if profile.status != "corrected" and not session_already_counted:
        new_confidence = min(profile.confidence + _REINFORCE_STEP, _REINFORCE_CAP)
        if new_confidence != profile.confidence:
            db.add(ProfileRevision(
                profile_id=profile_id,
                previous_category=profile.category,
                previous_content=profile.content,
                previous_confidence=profile.confidence,
                previous_status=profile.status,
                changed_by="system",
            ))
            profile.confidence = new_confidence

    commit_or_rollback(db)
    logger.info(f"强化画像: id={profile_id}, confidence={profile.confidence}")
    return True


def _apply_revise(
    db: Session,
    op_data: dict,
    memories: list,
) -> bool:
    """执行 REVISE 操作：候选画像直接修正，已确认画像生成候选修订版。"""
    profile_id = op_data.get("profile_id")
    if not isinstance(profile_id, int):
        return False
    profile = db.get(Profile, profile_id)
    if profile is None or profile.status in ("rejected", "deleted"):
        return False

    new_content = str(op_data.get("new_content") or op_data.get("content") or "").strip()
    if len(new_content) < 5:
        return False
    new_content = new_content[:_PROFILE_CONTENT_MAX_CHARS]

    if new_content == profile.content:
        return False

    if profile.status == "candidate":
        db.add(ProfileRevision(
            profile_id=profile_id,
            previous_category=profile.category,
            previous_content=profile.content,
            previous_confidence=profile.confidence,
            previous_status=profile.status,
            changed_by="system",
        ))
        profile.content = new_content
        profile.version += 1
        commit_or_rollback(db)
        logger.info(f"修正候选画像: id={profile_id}, version={profile.version}")
        return True

    # confirmed/corrected 的内容经用户确认，系统不直接改，生成候选修订版供用户复核
    return _apply_create(
        db, op_data, memories,
        supersedes_profile_id=profile.id,
        forced_category=profile.category,
        forced_confidence=min(profile.confidence, 60),
    )


def _find_evidence_memory(evidence: str, memories: list):
    """根据证据文本匹配来源记忆（内容互相包含即视为匹配）。"""
    if not evidence:
        return None
    for mem in memories:
        content = mem.content or ""
        if content and (evidence in content or content in evidence):
            return mem
    return None


def _is_similar_content(normalized_a: str, normalized_b: str) -> bool:
    """判断两段标准化画像文本是否相同或高度相似。"""
    if normalized_a == normalized_b:
        return True
    return SequenceMatcher(
        None, normalized_a, normalized_b,
    ).ratio() >= _CROSS_SOURCE_DUPLICATE_THRESHOLD


def _parse_extraction_result(text: str) -> dict | None:
    """解析模型返回的 JSON 结果。"""
    text = text.strip()

    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试从 ```json ... ``` 代码块提取
    if "```" in text:
        import re

        matches = re.findall(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

    # 尝试找到第一个 { 和最后一个 }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None


def _get_profile_or_error(db: Session, profile_id: int) -> Profile:
    """获取画像实体，不存在时抛出异常。"""
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, f"画像不存在: {profile_id}")
    return profile


def _query_active_hours(db: Session, since: datetime) -> list[dict]:
    """查询活跃时段分布（按小时）。"""
    rows = db.execute(
        select(
            func.strftime("%H", Activity.started_at).label("hour"),
            func.count().label("count"),
        )
        .where(
            Activity.created_at >= since,
            Activity.privacy_action == "allowed",
        )
        .group_by("hour")
        .order_by("hour")
    ).all()

    # 补齐 24 小时，值为 0
    hour_counts = {int(r[0]): r[1] for r in rows}
    return [
        {"hour": h, "count": hour_counts.get(h, 0)} for h in range(24)
    ]


def _query_app_usage(db: Session, since: datetime) -> list[dict]:
    """查询应用使用分布（按应用聚合时长，取 Top 10）。"""
    rows = db.execute(
        select(
            Activity.app_name,
            func.sum(Activity.duration_seconds).label("total_seconds"),
        )
        .where(
            Activity.created_at >= since,
            Activity.privacy_action == "allowed",
            Activity.duration_seconds.isnot(None),
        )
        .group_by(Activity.app_name)
        .order_by(func.sum(Activity.duration_seconds).desc())
        .limit(10)
    ).all()

    if not rows:
        return []

    total_seconds = sum(r[1] or 0 for r in rows)
    if total_seconds == 0:
        return []

    result = []
    for r in rows:
        total_minutes = round((r[1] or 0) / 60, 1)
        percentage = round((r[1] or 0) / total_seconds * 100, 1)
        result.append({
            "app_name": r[0],
            "total_minutes": total_minutes,
            "percentage": percentage,
        })

    return result


def _query_chat_activity(db: Session, since: datetime) -> list[dict]:
    """查询用户对话活跃度（按日期聚合用户主动发送次数）。

    一轮对话会同时保存用户消息和助手回复；活跃度应反映用户的主动发言，
    因此不计入 assistant/system 消息。
    """
    rows = db.execute(
        select(
            func.date(Message.created_at).label("date"),
            func.count().label("count"),
        )
        .where(
            Message.created_at >= since,
            Message.status == "completed",
            Message.role == "user",
        )
        .group_by(func.date(Message.created_at))
        .order_by(func.date(Message.created_at))
    ).all()

    return [
        {"date": str(r[0]), "message_count": r[1]}
        for r in rows
    ]
