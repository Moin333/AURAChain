from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, ClassVar
from pydantic import BaseModel
from datetime import datetime
from app.core.observability import observability
from app.core.streaming import streaming_service
from loguru import logger
import math
import numpy as np


class ConfidenceScore(BaseModel):
    """Standardized confidence output from any agent."""
    score: float                        # 0.0-1.0
    justification: str                  # Why this score
    factors: Dict[str, float] = {}      # Contributing factors (e.g., {"data_quality": 0.9, "model_fit": 0.7})


class ReasoningResult(BaseModel):
    """Wraps agent output with reasoning trace and evaluation."""
    response: Dict[str, Any]            # The actual agent output
    confidence: ConfidenceScore
    attempts: int                       # How many attempts were made
    reasoning_trace: List[str]          # Step-by-step reasoning log
    evaluation_score: float             # Final evaluation score
    evaluation_issues: List[str]        # Issues found during evaluation


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
    workflow_id: Optional[str] = None  # For inter-agent communication

class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    
    Phase 5 additions:
      - Opt-in reasoning loop: plan → act → evaluate → retry
      - ConfidenceScore in every response
      - Best-result tracking across retries
      - Reasoning trace stored in artifact metadata
    """
    
    # Maximum reasoning attempts before accepting best result
    max_reasoning_attempts: int = 2
    # Minimum evaluation score to accept output without retry
    min_acceptable_score: float = 0.5
    # Agent capability (override in subclass for auto-introspection)
    capability: ClassVar[Optional[Any]] = None
    
    def __init__(self, name: str, model: str, api_client: Any):
        self.name = name
        self.model = model
        self.api_client = api_client
        self.tools = []
        self.shared_context = None  # Injected per-workflow by orchestrator
        self._tools_registry = None
    
    @property
    def tools_registry(self):
        """Lazy access to the global tool registry."""
        if self._tools_registry is None:
            from app.core.tool_registry import tool_registry
            self._tools_registry = tool_registry
        return self._tools_registry
    
    async def log_reasoning(
        self,
        step: str,
        input_summary: str,
        reasoning: str,
        output_summary: str,
        confidence: float,
        evidence: List[str] = None,
        workflow_id: str = None
    ) -> None:
        """
        Log a structured reasoning entry for this agent.
        
        Stores decision summary (NOT raw chain-of-thought).
        """
        if not workflow_id:
            return
        
        try:
            from app.core.reasoning_trace import reasoning_trace_store, ReasoningEntry
            entry = ReasoningEntry(
                agent=self.name,
                step=step,
                input_summary=input_summary[:200],
                reasoning=reasoning[:500],
                output_summary=output_summary[:200],
                confidence=confidence,
                evidence=evidence or []
            )
            await reasoning_trace_store.append(workflow_id, entry)
        except Exception as e:
            logger.warning(f"Failed to log reasoning: {e}")
    
    @abstractmethod
    async def process(self, request: AgentRequest) -> AgentResponse:
        """Main processing method - must be implemented by each agent"""
        pass
    
    # ── Reasoning Loop (opt-in) ──
    
    def should_reason(self) -> bool:
        """Override to enable reasoning loop. Default: False (single-shot)."""
        return False
    
    def evaluate_output(self, output: Dict[str, Any], request: AgentRequest) -> tuple[float, List[str]]:
        """
        Agent-specific output evaluation. Override for custom checks.
        
        Returns: (score 0.0-1.0, list of issues)
        Default: delegates to AgentEvaluator.
        """
        from app.core.evaluation import agent_evaluator
        result = agent_evaluator.evaluate(
            agent_name=self.name.lower().replace(" ", "_"),
            output=output,
            success=True
        )
        return result.score, result.issues
    
    def compute_confidence(self, output: Dict[str, Any], eval_score: float) -> ConfidenceScore:
        """
        Compute confidence score for agent output. Override for custom logic.
        
        Default: uses evaluation score as confidence.
        """
        return ConfidenceScore(
            score=eval_score,
            justification=f"{self.name} output evaluated with score {eval_score:.2f}",
            factors={"evaluation_score": eval_score}
        )
    
    async def execute_with_reasoning(self, request: AgentRequest) -> AgentResponse:
        """
        The reasoning loop: plan → act → evaluate → retry (if needed).
        
        Tracks the best result across attempts and returns it even if
        no attempt passes the minimum threshold. This prevents regressions
        where a later retry produces worse output than an earlier one.
        """
        reasoning_trace = []
        best_result: Optional[AgentResponse] = None
        best_score: float = -1.0
        best_confidence: Optional[ConfidenceScore] = None
        best_issues: List[str] = []
        
        for attempt in range(1, self.max_reasoning_attempts + 1):
            reasoning_trace.append(f"Attempt {attempt}/{self.max_reasoning_attempts}")
            
            # ── PLAN: Log what we're about to do ──
            if attempt > 1:
                reasoning_trace.append(f"Retrying due to issues: {best_issues}")
                # Inject retry context into request parameters
                request.parameters["_retry_attempt"] = attempt
                request.parameters["_previous_issues"] = best_issues
            
            # ── ACT: Execute the agent's process() ──
            try:
                response = await self.process(request)
            except Exception as e:
                reasoning_trace.append(f"Execution failed: {e}")
                if best_result is None:
                    best_result = AgentResponse(
                        agent_name=self.name, success=False, error=str(e)
                    )
                continue
            
            if not response.success or not response.data:
                reasoning_trace.append(f"Agent returned failure or empty data")
                if best_result is None:
                    best_result = response
                continue
            
            # ── EVALUATE: Check output quality ──
            eval_score, issues = self.evaluate_output(response.data, request)
            confidence = self.compute_confidence(response.data, eval_score)
            
            reasoning_trace.append(
                f"Evaluation: score={eval_score:.2f}, issues={len(issues)}, "
                f"confidence={confidence.score:.2f}"
            )
            
            # ── TRACK BEST: Keep the highest-scoring result ──
            if eval_score > best_score:
                best_score = eval_score
                best_result = response
                best_confidence = confidence
                best_issues = issues
            
            # ── ACCEPT if good enough ──
            if eval_score >= self.min_acceptable_score and len(issues) == 0:
                reasoning_trace.append(f"✅ Accepted on attempt {attempt}")
                break
            else:
                reasoning_trace.append(
                    f"⚠️ Below threshold ({eval_score:.2f} < {self.min_acceptable_score})"
                    f" or has {len(issues)} issues"
                )
        
        # ── BUILD FINAL RESPONSE ──
        if best_result is None:
            best_result = AgentResponse(
                agent_name=self.name, success=False,
                error="All reasoning attempts failed"
            )
        
        # Attach reasoning metadata (stored in artifact, not in report)
        if best_result.metadata is None:
            best_result.metadata = {}
        
        reasoning_result = ReasoningResult(
            response=best_result.data or {},
            confidence=best_confidence or ConfidenceScore(
                score=0.0, justification="No successful evaluation"
            ),
            attempts=min(attempt, self.max_reasoning_attempts),
            reasoning_trace=reasoning_trace,
            evaluation_score=best_score if best_score >= 0 else 0.0,
            evaluation_issues=best_issues
        )
        
        best_result.metadata["reasoning"] = {
            "attempts": reasoning_result.attempts,
            "evaluation_score": reasoning_result.evaluation_score,
            "confidence": reasoning_result.confidence.model_dump(),
            "trace": reasoning_result.reasoning_trace,
            "issues": reasoning_result.evaluation_issues
        }
        
        logger.info(
            f"🧠 {self.name} reasoning: {reasoning_result.attempts} attempts, "
            f"score={reasoning_result.evaluation_score:.2f}, "
            f"confidence={reasoning_result.confidence.score:.2f}"
        )
        
        return best_result
    
    async def publish_findings(self, workflow_id: str, findings: dict) -> None:
        """Publish curated findings for downstream agents to consume."""
        if not self.shared_context or not workflow_id:
            return
        await self.shared_context.publish_findings(workflow_id, self.name, findings)
    
    async def get_upstream_findings(self, workflow_id: str, agent_name: str) -> dict:
        """Read another agent's published findings. Returns {} if unavailable."""
        if not self.shared_context or not workflow_id:
            return {}
        data = await self.shared_context.get_findings(workflow_id, agent_name)
        return data or {}
    
    async def request_from_peer(self, workflow_id: str, target_agent: str, question: str) -> None:
        """Request additional data from a peer agent via SharedContext."""
        if not self.shared_context or not workflow_id:
            return
        await self.shared_context.publish_request(
            workflow_id, self.name, target_agent, question
        )
    
    async def get_peer_requests(self, workflow_id: str) -> List[Dict[str, str]]:
        """Get requests from other agents directed at this agent."""
        if not self.shared_context or not workflow_id:
            return []
        return await self.shared_context.get_requests(workflow_id, self.name)
    
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
            
            # Use reasoning loop if agent opts in, otherwise single-shot
            if self.should_reason():
                response = await self.execute_with_reasoning(request)
            else:
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