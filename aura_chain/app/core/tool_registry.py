# app/core/tool_registry.py
"""
Tool Registry — wraps MCPServer with logging, caching, and clean agent API.

Agents call:
    result = await self.tools_registry.invoke("detect_outliers", data=df)

Instead of direct function calls. This enables:
- Tool call logging with duration
- Result caching (Redis, hash of tool_name + args)
- Tool-level error recovery (retry once)
- Clean, discoverable API
"""

import json
import hashlib
import time
import pandas as pd
from collections import deque
import redis.asyncio as redis
from typing import Dict, Any, List, Optional, Callable, Literal
from pydantic import BaseModel
from loguru import logger
from app.config import get_settings
from app.core.error_handling import AURAChainError

settings = get_settings()

CACHE_TTL = 3600  # 1 hour cache for tool results


class ToolExecutionError(AURAChainError):
    """A tool failed during execution."""
    def __init__(self, message: str, tool_name: str = "unknown", **kwargs):
        super().__init__(message, **kwargs)
        self.tool_name = tool_name


class ToolResult(BaseModel):
    """Result of a tool invocation."""
    tool_name: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    duration_ms: float = 0
    cached: bool = False


class ToolInfo(BaseModel):
    """Metadata about a registered tool."""
    name: str
    description: str
    parameters: Dict[str, Any]
    cacheable: bool = True
    requires_approval: bool = False
    approval_callback: Optional[Callable] = None
    cost_type: Literal["zero", "compute", "network"] = "zero"
    avg_latency_ms: float = 0.0
    success_rate: float = 1.0
    fallback_tool: Optional[str] = None


class ToolRegistry:
    """
    Agent-facing tool API with logging, caching, and error recovery.
    
    Wraps the existing MCPServer under the hood but provides a cleaner
    interface for agents.
    """
    
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._tool_info: Dict[str, ToolInfo] = {}
        self._redis_client: Optional[redis.Redis] = None
        self._call_count: Dict[str, int] = {}
        self._success_window: Dict[str, deque] = {}
        self._cache_hits: int = 0
        self._total_calls: int = 0
    
    async def initialize(self):
        """Initialize Redis for caching."""
        self._redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        logger.info("✓ Tool registry initialized")
    
    async def close(self):
        if self._redis_client:
            await self._redis_client.close()
            logger.info("✓ Tool registry closed")
    
    def register(
        self,
        name: str,
        func: Callable,
        description: str = "",
        parameters: Dict[str, Any] = None,
        cacheable: bool = True,
        requires_approval: bool = False,
        approval_callback: Optional[Callable] = None,
        cost_type: Literal["zero", "compute", "network"] = "zero",
        fallback_tool: Optional[str] = None
    ) -> None:
        """Register a tool with the registry."""
        self._tools[name] = func
        self._tool_info[name] = ToolInfo(
            name=name,
            description=description,
            parameters=parameters or {},
            cacheable=cacheable,
            requires_approval=requires_approval,
            approval_callback=approval_callback,
            cost_type=cost_type,
            fallback_tool=fallback_tool
        )
        self._call_count[name] = 0
        self._success_window[name] = deque(maxlen=20)
        logger.debug(f"📦 Tool registered: {name}")
    
    async def _request_approval(self, name: str, kwargs: Dict[str, Any]):
        """Request human approval before executing sensitive tool."""
        tool_info = self._tool_info[name]
        logger.info(f"Tool {name} awaiting approval")
        if tool_info.approval_callback:
            await tool_info.approval_callback(name, kwargs)
        else:
            import asyncio
            await asyncio.sleep(1)  # mock approval

    async def invoke(self, name: str, **kwargs) -> ToolResult:
        """
        Invoke a registered tool by name.
        
        Handles: logging, caching, error recovery (1 retry), performance tracking.
        """
        if name not in self._tools:
            return ToolResult(
                tool_name=name,
                success=False,
                error=f"Tool '{name}' not registered"
            )
        
        self._total_calls += 1
        self._call_count[name] = self._call_count.get(name, 0) + 1
        tool_info = self._tool_info[name]

        if tool_info.requires_approval:
            await self._request_approval(name, kwargs)
        
        # Check cache for cacheable tools
        cache_key = None
        if tool_info.cacheable and self._redis_client:
            cache_key = self._cache_key(name, kwargs)
            cached = await self._get_cached(cache_key)
            if cached is not None:
                self._cache_hits += 1
                logger.debug(f"📦 Tool cache hit: {name}")
                return ToolResult(
                    tool_name=name,
                    success=True,
                    data=cached,
                    cached=True
                )
        
        # Execute with retry (1 retry on failure)
        for attempt in range(1, 3):
            start = time.perf_counter()
            try:
                func = self._tools[name]
                import inspect
                if inspect.iscoroutinefunction(func):
                    result = await func(**kwargs)
                else:
                    result = func(**kwargs)
                duration_ms = (time.perf_counter() - start) * 1000
                
                logger.info(
                    f"🔧 Tool {name}: {duration_ms:.0f}ms "
                    f"(attempt {attempt})"
                )
                
                # Update metrics
                alpha = 0.1
                tool_info.avg_latency_ms = alpha * duration_ms + (1 - alpha) * tool_info.avg_latency_ms
                window = self._success_window.get(name)
                if window is not None:
                    window.append(1)
                    tool_info.success_rate = sum(window) / len(window)

                # Cache result
                if cache_key and self._redis_client:
                    await self._set_cached(cache_key, result)
                
                return ToolResult(
                    tool_name=name,
                    success=True,
                    data=result,
                    duration_ms=round(duration_ms, 1)
                )
                
            except Exception as e:
                duration_ms = (time.perf_counter() - start) * 1000
                if attempt < 2:
                    logger.warning(
                        f"⚠️ Tool {name} failed ({duration_ms:.0f}ms), retrying: {e}"
                    )
                else:
                    logger.error(f"❌ Tool {name} failed after retry: {e}")
                    
                    # Update metrics on failure
                    alpha = 0.1
                    tool_info.avg_latency_ms = alpha * duration_ms + (1 - alpha) * tool_info.avg_latency_ms
                    window = self._success_window.get(name)
                    if window is not None:
                        window.append(0)
                        tool_info.success_rate = sum(window) / len(window)
                        
                    return ToolResult(
                        tool_name=name,
                        success=False,
                        error=str(e),
                        duration_ms=round(duration_ms, 1)
                    )
        
        # Should never reach here
        return ToolResult(tool_name=name, success=False, error="Unexpected error")
    
    def list_tools(self) -> List[ToolInfo]:
        """List all registered tools."""
        return list(self._tool_info.values())
    
    def get_tool_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Return a JSON-serializable schema dict for a tool.
        
        Used by the ReAct loop to describe available tools to the LLM.
        Returns None if the tool is not registered.
        """
        info = self._tool_info.get(name)
        if not info:
            return None
        return {
            "name": info.name,
            "description": info.description,
            "parameters": info.parameters,
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get tool usage statistics for health dashboard."""
        return {
            "total_calls": self._total_calls,
            "cache_hits": self._cache_hits,
            "cache_hit_rate": round(
                self._cache_hits / self._total_calls, 3
            ) if self._total_calls > 0 else 0,
            "per_tool": {
                name: {"calls": count}
                for name, count in self._call_count.items()
            }
        }
    
    def _cache_key(self, tool_name: str, kwargs: Dict) -> str:
        """Create a cache key using DataFrame-aware hashing."""
        def _df_key(df: pd.DataFrame) -> str:
            return hashlib.sha256(
                pd.util.hash_pandas_object(df, index=True).values.tobytes()
            ).hexdigest()[:16]

        hashable_args = {}
        for k, v in kwargs.items():
            if isinstance(v, pd.DataFrame):
                hashable_args[k] = _df_key(v)
            else:
                hashable_args[k] = v

        try:
            args_str = json.dumps(hashable_args, sort_keys=True, default=str)
        except (TypeError, ValueError):
            return ""
        
        args_hash = hashlib.md5(args_str.encode()).hexdigest()[:12]
        return f"toolcache:{tool_name}:{args_hash}"
    
    async def _get_cached(self, key: str) -> Any:
        if not key or not self._redis_client:
            return None
        try:
            data = await self._redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None
    
    async def _set_cached(self, key: str, data: Any) -> None:
        if not key or not self._redis_client:
            return
        try:
            await self._redis_client.setex(
                key, CACHE_TTL,
                json.dumps(data, default=str)
            )
        except Exception:
            pass  # Cache failures are non-critical


