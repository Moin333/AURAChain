# app/core/workflow_planner.py
"""
DAG-based Workflow Planner — builds execution graphs from intent + capabilities.

Takes a WorkflowIntent (semantic, no agent names) and maps it to concrete
agents using AgentCapability metadata from the registry. Enforces safety
guardrails programmatically, validates the DAG, and estimates cost.

Flow:
    WorkflowIntent → match capabilities → resolve dependencies →
    validate DAG → estimate cost → WorkflowPlan
"""

from typing import Dict, List, Set, Optional, Any
from pydantic import BaseModel
from collections import defaultdict, deque
from loguru import logger
from app.core.intent_analyzer import WorkflowIntent


class WorkflowPlan(BaseModel):
    """The output of the WorkflowPlanner — a validated execution graph."""
    intent: WorkflowIntent
    execution_levels: List[List[str]]   # [["data_harvester"], ["trend_analyst", "visualizer"], ...]
    agent_tasks: Dict[str, str]         # {"data_harvester": "Clean and profile dataset"}
    agents: List[str]                   # Flat list for backward compatibility
    reasoning: str                      # Human-readable plan explanation
    estimated_duration_ms: int          # Total estimated time
    estimated_llm_calls: int            # Number of LLM API calls
    validation_warnings: List[str]      # Non-fatal warnings


