from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, ClassVar
from pydantic import BaseModel
from datetime import datetime
from app.core.observability import observability
from app.core.streaming import streaming_service
from loguru import logger
import math
import numpy as np
import json


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
        
    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Execute a tool from the ToolRegistry.
        This serves as the single proxy layer for all LLM-driven or hardcoded computation tasks.
        """
        result = await self.tools_registry.invoke(tool_name, **kwargs)
        
        if result.error:
            raise RuntimeError(f"Tool '{tool_name}' failed: {result.error}")
        return result.result
    
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
        """Override to enable evaluation loop. Default: False (single-shot)."""
        return False
        
    def should_react(self) -> bool:
        """Override to enable ReAct loop. Default: False (procedural)."""
        return False
        
    def get_react_tools(self) -> List[str]:
        """Override to provide a list of tool names available in ReAct loop."""
        return []
    
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
        
    async def request_peer_assistance(self, request: AgentRequest, target_agent_name: str, query: str) -> str:
        """Dynamically spawn another agent to answer a question, suspending current loop."""
        from app.core.registry import get_agent
        target_agent = get_agent(target_agent_name)
        if not target_agent:
            return f"Error: Agent '{target_agent_name}' not found."
            
        logger.info(f"🔄 {self.name} delegating to {target_agent_name}: '{query}'")
        sub_request = AgentRequest(
            query=query,
            context=request.context,
            session_id=request.session_id,
            user_id=request.user_id,
            workflow_id=request.workflow_id
        )
        response = await target_agent.execute_with_observability(sub_request)
        if response.success:
            return f"Response from {target_agent_name}:\n{json.dumps(self._sanitize_for_json(response.data))}"
        return f"{target_agent_name} failed: {response.error}"

    async def _run_react_loop(self, request: AgentRequest) -> AgentResponse:
        """Main ReAct Loop execution simulating autonomous tool use."""
        available_tools = self.get_react_tools()
        system_prompt = self.get_system_prompt()
        
        system_prompt += "\n\nYou are operating in a ReAct (Reasoning and Acting) loop."
        system_prompt += "\nYou have access to the following tools:\n"
        
        tool_schemas = []
        for t in available_tools:
            schema = self.tools_registry.get_tool_schema(t)
            if schema:
                tool_schemas.append(schema)
                
        system_prompt += json.dumps(tool_schemas, indent=2)
        system_prompt += "\n\nYou also have a tool 'ask_peer' to request help from another agent. Args: {\"target_agent\": \"...\", \"query\": \"...\"}"
        
        system_prompt += "\n\nFormat your response exactly as follows:\n"
        system_prompt += "Thought: <reasoning>\n"
        system_prompt += "Action: <tool_name>\n"
        system_prompt += "Action Input: <json payload>\n"
        system_prompt += "OR to finish:\n"
        system_prompt += "Thought: <final reasoning>\n"
        system_prompt += "Final Answer: <json response payload>\n"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Query: {request.query}\nContext keys: {list(request.context.keys())}"}
        ]
        
        max_iterations = 6
        for i in range(max_iterations):
            resp = await self.api_client.create_completion(self.model, messages)
            response_text = resp["content"]
            logger.info(f"🧠 {self.name} ReAct step {i}:\n{response_text}")
            
            messages.append({"role": "assistant", "content": response_text})
            
            if "Final Answer:" in response_text:
                try:
                    ans_text = response_text.split("Final Answer:")[1].strip()
                    if ans_text.startswith("```json"):
                        ans_text = ans_text[7:-3].strip()
                    elif ans_text.startswith("```"):
                        ans_text = ans_text[3:-3].strip()
                    payload = json.loads(ans_text)
                    return AgentResponse(agent_name=self.name, success=True, data=payload)
                except Exception as e:
                    messages.append({"role": "user", "content": f"Failed to parse Final Answer JSON: {e}"})
                    continue
                    
            if "Action:" in response_text and "Action Input:" in response_text:
                lines = response_text.split("\n")
                action = next((l.split("Action:")[1].strip() for l in lines if l.startswith("Action:")), None)
                in_action_input = False
                action_input_lines = []
                for line in lines:
                    if line.startswith("Action Input:"):
                        in_action_input = True
                        action_input_lines.append(line.split("Action Input:")[1].strip())
                    elif in_action_input and line and not line.startswith("Thought:") and not line.startswith("Action:"):
                        action_input_lines.append(line)
                
                action_input_str = "\n".join(action_input_lines).strip()
                if action_input_str.startswith("```json"): action_input_str = action_input_str[7:-3].strip()
                if action_input_str.startswith("```"): action_input_str = action_input_str[3:-3].strip()
                
                if action and action_input_str:
                    try:
                        args = json.loads(action_input_str)
                        if action == "ask_peer":
                            obs = await self.request_peer_assistance(
                                request, args.get("target_agent", ""), args.get("query", "")
                            )
                        else:
                            obs = await self.execute_tool(action, **args)
                        messages.append({"role": "user", "content": f"Observation: {json.dumps(self._sanitize_for_json(obs))[:2000]}"})
                    except Exception as e:
                        messages.append({"role": "user", "content": f"Observation Tool Error: {e}"})
                else:
                    messages.append({"role": "user", "content": "Format error: Need Action and Action Input lines."})
            else:
                messages.append({"role": "user", "content": "You must use an Action or output Final Answer."})
                
        return AgentResponse(agent_name=self.name, success=False, error="Max iterations reached in ReAct loop.")
    
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
            
            # Use ReAct loop if agent opts in, else reasoning, else single-shot
            if self.should_react():
                response = await self._run_react_loop(request)
            elif self.should_reason():
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