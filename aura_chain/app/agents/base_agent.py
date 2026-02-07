# app/agents/base_agent.py
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from datetime import datetime
from app.core.observability import observability
from app.core.streaming import streaming_service
from loguru import logger
import math
import numpy as np

class AgentResponse(BaseModel):
    """Standard response format for all agents"""
    agent_name: str
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}
    timestamp: datetime = datetime.utcnow()

class AgentRequest(BaseModel):
    """Standard request format for all agents"""
    query: str
    context: Dict[str, Any] = {}
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    parameters: Dict[str, Any] = {}

class BaseAgent(ABC):
    """Abstract base class for all agents"""
    
    def __init__(self, name: str, model: str, api_client: Any):
        self.name = name
        self.model = model
        self.api_client = api_client
        self.tools = []
    
    @abstractmethod
    async def process(self, request: AgentRequest) -> AgentResponse:
        """Main processing method - must be implemented by each agent"""
        pass
    
    async def execute_with_observability(
        self,
        request: AgentRequest
    ) -> AgentResponse:
        """Execute agent with full observability + streaming"""
        session_id = request.session_id
        
        try:
            # Notify start
            if session_id:
                await streaming_service.publish_agent_started(
                    session_id,
                    self.name,
                    request.query
                )
                
            observability.logger.log_agent_activity(
                self.name,
                "request_received",
                {"query": request.query[:100]}
            )
            
            observability.logger.log_agent_activity(
                self.name,
                "execution_started",
                {"args": str(request)[:100], "kwargs": "{}"}
            )
            
            response = await self.process(request)
            
            observability.logger.log_agent_activity(
                self.name,
                "execution_completed",
                {"success": response.success}
            )
            
            # Sanitize Data for JSON
            if response.data:
                response.data = self._sanitize_for_json(response.data)
            if response.metadata:
                response.metadata = self._sanitize_for_json(response.metadata)
            # --------------------------------------------
            
            # Notify completion
            if session_id:
                if response.success:
                    await streaming_service.publish_agent_completed(
                        session_id,
                        self.name,
                        response.data or {}
                    )
                else:
                    await streaming_service.publish_agent_failed(
                        session_id,
                        self.name,
                        response.error or "Unknown error"
                    )
            
            return response
            
        except Exception as e:
            logger.error(f"Agent {self.name} failed: {str(e)}")
            
            observability.logger.log_agent_activity(
                self.name,
                "execution_failed",
                {"error": str(e)}
            )
            
            # Notify failure
            if session_id:
                await streaming_service.publish_agent_failed(
                    session_id,
                    self.name,
                    str(e)
                )
                
            return AgentResponse(
                agent_name=self.name,
                success=False,
                error=str(e)
            )
    
    def _sanitize_for_json(self, obj: Any) -> Any:
        """Recursively remove NaN, Infinity, and numpy types for JSON safety"""
        if isinstance(obj, dict):
            return {k: self._sanitize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize_for_json(v) for v in obj]
        elif isinstance(obj, (float, np.floating)):
            if math.isnan(obj) or math.isinf(obj):
                return 0.0  # Safe fallback for UI
            return float(obj)
        elif isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, np.ndarray):
            return self._sanitize_for_json(obj.tolist())
        return obj

    def add_tool(self, tool: Dict[str, Any]):
        """Register a tool with the agent"""
        self.tools.append(tool)
    
    def get_system_prompt(self) -> str:
        """Get agent-specific system prompt"""
        return f"You are {self.name}, a specialized AI agent."