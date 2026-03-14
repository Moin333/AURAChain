# tests/test_agents.py
"""
Unit tests: Agent Registry, Capability Introspection, Reasoning Loop
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ── Agent Registry ──

class TestAgentRegistry:
    """Unit tests for registry.py"""

    def test_register_agent(self):
        from app.core.registry import AgentRegistry, AgentCapability
        
        registry = AgentRegistry()
        mock_agent_class = MagicMock()
        cap = AgentCapability(
            name="test_agent",
            display_name="TestAgent",
            description="A test agent",
            required_inputs=["dataset"],
            produces_outputs=["result"],
            can_run_without_data=False,
            estimated_duration_ms=5000,
            dependencies=[]
        )
        
        registry.register("test_agent", mock_agent_class, cap)
        
        assert registry.count == 1
        assert registry.get_agent("test_agent") is not None
        assert registry.get_capability("test_agent") == cap
    
    def test_duplicate_registration_skipped(self):
        from app.core.registry import AgentRegistry, AgentCapability
        
        registry = AgentRegistry()
        mock_class = MagicMock()
        cap = AgentCapability(
            name="dup", display_name="Dup", description="",
            required_inputs=[], produces_outputs=[],
            can_run_without_data=True, estimated_duration_ms=1000,
            dependencies=[]
        )
        
        registry.register("dup", mock_class, cap)
        registry.register("dup", mock_class, cap)  # Should be skipped
        
        assert registry.count == 1
    
    def test_name_normalization(self):
        from app.core.registry import AgentRegistry, AgentCapability
        
        registry = AgentRegistry()
        mock_class = MagicMock()
        cap = AgentCapability(
            name="data_harvester", display_name="DataHarvester",
            description="", required_inputs=[], produces_outputs=[],
            can_run_without_data=True, estimated_duration_ms=1000,
            dependencies=[]
        )
        
        registry.register("data_harvester", mock_class, cap)
        
        # All of these should resolve to the same agent
        assert registry.resolve_name("data_harvester") == "data_harvester"
        assert registry.resolve_name("Data Harvester") == "data_harvester"
        assert registry.resolve_name("dataharvester") == "data_harvester"
    
    def test_register_auto_with_capability(self):
        from app.core.registry import AgentRegistry, AgentCapability
        
        registry = AgentRegistry()
        
        cap = AgentCapability(
            name="auto_agent", display_name="AutoAgent",
            description="Self-declaring", required_inputs=["data"],
            produces_outputs=["output"], can_run_without_data=False,
            estimated_duration_ms=3000, dependencies=[]
        )
        
        mock_class = MagicMock()
        mock_class.capability = cap
        
        registry.register_auto("auto_agent", mock_class)
        assert registry.count == 1
        assert registry.get_capability("auto_agent") == cap
    
    def test_register_auto_without_capability_raises(self):
        from app.core.registry import AgentRegistry
        
        registry = AgentRegistry()
        mock_class = MagicMock(spec=[])  # No capability attr
        mock_class.__name__ = "BadAgent"
        mock_class.capability = None
        
        with pytest.raises(ValueError, match="has no capability"):
            registry.register_auto("bad", mock_class)
    
    def test_list_capabilities(self):
        from app.core.registry import AgentRegistry, AgentCapability
        
        registry = AgentRegistry()
        for name in ["a", "b", "c"]:
            cap = AgentCapability(
                name=name, display_name=name.upper(), description="",
                required_inputs=[], produces_outputs=[],
                can_run_without_data=True, estimated_duration_ms=1000,
                dependencies=[]
            )
            registry.register(name, MagicMock(), cap)
        
        caps = registry.list_capabilities()
        assert len(caps) == 3
        assert set(caps.keys()) == {"a", "b", "c"}


# ── Evaluation Metrics ──

class TestEvaluationMetrics:
    """Unit tests for evaluation.py compute_metrics()"""

    def test_data_harvester_metrics(self):
        from app.core.evaluation import agent_evaluator
        
        output = {
            "metadata": {
                "quality_score": 0.95,
                "completeness": 0.88,
                "rows_processed": 100
            }
        }
        
        metrics = agent_evaluator.compute_metrics("data_harvester", output)
        assert len(metrics) >= 1
        
        completeness = next(m for m in metrics if m.metric_name == "data_completeness")
        assert completeness.value == 88.0  # 0.88 * 100
        assert completeness.interpretation == "good"
    
    def test_forecaster_mape_metric(self):
        from app.core.evaluation import agent_evaluator
        
        output = {"metadata": {"mape": 12.5, "confidence_score": 0.82}}
        
        metrics = agent_evaluator.compute_metrics("forecaster", output)
        mape = next(m for m in metrics if m.metric_name == "forecast_accuracy_mape")
        assert mape.value == 12.5
        assert mape.interpretation == "good"  # < 15
    
    def test_mcts_optimizer_cost_improvement(self):
        from app.core.evaluation import agent_evaluator
        
        output = {"expected_savings": {"percentage": 18.5}, "optimal_action": "reduce"}
        
        metrics = agent_evaluator.compute_metrics("mcts_optimizer", output)
        cost = next(m for m in metrics if m.metric_name == "cost_improvement")
        assert cost.value == 18.5
        assert cost.interpretation == "good"  # > 10
    
    def test_unknown_agent_returns_empty(self):
        from app.core.evaluation import agent_evaluator
        
        metrics = agent_evaluator.compute_metrics("unknown_agent", {"data": 123})
        assert metrics == []
    
    def test_visualizer_chart_validity(self):
        from app.core.evaluation import agent_evaluator
        
        good = agent_evaluator.compute_metrics("visualizer", {"chart_spec": "{}"})
        bad = agent_evaluator.compute_metrics("visualizer", {"text": "no chart"})
        
        assert good[0].value == 1.0
        assert bad[0].value == 0.0


# ── Workflow Visualizer ──

class TestWorkflowVisualizer:
    """Unit tests for workflow_visualizer.py"""

    def test_build_graph(self):
        from app.core.workflow_visualizer import workflow_visualizer
        
        plan = {
            "execution_levels": [["data_harvester"], ["trend_analyst", "visualizer"], ["forecaster"]],
            "execution_plan": [
                {"agent": "trend_analyst", "depends_on": ["data_harvester"]},
                {"agent": "visualizer", "depends_on": ["data_harvester"]},
                {"agent": "forecaster", "depends_on": ["trend_analyst"]}
            ]
        }
        
        graph = workflow_visualizer.build_graph(plan)
        assert graph["total_agents"] == 4
        assert graph["total_levels"] == 3
        assert len(graph["edges"]) == 3
    
    def test_to_mermaid(self):
        from app.core.workflow_visualizer import workflow_visualizer
        
        plan = {
            "execution_levels": [["a"], ["b"]],
            "execution_plan": [{"agent": "b", "depends_on": ["a"]}]
        }
        
        mermaid = workflow_visualizer.to_mermaid(plan)
        assert "graph TD" in mermaid
        assert "a --> b" in mermaid
    
    def test_critical_path(self):
        from app.core.workflow_visualizer import workflow_visualizer
        
        plan = {
            "execution_levels": [["a"], ["b", "c"], ["d"]],
            "execution_plan": [
                {"agent": "b", "depends_on": ["a"]},
                {"agent": "c", "depends_on": ["a"]},
                {"agent": "d", "depends_on": ["b"]}
            ]
        }
        
        path = workflow_visualizer.get_critical_path(plan)
        assert path == ["a", "b", "d"]
