# tests/test_reports.py
"""
Integration tests: Report API, Health Dashboard
Failure tests: LLM failure, circuit breaker, rate limit, timeout, Redis fallback
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch


# ── Report API (Integration) ──

class TestReportAPI:
    """Integration tests for /reports endpoints"""

    @pytest.mark.asyncio
    async def test_get_report_not_found(self):
        with patch("app.core.report_engine.report_engine.get_report", new_callable=AsyncMock, return_value=None):
            from app.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/reports/nonexistent_wf")
                assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_summary_not_found(self):
        with patch("app.core.artifacts.artifact_store.get", new_callable=AsyncMock, return_value=None):
            from app.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/reports/nonexistent_wf/summary")
                assert resp.status_code == 404


# ── Experiment API (Integration) ──

class TestExperimentAPI:
    """Integration tests for /experiments endpoints"""

    @pytest.mark.asyncio
    async def test_list_experiments_empty(self):
        with patch("app.core.experiments.experiment_logger.list_experiments", new_callable=AsyncMock, return_value=[]):
            from app.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/experiments/")
                assert resp.status_code == 200
                assert resp.json()["count"] == 0


# ── Decision API (Integration) ──

class TestDecisionAPI:
    """Integration tests for /decisions endpoints"""

    @pytest.mark.asyncio
    async def test_list_decisions_empty(self):
        with patch("app.core.decision_memory.decision_memory.get_decision_history", new_callable=AsyncMock, return_value=[]):
            from app.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/decisions/")
                assert resp.status_code == 200
                assert resp.json()["count"] == 0

    @pytest.mark.asyncio
    async def test_get_decision_not_found(self):
        with patch("app.core.decision_memory.decision_memory.get_decision", new_callable=AsyncMock, return_value=None):
            from app.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/decisions/dec_nonexistent")
                assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_decision_stats(self):
        with patch(
            "app.core.decision_memory.decision_memory.get_accuracy_stats",
            new_callable=AsyncMock,
            return_value={"total_decisions": 5, "average_accuracy": 0.87}
        ):
            from app.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/decisions/stats")
                assert resp.status_code == 200
                assert resp.json()["total_decisions"] == 5


# ── Visualization API (Integration) ──

class TestVisualizationAPI:
    """Integration tests for /workflows/visualize"""

    @pytest.mark.asyncio
    async def test_visualize_workflow(self):
        from app.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            plan = {
                "execution_levels": [["data_harvester"], ["trend_analyst"]],
                "execution_plan": [
                    {"agent": "trend_analyst", "depends_on": ["data_harvester"]}
                ]
            }
            resp = await client.post("/api/v1/workflows/visualize", json={"plan": plan})
            assert resp.status_code == 200
            data = resp.json()
            assert "graph" in data
            assert "mermaid" in data
            assert "critical_path" in data


# ── Failure Tests ──

class TestFailureScenarios:
    """Circuit breaker, timeout, Redis failure, rate limit"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self):
        from app.core.api_clients import CircuitBreaker
        from collections import defaultdict
        
        cb = CircuitBreaker.__new__(CircuitBreaker)
        cb.failure_threshold = 3
        cb.cooldown_seconds = 60
        cb._failures = defaultdict(int)
        cb._open_since = {}
        cb._latencies = defaultdict(list)
        cb._error_counts = defaultdict(int)
        cb._total_calls = defaultdict(int)
        cb._total_errors = defaultdict(int)
        
        key = "groq"
        model = "test-model"
        for _ in range(3):
            cb.record_failure(key, model)
        
        assert cb._key(key, model) in cb._open_since
    
    @pytest.mark.asyncio
    async def test_agent_timeout_produces_error_response(self):
        """Verify asyncio.wait_for wrapping in background.py"""
        import asyncio
        from app.agents.base_agent import AgentResponse
        from app.core.background import _execute_agent_with_timeout
        
        class SlowAgent:
            async def execute_with_observability(self, request):
                await asyncio.sleep(10)  # Would take 10s
                return AgentResponse(agent_name="slow", success=True)
        
        agent = SlowAgent()
        result = await _execute_agent_with_timeout(agent, None, "slow_agent", timeout_s=0.1)
        
        assert result.success is False
        assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_tool_registry_retry_on_failure(self):
        from app.core.tool_registry import ToolRegistry
        
        registry = ToolRegistry()
        attempt = 0
        
        async def fail_once():
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise RuntimeError("Transient error")
            return {"ok": True}
        
        registry.register("retry_test", fail_once, cacheable=False)
        result = await registry.invoke("retry_test")
        
        assert result.success is True
        assert attempt == 2

    @pytest.mark.asyncio
    async def test_semantic_memory_fallback_on_no_model(self):
        """Memory search should return all facts when model unavailable."""
        from app.core.memory import MemoryManager, Memory
        
        manager = MemoryManager()
        manager._embed_model = None  # No model
        manager.redis_client = AsyncMock()
        
        # Mock get_memory
        memory = Memory(user_id="u1", last_updated="2024-01-01T00:00:00Z")
        memory.facts = {"fact1": "value1", "fact2": "value2"}
        manager.get_memory = AsyncMock(return_value=memory)
        
        result = await manager.get_relevant_context("u1", "test query")
        
        # Should return ALL facts (fallback)
        assert result["facts"] == {"fact1": "value1", "fact2": "value2"}
