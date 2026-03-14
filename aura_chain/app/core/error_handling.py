# app/core/error_handling.py
"""
Structured error types for production error handling.

Typed exceptions enable:
- Precise catch blocks in agents and orchestrator
- Structured logging for debugging
- Recovery strategies based on error type
"""

from typing import Optional, Dict, Any


class AURAChainError(Exception):
    """Base exception for all AURAChain errors."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.context = context or {}


class LLMError(AURAChainError):
    """LLM provider returned an error or timed out."""
    
    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        model: str = "unknown",
        status_code: Optional[int] = None,
        retries_attempted: int = 0,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, context)
        self.provider = provider
        self.model = model
        self.status_code = status_code
        self.retries_attempted = retries_attempted


class RateLimitError(AURAChainError):
    """Request blocked by rate limiter. Caller should wait."""
    
    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        retry_after_ms: int = 0,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, context)
        self.provider = provider
        self.retry_after_ms = retry_after_ms


class CircuitBreakerOpen(AURAChainError):
    """Circuit breaker is open — provider temporarily unavailable."""
    
    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        model: str = "unknown",
        cooldown_remaining_s: float = 0,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, context)
        self.provider = provider
        self.model = model
        self.cooldown_remaining_s = cooldown_remaining_s


class AgentExecutionError(AURAChainError):
    """An agent failed during execution."""
    
    def __init__(
        self,
        message: str,
        agent_name: str = "unknown",
        workflow_id: Optional[str] = None,
        cause: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, context)
        self.agent_name = agent_name
        self.workflow_id = workflow_id
        self.cause = cause


class CheckpointError(AURAChainError):
    """Workflow checkpoint save/load failed."""
    
    def __init__(
        self,
        message: str,
        workflow_id: str = "unknown",
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, context)
        self.workflow_id = workflow_id
