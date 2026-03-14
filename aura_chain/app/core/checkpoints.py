# app/core/checkpoints.py
"""
Workflow Checkpointing — save/restore workflow state to Redis.

Enables crash recovery: if the server crashes mid-workflow, the workflow
can resume from the last completed execution level.

Storage:
    checkpoint:{workflow_id} → JSON {
        plan, completed_levels, completed_agents, status, timestamps
    }
"""

import json
import redis.asyncio as redis
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger
from app.config import get_settings
from app.core.error_handling import CheckpointError

settings = get_settings()

# Checkpoint TTL: 24 hours (same as artifacts)
CHECKPOINT_TTL = 86400


class WorkflowCheckpoint:
    """Redis-backed workflow state checkpointing."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
    
    async def initialize(self):
        """Initialize Redis connection."""
        self.redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        logger.info("✓ Checkpoint store initialized")
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("✓ Checkpoint store closed")
    
    def _key(self, workflow_id: str) -> str:
        return f"checkpoint:{workflow_id}"
    
    async def save_checkpoint(
        self,
        workflow_id: str,
        plan: Dict[str, Any],
        completed_level: int,
        completed_agents: List[str],
        status: str = "in_progress"
    ) -> None:
        """
        Save workflow state after an execution level completes.
        
        Called after each level in the DAG finishes, so on crash
        we know exactly which levels are done.
        """
        if not self.redis_client:
            return
        
        try:
            checkpoint_data = {
                "workflow_id": workflow_id,
                "plan": plan,
                "completed_level": completed_level,
                "completed_agents": completed_agents,
                "status": status,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            key = self._key(workflow_id)
            await self.redis_client.setex(
                key,
                CHECKPOINT_TTL,
                json.dumps(checkpoint_data, default=str)
            )
            
            # Track in global index
            await self.redis_client.sadd("checkpoint_workflows", workflow_id)
            
            logger.debug(
                f"💾 Checkpoint saved: workflow={workflow_id}, "
                f"level={completed_level}, agents={completed_agents}"
            )
            
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
    
    async def get_checkpoint(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve checkpoint for a workflow."""
        if not self.redis_client:
            return None
        
        try:
            key = self._key(workflow_id)
            data = await self.redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get checkpoint: {e}")
            return None
    
    async def mark_completed(self, workflow_id: str) -> None:
        """Mark workflow as completed in checkpoint."""
        if not self.redis_client:
            return
        
        try:
            checkpoint = await self.get_checkpoint(workflow_id)
            if checkpoint:
                checkpoint["status"] = "completed"
                checkpoint["updated_at"] = datetime.utcnow().isoformat()
                
                key = self._key(workflow_id)
                await self.redis_client.setex(
                    key, CHECKPOINT_TTL,
                    json.dumps(checkpoint, default=str)
                )
        except Exception as e:
            logger.error(f"Failed to mark checkpoint completed: {e}")
    
    async def mark_failed(self, workflow_id: str, error: str) -> None:
        """Mark workflow as failed in checkpoint."""
        if not self.redis_client:
            return
        
        try:
            checkpoint = await self.get_checkpoint(workflow_id)
            if checkpoint:
                checkpoint["status"] = "failed"
                checkpoint["error"] = error
                checkpoint["updated_at"] = datetime.utcnow().isoformat()
                
                key = self._key(workflow_id)
                await self.redis_client.setex(
                    key, CHECKPOINT_TTL,
                    json.dumps(checkpoint, default=str)
                )
        except Exception as e:
            logger.error(f"Failed to mark checkpoint failed: {e}")
    
    async def delete_checkpoint(self, workflow_id: str) -> None:
        """Delete a workflow checkpoint."""
        if not self.redis_client:
            return
        
        try:
            key = self._key(workflow_id)
            await self.redis_client.delete(key)
            await self.redis_client.srem("checkpoint_workflows", workflow_id)
        except Exception as e:
            logger.error(f"Failed to delete checkpoint: {e}")
    
    async def get_incomplete_workflows(self) -> List[Dict[str, Any]]:
        """List all workflows that have checkpoints but aren't completed."""
        if not self.redis_client:
            return []
        
        try:
            workflow_ids = await self.redis_client.smembers("checkpoint_workflows")
            incomplete = []
            
            for wf_id in workflow_ids:
                checkpoint = await self.get_checkpoint(wf_id)
                if checkpoint and checkpoint.get("status") == "in_progress":
                    incomplete.append(checkpoint)
            
            return incomplete
        except Exception as e:
            logger.error(f"Failed to list incomplete workflows: {e}")
            return []
    
    async def get_stats(self) -> Dict[str, int]:
        """Get checkpoint statistics for health dashboard."""
        if not self.redis_client:
            return {"total": 0, "in_progress": 0, "completed": 0, "failed": 0}
        
        try:
            workflow_ids = await self.redis_client.smembers("checkpoint_workflows")
            stats = {"total": len(workflow_ids), "in_progress": 0, "completed": 0, "failed": 0}
            
            for wf_id in workflow_ids:
                checkpoint = await self.get_checkpoint(wf_id)
                if checkpoint:
                    status = checkpoint.get("status", "unknown")
                    if status in stats:
                        stats[status] += 1
            
            return stats
        except Exception:
            return {"total": 0, "in_progress": 0, "completed": 0, "failed": 0}


# Global instance
workflow_checkpoint = WorkflowCheckpoint()
