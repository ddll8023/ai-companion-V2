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
from app.models.persona import Insight, InsightEvidence, InsightRevision, Observation, PersonaDocument, PersonaState
from app.schemas.common import ErrorCode
from app.schemas.persona import InsightCorrection, InsightListQuery, ObservationListQuery, PersonaDocumentEdit
from app.services import model_provider
from app.services.embedding import embed_text, serialize_embedding
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
    """基于观察调用模型并自动演化洞见。"""
    observations = db.scalars(select(Observation).where(Observation.is_deleted.is_(False), Observation.reflected_at.is_(None)).order_by(Observation.id).limit(100)).all()
    if not force and len(observations) < 15:
        return {"observations": len(observations), "insights_changed": 0, "reason": "观察数量未达到反思阈值"}
    if not observations:
        return {"observations": 0, "insights_changed": 0, "reason": "暂无新观察"}
    config = model_provider.get_active_config(db)
    if config is None:
        return {"error": "无激活的模型配置"}
    from app.prompts.persona import REFLECTION_PROMPT
    material = "\n".join(f"[O{o.id}] [{o.dimension}] {o.content}（证据：{o.evidence}）" for o in observations)
    result = model_provider.chat_sync(provider=config.provider, model_name=config.model_name, api_key=api_key, api_base=config.api_base, system_prompt=REFLECTION_PROMPT, messages=[{"role": "user", "content": material}], timeout=model_provider.SYNC_TIMEOUT_BACKGROUND)
    parsed = _parse_json(result) or {}
    changed = 0
    for item in (parsed.get("insights") or [])[:20]:
        ids = [value for value in item.get("cited_observation_ids", []) if isinstance(value, int)]
        cited = [o for o in observations if o.id in ids]
        if not cited or not str(item.get("content") or "").strip():
            continue
        insight = Insight(insight_type=str(item.get("insight_type") or "pattern"), dimension=str(item.get("dimension") or "其他")[:64], content=str(item["content"])[:2000], confidence=min(max(int(item.get("confidence", 30)), 0), 95), stability_score=min(max(len(cited) * 15, 10), 95), support_count=len(cited), maturity="developing" if len(cited) >= 2 else "emerging")
        db.add(insight)
        db.flush()
        db.add_all([InsightEvidence(insight_id=insight.id, observation_id=o.id) for o in cited])
        changed += 1
    for observation in observations:
        observation.reflected_at = datetime.now()
    commit_or_rollback(db)
    return {"observations": len(observations), "insights_changed": changed}


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
    """根据已建立洞见汇编人物侧写。"""
    insights = db.scalars(select(Insight).where(Insight.maturity.in_(["established", "developing"])).order_by(desc(Insight.confidence), Insight.id)).all()
    if not insights:
        return {"compiled": False, "reason": "暂无可汇编洞见"}
    config = model_provider.get_active_config(db)
    if config is None:
        return {"error": "无激活的模型配置"}
    current = get_active_document(db)
    old = current.content if current else "（暂无人物侧写）"
    material = "\n".join(f"[I{i.id}] [{i.dimension}] {i.content}（置信度 {i.confidence}）" for i in insights)
    from app.prompts.persona import COMPILATION_PROMPT
    result = model_provider.chat_sync(provider=config.provider, model_name=config.model_name, api_key=api_key, api_base=config.api_base, system_prompt=COMPILATION_PROMPT, messages=[{"role": "user", "content": f"【旧侧写】\n{old}\n\n【洞见】\n{material}"}], timeout=model_provider.SYNC_TIMEOUT_BACKGROUND)
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
    document = PersonaDocument(content=content[:20000], cited_insight_ids=cited, version=version, change_summary=str(parsed.get("change_summary") or "洞见发生变化"), edited_by="system")
    db.add(document)
    commit_or_rollback(db)
    return {"compiled": True, "document_id": document.id, "version": version}


    """获取活动和对话行为统计。"""
    since = datetime.now() - timedelta(days=days)
    from app.models.activity import Activity
    hours = db.execute(select(func.strftime("%H", Activity.started_at), func.count(Activity.id)).where(Activity.started_at >= since).group_by(func.strftime("%H", Activity.started_at)).order_by(func.strftime("%H", Activity.started_at))).all()
    apps = db.execute(select(Activity.app_name, func.sum(Activity.duration_seconds)).where(Activity.started_at >= since).group_by(Activity.app_name).order_by(func.sum(Activity.duration_seconds).desc()).limit(10)).all()
    total = sum((row[1] or 0) for row in apps)
    activity = db.execute(select(func.date(Message.created_at), func.count(Message.id)).where(Message.created_at >= since).group_by(func.date(Message.created_at)).order_by(func.date(Message.created_at))).all()
    return {"active_hours": [{"hour": int(hour), "count": count} for hour, count in hours], "app_usage": [{"app_name": name or "未知", "duration_seconds": duration or 0, "percentage": round((duration or 0) / total * 100, 1) if total else 0} for name, duration in apps], "chat_activity": [{"date": str(date), "message_count": count} for date, count in activity]}
