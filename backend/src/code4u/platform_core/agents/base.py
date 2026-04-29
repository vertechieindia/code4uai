from __future__ import annotations
"""Base agent interface for code4u.ai."""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List
from pydantic import BaseModel

class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    VALIDATION_ERROR = "validation_error"

class AgentResult(BaseModel):
    status: AgentStatus
    output: Dict[str, Any]
    errors: List[str] = []
    validation_warnings: List[str] = []
    execution_time_ms: float = 0
    
    @property
    def success(self) -> bool: return self.status == AgentStatus.SUCCESS

class AgentContext(BaseModel):
    session_id: str
    workspace_path: str
    intent: str
    scope: Dict[str, Any] = {}
    constraints: Dict[str, Any] = {}
    previous_results: list[AgentResult] = []

class Agent(ABC):
    name: str = "base"
    def __init__(self): self.logger = __import__("structlog").get_logger(self.name)
    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult: ...
    async def validate_output(self, output: Dict[str, Any], context: AgentContext) -> List[str]: return []