class WorkflowPlanner:
    """
    Builds execution DAGs from intent + agent capabilities.
    
    Key design: The LLM never names agents. The planner maps semantic
    intent flags → agents via AgentCapability metadata.
    """
    
    # Intent flag → agent mapping
    # This is the ONLY place where intent is mapped to concrete agents.
    INTENT_TO_AGENTS = {
        "wants_forecast": ["forecaster"],
        "wants_optimization": ["mcts_optimizer"],
        "wants_visualization": ["visualizer"],
        "wants_order": ["order_manager"],
        "wants_notification": ["notifier"],
    }
    
    # Analysis type → agents that should run for this analysis
    ANALYSIS_TYPE_AGENTS = {
        "forecast": ["trend_analyst", "forecaster"],
        "trend": ["trend_analyst"],
        "optimization": ["trend_analyst", "forecaster", "mcts_optimizer"],
        "visualization": ["visualizer"],
        "general": ["trend_analyst"],
    }
    
    # LLM call estimates per agent (for cost estimation)
    LLM_CALLS_PER_AGENT = {
        "data_harvester": 1,
        "trend_analyst": 1,
        "forecaster": 1,
        "mcts_optimizer": 1,
        "visualizer": 1,
        "order_manager": 1,
        "notifier": 0,
    }
    
    def build_plan(
        self,
        intent: WorkflowIntent,
        context: Dict[str, Any]
    ) -> WorkflowPlan:
        """
        Build a validated execution plan from intent + context.
        
        Steps:
            1. Map intent → candidate agents
            2. Resolve dependencies (add upstream agents)
            3. Apply guardrails (cold-start bans, notifier rules)
            4. Auto-include data_harvester for deep analysis
            5. Build DAG via topological sort
            6. Validate the DAG
            7. Generate task descriptions
            8. Estimate cost
        """
        from app.core.registry import agent_registry
        
        warnings: List[str] = []
        
        # ── Step 1: Map intent to candidate agents ──
        candidates: Set[str] = set()
        
        # Add agents from analysis type
        analysis_agents = self.ANALYSIS_TYPE_AGENTS.get(intent.analysis_type, ["trend_analyst"])
        candidates.update(analysis_agents)
        
        # Add agents from intent flags
        for flag, agents in self.INTENT_TO_AGENTS.items():
            if getattr(intent, flag, False):
                candidates.update(agents)
        
        # ── Step 2: Resolve dependencies ──
        resolved = self._resolve_dependencies(candidates, agent_registry)
        
        # ── Step 3: Apply guardrails ──
        resolved, guardrail_warnings = self._apply_guardrails(resolved, intent)
        warnings.extend(guardrail_warnings)
        
        # ── Step 4: Auto-include data_harvester if dataset exists ──
        # BUG-9 fix: If the query involves data, ALWAYS include data_harvester
        # Otherwise agents like trend_analyst get removed due to missing dependencies
        if intent.has_data and "data_harvester" not in resolved:
            resolved.add("data_harvester")
            logger.info("Auto-included data_harvester because dataset exists")

        # Passive AutoEDA
        if intent.has_data and "dataset" in context:
            try:
                import pandas as pd
                from app.tools.analysis_tools import AnalysisTools
                df_eda = pd.DataFrame(context["dataset"][:500])
                eda_profile = AnalysisTools.auto_eda(df_eda)
                logger.info(f"Passive AutoEDA complete: {len(eda_profile.get('insights', []))} insights found")
            except Exception as e:
                logger.warning(f"Passive AutoEDA failed: {str(e)}")
        
        # ── Step 5: Topological sort → execution levels ──
        execution_levels = self._topological_sort(resolved, agent_registry)
        
        # ── Step 6: Validate DAG ──
        validation_errors = self._validate_dag(execution_levels, resolved, agent_registry)
        if validation_errors:
            warnings.extend(validation_errors)
        
        # ── Step 7: Generate task descriptions ──
        agent_tasks = self._generate_tasks(resolved, intent)
        
        # ── Step 8: Estimate cost ──
        estimated_duration = self._estimate_duration(resolved, agent_registry)
        estimated_llm_calls = sum(
            self.LLM_CALLS_PER_AGENT.get(a, 1) for a in resolved
        )
        
        # Build flat agent list (ordered by execution levels)
        flat_agents = []
        for level in execution_levels:
            flat_agents.extend(level)
        
        # Build reasoning
        reasoning = self._build_reasoning(intent, flat_agents, execution_levels)
        
        plan = WorkflowPlan(
            intent=intent,
            execution_levels=execution_levels,
            agent_tasks=agent_tasks,
            agents=flat_agents,
            reasoning=reasoning,
            estimated_duration_ms=estimated_duration,
            estimated_llm_calls=estimated_llm_calls,
            validation_warnings=warnings
        )
        
        logger.info(
            f"📋 Plan built: {len(flat_agents)} agents in {len(execution_levels)} levels, "
            f"~{estimated_duration}ms, ~{estimated_llm_calls} LLM calls"
        )
        
        return plan
    
    def _resolve_dependencies(self, candidates: Set[str], registry) -> Set[str]:
        """Walk dependency graph to include all required upstream agents."""
        resolved = set(candidates)
        queue = deque(candidates)
        
        while queue:
            agent_name = queue.popleft()
            capability = registry.get_capability(agent_name)
            if capability is None:
                continue
            
            for dep in capability.dependencies:
                dep_key = registry.resolve_name(dep)
                if dep_key and dep_key not in resolved:
                    resolved.add(dep_key)
                    queue.append(dep_key)
        
        return resolved
    
    def _apply_guardrails(
        self,
        agents: Set[str],
        intent: WorkflowIntent
    ) -> tuple[Set[str], List[str]]:
        """Enforce safety rules. Returns (filtered_agents, warnings)."""
        warnings = []
        filtered = set(agents)
        
        # Rule 1: Cold start — no data-dependent agents without data
        if not intent.has_data:
            data_dependent = {"data_harvester", "forecaster", "mcts_optimizer"}
            removed = filtered & data_dependent
            if removed:
                warnings.append(f"Cold start: removed {removed} (no dataset)")
                filtered -= data_dependent
        
        # Rule 2: Notifier requires order_manager
        if "notifier" in filtered and "order_manager" not in filtered:
            filtered.discard("notifier")
            warnings.append("Removed notifier: no order_manager in plan")
        
        # Rule 3: Order manager only when explicitly requested
        if "order_manager" in filtered and not intent.wants_order:
            filtered.discard("order_manager")
            filtered.discard("notifier")
            warnings.append("Removed order_manager: not explicitly requested")
        
        # Rule 4: Must have at least one agent
        if not filtered:
            filtered.add("trend_analyst")
            warnings.append("Empty plan — defaulting to trend_analyst")
        
        return filtered, warnings
    
    def _topological_sort(self, agents: Set[str], registry) -> List[List[str]]:
        """
        Sort agents into execution levels via topological ordering.
        
        Level 0: agents with no dependencies in the plan
        Level 1: agents whose deps are all in level 0
        ...and so on.
        
        Agents at the same level can run in parallel.
        """
        # Build adjacency for agents in this plan only
        in_degree: Dict[str, int] = {a: 0 for a in agents}
        dependents: Dict[str, List[str]] = defaultdict(list)
        
        for agent_name in agents:
            capability = registry.get_capability(agent_name)
            if capability is None:
                continue
            
            for dep in capability.dependencies:
                dep_key = registry.resolve_name(dep)
                if dep_key and dep_key in agents:
                    in_degree[agent_name] += 1
                    dependents[dep_key].append(agent_name)
        
        # BFS by levels (Kahn's algorithm)
        levels: List[List[str]] = []
        queue = deque([a for a, deg in in_degree.items() if deg == 0])
        
        while queue:
            current_level = sorted(queue)  # Deterministic ordering within level
            levels.append(current_level)
            
            next_queue = deque()
            for agent_name in current_level:
                for dependent in dependents[agent_name]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_queue.append(dependent)
            
            queue = next_queue
        
        # Check for cycles (agents not placed in any level)
        placed = {a for level in levels for a in level}
        unplaced = agents - placed
        if unplaced:
            logger.error(f"Cycle detected in agent dependencies: {unplaced}")
            # Force them into a final level to avoid deadlock
            levels.append(sorted(unplaced))
        
        return levels
    
    def _validate_dag(
        self,
        levels: List[List[str]],
        agents: Set[str],
        registry
    ) -> List[str]:
        """Validate the execution DAG. Returns list of warnings."""
        warnings = []
        
        # Check 1: All agents exist in registry
        for agent_name in agents:
            if registry.get_agent(agent_name) is None:
                warnings.append(f"Agent '{agent_name}' not found in registry")
        
        # Check 2: All dependencies satisfied within the plan
        for agent_name in agents:
            capability = registry.get_capability(agent_name)
            if capability is None:
                continue
            for dep in capability.dependencies:
                dep_key = registry.resolve_name(dep)
                if dep_key and dep_key not in agents:
                    warnings.append(f"Agent '{agent_name}' depends on '{dep}' which is not in this plan")
        
        # Check 3: No empty levels
        empty_levels = [i for i, lvl in enumerate(levels) if not lvl]
        if empty_levels:
            warnings.append(f"Empty execution levels detected: {empty_levels}")
        
        return warnings
    
    def _generate_tasks(self, agents: Set[str], intent: WorkflowIntent) -> Dict[str, str]:
        """Generate human-readable task descriptions per agent."""
        task_templates = {
            "data_harvester": f"Clean and profile the dataset for: {intent.goal}",
            "trend_analyst": f"Analyze trends relevant to: {intent.goal}",
            "forecaster": f"Generate demand/value forecasts for: {intent.goal}",
            "mcts_optimizer": f"Optimize inventory decisions for: {intent.goal}",
            "visualizer": f"Create visualizations for: {intent.goal}",
            "order_manager": f"Draft purchase order for: {intent.goal}",
            "notifier": f"Send notification about: {intent.goal}",
        }
        
        return {a: task_templates.get(a, f"Process: {intent.goal}") for a in agents}
    
    def _estimate_duration(self, agents: Set[str], registry) -> int:
        """Estimate total duration accounting for parallelism."""
        levels = self._topological_sort(agents, registry)
        total_ms = 0
        
        for level in levels:
            # Parallel execution: level takes as long as the slowest agent
            level_max = 0
            for agent_name in level:
                capability = registry.get_capability(agent_name)
                if capability:
                    level_max = max(level_max, capability.estimated_duration_ms)
            total_ms += level_max
        
        return total_ms
    
    def _build_reasoning(
        self,
        intent: WorkflowIntent,
        agents: List[str],
        levels: List[List[str]]
    ) -> str:
        """Build human-readable reasoning for the plan."""
        level_strs = []
        for i, level in enumerate(levels):
            if len(level) > 1:
                level_strs.append(f"Level {i}: {', '.join(level)} (parallel)")
            else:
                level_strs.append(f"Level {i}: {level[0]}")
        
        return (
            f"Goal: {intent.goal}\n"
            f"Analysis: {intent.analysis_type} ({intent.depth})\n"
            f"Pipeline: {' → '.join(level_strs)}\n"
            f"Agents: {len(agents)} total in {len(levels)} levels"
        )


# Global instance
workflow_planner = WorkflowPlanner()
