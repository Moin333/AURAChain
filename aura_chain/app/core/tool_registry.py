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
import redis.asyncio as redis
from typing import Dict, Any, List, Optional, Callable
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
        cacheable: bool = True
    ) -> None:
        """Register a tool with the registry."""
        self._tools[name] = func
        self._tool_info[name] = ToolInfo(
            name=name,
            description=description,
            parameters=parameters or {},
            cacheable=cacheable
        )
        self._call_count[name] = 0
        logger.debug(f"📦 Tool registered: {name}")
    
    async def invoke(self, name: str, **kwargs) -> ToolResult:
        """
        Invoke a registered tool by name.
        
        Handles: logging, caching, error recovery (1 retry).
        """
        if name not in self._tools:
            return ToolResult(
                tool_name=name,
                success=False,
                error=f"Tool '{name}' not registered"
            )
        
        self._total_calls += 1
        self._call_count[name] = self._call_count.get(name, 0) + 1
        
        # Check cache for cacheable tools
        tool_info = self._tool_info[name]
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
            start = time.time()
            try:
                func = self._tools[name]
                result = await func(**kwargs)
                duration_ms = (time.time() - start) * 1000
                
                logger.info(
                    f"🔧 Tool {name}: {duration_ms:.0f}ms "
                    f"(attempt {attempt})"
                )
                
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
                duration_ms = (time.time() - start) * 1000
                if attempt < 2:
                    logger.warning(
                        f"⚠️ Tool {name} failed ({duration_ms:.0f}ms), retrying: {e}"
                    )
                else:
                    logger.error(f"❌ Tool {name} failed after retry: {e}")
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
        """Create a cache key from tool name + args hash."""
        # Only hash serializable args
        try:
            args_str = json.dumps(kwargs, sort_keys=True, default=str)
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
    
    logger.info(f"📦 {len(tool_registry._tools)} tools registered")
