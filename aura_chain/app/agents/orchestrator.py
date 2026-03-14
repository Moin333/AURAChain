# app/agents/orchestrator.py
"""
Central Orchestrator — delegates intent analysis and workflow planning
to dedicated components, then executes the DAG with parallel support.

Phase 3 changes:
  - create_plan() uses IntentAnalyzer + WorkflowPlanner (no hardcoded modes)
  - route_to_agents() executes by topological levels with asyncio.gather()
  - Removed: _detect_mode(), AGENT_CAPABILITIES, mode-locked get_system_prompt()
"""

import asyncio
from typing import Dict, List, Any, Optional
from app.agents.base_agent import BaseAgent, AgentRequest, AgentResponse
from app.core.streaming import streaming_service
from app.core.api_clients import groq_client
from app.config import get_settings
from loguru import logger
import json

settings = get_settings()


class OrchestratorAgent(BaseAgent):
    """
    Central orchestrator that interprets queries and routes to appropriate agents.
    
    Phase 3:
      - Plan creation delegated to IntentAnalyzer + WorkflowPlanner
      - Execution uses topological levels with parallel dispatch
    """
    
    def __init__(self):
        super().__init__(
            name="Orchestrator",
            model=settings.ORCHESTRATOR_MODEL,
            api_client=groq_client
        )
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        """
        Implementation of the abstract process method.
        For the Orchestrator, 'processing' means creating the plan.
        """
        return await self.create_plan(request)
    
    async def create_plan(self, request: AgentRequest) -> AgentResponse:
        """
        Creates orchestration plan using IntentAnalyzer + WorkflowPlanner.
        
        Flow:
            1. IntentAnalyzer: query → WorkflowIntent (no agent names)
            2. WorkflowPlanner: intent + capabilities → WorkflowPlan (DAG)
            3. Return plan with execution_levels for parallel dispatch
        """
        from app.core.intent_analyzer import intent_analyzer
        from app.core.workflow_planner import workflow_planner
        
        try:
            # 1. Analyze intent (LLM-powered, semantic understanding)
            logger.info("🎯 Analyzing user intent...")
            intent = await intent_analyzer.analyze(request.query, request.context)
            
            # 2. Build execution plan (deterministic, capability-driven)
            logger.info("📋 Building workflow plan...")
            plan = workflow_planner.build_plan(intent, request.context)
            
            # 3. Log warnings
            for warning in plan.validation_warnings:
                logger.warning(f"⚠️ Plan warning: {warning}")
            
            # 4. Format plan for backward-compatible response
            plan_dict = {
                "mode": intent.analysis_type,
                "reasoning": plan.reasoning,
                "agents": plan.agents,
                "execution_levels": [list(level) for level in plan.execution_levels],
                "execution_plan": [
                    {
                        "agent": agent_name,
                        "task": plan.agent_tasks.get(agent_name, request.query),
                        "parameters": {},
                        "depends_on": self._get_deps_for_agent(agent_name)
                    }
                    for agent_name in plan.agents
                ],
                "estimated_duration_ms": plan.estimated_duration_ms,
                "estimated_llm_calls": plan.estimated_llm_calls,
                "intent": {
                    "goal": intent.goal,
                    "analysis_type": intent.analysis_type,
                    "depth": intent.depth,
                    "confidence": intent.confidence
                },
                "validation_warnings": plan.validation_warnings
            }
            
            return AgentResponse(
                agent_name=self.name,
                success=True,
                data={"plan": plan_dict}
            )
            
        except Exception as e:
            logger.error(f"Orchestrator plan creation error: {str(e)}")
            return AgentResponse(agent_name=self.name, success=False, error=str(e))
    
    def _get_deps_for_agent(self, agent_name: str) -> List[str]:
        """Get dependencies for an agent from the registry."""
        from app.core.registry import agent_registry
        capability = agent_registry.get_capability(agent_name)
        if capability:
            return [d for d in capability.dependencies if agent_registry.resolve_name(d)]
        return []
    
    async def route_to_agents(
        self,
        execution_plan: Dict[str, Any],
        request: AgentRequest
    ) -> List[AgentResponse]:
        """
        Execute agents using topological levels with parallel dispatch.
        
        For each level:
          - All agents in the level run concurrently via asyncio.gather()
          - Each level waits for completion before the next level starts
          - SharedContext enables cross-agent data sharing
        """
        from app.core.registry import agent_registry
        from app.core.shared_context import shared_context
        
        responses = []
        completed_agents = set()
        
        # Use execution_levels if available, otherwise fall back to flat execution_plan
        execution_levels = execution_plan.get("execution_levels")
        
        if execution_levels:
            # ── NEW: Level-based parallel execution ──
            allowed_agents = set(execution_plan.get("agents", []))
            agent_tasks = {}
            for step in execution_plan.get("execution_plan", []):
                key = agent_registry.resolve_name(step["agent"])
                if key:
                    agent_tasks[key] = step.get("task", request.query)
            
            for level_idx, level in enumerate(execution_levels):
                logger.info(f"▶ Executing level {level_idx}: {level}")
                
                # Build coroutines for this level
                level_coros = []
                level_agents = []
                
                for raw_name in level:
                    registry_key = agent_registry.resolve_name(raw_name)
                    if registry_key is None:
                        logger.warning(f"Skipping unknown agent: {raw_name}")
                        continue
                    
                    if registry_key not in allowed_agents:
                        continue
                    
                    agent = agent_registry.get_agent(registry_key)
                    if agent is None:
                        logger.error(f"Agent '{registry_key}' registered but instance is None")
                        continue
                    
                    # Inject shared context
                    agent.shared_context = shared_context
                    
                    agent_req = AgentRequest(
                        query=agent_tasks.get(registry_key, request.query),
                        context=request.context,
                        session_id=request.session_id,
                        user_id=request.user_id,
                        parameters={},
                        workflow_id=request.workflow_id
                    )
                    
                    level_coros.append(agent.execute_with_observability(agent_req))
                    level_agents.append(registry_key)
                
                if not level_coros:
                    continue
                
                # Execute level in parallel
                level_results = await asyncio.gather(*level_coros, return_exceptions=True)
                
                for registry_key, result in zip(level_agents, level_results):
                    if isinstance(result, Exception):
                        logger.error(f"Agent '{registry_key}' raised exception: {result}")
                        response = AgentResponse(
                            agent_name=registry_key,
                            success=False,
                            error=str(result)
                        )
                    else:
                        response = result
                        response.agent_name = registry_key
                    
                    responses.append(response)
                    
                    if response.success:
                        completed_agents.add(registry_key)
                        if response.data:
                            request.context[f"{registry_key}_output"] = response.data
                            if registry_key == "order_manager":
                                request.context["order_manager_output"] = response.data
        
        else:
            # ── FALLBACK: Sequential execution (backward compatibility) ──
            for step in execution_plan.get("execution_plan", []):
                raw_name = step["agent"]
                registry_key = agent_registry.resolve_name(raw_name)
                
                if registry_key is None:
                    logger.warning(f"Skipping unknown agent: {raw_name}")
                    continue
                
                allowed_agents = {
                    agent_registry.resolve_name(a) 
                    for a in execution_plan.get("agents", [])
                }
                allowed_agents.discard(None)
                
                if registry_key not in allowed_agents:
                    continue

                # Check Dependencies
                raw_deps = step.get("depends_on", [])
                relevant_deps = [
                    d for d in raw_deps 
                    if agent_registry.resolve_name(d) in allowed_agents
                ]
                missing_deps = [
                    d for d in relevant_deps 
                    if agent_registry.resolve_name(d) not in completed_agents
                ]
                
                if missing_deps:
                    logger.warning(f"Skipping {registry_key} due to missing dependencies: {missing_deps}")
                    continue

                agent = agent_registry.get_agent(registry_key)
                if agent is None:
                    logger.error(f"Agent '{registry_key}' registered but instance is None")
                    continue
                
                # Inject shared context
                agent.shared_context = shared_context
                
                agent_req = AgentRequest(
                    query=step.get("task", request.query),
                    context=request.context,
                    session_id=request.session_id,
                    user_id=request.user_id,
                    parameters=step.get("parameters", {}),
                    workflow_id=request.workflow_id
                )
                
                response = await agent.execute_with_observability(agent_req)
                response.agent_name = registry_key
                
                responses.append(response)
                
                if response.success:
                    completed_agents.add(registry_key)
                    if response.data:
                        request.context[f"{registry_key}_output"] = response.data
                        if registry_key == "order_manager":
                            request.context["order_manager_output"] = response.data
                        
        if request.session_id:
            await streaming_service.publish_workflow_completed(request.session_id)
            logger.info(f"✅ Workflow completed for session {request.session_id}")

        return responses


# Singleton
orchestrator = OrchestratorAgent()