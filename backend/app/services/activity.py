"""活动记录与隐私规则服务。

职责：
- 活动事件接收、校验、去重、脱敏和入库
- 隐私规则引擎（评估是否允许采集）
- 活动记录查询、统计和删除
- 基础审计记录
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date, datetime, timedelta

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from app.core.database import commit_or_rollback
from app.models.activity import Activity, PrivacyRule
from app.schemas.activity import (
    ActivityEvent,
    ActivityListQuery,
    ActivityResponse,
    ActivityStats,
    PrivacyEvaluateRequest,
    PrivacyEvaluateResult,
    PrivacyRuleCreate,
    PrivacyRuleListQuery,
    PrivacyRuleResponse,
    PrivacyRuleUpdate,
)
from app.schemas.common import ErrorCode, PaginatedResponse, PaginationInfo
from app.services.audit import record_audit
from app.utils.exception import ServiceException
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)


# ── 活动事件处理 ────────────────────────────────────────────────────────────────


def submit_activity_events(
    db: Session,
    events: list[ActivityEvent],
) -> int:
    """批量提交活动事件。

    对事件进行校验、去重、隐私规则评估和脱敏处理后入库。

    Args:
        db: 数据库会话
        events: 活动事件列表

    Returns:
        成功入库的事件数量

    Raises:
        ServiceException: 参数错误
    """
    if not events:
        return 0

    saved_count = 0
    for event in events:
        try:
            _process_single_event(db, event)
            saved_count += 1
        except Exception as exc:
            logger.warning(
                f"活动事件处理失败: app={event.app_name}, "
                f"source_id={event.source_id}, error={exc}",
            )
            # 单个事件异常不影响批量提交

    if saved_count > 0:
        commit_or_rollback(db)

    logger.info(f"活动事件提交: received={len(events)}, saved={saved_count}")
    return saved_count


def _process_single_event(db: Session, event: ActivityEvent) -> None:
    """处理单条活动事件。

    1. 来源去重
    2. 隐私规则评估
    3. 脱敏处理
    4. 入库
    """
    # 去重检查
    if event.source_id:
        existing = db.scalar(
            select(Activity).where(Activity.source_id == event.source_id),
        )
        if existing is not None:
            logger.debug(f"活动事件已存在: source_id={event.source_id}")
            return

    # 隐私规则评估
    evaluate_req = PrivacyEvaluateRequest(
        app_name=event.app_name,
        window_title=event.window_title,
        platform=event.platform,
    )
    eval_result = _evaluate_privacy(db, evaluate_req)

    # 构造活动记录
    activity = Activity(
        app_name=event.app_name,
        window_title=event.window_title,
        started_at=event.started_at,
        ended_at=event.ended_at,
        duration_seconds=event.duration_seconds,
        is_idle=1 if event.is_idle else 0,
        platform=event.platform,
        privacy_action=eval_result.action,
        masked_app_name=eval_result.masked_app_name,
        masked_window_title=eval_result.masked_window_title,
        source_id=event.source_id or _generate_source_id(event),
    )
    db.add(activity)


def _generate_source_id(event: ActivityEvent) -> str:
    """为没有 source_id 的事件生成去重标识。"""
    raw = (
        f"{event.app_name}|{event.started_at.isoformat()}|{event.platform}"
        f"|{event.window_title or ''}|{event.duration_seconds or ''}"
    )
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


# ── 隐私规则引擎 ────────────────────────────────────────────────────────────────


def _deactivate_expired_temp_pauses(
    db: Session,
    rules: list[PrivacyRule],
) -> None:
    """检查并自动禁用已过期的 temp_pause 规则。

    将 temp_pause 的过期检测从 _evaluate_single_rule 中分离出来，
    确保过期规则的禁用状态能被持久化。
    """
    modified = False
    for rule in rules:
        if rule.rule_type != "temp_pause":
            continue
        try:
            pause_config = json.loads(rule.rule_value)
            pause_until = pause_config.get("pause_until")
            if pause_until:
                until_time = datetime.fromisoformat(pause_until)
                if datetime.now() >= until_time:
                    rule.is_active = 0
                    modified = True
                    logger.info(f"临时暂停规则已过期，自动禁用: rule_id={rule.id}")
        except (json.JSONDecodeError, ValueError):
            continue

    if modified:
        db.flush()


def _collect_whitelist_values(
    rules: list[PrivacyRule],
) -> list[str] | None:
    """收集所有白名单规则的值。

    白名单是集合性规则，需要收集所有同类型规则的值才能做包含判断。
    返回 None 表示没有配置白名单规则（即不启用白名单模式）。
    返回非空列表表示启用了白名单模式，只有列表中的应用才允许采集。
    """
    values: list[str] = []
    for rule in rules:
        if rule.rule_type == "app_whitelist":
            for line in rule.rule_value.strip().split("\n"):
                line = line.strip()
                if line:
                    values.append(line)
    return values if values else None


def _evaluate_privacy(
    db: Session,
    req: PrivacyEvaluateRequest,
) -> PrivacyEvaluateResult:
    """隐私规则引擎：按优先级评估给定事件是否允许采集。

    评估流程：
    1. 先处理 temp_pause 过期自动禁用（持久化 side effect）
    2. 白名单模式统一判断（集合性规则）
    3. 其余规则按优先级逐条评估（首次命中即返回）

    Args:
        db: 数据库会话
        req: 评估请求（应用名、窗口标题、平台）

    Returns:
        评估结果（是否允许、处理动作、原因等）
    """
    # 获取所有已启用的规则，按优先级降序排列
    rules = db.scalars(
        select(PrivacyRule)
        .where(PrivacyRule.is_active == 1)
        .order_by(PrivacyRule.priority.desc(), PrivacyRule.id)
    ).all()

    if not rules:
        # 没有配置规则时默认阻断（fail closed — 无法确认安全时停止采集）
        return PrivacyEvaluateResult(allowed=False, action="blocked", reason="无隐私规则，默认阻断")

    # 1. 处理 temp_pause 规则过期自动禁用
    _deactivate_expired_temp_pauses(db, rules)

    # 2. 白名单是集合性规则：先收集所有白名单条目，再统一判断
    whitelist_values = _collect_whitelist_values(rules)
    if whitelist_values is not None:
        # 白名单模式启用时，只有白名单中的应用才允许被采集
        app_name_lower = req.app_name.lower()
        if not any(app_name_lower == wl.lower() for wl in whitelist_values):
            return PrivacyEvaluateResult(
                allowed=False,
                action="blocked",
                reason=f"应用不在白名单中: {req.app_name}",
            )

    # 3. 其余按优先级逐条评估（首次命中即返回）
    for rule in rules:
        if rule.rule_type == "app_whitelist":
            continue  # 白名单已在上面统一处理
        result = _evaluate_single_rule(rule, req)
        if result is not None:
            return result

    # 通过所有规则检查，允许采集
    return PrivacyEvaluateResult(allowed=True, action="allowed")


def _evaluate_single_rule(
    rule: PrivacyRule,
    req: PrivacyEvaluateRequest,
) -> PrivacyEvaluateResult | None:
    """评估单条规则。返回 None 表示规则不适用（继续检查下一条）。"""
    try:
        rule_value = rule.rule_value.strip()

        if rule.rule_type == "global_pause":
            return PrivacyEvaluateResult(
                allowed=False,
                action="blocked",
                reason="全局暂停采集",
                matched_rule_id=rule.id,
            )

        elif rule.rule_type == "app_blacklist":
            if req.app_name.lower() == rule_value.lower():
                return PrivacyEvaluateResult(
                    allowed=False,
                    action="blocked",
                    reason=f"应用在黑名单中: {req.app_name}",
                    matched_rule_id=rule.id,
                )

        elif rule.rule_type == "app_whitelist":
            # 白名单模式：只有白名单中的应用才允许采集
            # 这里用包含匹配，因为可能有多个白名单条目
            pass  # 在批量评估中处理

        elif rule.rule_type == "title_keyword":
            if req.window_title and rule_value.lower() in req.window_title.lower():
                return PrivacyEvaluateResult(
                    allowed=False,
                    action="blocked",
                    reason=f"窗口标题包含敏感关键字: {rule_value}",
                    matched_rule_id=rule.id,
                )

        elif rule.rule_type == "time_based":
            try:
                time_config = json.loads(rule_value)
                start_hour = time_config.get("start_hour")
                end_hour = time_config.get("end_hour")
                current_hour = datetime.now().hour
                if start_hour is not None and end_hour is not None:
                    if start_hour <= current_hour < end_hour:
                        return PrivacyEvaluateResult(
                            allowed=False,
                            action="blocked",
                            reason=f"当前时段 {current_hour}:00 在禁用时段内",
                            matched_rule_id=rule.id,
                        )
            except (json.JSONDecodeError, KeyError):
                logger.warning(f"time_based 规则值解析失败: {rule_value}")

        elif rule.rule_type == "content_masking":
            # 内容脱敏：使用大小写不敏感替换
            if not rule_value:
                return None
            masked_app = None
            masked_title = None
            if req.app_name and rule_value.lower() in req.app_name.lower():
                masked_app = re.sub(
                    re.escape(rule_value), "***", req.app_name,
                    count=1, flags=re.IGNORECASE,
                )
            if req.window_title and rule_value.lower() in req.window_title.lower():
                masked_title = re.sub(
                    re.escape(rule_value), "***", req.window_title,
                    count=1, flags=re.IGNORECASE,
                )
            if masked_app or masked_title:
                return PrivacyEvaluateResult(
                    allowed=True,
                    action="masked",
                    reason=f"内容脱敏: {rule_value}",
                    matched_rule_id=rule.id,
                    masked_app_name=masked_app or req.app_name,
                    masked_window_title=masked_title or req.window_title,
                )

        elif rule.rule_type == "temp_pause":
            # 临时暂停：检查是否在暂停有效期内
            try:
                pause_config = json.loads(rule_value)
                pause_until = pause_config.get("pause_until")
                if pause_until:
                    until_time = datetime.fromisoformat(pause_until)
                    if datetime.now() < until_time:
                        return PrivacyEvaluateResult(
                            allowed=False,
                            action="blocked",
                            reason=f"临时暂停中，直到 {pause_until}",
                            matched_rule_id=rule.id,
                        )
                    # 过期规则由 _deactivate_expired_temp_pauses 统一处理，不在评估中修改
            except (json.JSONDecodeError, ValueError):
                logger.warning(f"temp_pause 规则值解析失败: {rule_value}")

    except Exception as exc:
        logger.warning(f"隐私规则评估异常: rule_id={rule.id}, error={exc}")

    return None


def evaluate_privacy(
    db: Session,
    req: PrivacyEvaluateRequest,
) -> PrivacyEvaluateResult:
    """评估隐私规则的公共接口。"""
    return _evaluate_privacy(db, req)


# ── 活动记录查询 ────────────────────────────────────────────────────────────────


def query_activities(
    db: Session,
    query: ActivityListQuery,
) -> PaginatedResponse[ActivityResponse]:
    """查询活动记录列表。

    Args:
        db: 数据库会话
        query: 查询参数

    Returns:
        分页的活动记录列表
    """
    base_stmt = select(Activity)

    conditions = []

    if query.app_name:
        conditions.append(Activity.app_name.contains(query.app_name))
    if query.platform:
        conditions.append(Activity.platform == query.platform)
    if query.privacy_action:
        conditions.append(Activity.privacy_action == query.privacy_action)
    if query.keyword:
        conditions.append(
            or_(
                Activity.app_name.contains(query.keyword),
                Activity.window_title.contains(query.keyword),
            ),
        )
    if query.start_time:
        conditions.append(Activity.started_at >= query.start_time)
    if query.end_time:
        conditions.append(Activity.started_at <= query.end_time)

    if conditions:
        base_stmt = base_stmt.where(and_(*conditions))

    total = db.scalar(select(func.count()).select_from(base_stmt.subquery()))

    items = (
        db.scalars(
            base_stmt
            .order_by(desc(Activity.started_at), desc(Activity.id))
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        ).all()
    )

    return PaginatedResponse(
        lists=[ActivityResponse.model_validate(item) for item in items],
        pagination=PaginationInfo(
            page=query.page,
            page_size=query.page_size,
            total=total or 0,
            total_pages=math.ceil((total or 0) / query.page_size),
        ),
    )


def get_activity_stats(db: Session) -> ActivityStats:
    """获取活动统计信息。"""
    today_start = datetime.combine(date.today(), datetime.min.time())

    total_count = db.scalar(select(func.count(Activity.id))) or 0
    today_count = (
        db.scalar(
            select(func.count(Activity.id))
            .where(Activity.created_at >= today_start)
        ) or 0
    )
    # 今日唯一应用数
    today_apps = db.scalar(
        select(func.count(func.distinct(Activity.app_name)))
        .where(
            Activity.created_at >= today_start,
            Activity.privacy_action == "allowed",
        )
    ) or 0

    return ActivityStats(
        total_count=total_count,
        today_count=today_count,
        unique_apps=today_apps,
    )


def get_activity(db: Session, activity_id: int) -> ActivityResponse:
    """获取单条活动记录详情。"""
    activity = _get_activity_or_error(db, activity_id)
    return ActivityResponse.model_validate(activity)


def delete_activity(db: Session, activity_id: int) -> None:
    """删除单条活动记录（含审计）。"""
    activity = _get_activity_or_error(db, activity_id)

    record_audit(
        db=db,
        action="activity.delete",
        target_type="activity",
        target_id=activity_id,
        summary=f"删除活动记录: {activity.app_name} ({activity.started_at})",
    )

    # 人物理解观察以消息为证据；活动数据不再直接关联人物理解。

    db.delete(activity)
    commit_or_rollback(db)
    logger.info(f"删除活动记录: id={activity_id}")


def clear_activities(db: Session) -> int:
    """清空所有活动记录。

    Returns:
        删除的记录数量
    """
    total = db.scalar(select(func.count(Activity.id))) or 0
    if total == 0:
        return 0

    db.execute(Activity.__table__.delete())
    commit_or_rollback(db)

    record_audit(
        db=db,
        action="activity.clear_all",
        target_type="activity",
        summary=f"清空所有活动记录: count={total}",
    )

    logger.info(f"清空所有活动记录: count={total}")
    return total


# ── 隐私规则管理 ────────────────────────────────────────────────────────────────


def create_privacy_rule(
    db: Session,
    data: PrivacyRuleCreate,
) -> PrivacyRuleResponse:
    """创建隐私规则。"""
    rule = PrivacyRule(
        rule_type=data.rule_type,
        rule_value=data.rule_value,
        description=data.description,
        is_active=1,
        priority=data.priority,
    )
    db.add(rule)
    commit_or_rollback(db)

    record_audit(
        db=db,
        action="privacy_rule.create",
        target_type="privacy_rule",
        target_id=rule.id,
        summary=f"创建隐私规则: type={data.rule_type}",
    )

    logger.info(f"创建隐私规则: id={rule.id}, type={data.rule_type}")
    return PrivacyRuleResponse.model_validate(rule)


def query_privacy_rules(
    db: Session,
    query: PrivacyRuleListQuery,
) -> PaginatedResponse[PrivacyRuleResponse]:
    """查询隐私规则列表。"""
    base_stmt = select(PrivacyRule)

    if query.rule_type:
        base_stmt = base_stmt.where(PrivacyRule.rule_type == query.rule_type)
    if query.is_active is not None:
        base_stmt = base_stmt.where(PrivacyRule.is_active == (1 if query.is_active else 0))

    total = db.scalar(select(func.count()).select_from(base_stmt.subquery()))

    items = (
        db.scalars(
            base_stmt
            .order_by(PrivacyRule.priority.desc(), PrivacyRule.id)
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        ).all()
    )

    return PaginatedResponse(
        lists=[PrivacyRuleResponse.model_validate(item) for item in items],
        pagination=PaginationInfo(
            page=query.page,
            page_size=query.page_size,
            total=total or 0,
            total_pages=math.ceil((total or 0) / query.page_size),
        ),
    )


def get_privacy_rule(db: Session, rule_id: int) -> PrivacyRuleResponse:
    """获取单条隐私规则。"""
    rule = _get_rule_or_error(db, rule_id)
    return PrivacyRuleResponse.model_validate(rule)


def update_privacy_rule(
    db: Session,
    rule_id: int,
    data: PrivacyRuleUpdate,
) -> PrivacyRuleResponse:
    """更新隐私规则。"""
    rule = _get_rule_or_error(db, rule_id)

    if data.rule_type is not None:
        rule.rule_type = data.rule_type
    if data.rule_value is not None:
        rule.rule_value = data.rule_value
    if data.description is not None:
        rule.description = data.description
    if data.is_active is not None:
        rule.is_active = 1 if data.is_active else 0
    if data.priority is not None:
        rule.priority = data.priority

    commit_or_rollback(db)

    record_audit(
        db=db,
        action="privacy_rule.update",
        target_type="privacy_rule",
        target_id=rule_id,
        summary=f"更新隐私规则: type={rule.rule_type}",
    )

    logger.info(f"更新隐私规则: id={rule_id}")
    return PrivacyRuleResponse.model_validate(rule)


def delete_privacy_rule(db: Session, rule_id: int) -> None:
    """删除隐私规则。"""
    rule = _get_rule_or_error(db, rule_id)

    record_audit(
        db=db,
        action="privacy_rule.delete",
        target_type="privacy_rule",
        target_id=rule_id,
        summary=f"删除隐私规则: type={rule.rule_type}",
    )

    db.delete(rule)
    commit_or_rollback(db)
    logger.info(f"删除隐私规则: id={rule_id}")


# ── 内部方法 ────────────────────────────────────────────────────────────────────


def _get_activity_or_error(db: Session, activity_id: int) -> Activity:
    """获取活动记录，不存在时抛出异常。"""
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, f"活动记录不存在: {activity_id}")
    return activity


def _get_rule_or_error(db: Session, rule_id: int) -> PrivacyRule:
    """获取隐私规则，不存在时抛出异常。"""
    rule = db.get(PrivacyRule, rule_id)
    if rule is None:
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, f"隐私规则不存在: {rule_id}")
    return rule
