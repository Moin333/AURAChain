# app/core/registry.py
"""
Centralized Agent Registry — singleton agent instances + capability metadata.

Replaces the per-request lazy imports and fresh instantiation previously
hardcoded in orchestrator.route_to_agents().

Key design decisions:
  - Agents are created once at registration time (singleton instances)
  - Each agent self-describes via AgentCapability (required_inputs, produces_outputs)
  - Aggressive name normalization for LLM plan resilience
  - Lazy-safe: get_agent() returns None for unknown names, never crashes
"""

from typing import Dict, List, Optional, Type
from pydantic import BaseModel
from app.agents.base_agent import BaseAgent
from loguru import logger


class AgentCapability(BaseModel):
    """Describes what an agent needs and what it produces."""
    name: str                         # Registry key: "data_harvester"
    display_name: str                 # Human-readable: "DataHarvester"
    description: str                  # For LLM prompts and auto-discovery
    required_inputs: List[str]        # What this agent needs: ["dataset"]
    produces_outputs: List[str]       # What this agent creates: ["cleaned_dataset", "quality_report"]
    can_run_without_data: bool        # For cold-start scenarios
    estimated_duration_ms: int        # Rough execution time
    dependencies: List[str]           # Upstream agent names: ["data_harvester"]


class AgentRegistry:
    """
    Manages registration, lookup, and lifecycle of all agents.
    
    Usage:
        registry = AgentRegistry()
        registry.register("data_harvester", DataHarvesterAgent, capability)
        agent = registry.get_agent("data_harvester")       # singleton
        agent = registry.get_agent("Data Harvester")        # normalization
        caps = registry.list_capabilities()
    """
    
    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self._capabilities: Dict[str, AgentCapability] = {}
        self._name_lookup: Dict[str, str] = {}  # normalized → registry key
    
    @staticmethod
    def _normalize(name: str) -> str:
        """Aggressive normalization: 'Data Harvester', 'data_harvester', 'dataharvester' → 'dataharvester'"""
        return name.lower().replace("_", "").replace(" ", "").replace("-", "")
    
    def register(
        self,
        name: str,
        agent_class: Type[BaseAgent],
        capability: AgentCapability
    ) -> None:
        """Register an agent class with its capability metadata. Instantiates once."""
        if name in self._agents:
            logger.warning(f"Agent '{name}' already registered, skipping duplicate")
            return
        
        self._agents[name] = agent_class()
        self._capabilities[name] = capability
        self._name_lookup[self._normalize(name)] = name
        
        logger.debug(f"Registered agent: {name} ({capability.display_name})")
    
    def register_auto(
        self,
        name: str,
        agent_class: Type[BaseAgent]
    ) -> None:
        """
        Register an agent using its class-level capability (auto-introspection).
        
        Falls back to register() if the agent class has a `capability` attribute.
        Raises ValueError if no capability is defined.
        """
        cap = getattr(agent_class, "capability", None)
        if cap is None:
            raise ValueError(
                f"Agent class '{agent_class.__name__}' has no capability attribute. "
                f"Use register() with explicit capability instead."
            )
        self.register(name, agent_class, cap)
    
    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Get a singleton agent instance by name (supports normalized lookup)."""
        key = self.resolve_name(name)
        if key is None:
            return None
        return self._agents.get(key)
    
    def get_capability(self, name: str) -> Optional[AgentCapability]:
        """Get capability metadata for an agent."""
        key = self.resolve_name(name)
        if key is None:
            return None
        return self._capabilities.get(key)
    
    def resolve_name(self, raw_name: str) -> Optional[str]:
        """Resolve any name variant to the canonical registry key."""
        # Direct match first
        if raw_name in self._agents:
            return raw_name
        # Normalized match
        normalized = self._normalize(raw_name)
        return self._name_lookup.get(normalized)
    
    def list_capabilities(self) -> Dict[str, AgentCapability]:
        """Return all registered capabilities."""
        return dict(self._capabilities)
    
    def list_agent_names(self) -> List[str]:
        """Return all registered agent names."""
        return list(self._agents.keys())
    
    @property
    def count(self) -> int:
        return len(self._agents)


# ==================== GLOBAL INSTANCE ====================

agent_registry = AgentRegistry()


def register_all_agents() -> None:
    """
    Import and register all agents at startup.
    Called from main.py lifespan — replaces lazy imports in orchestrator.route_to_agents().
    """
    from app.agents.data_harvester import DataHarvesterAgent
    from app.agents.trend_analyst import TrendAnalystAgent
    from app.agents.forecaster import ForecasterAgent
    from app.agents.mcts_optimizer import MCTSOptimizerAgent
    from app.agents.visualizer import VisualizerAgent
    from app.agents.order_manager import OrderManagerAgent
    from app.agents.notifier import NotifierAgent

    registrations = [
        (
            "data_harvester",
            DataHarvesterAgent,
            AgentCapability(
                name="data_harvester",
                display_name="DataHarvester",
                description="Ingests, cleans, and preprocesses data. Runs for new uploads or when deep analysis requires guaranteed data quality.",
                required_inputs=["dataset"],
                produces_outputs=["cleaned_dataset", "quality_report", "data_profile"],
                can_run_without_data=False,
                estimated_duration_ms=5000,
                dependencies=[]
            )
        ),
        (
            "trend_analyst",
            TrendAnalystAgent,
            AgentCapability(
                name="trend_analyst",
                display_name="TrendAnalyst",
                description="Identifies trends combining internal statistical analysis with external Google Trends data.",
                required_inputs=["dataset"],
                produces_outputs=["trend_analysis", "market_insights", "seasonality_patterns"],
                can_run_without_data=False,
                estimated_duration_ms=8000,
                dependencies=["data_harvester"]
            )
        ),
        (
            "forecaster",
            ForecasterAgent,
            AgentCapability(
                name="forecaster",
                display_name="Forecaster",
                description="Predicts future values using Facebook Prophet with holiday awareness.",
                required_inputs=["dataset"],
                produces_outputs=["forecast_results", "seasonality_components", "confidence_scores"],
                can_run_without_data=False,
                estimated_duration_ms=10000,
                dependencies=["data_harvester", "trend_analyst"]
            )
        ),
        (
            "mcts_optimizer",
            MCTSOptimizerAgent,
            AgentCapability(
                name="mcts_optimizer",
                display_name="MCTSOptimizer",
                description="Optimizes inventory decisions using Monte Carlo Tree Search with UCB1 selection.",
                required_inputs=["dataset"],
                produces_outputs=["optimal_action", "expected_savings", "bullwhip_metrics"],
                can_run_without_data=False,
                estimated_duration_ms=15000,
                dependencies=["forecaster"]
            )
        ),
        (
            "visualizer",
            VisualizerAgent,
            AgentCapability(
                name="visualizer",
                display_name="Visualizer",
                description="Creates charts and graphs using LLM-driven Plotly specifications.",
                required_inputs=["dataset"],
                produces_outputs=["chart_spec", "chart_json", "chart_html"],
                can_run_without_data=False,
                estimated_duration_ms=3000,
                dependencies=[]
            )
        ),
        (
            "order_manager",
            OrderManagerAgent,
            AgentCapability(
                name="order_manager",
                display_name="OrderManager",
                description="Drafts purchase orders based on analysis results. Used only when user explicitly wants to order.",
                required_inputs=[],
                produces_outputs=["order_plan"],
                can_run_without_data=True,
                estimated_duration_ms=3000,
                dependencies=[]
            )
        ),
        (
            "notifier",
            NotifierAgent,
            AgentCapability(
                name="notifier",
                display_name="Notifier",
                description="Sends Discord webhook notifications. Used only after an order is created.",
                required_inputs=["order_manager_output"],
                produces_outputs=["notification_result"],
                can_run_without_data=True,
                estimated_duration_ms=2000,
                dependencies=["order_manager"]
            )
        ),
    ]

    for name, agent_class, capability in registrations:
        agent_registry.register(name, agent_class, capability)

    logger.info(f"✓ Agent registry initialized ({agent_registry.count} agents)")
