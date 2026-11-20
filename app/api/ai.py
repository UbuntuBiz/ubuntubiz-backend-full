from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.models import AgentTask, AgentToolCall, User
from app.schemas.ai import (
    AIChatRequest,
    AIChatResponse,
    AgentTaskResponse,
    AgentTraceResponse,
    AgentToolCallResponse,
)
from app.agents.orchestrator import OrchestratorAgent
from app.api.deps import get_current_user_and_tenant

router = APIRouter(prefix="/ai", tags=["AI Multi-Agent System"])


@router.post("/chat", response_model=AIChatResponse)
def chat_with_agents(
    req: AIChatRequest,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Conversational interface connecting spaza shop owners to the UbuntuBiz AI Agent Team.
    Routes intent through the Orchestrator to specialized agents.
    """
    execution = OrchestratorAgent.route_and_execute(
        db=db,
        business_id=current_user.business_id,
        user_message=req.message,
        user_id=current_user.id
    )

    task_id = execution["task_id"]
    intent = execution["intent"]
    result = execution.get("result", {})

    reply_text = (
        result.get("response") or
        result.get("confirmation_message") or
        f"Processed request under intent '{intent}'."
    )

    return AIChatResponse(
        task_id=task_id,
        intent=intent,
        reply=reply_text,
        data=result
    )


@router.get("/tasks/{task_id}", response_model=AgentTaskResponse)
def get_agent_task(
    task_id: str,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Query status and inputs/results of an AI task.
    """
    task = db.query(AgentTask).filter(
        AgentTask.id == task_id,
        AgentTask.business_id == current_user.business_id
    ).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent task not found")
    return task


@router.get("/tasks/{task_id}/trace", response_model=AgentTraceResponse)
def get_agent_task_trace(
    task_id: str,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Retrieve full audit trace of tool calls dispatched by agents during a task.
    """
    task = db.query(AgentTask).filter(
        AgentTask.id == task_id,
        AgentTask.business_id == current_user.business_id
    ).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent task not found")

    tool_calls = db.query(AgentToolCall).filter(
        AgentToolCall.task_id == task_id
    ).order_by(AgentToolCall.created_at.asc()).all()

    return AgentTraceResponse(
        task=task,
        tool_calls=tool_calls
    )
