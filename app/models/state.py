from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class AgentThoughtStep(BaseModel):
    agent_name: str
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class AgentState(BaseModel):
    query: str
    intent: Optional[str] = None
    search_queries: List[str] = Field(default_factory=list)
    retrieved_chunks: List[Dict[str, Any]] = Field(default_factory=list)
    thought_history: List[AgentThoughtStep] = Field(default_factory=list)
    draft_summary: Optional[Dict[str, Any]] = None
    verification_attempts: int = 0
    is_verified: bool = False
    final_output: Optional[Dict[str, Any]] = None
