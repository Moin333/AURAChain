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
        return result.data
    
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
        """Dynamically spawn another agent to answer a question, suspending current loop.
        
        BUG-7 fix: Validates agent name against registry with fuzzy matching.
        """
        from app.core.registry import agent_registry
        
        # BUG-7: Try exact match first, then fuzzy match
        target_agent = agent_registry.get_agent(target_agent_name)
        if not target_agent:
            # Fuzzy match: normalize to lowercase/underscore and try common aliases
            normalized = target_agent_name.lower().replace(" ", "_").replace("-", "_")
            # Try common patterns: "DataAgent" → "data_harvester", "Data Analyst" → "data_harvester"
            alias_map = {
                "data_agent": "data_harvester", "dataagent": "data_harvester",
                "data_analyst": "data_harvester", "harvester": "data_harvester",
                "trend_agent": "trend_analyst", "trendagent": "trend_analyst",
                "forecast_agent": "forecaster", "forecastagent": "forecaster",
                "optimizer": "mcts_optimizer", "mcts": "mcts_optimizer",
                "viz": "visualizer", "chart_agent": "visualizer",
                "order": "order_manager", "notif": "notifier",
            }
            resolved = alias_map.get(normalized, normalized)
            target_agent = agent_registry.get_agent(resolved)
            if not target_agent:
                all_names = list(agent_registry.list_capabilities().keys())
                return f"Error: Agent '{target_agent_name}' not found. Available agents: {all_names}"
            target_agent_name = resolved
            
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

    def _build_react_system_prompt(self, request: AgentRequest) -> str:
        """Build a comprehensive system prompt for the ReAct loop.
        
        BUG-4 fix: Injects dataset metadata so LLM knows columns/types/sample data.
        BUG-7 fix: Includes valid peer agent names.
        """
        import pandas as pd
        
        available_tools = self.get_react_tools()
        system_prompt = self.get_system_prompt()
        
        system_prompt += "\n\nYou are operating in a ReAct (Reasoning and Acting) loop."
        system_prompt += "\nYou have access to the following tools:\n"
        
        tool_schemas = []
        for t in available_tools:
            schema = self.tools_registry.get_tool_schema(t)
            if schema:
                # Remove 'df' from visible parameters — it's auto-injected
                clean_schema = dict(schema)
                if "parameters" in clean_schema and isinstance(clean_schema["parameters"], dict):
                    clean_params = {k: v for k, v in clean_schema["parameters"].items() if k != "df"}
                    clean_schema["parameters"] = clean_params
                tool_schemas.append(clean_schema)
                
        system_prompt += json.dumps(tool_schemas, indent=2)
        
        # BUG-7: List valid peer agents
        try:
            from app.core.registry import agent_registry
            peer_names = [name for name in agent_registry.list_capabilities().keys() if name != self.name.lower().replace(" ", "_")]
            system_prompt += f"\n\nYou also have a tool 'ask_peer' to request help from another agent."
            system_prompt += f"\nValid peer agents: {peer_names}"
            system_prompt += '\nArgs: {"target_agent": "<name_from_list_above>", "query": "..."}'
        except Exception:
            system_prompt += "\n\nYou also have a tool 'ask_peer' to request help from another agent. Args: {\"target_agent\": \"...\", \"query\": \"...\"}"
        
        # BUG-4: Inject dataset metadata
        dataset = request.context.get("dataset")
        if dataset is not None:
            try:
                df = pd.DataFrame(dataset) if not isinstance(dataset, pd.DataFrame) else dataset
                cols_info = {col: str(df[col].dtype) for col in df.columns}
                sample = df.head(3).to_dict(orient='records')
                # Truncate sample values for prompt brevity
                for row in sample:
                    for k, v in row.items():
                        if isinstance(v, str) and len(v) > 50:
                            row[k] = v[:50] + "..."
                
                system_prompt += f"\n\nDATASET AVAILABLE ({len(df)} rows, {len(df.columns)} columns):"
                system_prompt += f"\nColumns & types: {json.dumps(cols_info)}"
                system_prompt += f"\nSample (first 3 rows): {json.dumps(sample, default=str)}"
                system_prompt += "\n\nIMPORTANT: Tools that need a DataFrame (sql_query, demand_velocity, "
                system_prompt += "detect_outliers, correlation_analysis, etc.) automatically receive the dataset."
                system_prompt += "\nDo NOT include a 'df' parameter in your Action Input."
                system_prompt += "\nFor sql_query, the table name is 'df'. Example: SELECT * FROM df LIMIT 10"
            except Exception as e:
                logger.warning(f"Failed to inject dataset metadata into prompt: {e}")
        
        # ReAct format instructions
        system_prompt += "\n\nRULES:"
        system_prompt += "\n1. NEVER write Python code. Only use the tools listed above."
        system_prompt += "\n2. NEVER fabricate or invent data. Only use tool observations."
        system_prompt += "\n3. Each step: Thought → Action → Action Input. One action per step."
        system_prompt += "\n4. When you have enough information, output Final Answer with JSON."
        
        system_prompt += "\n\nFormat your response EXACTLY as follows:\n"
        system_prompt += "Thought: <your reasoning>\n"
        system_prompt += "Action: <tool_name>\n"
        system_prompt += "Action Input: <json payload without df parameter>\n"
        system_prompt += "\nOR to finish:\n"
        system_prompt += "Final Answer: <json response payload>\n"
        
        return system_prompt

    def _parse_final_answer(self, response_text: str) -> dict:
        """Parse the Final Answer JSON from LLM response.
        
        BUG-3 fix: Uses strict=False and escapes raw newlines.
        """
        ans_text = response_text.split("Final Answer:")[1].strip()
        
        # Strip markdown code fences
        if ans_text.startswith("```json"):
            end_idx = ans_text.find("```", 7)
            ans_text = ans_text[7:end_idx].strip() if end_idx > 7 else ans_text[7:].strip()
        elif ans_text.startswith("```"):
            end_idx = ans_text.find("```", 3)
            ans_text = ans_text[3:end_idx].strip() if end_idx > 3 else ans_text[3:].strip()
        
        # BUG-3: Try strict=False first (handles control chars like raw newlines)
        try:
            return json.loads(ans_text, strict=False)
        except json.JSONDecodeError:
            pass
        
        # Escape raw newlines inside strings and retry
        ans_text_escaped = ans_text.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        try:
            return json.loads(ans_text_escaped)
        except json.JSONDecodeError:
            pass
        
        # Repair truncated JSON (close open strings/brackets)
        repaired = ans_text.rstrip()
        if repaired.count('"') % 2 != 0:
            repaired += '"'
        for open_ch, close_ch in [('[', ']'), ('{', '}')]:
            diff = repaired.count(open_ch) - repaired.count(close_ch)
            repaired += close_ch * max(0, diff)
        return json.loads(repaired, strict=False)

    def _parse_action(self, response_text: str) -> tuple:
        """Parse Action and Action Input from LLM response.
        
        BUG-2 fix: Handles whitespace, JSON-format tool calls, and 'Action: Final Answer'.
        """
        lines = response_text.split("\n")
        action = None
        action_input_lines = []
        in_action_input = False
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Action:") and not stripped.startswith("Action Input:"):
                action = stripped.split("Action:", 1)[1].strip()
                in_action_input = False  # Reset
            elif stripped.startswith("Action Input:"):
                in_action_input = True
                action_input_lines.append(stripped.split("Action Input:", 1)[1].strip())
            elif in_action_input and stripped and not stripped.startswith("Thought:"):
                action_input_lines.append(line)  # Preserve indentation for JSON
        
        action_input_str = "\n".join(action_input_lines).strip()
        
        # Strip code fences
        if action_input_str.startswith("```json"):
            end_idx = action_input_str.find("```", 7)
            action_input_str = action_input_str[7:end_idx].strip() if end_idx > 7 else action_input_str[7:].strip()
        elif action_input_str.startswith("```"):
            end_idx = action_input_str.find("```", 3)
            action_input_str = action_input_str[3:end_idx].strip() if end_idx > 3 else action_input_str[3:].strip()
        
        return action, action_input_str

    def _try_parse_json_tool_call(self, response_text: str) -> tuple:
        """BUG-2 fallback: Try to parse JSON-format tool calls like {"name": "...", "parameters": {...}}.
        
        Some LLMs output function-call style JSON instead of Action/Action Input format.
        """
        import re
        # Look for JSON object in the response
        json_match = re.search(r'\{[\s\S]*"name"\s*:\s*"[^"]+"\s*,[\s\S]*"parameters"\s*:\s*\{[\s\S]*\}[\s\S]*\}', response_text)
        if json_match:
            try:
                call = json.loads(json_match.group(), strict=False)
                return call.get("name"), call.get("parameters", {})
            except json.JSONDecodeError:
                pass
        return None, None

    def _inject_dataframe(self, action: str, args: dict, request: AgentRequest) -> dict:
        """BUG-1 fix: Auto-inject DataFrame from request context into tool arguments.
        
        Tools like sql_query(df, query) and demand_velocity(df, ...) require a pd.DataFrame,
        but the LLM sends string placeholders. This method replaces them with actual data.
        
        Raises RuntimeError if the tool needs df but no dataset is available.
        """
        import pandas as pd
        import inspect
        
        func = self.tools_registry._tools.get(action)
        if not func:
            logger.warning(f"⚠️ _inject_dataframe: tool '{action}' not found in registry")
            return args
        
        sig = inspect.signature(func)
        if 'df' not in sig.parameters:
            return args
        
        # Remove LLM's string placeholder for df
        args.pop('df', None)
        
        # Inject actual DataFrame from context
        dataset = request.context.get("dataset") if request.context else None
        
        if dataset is None:
            raise RuntimeError(
                f"Dataset not available in request context for tool '{action}'. "
                "Ensure DataHarvester ran before this agent and populated request.context['dataset']."
            )
        
        if isinstance(dataset, pd.DataFrame):
            args["df"] = dataset
        else:
            args["df"] = pd.DataFrame(dataset)
        
        logger.debug(f"✅ _inject_dataframe: injected DataFrame ({len(args['df'])} rows) for tool '{action}'")
        return args

    async def _run_react_loop(self, request: AgentRequest) -> AgentResponse:
        """Main ReAct Loop — hardened with fixes for BUG-1 through BUG-4 and BUG-7.
        
        Fixes:
        - BUG-1: Auto-injects DataFrame from request.context into tool calls
        - BUG-2: Robust parser with .strip(), JSON fallback, Final Answer via Action
        - BUG-3: strict=False + newline escaping on Final Answer JSON parsing
        - BUG-4: Injects dataset metadata (columns, types, sample) into system prompt
        - BUG-7: Valid peer agent names in prompt + fuzzy matching in request_peer_assistance
        """
        # Build comprehensive system prompt (BUG-4, BUG-7)
        system_prompt = self._build_react_system_prompt(request)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Query: {request.query}"}
        ]
        
        max_iterations = 6
        for i in range(max_iterations):
            resp = await self.api_client.create_completion(self.model, messages)
            response_text = resp["content"]
            logger.info(f"🧠 {self.name} ReAct step {i}:\n{response_text}")
            
            messages.append({"role": "assistant", "content": response_text})
            
            # ── Check for Final Answer ──
            if "Final Answer:" in response_text:
                try:
                    payload = self._parse_final_answer(response_text)
                    return AgentResponse(agent_name=self.name, success=True, data=payload)
                except Exception as e:
                    messages.append({"role": "user", "content": f"Your Final Answer JSON was invalid: {e}. Please output valid JSON."})
                    continue
            
            # ── Check for Action + Action Input ──
            action, action_input_str = None, None
            
            if "Action:" in response_text:
                action, action_input_str = self._parse_action(response_text)
                
                # BUG-2: If action is "Final Answer", treat action_input as the answer
                if action and action.lower().replace(" ", "") == "finalanswer":
                    try:
                        if action_input_str:
                            payload = json.loads(action_input_str, strict=False)
                        else:
                            # The answer might be in the rest of the text
                            payload = self._parse_final_answer("Final Answer:" + (action_input_str or "{}"))
                        return AgentResponse(agent_name=self.name, success=True, data=payload)
                    except Exception as e:
                        messages.append({"role": "user", "content": f"Your Final Answer JSON was invalid: {e}. Please output valid JSON."})
                        continue
            
            # BUG-2 fallback: Try JSON function-call format
            if not action or not action_input_str:
                json_action, json_params = self._try_parse_json_tool_call(response_text)
                if json_action:
                    action = json_action
                    action_input_str = json.dumps(json_params) if isinstance(json_params, dict) else str(json_params)
            
            if action and action_input_str:
                try:
                    args = json.loads(action_input_str, strict=False)
                    if action == "ask_peer":
                        obs = await self.request_peer_assistance(
                            request, args.get("target_agent", ""), args.get("query", "")
                        )
                    else:
                        # BUG-1: Auto-inject DataFrame
                        args = self._inject_dataframe(action, args, request)
                        obs = await self.execute_tool(action, **args)
                    
                    obs_str = json.dumps(self._sanitize_for_json(obs), default=str)
                    messages.append({"role": "user", "content": f"Observation: {obs_str[:3000]}"})
                except json.JSONDecodeError as e:
                    messages.append({"role": "user", "content": f"Your Action Input was not valid JSON: {e}. Please use proper JSON format."})
                except Exception as e:
                    messages.append({"role": "user", "content": f"Tool '{action}' error: {e}"})
            else:
                # BUG-2: Check if LLM wrote Python code (common hallucination)
                if "```python" in response_text or "import pandas" in response_text:
                    messages.append({"role": "user", "content": 
                        "ERROR: You wrote Python code. You CANNOT execute code. "
                        "You MUST use the available tools (sql_query, demand_velocity, etc). "
                        "Use Action: <tool_name> and Action Input: <json>."
                    })
                else:
                    messages.append({"role": "user", "content": "You must use Action: <tool_name> + Action Input: <json>, or output Final Answer: <json>."})
                
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