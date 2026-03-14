# app/core/shared_context.py
"""
Workflow-scoped SharedContext for inter-agent communication.

Backed by a single Redis hash per workflow:
    workflow:{workflow_id}:findings
        ├── data_harvester  → JSON (curated findings)
        ├── trend_analyst   → JSON
        ├── forecaster      → JSON
        └── mcts_optimizer  → JSON

Agents publish curated findings (not full output) so downstream agents
can adapt their reasoning based on upstream discoveries.

Phase 3 Migration Path:
    This module uses the same API surface (publish_findings / get_findings)
    that a full AgentMessageBus would use. When parallel execution arrives,
    only the backend changes — the agent-facing API stays identical.
"""

import redis.asyncio as redis
import json
from typing import Dict, Any, Optional, List
from loguru import logger
from app.config import get_settings

settings = get_settings()

# TTL: 24 hours — prevents unbounded Redis growth
WORKFLOW_TTL = 86400


class SharedContext:
    """
    Redis hash-backed shared scratchpad for workflow-scoped inter-agent state.
    
    Usage in agents:
        # Publish curated findings
        await shared_context.publish_findings(workflow_id, "trend_analyst", {
            "seasonality_patterns": {...},
            "trend_directions": {...}
        })
        
        # Read upstream findings
        trend_data = await shared_context.get_findings(workflow_id, "trend_analyst")
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
    
    async def initialize(self):
        """Initialize Redis connection."""
        self.redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        logger.info("✓ Shared context initialized")
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("✓ Shared context closed")
    
    def _findings_key(self, workflow_id: str) -> str:
        """Single Redis hash key per workflow."""
        return f"workflow:{workflow_id}:findings"
    
    async def create_workflow(self, workflow_id: str) -> None:
        """Initialize a new workflow context."""
        if not self.redis_client:
            logger.warning("Shared context not initialized, skipping create_workflow")
            return
        
        try:
            key = self._findings_key(workflow_id)
            # Set a placeholder to establish TTL on the hash
            await self.redis_client.hset(key, "_created", "true")
            await self.redis_client.expire(key, WORKFLOW_TTL)
            logger.debug(f"Created workflow context: {workflow_id}")
        except Exception as e:
            logger.error(f"Failed to create workflow context: {e}")
    
    async def publish_findings(
        self,
        workflow_id: str,
        agent_name: str,
        findings: Dict[str, Any]
    ) -> None:
        """
        Publish an agent's curated findings to the shared context.
        
        Agents should publish SUMMARIES, not full output:
            ✅ {"seasonality_patterns": {...}, "trend_direction": "increasing"}
            ❌ {"full_dataframe": [...thousands of rows...]}
        """
        if not self.redis_client:
            logger.warning("Shared context not initialized, skipping publish")
            return
        
        try:
            key = self._findings_key(workflow_id)
            await self.redis_client.hset(
                key,
                agent_name,
                json.dumps(findings, default=str)
            )
            # Refresh TTL on each write
            await self.redis_client.expire(key, WORKFLOW_TTL)
            logger.info(f"📤 {agent_name} published findings to workflow {workflow_id}")
        except Exception as e:
            logger.error(f"Failed to publish findings for {agent_name}: {e}")
    
    async def get_findings(
        self,
        workflow_id: str,
        agent_name: str
    ) -> Dict[str, Any]:
        """
        Retrieve a specific agent's findings.
        Returns empty dict if not found (safe fallback).
        """
        if not self.redis_client:
            return {}
        
        try:
            key = self._findings_key(workflow_id)
            data = await self.redis_client.hget(key, agent_name)
            if data:
                return json.loads(data)
            return {}
        except Exception as e:
            logger.error(f"Failed to get findings for {agent_name}: {e}")
            return {}
    
    async def get_all_findings(self, workflow_id: str) -> Dict[str, Dict[str, Any]]:
        """Retrieve all agent findings for a workflow."""
        if not self.redis_client:
            return {}
        
        try:
            key = self._findings_key(workflow_id)
            all_data = await self.redis_client.hgetall(key)
            
            results = {}
            for agent_name, raw_data in all_data.items():
                if agent_name == "_created":
                    continue  # Skip placeholder
                try:
                    results[agent_name] = json.loads(raw_data)
                except json.JSONDecodeError:
                    results[agent_name] = {"raw": raw_data}
            
            return results
        except Exception as e:
            logger.error(f"Failed to get all findings: {e}")
            return {}
    
    async def cleanup_workflow(self, workflow_id: str) -> None:
        """Clean up workflow context after completion."""
        if not self.redis_client:
            return
        
        try:
            key = self._findings_key(workflow_id)
            await self.redis_client.delete(key)
            logger.debug(f"Cleaned up workflow context: {workflow_id}")
        except Exception as e:
            logger.error(f"Failed to cleanup workflow context: {e}")
    
    async def list_agents_with_findings(self, workflow_id: str) -> List[str]:
        """List which agents have published findings for this workflow."""
        if not self.redis_client:
            return []
        
        try:
            key = self._findings_key(workflow_id)
            fields = await self.redis_client.hkeys(key)
            return [f for f in fields if f != "_created"]
        except Exception as e:
            logger.error(f"Failed to list agents: {e}")
            return []
    
    # ── Phase 5: Peer Requests ──
    
    def _requests_key(self, workflow_id: str, target_agent: str) -> str:
        """Redis key for requests directed at a specific agent."""
        return f"sc:{workflow_id}:requests:{target_agent}"
    
    async def publish_request(
        self,
        workflow_id: str,
        from_agent: str,
        target_agent: str,
        question: str
    ) -> None:
        """
        Publish a request from one agent to another.
        
        Example: Forecaster asks TrendAnalyst for seasonality clarification.
        The target agent can check for pending requests via get_requests().
        """
        if not self.redis_client:
            return
        
        try:
            key = self._requests_key(workflow_id, target_agent)
            request_data = json.dumps({
                "from": from_agent,
                "question": question
            })
            await self.redis_client.rpush(key, request_data)
            await self.redis_client.expire(key, WORKFLOW_TTL)
            logger.info(f"📨 {from_agent} → {target_agent}: {question[:50]}")
        except Exception as e:
            logger.error(f"Failed to publish request: {e}")
    
    async def get_requests(
        self,
        workflow_id: str,
        agent_name: str
    ) -> List[Dict[str, str]]:
        """
        Get all pending requests directed at this agent.
        
        Returns list of {"from": "agent_name", "question": "..."}
        """
        if not self.redis_client:
            return []
        
        try:
            key = self._requests_key(workflow_id, agent_name)
            raw_items = await self.redis_client.lrange(key, 0, -1)
            return [json.loads(item) for item in raw_items]
        except Exception as e:
            logger.error(f"Failed to get requests for {agent_name}: {e}")
            return []


# Global shared context instance
shared_context = SharedContext()
