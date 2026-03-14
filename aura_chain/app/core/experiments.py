# app/core/experiments.py
"""
Experiment Logger — track analysis runs for reproducibility and comparison.

Each workflow execution is logged as an experiment with:
- Input dataset fingerprint (hash)
- Agent configuration at time of run
- Key metrics per agent (not full outputs)
- Confidence scores
- Planner reasoning
- Execution time

Enables: A/B testing, agent tuning, model comparison, planner evaluation.
"""

import json
import hashlib
import redis.asyncio as redis
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
from loguru import logger
from app.config import get_settings

settings = get_settings()

EXPERIMENT_TTL = 604800  # 7 days


class ExperimentRecord(BaseModel):
    """A single experiment (workflow execution)."""
    experiment_id: str
    workflow_id: str
    dataset_hash: str               # SHA-256 of input dataset
    agent_config: Dict[str, Any]    # Agent capabilities at time of run
    agent_metrics: Dict[str, Any]   # Key metrics per agent (not full outputs)
    confidence_scores: Dict[str, float]  # Per-agent confidence
    overall_confidence: float
    planner_reasoning: str          # Why the planner chose these agents
    report_summary: str             # Brief report summary
    execution_time_ms: float
    timestamp: datetime = None
    
    def __init__(self, **data):
        if data.get("timestamp") is None:
            data["timestamp"] = datetime.utcnow()
        super().__init__(**data)


class ComparisonResult(BaseModel):
    """Result of comparing two experiments."""
    experiment_a: str
    experiment_b: str
    metric_diffs: Dict[str, Dict[str, Any]]  # agent → {metric: {a, b, diff}}
    confidence_diffs: Dict[str, Dict[str, float]]
    execution_time_diff_ms: float
    overall_confidence_diff: float
    summary: str


class ExperimentLogger:
    """Redis-backed experiment tracking."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
    
    async def initialize(self):
        self.redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        logger.info("✓ Experiment logger initialized")
    
    async def close(self):
        if self.redis_client:
            await self.redis_client.close()
            logger.info("✓ Experiment logger closed")
    
    def _key(self, experiment_id: str) -> str:
        return f"experiment:{experiment_id}"
    
    @staticmethod
    def hash_dataset(data: Any) -> str:
        """Create a fingerprint of the input dataset."""
        raw = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
    
    async def log_experiment(
        self,
        workflow_id: str,
        dataset_hash: str,
        agent_config: Dict[str, Any],
        agent_metrics: Dict[str, Any],
        confidence_scores: Dict[str, float],
        overall_confidence: float,
        planner_reasoning: str,
        report_summary: str,
        execution_time_ms: float
    ) -> ExperimentRecord:
        """Log a completed workflow as an experiment."""
        experiment_id = f"exp_{workflow_id}"
        
        record = ExperimentRecord(
            experiment_id=experiment_id,
            workflow_id=workflow_id,
            dataset_hash=dataset_hash,
            agent_config=agent_config,
            agent_metrics=agent_metrics,
            confidence_scores=confidence_scores,
            overall_confidence=overall_confidence,
            planner_reasoning=planner_reasoning,
            report_summary=report_summary,
            execution_time_ms=execution_time_ms
        )
        
        if self.redis_client:
            try:
                key = self._key(experiment_id)
                await self.redis_client.setex(
                    key, EXPERIMENT_TTL,
                    record.model_dump_json()
                )
                # Add to sorted set index (sorted by timestamp)
                await self.redis_client.zadd(
                    "experiments:index",
                    {experiment_id: record.timestamp.timestamp()}
                )
                logger.info(f"📋 Experiment logged: {experiment_id}")
            except Exception as e:
                logger.error(f"Failed to log experiment: {e}")
        
        return record
    
    async def get_experiment(self, experiment_id: str) -> Optional[ExperimentRecord]:
        """Retrieve a specific experiment."""
        if not self.redis_client:
            return None
        
        try:
            key = self._key(experiment_id)
            data = await self.redis_client.get(key)
            if data:
                return ExperimentRecord.model_validate_json(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get experiment: {e}")
            return None
    
    async def list_experiments(self, limit: int = 20) -> List[ExperimentRecord]:
        """List recent experiments (newest first)."""
        if not self.redis_client:
            return []
        
        try:
            # Get experiment IDs from sorted set (newest first)
            exp_ids = await self.redis_client.zrevrange(
                "experiments:index", 0, limit - 1
            )
            
            experiments = []
            for exp_id in exp_ids:
                record = await self.get_experiment(exp_id)
                if record:
                    experiments.append(record)
            
            return experiments
        except Exception as e:
            logger.error(f"Failed to list experiments: {e}")
            return []
    
    async def compare_experiments(
        self, id1: str, id2: str
    ) -> Optional[ComparisonResult]:
        """Compare two experiments by metrics and confidence scores."""
        exp_a = await self.get_experiment(id1)
        exp_b = await self.get_experiment(id2)
        
        if not exp_a or not exp_b:
            return None
        
        # Compare metrics per agent
        metric_diffs = {}
        all_agents = set(list(exp_a.agent_metrics.keys()) + list(exp_b.agent_metrics.keys()))
        
        for agent in all_agents:
            metrics_a = exp_a.agent_metrics.get(agent, {})
            metrics_b = exp_b.agent_metrics.get(agent, {})
            all_metrics = set(list(metrics_a.keys()) + list(metrics_b.keys()))
            
            diffs = {}
            for metric in all_metrics:
                val_a = metrics_a.get(metric, 0)
                val_b = metrics_b.get(metric, 0)
                if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
                    diffs[metric] = {
                        "a": val_a,
                        "b": val_b,
                        "diff": round(val_b - val_a, 4),
                        "improved": val_b > val_a
                    }
            
            if diffs:
                metric_diffs[agent] = diffs
        
        # Compare confidence scores
        confidence_diffs = {}
        all_conf_agents = set(
            list(exp_a.confidence_scores.keys()) +
            list(exp_b.confidence_scores.keys())
        )
        for agent in all_conf_agents:
            ca = exp_a.confidence_scores.get(agent, 0)
            cb = exp_b.confidence_scores.get(agent, 0)
            confidence_diffs[agent] = {
                "a": ca, "b": cb,
                "diff": round(cb - ca, 4)
            }
        
        # Build summary
        improvements = sum(
            1 for agent_diffs in metric_diffs.values()
            for m in agent_diffs.values()
            if m.get("improved")
        )
        total_metrics = sum(len(d) for d in metric_diffs.values())
        
        summary = (
            f"Compared {len(all_agents)} agents across {total_metrics} metrics. "
            f"{improvements}/{total_metrics} metrics improved. "
            f"Overall confidence: {exp_a.overall_confidence:.2f} → {exp_b.overall_confidence:.2f}"
        )
        
        return ComparisonResult(
            experiment_a=id1,
            experiment_b=id2,
            metric_diffs=metric_diffs,
            confidence_diffs=confidence_diffs,
            execution_time_diff_ms=round(exp_b.execution_time_ms - exp_a.execution_time_ms),
            overall_confidence_diff=round(
                exp_b.overall_confidence - exp_a.overall_confidence, 4
            ),
            summary=summary
        )


# Global instance
experiment_logger = ExperimentLogger()
