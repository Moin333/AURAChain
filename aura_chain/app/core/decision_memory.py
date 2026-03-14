# app/core/decision_memory.py
"""
Decision Memory Layer — track recommendations and outcomes for learning.

Creates a closed intelligence loop:
    analysis → recommendation → outcome → accuracy

Only records decisions when recommended_actions exist (not passive queries).
Outcomes recorded later via API, enabling accuracy tracking over time.
"""

import json
import redis.asyncio as redis
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
from loguru import logger
from app.config import get_settings

settings = get_settings()

DECISION_TTL = 2592000  # 30 days (decisions need long retention)


class OutcomeRecord(BaseModel):
    """Actual outcome recorded after a decision was acted upon."""
    expected_outcome: str           # What the system predicted
    actual_outcome: str             # What actually happened
    accuracy_score: float           # Computed: how close (0.0-1.0)
    feedback: str = ""              # User/system feedback
    recorded_at: datetime = None
    
    def __init__(self, **data):
        if data.get("recorded_at") is None:
            data["recorded_at"] = datetime.utcnow()
        super().__init__(**data)


class DecisionRecord(BaseModel):
    """A decision made by the system."""
    decision_id: str
    workflow_id: str
    decision_type: str              # "forecast", "inventory_order", "pricing_strategy", etc.
    query: str                      # Original user query
    recommended_actions: List[str]  # What the system recommended
    confidence: float               # Overall confidence at time of decision
    agent_metrics: Dict[str, Any]   # Key metrics from agents
    timestamp: datetime = None
    outcome: Optional[OutcomeRecord] = None  # Filled later
    
    def __init__(self, **data):
        if data.get("timestamp") is None:
            data["timestamp"] = datetime.utcnow()
        super().__init__(**data)


class DecisionMemory:
    """Redis-backed decision tracking with outcome recording."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
    
    async def initialize(self):
        self.redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        logger.info("✓ Decision memory initialized")
    
    async def close(self):
        if self.redis_client:
            await self.redis_client.close()
            logger.info("✓ Decision memory closed")
    
    def _key(self, decision_id: str) -> str:
        return f"decision:{decision_id}"
    
    async def record_decision(
        self,
        workflow_id: str,
        decision_type: str,
        query: str,
        recommended_actions: List[str],
        confidence: float,
        agent_metrics: Dict[str, Any] = None
    ) -> DecisionRecord:
        """
        Record a decision. Only call when recommended_actions exist.
        
        This should be called from the report engine when the report
        contains actionable recommendations.
        """
        decision_id = f"dec_{workflow_id}"
        
        record = DecisionRecord(
            decision_id=decision_id,
            workflow_id=workflow_id,
            decision_type=decision_type,
            query=query,
            recommended_actions=recommended_actions,
            confidence=confidence,
            agent_metrics=agent_metrics or {}
        )
        
        if self.redis_client:
            try:
                key = self._key(decision_id)
                await self.redis_client.setex(
                    key, DECISION_TTL,
                    record.model_dump_json()
                )
                # Index by timestamp
                await self.redis_client.zadd(
                    "decisions:index",
                    {decision_id: record.timestamp.timestamp()}
                )
                # Index by type
                await self.redis_client.sadd(
                    f"decisions:type:{decision_type}",
                    decision_id
                )
                logger.info(
                    f"📌 Decision recorded: {decision_id} "
                    f"(type={decision_type}, confidence={confidence:.2f})"
                )
            except Exception as e:
                logger.error(f"Failed to record decision: {e}")
        
        return record
    
    async def record_outcome(
        self,
        decision_id: str,
        expected_outcome: str,
        actual_outcome: str,
        accuracy_score: float,
        feedback: str = ""
    ) -> Optional[DecisionRecord]:
        """
        Attach an outcome to an existing decision.
        
        Called later (days/weeks) when the actual result is known.
        accuracy_score: 0.0-1.0 (computed by caller from expected vs actual).
        """
        record = await self.get_decision(decision_id)
        if not record:
            return None
        
        record.outcome = OutcomeRecord(
            expected_outcome=expected_outcome,
            actual_outcome=actual_outcome,
            accuracy_score=accuracy_score,
            feedback=feedback
        )
        
        if self.redis_client:
            try:
                key = self._key(decision_id)
                await self.redis_client.setex(
                    key, DECISION_TTL,
                    record.model_dump_json()
                )
                # Track in outcomes index for analytics
                await self.redis_client.zadd(
                    "decisions:with_outcomes",
                    {decision_id: accuracy_score}
                )
                logger.info(
                    f"📊 Outcome recorded for {decision_id}: "
                    f"accuracy={accuracy_score:.2f}"
                )
            except Exception as e:
                logger.error(f"Failed to record outcome: {e}")
        
        return record
    
    async def get_decision(self, decision_id: str) -> Optional[DecisionRecord]:
        """Retrieve a specific decision."""
        if not self.redis_client:
            return None
        try:
            key = self._key(decision_id)
            data = await self.redis_client.get(key)
            if data:
                return DecisionRecord.model_validate_json(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get decision: {e}")
            return None
    
    async def get_decision_history(
        self, limit: int = 20, decision_type: str = None
    ) -> List[DecisionRecord]:
        """List recent decisions, optionally filtered by type."""
        if not self.redis_client:
            return []
        
        try:
            if decision_type:
                dec_ids = await self.redis_client.smembers(
                    f"decisions:type:{decision_type}"
                )
                dec_ids = list(dec_ids)[:limit]
            else:
                dec_ids = await self.redis_client.zrevrange(
                    "decisions:index", 0, limit - 1
                )
            
            decisions = []
            for did in dec_ids:
                record = await self.get_decision(did)
                if record:
                    decisions.append(record)
            
            return decisions
        except Exception as e:
            logger.error(f"Failed to list decisions: {e}")
            return []
    
    async def get_accuracy_stats(self) -> Dict[str, Any]:
        """
        Aggregate decision accuracy for health dashboard.
        
        Returns overall accuracy + per-type breakdown.
        """
        if not self.redis_client:
            return {"total_decisions": 0}
        
        try:
            # All decisions with outcomes
            outcomes = await self.redis_client.zrangebyscore(
                "decisions:with_outcomes", "-inf", "+inf", withscores=True
            )
            
            if not outcomes:
                total = await self.redis_client.zcard("decisions:index")
                return {
                    "total_decisions": total,
                    "decisions_with_outcomes": 0,
                    "average_accuracy": None
                }
            
            scores = [score for _, score in outcomes]
            
            # Per-type breakdown
            type_stats = {}
            for did, score in outcomes:
                record = await self.get_decision(did)
                if record:
                    dt = record.decision_type
                    if dt not in type_stats:
                        type_stats[dt] = {"count": 0, "total_accuracy": 0}
                    type_stats[dt]["count"] += 1
                    type_stats[dt]["total_accuracy"] += score
            
            for dt, stats in type_stats.items():
                stats["average_accuracy"] = round(
                    stats["total_accuracy"] / stats["count"], 3
                )
                del stats["total_accuracy"]
            
            total = await self.redis_client.zcard("decisions:index")
            
            return {
                "total_decisions": total,
                "decisions_with_outcomes": len(outcomes),
                "average_accuracy": round(sum(scores) / len(scores), 3),
                "per_type": type_stats
            }
        except Exception as e:
            logger.error(f"Failed to get accuracy stats: {e}")
            return {"total_decisions": 0, "error": str(e)}


# Global instance
decision_memory = DecisionMemory()
