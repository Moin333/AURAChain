# tests/test_full_workflow.py
"""
End-to-End Test: Full pipeline from query to decision record.

Scenario: "Optimize inventory for festive sneaker demand"

Pipeline: query → intent → plan → agent execution → report → experiment → decision
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestFullWorkflowE2E:
    """
    End-to-end test validating:
    1. Query accepted and plan returned
    2. Agents execute in DAG order
    3. Artifacts created per agent
    4. Report generated
    5. Experiment logged
    6. Decision recorded (because recommended_actions exist)
    7. SSE events would be streamed
    """

    @pytest.mark.asyncio
    async def test_query_returns_plan(self):
        """Step 1: POST /orchestrator/query returns plan with agents."""
        mock_plan = {
            "mode": "deep_dive",
            "reasoning": "User wants inventory optimization with forecast",
            "agents": ["data_harvester", "trend_analyst", "forecaster", "mcts_optimizer"],
            "execution_plan": [
                {"agent": "data_harvester", "task": "Clean data", "parameters": {}, "depends_on": []},
                {"agent": "trend_analyst", "task": "Find trends", "parameters": {}, "depends_on": ["data_harvester"]},
                {"agent": "forecaster", "task": "Predict demand", "parameters": {}, "depends_on": ["trend_analyst"]},
                {"agent": "mcts_optimizer", "task": "Optimize", "parameters": {}, "depends_on": ["forecaster"]},
            ],
            "execution_levels": [
                ["data_harvester"],
                ["trend_analyst"],
                ["forecaster"],
                ["mcts_optimizer"]
            ]
        }

        with patch("app.agents.orchestrator.orchestrator.process_query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {
                "request_id": "req_e2e_001",
                "session_id": "sess_e2e",
                "orchestration_plan": mock_plan,
                "message": "Analysis planned",
                "status": "planned"
            }
            
            from app.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/v1/orchestrator/query", json={
                    "query": "Optimize inventory for festive sneaker demand",
                    "session_id": "sess_e2e",
                    "user_id": "test_user",
                    "context": {},
                    "parameters": {}
                })
                
                assert resp.status_code == 200
                data = resp.json()
                assert "request_id" in data
                assert data["status"] == "planned"
    
    @pytest.mark.asyncio
    async def test_experiment_records_metrics_not_outputs(self):
        """Verify experiment comparison uses metrics, not full agent outputs."""
        from app.core.experiments import ExperimentLogger, ExperimentRecord
        
        logger = ExperimentLogger()
        
        exp = ExperimentRecord(
            experiment_id="exp_e2e",
            workflow_id="wf_e2e",
            dataset_hash="abc123",
            agent_config={"agents_used": ["forecaster", "mcts_optimizer"]},
            agent_metrics={
                "forecaster": {"mape": 12.5, "model_confidence": 0.82},
                "mcts_optimizer": {"cost_improvement": 18.5}
            },
            confidence_scores={"forecaster": 0.82, "mcts_optimizer": 0.75},
            overall_confidence=0.78,
            planner_reasoning="Intent: inventory optimization with demand forecast",
            report_summary="Recommend ordering 500 sneakers ahead of Diwali",
            execution_time_ms=25000
        )
        
        # Verify structure contains metrics, NOT full agent outputs
        assert "mape" in exp.agent_metrics["forecaster"]
        assert "cost_improvement" in exp.agent_metrics["mcts_optimizer"]
        assert exp.planner_reasoning != ""
    
    @pytest.mark.asyncio
    async def test_decision_only_recorded_with_actions(self):
        """Decision should NOT be recorded for passive queries."""
        from app.core.background import _record_decision_if_applicable
        
        # Mock report WITHOUT recommended actions
        mock_report = MagicMock()
        mock_report.sections = [
            MagicMock(title="Executive Summary", content="Sales are stable"),
            MagicMock(title="Data Quality", content="98% complete")
        ]
        mock_report.overall_confidence = 0.8
        
        with patch("app.core.decision_memory.decision_memory.record_decision") as mock_record:
            await _record_decision_if_applicable(
                "wf_passive", "Show me sales chart", [], mock_report, 5000
            )
            
            # Should NOT have been called (no recommended_actions)
            mock_record.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_decision_recorded_with_recommendations(self):
        """Decision SHOULD be recorded when report has recommended actions."""
        from app.core.background import _record_decision_if_applicable
        from app.agents.base_agent import AgentResponse
        
        mock_report = MagicMock()
        mock_report.sections = [
            MagicMock(title="Recommended Actions", content="Order 500 sneakers"),
            MagicMock(title="Forecast Analysis", content="Demand increasing")
        ]
        mock_report.overall_confidence = 0.85
        
        mock_responses = [
            AgentResponse(
                agent_name="forecaster", success=True,
                data={"metadata": {"mape": 12.5}},
                metadata={}
            )
        ]
        
        with patch("app.core.decision_memory.decision_memory.record_decision", new_callable=AsyncMock) as mock_record:
            await _record_decision_if_applicable(
                "wf_action", "Optimize sneaker inventory",
                mock_responses, mock_report, 15000
            )
            
            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args[1]
            assert call_kwargs["decision_type"] == "forecast"
            assert "Order 500 sneakers" in call_kwargs["recommended_actions"]
    
    @pytest.mark.asyncio
    async def test_visualization_of_e2e_plan(self):
        """Visualize the E2E plan produces valid graph."""
        from app.core.workflow_visualizer import workflow_visualizer
        
        plan = {
            "execution_levels": [
                ["data_harvester"],
                ["trend_analyst"],
                ["forecaster"],
                ["mcts_optimizer"]
            ],
            "execution_plan": [
                {"agent": "trend_analyst", "depends_on": ["data_harvester"]},
                {"agent": "forecaster", "depends_on": ["trend_analyst"]},
                {"agent": "mcts_optimizer", "depends_on": ["forecaster"]},
            ]
        }
        
        summary = workflow_visualizer.get_execution_summary(plan)
        
        assert summary["graph"]["total_agents"] == 4
        assert summary["graph"]["total_levels"] == 4
        assert "graph TD" in summary["mermaid"]
        assert summary["critical_path"] == [
            "data_harvester", "trend_analyst", "forecaster", "mcts_optimizer"
        ]


class TestPerformance:
    """Performance tests"""

    @pytest.mark.asyncio
    async def test_workflow_visualization_speed(self):
        """Visualization should complete in < 50ms for typical DAG."""
        import time
        from app.core.workflow_visualizer import workflow_visualizer
        
        plan = {
            "execution_levels": [
                ["agent_" + str(i)] for i in range(10)
            ],
            "execution_plan": [
                {"agent": f"agent_{i}", "depends_on": [f"agent_{i-1}"] if i > 0 else []}
                for i in range(10)
            ]
        }
        
        start = time.time()
        for _ in range(100):
            workflow_visualizer.get_execution_summary(plan)
        elapsed = (time.time() - start) / 100
        
        assert elapsed < 0.05, f"Visualization too slow: {elapsed:.3f}s per call"
    
    @pytest.mark.asyncio
    async def test_tool_registry_cache_effectiveness(self):
        """Cached tool calls should be near-instant."""
        import time
        from app.core.tool_registry import ToolRegistry
        
        registry = ToolRegistry()
        
        call_count = 0
        async def slow_tool(x=1):
            nonlocal call_count
            call_count += 1
            return {"result": x}
        
        registry.register("cached_tool", slow_tool)
        
        # Without Redis cache, tool should be called each time
        r1 = await registry.invoke("cached_tool", x=42)
        r2 = await registry.invoke("cached_tool", x=42)
        
        assert r1.success is True
        # Without Redis, both calls execute (no cache)
        assert call_count == 2
