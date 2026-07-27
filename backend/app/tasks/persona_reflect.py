"""人物理解后台反思任务。"""

from __future__ import annotations

import json

from app.core import api_key_cache
from app.core.database import get_background_db_session
from app.services import persona as services_persona
from app.tasks.registry import register_handler


@register_handler("persona.reflect")
def handle_persona_reflect(payload: dict | None) -> str | None:
    """执行人物洞见反思。"""
    with get_background_db_session() as db:
        api_key = api_key_cache.peek_global()
        if not api_key:
            raise RuntimeError("API Key 不可用")
        result = services_persona.reflect_observations(db, api_key, force=bool((payload or {}).get("force")))
        if "error" in result:
            raise RuntimeError(result["error"])
        return json.dumps(result, ensure_ascii=False)
