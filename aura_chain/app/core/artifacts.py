# app/core/artifacts.py
"""
Redis-backed Artifact Store for per-workflow agent outputs.

Solves the problem of agent results only existing in BackgroundTask memory —
if the process crashes mid-workflow, all results are now recoverable from Redis.

Each artifact includes full metadata: timestamp, duration, success status.
This supports experiment logging, debugging, and performance tracking.
"""

import redis.asyncio as redis
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger
from app.config import get_settings

settings = get_settings()

# Default TTL: 24 hours (artifacts are ephemeral but survive crashes)
ARTIFACT_TTL = 86400


class ArtifactStore:
    """
    Persists individual agent outputs per workflow to Redis.
    
    Storage layout:
        artifact:{workflow_id}:{agent_name} → JSON blob with metadata
        artifact_index:{workflow_id}        → Set of agent names
        artifact_workflows                  → Set of workflow IDs
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
        logger.info("✓ Artifact store initialized")
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("✓ Artifact store closed")
    
    def _artifact_key(self, workflow_id: str, agent_name: str) -> str:
        return f"artifact:{workflow_id}:{agent_name}"
    
    def _index_key(self, workflow_id: str) -> str:
        return f"artifact_index:{workflow_id}"
    
    async def save(
        self,
        workflow_id: str,
        agent_name: str,
        data: Dict[str, Any],
        duration_ms: float = 0.0,
        success: bool = True
    ) -> None:
        """
        Save an agent's output with full metadata.
        
        Args:
            workflow_id: Unique workflow/request ID
            agent_name: Registry key of the agent
            data: The agent's response data
            duration_ms: Execution time in milliseconds
            success: Whether the agent completed successfully
        """
        if not self.redis_client:
            logger.warning("Artifact store not initialized, skipping save")
            return
        
        artifact = {
            "agent": agent_name,
            "workflow_id": workflow_id,
            "timestamp": datetime.utcnow().isoformat(),
            "duration_ms": duration_ms,
            "success": success,
            "data": data
        }
        
        key = self._artifact_key(workflow_id, agent_name)
        
        try:
            # Store the artifact
            await self.redis_client.setex(
                key,
                ARTIFACT_TTL,
                json.dumps(artifact, default=str)
            )
            
            # Track agent in workflow index
            index_key = self._index_key(workflow_id)
            await self.redis_client.sadd(index_key, agent_name)
            await self.redis_client.expire(index_key, ARTIFACT_TTL)
            
            # Track workflow in global index
            await self.redis_client.sadd("artifact_workflows", workflow_id)
            
            logger.debug(f"Saved artifact: {agent_name} for workflow {workflow_id}")
            
        except Exception as e:
            logger.error(f"Failed to save artifact: {e}")
    
    async def get(
        self,
        workflow_id: str,
        agent_name: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a single agent's artifact (with metadata)."""
        if not self.redis_client:
            return None
        
        key = self._artifact_key(workflow_id, agent_name)
        
        try:
            data = await self.redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get artifact: {e}")
            return None
    
    async def get_all(self, workflow_id: str) -> Dict[str, Dict[str, Any]]:
        """Retrieve all agent artifacts for a given workflow."""
        if not self.redis_client:
            return {}
        
        try:
            index_key = self._index_key(workflow_id)
            agent_names = await self.redis_client.smembers(index_key)
            
            results = {}
            for agent_name in agent_names:
                artifact = await self.get(workflow_id, agent_name)
                if artifact:
                    results[agent_name] = artifact
            
            return results
        except Exception as e:
            logger.error(f"Failed to get all artifacts: {e}")
            return {}
    
    async def delete_workflow(self, workflow_id: str) -> None:
        """Delete all artifacts for a workflow."""
        if not self.redis_client:
            return
        
        try:
            index_key = self._index_key(workflow_id)
            agent_names = await self.redis_client.smembers(index_key)
            
            # Delete each artifact
            for agent_name in agent_names:
                key = self._artifact_key(workflow_id, agent_name)
                await self.redis_client.delete(key)
            
            # Delete the index and remove from global tracking
            await self.redis_client.delete(index_key)
            await self.redis_client.srem("artifact_workflows", workflow_id)
            
            logger.debug(f"Deleted all artifacts for workflow {workflow_id}")
            
        except Exception as e:
            logger.error(f"Failed to delete workflow artifacts: {e}")
    
    async def list_workflows(self) -> List[str]:
        """List all workflow IDs that have stored artifacts."""
        if not self.redis_client:
            return []
        
        try:
            workflows = await self.redis_client.smembers("artifact_workflows")
            return list(workflows)
        except Exception as e:
            logger.error(f"Failed to list workflows: {e}")
            return []


# Global artifact store instance
artifact_store = ArtifactStore()
