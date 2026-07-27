"""人物理解档案汇编任务。"""

from __future__ import annotations

import json

from app.core import api_key_cache
from app.core.database import get_background_db_session
from app.services import persona as services_persona
from app.tasks.registry import register_handler


@register_handler("persona.compile")
def handle_persona_compile(payload: dict | None) -> str | None:
    """执行人物侧写档案汇编。"""
    with get_background_db_session() as db:
        api_key = api_key_cache.peek_global()
        if not api_key:
            raise RuntimeError("API Key 不可用")
        result = services_persona.compile_document(db, api_key)
        if "error" in result:
            raise RuntimeError(result["error"])
        return json.dumps(result, ensure_ascii=False)
