from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, ConfigDict


class AIChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)


class AIChatResponse(BaseModel):
    task_id: str
    intent: str
    reply: str
    data: Optional[Dict[str, Any]] = None


class AgentTaskResponse(BaseModel):
    id: str
    business_id: str
    intent: str
    status: str
    cost: float
    created_at: datetime
    input_json: Optional[Dict[str, Any]]
    result_json: Optional[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)


class AgentToolCallResponse(BaseModel):
    id: str
    task_id: str
    agent: str
    tool: str
    status: str
    latency: float
    args_json: Optional[Dict[str, Any]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentTraceResponse(BaseModel):
    task: AgentTaskResponse
    tool_calls: List[AgentToolCallResponse]


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(..., description="'approved' or 'rejected'")
    pin: Optional[str] = Field(None, min_length=4, max_length=6, description="Required for high-value operations > R500.00")
    decided_via: str = Field("web", description="web, whatsapp, pos")


class ApprovalResponse(BaseModel):
    id: str
    business_id: str
    task_id: Optional[str]
    action: str
    summary: str
    status: str
    decided_via: Optional[str]
    decided_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
