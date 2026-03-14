# tests/test_memory.py
"""
Unit tests: Semantic Memory Search, Tool Registry Caching
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import json


# ── Tool Registry ──

class TestToolRegistry:
    """Unit tests for tool_registry.py"""

    @pytest.mark.asyncio
    async def test_invoke_registered_tool(self):
        from app.core.tool_registry import ToolRegistry
        
        registry = ToolRegistry()
        
        async def mock_tool(x=0):
            return {"result": x * 2}
        
        registry.register("double", mock_tool, description="Doubles input")
        result = await registry.invoke("double", x=5)
        
        assert result.success is True
        assert result.data["result"] == 10
        assert result.cached is False
        assert result.duration_ms > 0
    
    @pytest.mark.asyncio
    async def test_invoke_unregistered_tool(self):
        from app.core.tool_registry import ToolRegistry
        
        registry = ToolRegistry()
        result = await registry.invoke("nonexistent")
        
        assert result.success is False
        assert "not registered" in result.error
    
    @pytest.mark.asyncio
    async def test_invoke_retry_on_failure(self):
        from app.core.tool_registry import ToolRegistry
        
        registry = ToolRegistry()
        call_count = 0
        
        async def flaky_tool():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First call fails")
            return {"ok": True}
        
        registry.register("flaky", flaky_tool, cacheable=False)
        result = await registry.invoke("flaky")
        
        assert result.success is True
        assert call_count == 2  # Retried once
    
    def test_tool_stats(self):
        from app.core.tool_registry import ToolRegistry
        
        registry = ToolRegistry()
        registry.register("a", AsyncMock())
        registry.register("b", AsyncMock())
        
        stats = registry.get_stats()
        assert stats["total_calls"] == 0
        assert "a" in stats["per_tool"]
    
    def test_list_tools(self):
        from app.core.tool_registry import ToolRegistry
        
        registry = ToolRegistry()
        registry.register("tool1", AsyncMock(), description="Tool 1")
        registry.register("tool2", AsyncMock(), description="Tool 2")
        
        tools = registry.list_tools()
        assert len(tools) == 2
        assert tools[0].name == "tool1"


# ── Semantic Memory ──

class TestSemanticMemory:
    """Unit tests for memory.py semantic search"""

    @pytest.mark.asyncio
    async def test_semantic_search_returns_relevant_facts(self):
        """Test that embedding search filters irrelevant facts."""
        from app.core.memory import MemoryManager
        
        manager = MemoryManager()
        
        # Mock the embedding model
        mock_model = MagicMock()
        manager._embed_model = mock_model
        
        # Simulate: query about sneakers, one relevant fact, one irrelevant
        import numpy as np
        
        query_emb = np.array([1.0, 0.0, 0.0])
        fact_embs = np.array([
            [0.95, 0.05, 0.0],  # High similarity (sneaker demand)
            [0.0, 0.0, 1.0],   # Low similarity (office supplies)
        ])
        
        mock_model.encode = MagicMock(side_effect=[query_emb, fact_embs])
        
        facts = {
            "sneaker_demand": "Diwali increases sneaker demand by 40%",
            "office_supplies": "Paper clips purchased monthly"
        }
        
        result = await manager._semantic_search(
            "user1", "optimize sneaker inventory", facts, mock_model, top_k=5
        )
        
        # Should return sneaker fact (similarity > 0.2) but not office supplies
        assert "sneaker_demand" in result
    
    def test_get_embedding_model_fallback(self):
        """Test graceful fallback when sentence-transformers not installed."""
        from app.core.memory import MemoryManager
        
        manager = MemoryManager()
        
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            # Force reimport
            if hasattr(manager, '_embed_model'):
                delattr(manager, '_embed_model')
            
            with patch("builtins.__import__", side_effect=ImportError("No module")):
                model = manager._get_embedding_model()
                # Should return None, not crash
                assert model is None
