"""人物理解业务服务。"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.database import commit_or_rollback, paginate_query
from app.models.chat import Message
from app.models.conversation import SessionSummary
from app.models.memory import Memory
from app.models.persona import Insight, InsightEvidence, InsightRelation, InsightRevision, Observation, PersonaDocument, PersonaState
from app.schemas.common import ErrorCode
from app.schemas.persona import InsightCorrection, InsightListQuery, ObservationListQuery, PersonaDocumentEdit
from app.services import model_provider
from app.services.embedding import cosine_similarity, deserialize_embedding, embed_text, serialize_embedding
from app.utils.exception import ServiceException
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)


def _parse_json(text: str) -> dict | None:
    """宽松解析模型返回的 JSON。"""
    text = (text or "").strip()
    for candidate in (text, re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.S),):
        value = candidate.group(1) if hasattr(candidate, "group") else candidate
        try:
            return json.loads(value.strip())
        except (json.JSONDecodeError, AttributeError):
            continue
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


def save_observations(db: Session, observations: list[dict], session_id: int | None = None) -> int:
    """校验并保存一批观察。"""
    created = 0
    recent = list(db.scalars(select(Observation).where(Observation.created_at >= datetime.now() - timedelta(days=30), Observation.is_deleted.is_(False))).all())
    for item in observations[:30]:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        evidence = str(item.get("evidence") or "").strip()
        source_id = item.get("source_message_id")
        source = db.get(Message, source_id) if isinstance(source_id, int) else None
        if not content or not evidence or source is None or source.role != "user" or evidence not in source.content:
            continue
        normalized = re.sub(r"\W+", "", content).casefold()
        if any(SequenceMatcher(None, normalized, re.sub(r"\W+", "", old.content).casefold()).ratio() >= 0.88 for old in recent):
            continue
        observation = Observation(
            observation_type=str(item.get("observation_type") or "content"),
            dimension=str(item.get("dimension") or "其他")[:64],
            content=content[:2000],
            session_id=session_id,
            source_message_id=source.id,
            evidence=evidence[:512],
            embedding=serialize_embedding(embed_text(content)),
        )
        db.add(observation)
        recent.append(observation)
        created += 1
    if created:
        commit_or_rollback(db)
    return created


def list_observations(db: Session, query: ObservationListQuery):
    """分页查询观察。"""
    stmt = select(Observation).where(Observation.is_deleted.is_(False))
    if query.dimension:
        stmt = stmt.where(Observation.dimension == query.dimension)
    if query.observation_type:
        stmt = stmt.where(Observation.observation_type == query.observation_type)
    if query.keyword:
        stmt = stmt.where(Observation.content.contains(query.keyword))
    return paginate_query(db, stmt, query.page, query.page_size, response_class=None, ordering=Observation.id.desc(), transform=lambda item: item)


def delete_observation(db: Session, observation_id: int) -> None:
    """软删除观察并使失去证据的洞见降级。"""
    observation = db.get(Observation, observation_id)
    if observation is None:
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, "观察不存在")
    observation.is_deleted = True
    evidence = db.scalars(select(InsightEvidence).where(InsightEvidence.observation_id == observation_id, InsightEvidence.is_valid.is_(True))).all()
    for item in evidence:
        item.is_valid = False
        insight = db.get(Insight, item.insight_id)
        if insight and not db.scalar(select(InsightEvidence.id).where(InsightEvidence.insight_id == insight.id, InsightEvidence.is_valid.is_(True), InsightEvidence.id != item.id)):
            insight.maturity = "declining"
            insight.confidence = min(insight.confidence, 30)
    commit_or_rollback(db)


def list_insights(db: Session, query: InsightListQuery):
    """分页查询洞见。"""
    stmt = select(Insight).where(Insight.maturity.not_in(["rejected", "superseded"]))
    if query.maturity:
        stmt = stmt.where(Insight.maturity == query.maturity)
    if query.dimension:
        stmt = stmt.where(Insight.dimension == query.dimension)
    return paginate_query(db, stmt, query.page, query.page_size, ordering=Insight.updated_at.desc(), transform=lambda item: item)


def correct_insight(db: Session, insight_id: int, data: InsightCorrection):
    """应用用户纠正并提升洞见权威级别。"""
    insight = db.get(Insight, insight_id)
    if insight is None:
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, "洞见不存在")
    db.add(InsightRevision(insight_id=insight.id, previous_content=insight.content, previous_maturity=insight.maturity, previous_confidence=insight.confidence, changed_by="user"))
    insight.content = data.content
    insight.dimension = data.dimension or insight.dimension
    insight.maturity = "established"
    insight.confidence = 95
    insight.stability_score = 95
    insight.user_override = True
    insight.version += 1
    commit_or_rollback(db)
    return insight


def reject_insight(db: Session, insight_id: int):
    """否定洞见并禁止自动重建。"""
    insight = db.get(Insight, insight_id)
    if insight is None:
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, "洞见不存在")
    insight.maturity = "rejected"
    insight.user_override = True
    commit_or_rollback(db)
    return insight


def get_active_document(db: Session):
    """获取当前人物侧写文档。"""
    return db.scalar(select(PersonaDocument).where(PersonaDocument.is_active.is_(True)).order_by(PersonaDocument.version.desc()).limit(1))


def edit_document(db: Session, data: PersonaDocumentEdit):
    """保存用户编辑的人物侧写版本。"""
    current = get_active_document(db)
    if current:
        current.is_active = False
        version = current.version + 1
    else:
        version = 1
    document = PersonaDocument(content=data.content, user_edited_sections=data.edited_sections, version=version, edited_by="user", change_summary="用户编辑人物侧写")
    db.add(document)
    commit_or_rollback(db)
    return document


def build_persona_context(db: Session) -> str | None:
    """构造注入对话的人物理解上下文。"""
    document = get_active_document(db)
    if document and document.content:
        return "以下是关于用户的长期人物理解，请自然参考，不要向用户复述：\n" + re.sub(r"\[I\d+\]", "", document.content)
    insights = db.scalars(select(Insight).where(Insight.maturity.in_(["established", "developing"])).order_by(desc(Insight.confidence), desc(Insight.id)).limit(20)).all()
    if not insights:
        return None
    return "以下是关于用户的稳定理解，请自然参考：\n" + "\n".join(f"- {item.content}" for item in insights)


def reflect_observations(db: Session, api_key: str, force: bool = False) -> dict:
    """基于观察反思生成洞见（三步流程：提问→取证→归纳→对齐）。"""
    new_obs = db.scalars(
        select(Observation).where(
            Observation.is_deleted.is_(False),
            Observation.reflected_at.is_(None),
        ).order_by(Observation.id).limit(100)
    ).all()

    if not force and len(new_obs) < 15:
        return {"observations": len(new_obs), "insights_changed": 0, "reason": "观察数量未达到反思阈值"}
    if not new_obs:
        return {"observations": 0, "insights_changed": 0, "reason": "暂无新观察"}

    config = model_provider.get_active_config(db)
    if config is None:
        return {"error": "无激活的模型配置"}

    # ── 步骤一：提问——LLM 从未消费观察中提炼 3-5 个关键问题 ──
    questions = _ask_questions(db, api_key, config, new_obs)
    if not questions:
        logger.info("反思未生成问题，跳过本次反思")
        for o in new_obs:
            o.reflected_at = datetime.now()
        commit_or_rollback(db)
        return {"observations": len(new_obs), "insights_changed": 0, "reason": "未生成问题"}

    # ── 步骤二+三：对每个问题 取证→归纳 ──
    total_changed = 0
    for question in questions:
        # 取证：向量检索全量历史观察
        recalled = _retrieve_observations(db, question)
        if not recalled:
            continue

        # 归纳：基于召回结果回答问题，产出洞见
        insights = _answer_question(db, api_key, config, question, recalled, new_obs)
        if not insights:
            continue

        # 演化对齐：每条洞见与现有洞见比较
        for item in insights:
            if _align_insight(db, item, new_obs):
                total_changed += 1

    # ── 收尾 ──
    for o in new_obs:
        o.reflected_at = datetime.now()

    # 若产生新洞见，自动触发档案汇编（带防抖）
    if total_changed > 0:
        _schedule_compile(db)

    # 检查二级反思条件（confirmed level-1 ≥ 10 且无活跃二级洞见）
    _reflect_level2_if_applicable(db, api_key, config)

    commit_or_rollback(db)
    return {"observations": len(new_obs), "insights_changed": total_changed}


# ═══════════════════════════════════════════════════════════════════
# 反思三步流程辅助函数
# ═══════════════════════════════════════════════════════════════════


def _ask_questions(db: Session, api_key: str, config, observations: list[Observation]) -> list[str]:
    """步骤一：LLM 阅读未消费观察，生成 3-5 个关键问题。"""
    from app.prompts.persona import REFLECTION_QUESTION_PROMPT

    material = "\n".join(f"[O{o.id}] [{o.dimension}] {o.content}（证据：{o.evidence}）" for o in observations)
    result = model_provider.chat_sync(
        provider=config.provider, model_name=config.model_name,
        api_key=api_key, api_base=config.api_base,
        system_prompt=REFLECTION_QUESTION_PROMPT,
        messages=[{"role": "user", "content": material}],
        timeout=model_provider.SYNC_TIMEOUT_BACKGROUND,
    )
    parsed = _parse_json(result) or {}
    return parsed.get("questions", [])[:5]


def _retrieve_observations(db: Session, question: str, top_k: int = 20) -> list[Observation]:
    """步骤二：对问题做向量检索，从全量历史观察中召回最相关的观察。

    使用问题的嵌入向量与每条观察的存储向量计算余弦相似度，取 Top K。
    全量 O(n) 遍历，当前观察表量级下可接受。
    """
    question_vec = embed_text(question)
    if question_vec is None:
        logger.warning("问题向量化失败，跳过向量检索")
        return []

    all_obs = db.scalars(
        select(Observation).where(
            Observation.is_deleted.is_(False),
            Observation.embedding.isnot(None),
        )
    ).all()

    scored = []
    for obs in all_obs:
        obs_vec = deserialize_embedding(obs.embedding)
        if obs_vec is None:
            continue
        sim = cosine_similarity(question_vec, obs_vec)
        scored.append((sim, obs))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [obs for _, obs in scored[:top_k]]


def _answer_question(
    db: Session, api_key: str, config,
    question: str, recalled: list[Observation],
    new_obs: list[Observation],
) -> list[dict]:
    """步骤三：LLM 基于召回结果回答问题，产出洞见数据。"""
    from app.prompts.persona import REFLECTION_ANSWER_PROMPT

    # 召回结果（新旧观察混合）
    all_material = "\n".join(
        f"[O{o.id}] [{o.dimension}] {o.content}（证据：{o.evidence}）"
        for o in recalled
    )

    # 现有洞见（避免重复）
    existing = db.scalars(
        select(Insight).where(Insight.maturity.not_in(["rejected", "superseded"])).limit(50)
    ).all()
    existing_text = "\n".join(
        f"[I{i.id}] [{i.dimension}] {i.content}（成熟度：{i.maturity}）"
        for i in existing
    ) or "无"

    # 被否定的洞见（禁止重建）
    rejected = db.scalars(
        select(Insight).where(Insight.maturity == "rejected").limit(30)
    ).all()
    rejected_text = "\n".join(f"[I{i.id}] {i.content}" for i in rejected) or "无"

    user_content = f"""回答以下问题：{question}

