import os
import re
import json
import time
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database.models import AgentTask
from app.mcp.dispatcher import MCPDispatcher
from app.core.logging import logger

settings = get_settings()

PROMPT_INJECTION_PATTERNS = [
    r"ignore previous instructions",
    r"disregard all prior directives",
    r"system override",
    r"grant admin access",
    r"transfer all funds",
    r"delete database",
]


class BaseAgent:
    name: str = "base"
    system_prompt: str = ""
    allowed_tools: List[str] = []

    @classmethod
    def sanitize_untrusted_input(cls, user_text: str) -> str:
        """
        Guards against prompt injection attacks by neutralizing known jailbreak patterns.
        Treats user input strictly as data, never as control instructions.
        """
        sanitized = user_text
        for pattern in PROMPT_INJECTION_PATTERNS:
            sanitized = re.sub(pattern, "[FILTERED_ATTEMPT]", sanitized, flags=re.IGNORECASE)
        return sanitized

    @classmethod
    def call_tool(
        cls,
        db: Session,
        tool_name: str,
        args: Dict[str, Any],
        business_id: str,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dispatches tool call through MCP server layer.
        """
        return MCPDispatcher.dispatch(
            db=db,
            agent_name=cls.name,
            tool_name=tool_name,
            args=args,
            business_id=business_id,
            task_id=task_id
        )

    @classmethod
    def record_task_start(
        cls,
        db: Session,
        business_id: str,
        intent: str,
        input_data: Dict[str, Any],
        parent_id: Optional[str] = None
    ) -> AgentTask:
        task = AgentTask(
            parent_id=parent_id,
            business_id=business_id,
            intent=intent,
            status="in_progress",
            input_json=input_data,
            cost=0.0001
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    @classmethod
    def record_task_finish(
        cls,
        db: Session,
        task: AgentTask,
        result_data: Dict[str, Any],
        status: str = "completed"
    ) -> None:
        task.status = status
        task.result_json = result_data
        db.commit()