# Global instance
tool_registry = ToolRegistry()


def register_default_tools():
    """Register standard tools from existing tool modules."""
    from app.tools.analysis_tools import AnalysisTools
    from app.tools.data_tools import DataTools
    
    tool_registry.register(
        "auto_eda",
        AnalysisTools.auto_eda,
        description="Automatically profile the dataset for schema, nulls, skewness, and cardinality",
        parameters={"df": "DataFrame"}
    )
    tool_registry.register(
        "detect_outliers",
        AnalysisTools.detect_outliers,
        description="Detect outliers in data using IQR or Z-score",
        parameters={"df": "DataFrame", "column": "str", "method": "str"}
    )
    tool_registry.register(
        "correlation_analysis",
        AnalysisTools.correlation_analysis,
        description="Calculate correlations between numeric columns",
        parameters={"df": "DataFrame", "columns": "List[str]"}
    )
    tool_registry.register(
        "segment_customers",
        AnalysisTools.segment_customers,
        description="K-means customer segmentation",
        parameters={"df": "DataFrame", "features": "List[str]", "n_clusters": "int"},
        cacheable=False  # Clustering results should be fresh
    )
    tool_registry.register(
        "filter_data",
        DataTools.filter_data,
        description="Filter dataset based on conditions",
        parameters={"df": "DataFrame", "conditions": "Dict"}
    )
    tool_registry.register(
        "aggregate_data",
        DataTools.aggregate_data,
        description="Group and aggregate data",
        parameters={"df": "DataFrame", "group_by": "List[str]", "aggregations": "Dict"}
    )
    tool_registry.register(
        "demand_velocity",
        AnalysisTools.demand_velocity,
        description="Calculate rolling sales velocity or demand pacing",
        parameters={"df": "DataFrame", "date_column": "str", "value_column": "str", "freq": "str"}
    )
    tool_registry.register(
        "sql_query",
        DataTools.sql_query,
        description="Run a SQL query against the dataset using DuckDB",
        parameters={"df": "DataFrame", "query": "str"}
    )
    tool_registry.register(
        "fetch_global_trends",
        AnalysisTools.fetch_global_trends,
        description="Fetch external market trends from Google Trends for a list of keywords.",
        parameters={"keywords": "List[str]"}
    )
    
    logger.info(f"📦 {len(tool_registry._tools)} tools registered")