观察记录：
{all_material}

已有洞见：
{existing_text}

被用户否定的洞见（禁止再次提出）：
{rejected_text}"""

    result = model_provider.chat_sync(
        provider=config.provider, model_name=config.model_name,
        api_key=api_key, api_base=config.api_base,
        system_prompt=REFLECTION_ANSWER_PROMPT,
        messages=[{"role": "user", "content": user_content}],
        timeout=model_provider.SYNC_TIMEOUT_BACKGROUND,
    )
    parsed = _parse_json(result) or {}
    return parsed.get("insights", [])[:5]


def _align_insight(db: Session, item: dict, new_obs: list[Observation]) -> bool:
    """演化对齐：将单条洞见数据与现有洞见比较，执行新建 / 增强 / 修订决策。"""
    content = str(item.get("content") or "").strip()
    if not content:
        return False

    dimension = str(item.get("dimension") or "其他")[:64]
    insight_type = str(item.get("insight_type") or "pattern")
    confidence = min(max(int(item.get("confidence", 30)), 0), 95)

    cited_ids = [v for v in item.get("cited_observation_ids", []) if isinstance(v, int)]
    cited_obs = [o for o in new_obs if o.id in cited_ids]
    if not cited_obs:
        return False

    normalized = re.sub(r"\W+", "", content).casefold()

    # 1) 检查是否与被否定的洞见相似
    rejected_all = db.scalars(
        select(Insight).where(Insight.maturity == "rejected")
    ).all()
    for rp in rejected_all:
        if SequenceMatcher(None, normalized, re.sub(r"\W+", "", rp.content).casefold()).ratio() >= 0.88:
            logger.info("洞见与被否定洞见相似，跳过: rejected_id=%s", rp.id)
            return False

    # 2) 检查是否与现有非终态洞见相关（支持 / 矛盾）
    existing = db.scalars(
        select(Insight).where(Insight.maturity.not_in(["rejected", "superseded"]))
    ).all()
    for ex in existing:
        ratio = SequenceMatcher(None, normalized, re.sub(r"\W+", "", ex.content).casefold()).ratio()
        if ratio >= 0.80:
            # 支持现有洞见：追加证据 + 步进置信度
            ex.support_count += len(cited_obs)
            ex.confidence = min(ex.confidence + 10 * len(cited_obs), 95)
            ex.stability_score = min(ex.stability_score + 5 * len(cited_obs), 95)
            if ex.maturity == "emerging" and len(cited_obs) >= 2:
                ex.maturity = "developing"

            db.add_all([InsightEvidence(insight_id=ex.id, observation_id=o.id) for o in cited_obs])
            logger.info("洞见已增强: insight_id=%s confidence=%s", ex.id, ex.confidence)
            return True

    # 3) 无匹配 → 新建
    insight = Insight(
        insight_type=insight_type,
        dimension=dimension,
        content=content[:2000],
        confidence=confidence,
        stability_score=min(max(len(cited_obs) * 15, 10), 95),
        support_count=len(cited_obs),
        maturity="developing" if len(cited_obs) >= 2 else "emerging",
    )
    db.add(insight)
    db.flush()
    db.add_all([InsightEvidence(insight_id=insight.id, observation_id=o.id) for o in cited_obs])
    logger.info("新建洞见: id=%s dimension=%s", insight.id, dimension)
    return True


def _schedule_compile(db: Session) -> None:
    """防抖触发档案汇编任务。"""
    from app.schemas.task import TaskCreate
    from app.services import task as services_task

    existing = services_task.find_active_task(db, "persona.compile", "persona.compile:auto")
    if existing is not None:
        logger.debug("compile 任务已存在（防抖），跳过触发")
        return

    task = services_task.create_task(
        db, TaskCreate(
            task_type="persona.compile",
            payload="{}",
            dedup_key="persona.compile:auto",
            priority=2,
        )
    )
    logger.info("自动触发档案汇编任务: task_id=%s", task.id)


def _reflect_level2_if_applicable(db: Session, api_key: str, config) -> None:
    """检查并执行二级反思：当 confirmed level-1 洞见 ≥ 10 条且无活跃二级洞见时触发。"""
    total_established = db.scalar(
        select(func.count(Insight.id)).where(
            Insight.maturity == "established",
            Insight.abstraction_level == 1,
        )
    ) or 0
    if total_established < 10:
        return

    # 已有活跃二级洞见则跳过（避免短期内反复触发）
    has_level2 = db.scalar(
        select(Insight.id).where(
            Insight.abstraction_level == 2,
            Insight.maturity.not_in(["rejected", "superseded"]),
        ).limit(1)
    )
    if has_level2:
        return

    from app.prompts.persona import LEVEL2_REFLECTION_PROMPT

    level1 = db.scalars(
        select(Insight).where(
            Insight.maturity == "established",
            Insight.abstraction_level == 1,
        ).order_by(desc(Insight.confidence))
    ).all()

    material = "\n".join(f"[I{i.id}] [{i.dimension}] {i.content}（置信度：{i.confidence}）" for i in level1)
    result = model_provider.chat_sync(
        provider=config.provider, model_name=config.model_name,
        api_key=api_key, api_base=config.api_base,
        system_prompt=LEVEL2_REFLECTION_PROMPT,
        messages=[{"role": "user", "content": f"一级洞见列表：\n{material}\n\n请基于以上一级洞见做归纳的归纳，产出核心洞见。"}],
        timeout=model_provider.SYNC_TIMEOUT_BACKGROUND,
    )
    parsed = _parse_json(result) or {}
    created = 0
    for item in (parsed.get("insights") or [])[:5]:
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        insight = Insight(
            insight_type=str(item.get("insight_type") or "core_pattern"),
            dimension=str(item.get("dimension") or "核心")[:64],
            content=content[:2000],
            abstraction_level=2,
            confidence=min(max(int(item.get("confidence", 60)), 0), 95),
            stability_score=80,
            support_count=3,
            maturity="developing",
        )
        db.add(insight)
        db.flush()

        # 关联引用的一级洞见
        cited_ids = [v for v in (item.get("cited_layer1_ids") or []) if isinstance(v, int)]
        for l1_id in cited_ids:
            if db.get(Insight, l1_id):
                db.add(InsightRelation(
                    insight_id=insight.id,
                    related_insight_id=l1_id,
                    relation_type="refines",
                ))
        created += 1

    if created > 0:
        logger.info("二级反思完成: 核心洞见=%s", created)
        _schedule_compile(db)


def extract_session_observations(db: Session, api_key: str, session_id: int, from_message_id: int, to_message_id: int) -> dict:
    """从会话区间提取内容观察和表达观察。"""
    messages = db.scalars(select(Message).where(Message.session_id == session_id, Message.id >= from_message_id, Message.id <= to_message_id, Message.role.in_(["user", "assistant"]), Message.status == "completed").order_by(Message.id)).all()
    users = [message for message in messages if message.role == "user"]
    if not users:
        return {"created": 0, "reason": "没有用户消息"}
    config = model_provider.get_active_config(db)
    if config is None:
        return {"error": "无激活的模型配置"}
    from app.prompts.persona import CONTENT_OBSERVATION_PROMPT, EXPRESSION_OBSERVATION_PROMPT
    transcript = "\n".join(f"[{message.role} #{message.id}] {message.content}" for message in messages)
    created = 0
    for prompt in (CONTENT_OBSERVATION_PROMPT, EXPRESSION_OBSERVATION_PROMPT):
        result = model_provider.chat_sync(provider=config.provider, model_name=config.model_name, api_key=api_key, api_base=config.api_base, system_prompt=prompt, messages=[{"role": "user", "content": transcript}], timeout=model_provider.SYNC_TIMEOUT_BACKGROUND)
        parsed = _parse_json(result) or {}
        created += save_observations(db, parsed.get("observations") or [], session_id)
    return {"created": created}


def compile_document(db: Session, api_key: str) -> dict:
    """根据已建立洞见汇编人物侧写（含防漂移：引用锚定 + 熔断 + 用户编辑保护）。"""
    insights = db.scalars(select(Insight).where(Insight.maturity.in_(["established", "developing"])).order_by(desc(Insight.confidence), Insight.id)).all()
    if not insights:
        return {"compiled": False, "reason": "暂无可汇编洞见"}
    config = model_provider.get_active_config(db)
    if config is None:
        return {"error": "无激活的模型配置"}
    current = get_active_document(db)
    old = current.content if current else "（暂无人物侧写）"

    # 用户编辑保护：注入已编辑段落到模型上下文
    user_note = ""
    if current and current.user_edited_sections:
        user_note = f'\n\n【用户手动编辑 - 必须原文保留，不得修改或合并】\n{json.dumps(current.user_edited_sections, ensure_ascii=False, indent=2)}'

    material = "\n".join(f"[I{i.id}] [{i.dimension}] {i.content}（置信度 {i.confidence}）" for i in insights)
    from app.prompts.persona import COMPILATION_PROMPT
    result = model_provider.chat_sync(provider=config.provider, model_name=config.model_name, api_key=api_key, api_base=config.api_base, system_prompt=COMPILATION_PROMPT, messages=[{"role": "user", "content": f"【旧侧写】\n{old}{user_note}\n\n【洞见】\n{material}"}], timeout=model_provider.SYNC_TIMEOUT_BACKGROUND)
    parsed = _parse_json(result) or {}
    content = str(parsed.get("content") or "").strip()
    if not content:
        return {"error": "模型未生成侧写"}
    cited = [int(value) for value in re.findall(r"\[I(\d+)\]", content) if any(item.id == int(value) for item in insights)]
    if not cited:
        return {"error": "侧写缺少有效洞见引用"}
    if current:
        current.is_active = False
        version = current.version + 1
    else:
        version = 1

    # 防漂移-熔断：变更幅度 >50% 时不自动激活，待用户审核
    is_pending = False
    if current and current.content:
        old_clean = re.sub(r"\s+", "", current.content)
        new_clean = re.sub(r"\s+", "", content)
        ratio = SequenceMatcher(None, old_clean, new_clean).ratio()
        change_ratio = 1 - ratio
        if change_ratio > 0.5:
            is_pending = True

    if is_pending:
        document = PersonaDocument(
            content=content[:20000], cited_insight_ids=cited,
            version=version,
            change_summary=str(parsed.get("change_summary") or f"变更幅度较大（{change_ratio:.0%}），待用户审核"),
            edited_by="system",
            is_active=False, is_pending_review=True,
        )
    else:
        document = PersonaDocument(
            content=content[:20000], cited_insight_ids=cited,
            version=version,
            change_summary=str(parsed.get("change_summary") or "洞见发生变化"),
            edited_by="system",
        )

    db.add(document)
    commit_or_rollback(db)
    return {"compiled": True, "document_id": document.id, "version": version, "pending_review": is_pending}
