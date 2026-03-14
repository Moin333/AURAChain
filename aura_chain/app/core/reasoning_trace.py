# app/core/reasoning_trace.py
"""
Reasoning Trace Layer — structured logging of agent decisions.

Every agent decision is logged as a ReasoningEntry. This enables:
- Debugging unexpected agent decisions
- Auditing AI recommendations
- User explanation of "why did the AI suggest this?"
- Training data for fine-tuning future models

Storage: Redis list per workflow. TTL: 24h.
"""

import json
import redis.asyncio as redis
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from loguru import logger
from app.config import get_settings

settings = get_settings()

TRACE_TTL = 86400  # 24 hours


class ReasoningEntry(BaseModel):
    """A single reasoning step in an agent's decision process."""
    agent: str
    step: str                   # "data_quality_check", "trend_detection", etc.
    input_summary: str          # What the agent received (brief, NOT raw data)
    reasoning: str              # Decision rationale (summary, NOT raw chain-of-thought)
    output_summary: str         # What was produced (brief)
    confidence: float           # 0.0-1.0
    evidence: List[str] = []    # Supporting evidence for the decision
    timestamp: datetime = None
    
    def __init__(self, **data):
        if data.get("timestamp") is None:
            data["timestamp"] = datetime.utcnow()
        super().__init__(**data)


class ReasoningTraceStore:
    """Redis-backed store for reasoning traces per workflow."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
    
    async def initialize(self):
        self.redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        logger.info("✓ Reasoning trace store initialized")
    
    async def close(self):
        if self.redis_client:
            await self.redis_client.close()
            logger.info("✓ Reasoning trace store closed")
    
    def _key(self, workflow_id: str) -> str:
        return f"reasoning:{workflow_id}"
    
    async def append(self, workflow_id: str, entry: ReasoningEntry) -> None:
        """Append a reasoning entry to the workflow trace."""
        if not self.redis_client:
            return
        
        try:
            key = self._key(workflow_id)
            await self.redis_client.rpush(
                key,
                entry.model_dump_json()
            )
            await self.redis_client.expire(key, TRACE_TTL)
            
            logger.debug(
                f"🧠 Trace: {entry.agent} → {entry.step} "
                f"(confidence: {entry.confidence:.2f})"
            )
        except Exception as e:
            logger.error(f"Failed to append reasoning entry: {e}")
    
    async def get_trace(self, workflow_id: str) -> List[ReasoningEntry]:
        """Get full reasoning trace for a workflow."""
        if not self.redis_client:
            return []
        
        try:
            key = self._key(workflow_id)
            raw_entries = await self.redis_client.lrange(key, 0, -1)
            return [ReasoningEntry.model_validate_json(e) for e in raw_entries]
        except Exception as e:
            logger.error(f"Failed to get reasoning trace: {e}")
            return []
    
    async def get_agent_trace(
        self, workflow_id: str, agent_name: str
    ) -> List[ReasoningEntry]:
        """Get reasoning entries for a specific agent."""
        all_entries = await self.get_trace(workflow_id)
        return [e for e in all_entries if e.agent == agent_name]
    
    async def get_trace_summary(self, workflow_id: str) -> Dict[str, Any]:
        """Get a summary of the reasoning trace for health/debugging."""
        entries = await self.get_trace(workflow_id)
        if not entries:
            return {"total_entries": 0}
        
        agents = {}
        for e in entries:
            if e.agent not in agents:
                agents[e.agent] = {"steps": 0, "avg_confidence": 0, "entries": []}
            agents[e.agent]["steps"] += 1
            agents[e.agent]["entries"].append(e.confidence)
        
        for agent, data in agents.items():
            data["avg_confidence"] = round(
                sum(data["entries"]) / len(data["entries"]), 2
            )
            del data["entries"]
        
        return {
            "total_entries": len(entries),
            "agents": agents
        }


# Global instance
reasoning_trace_store = ReasoningTraceStore()
