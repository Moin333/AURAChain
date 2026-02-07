# aura_chain/app/core/streaming.py
import redis.asyncio as redis
import json
import math
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger
from app.config import get_settings

settings = get_settings()

class StreamingService:
    """
    Centralized service for publishing real-time agent updates
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
    
    async def initialize(self):
        """Initialize Redis connection for pub/sub"""
        self.redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        logger.info("✓ Streaming service initialized")
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("✓ Streaming service closed")
    
    def _get_channel_name(self, session_id: str) -> str:
        """Generate channel name for session"""
        return f"session:{session_id}:stream"
    
    def _sanitize_for_json(self, obj: Any) -> Any:
        """
        🔥 CRITICAL FIX: Recursively sanitize data for JSON serialization
        Handles Timestamps, NaN, Infinity, numpy types
        """
        if isinstance(obj, dict):
            return {k: self._sanitize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize_for_json(v) for v in obj]
        elif isinstance(obj, (pd.Timestamp, datetime)):
            # Convert Timestamp/datetime to ISO string
            return obj.isoformat()
        elif isinstance(obj, (float, np.floating)):
            if math.isnan(obj) or math.isinf(obj):
                return 0.0
            return float(obj)
        elif isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, np.ndarray):
            return self._sanitize_for_json(obj.tolist())
        elif isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        elif pd.isna(obj):
            return None
        return obj
    
    async def publish_event(
        self,
        session_id: str,
        event_type: str,
        agent_name: str,
        data: Dict[str, Any]
    ):
        """
        Publish event to session stream
        
        Args:
            session_id: User session ID
            event_type: 'agent_started' | 'agent_progress' | 'agent_completed' | 'agent_failed' | 'workflow_completed'
            agent_name: Name of agent
            data: Event payload
        """
        if not self.redis_client:
            logger.warning("Streaming service not initialized")
            return
        
        sanitized_data = self._sanitize_for_json(data)
        
        event = {
            "type": event_type,
            "agent": agent_name,
            "data": sanitized_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        channel = self._get_channel_name(session_id)
        
        try:
            json_str = json.dumps(event)
            await self.redis_client.publish(
                channel,
                json.dumps(event)
            )
            logger.debug(f"📡 Published {event_type} for {agent_name} to session {session_id}")
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
    
    async def publish_agent_started(
        self,
        session_id: str,
        agent_name: str,
        task: str
    ):
        """Notify that agent has started processing"""
        await self.publish_event(
            session_id,
            "agent_started",
            agent_name,
            {
                "status": "processing",
                "task": task,
                "progress": 0
            }
        )
    
    async def publish_agent_progress(
        self,
        session_id: str,
        agent_name: str,
        progress: float,
        current_activity: str,
        metrics: Optional[Dict[str, Any]] = None
    ):
        """Notify agent progress update"""
        await self.publish_event(
            session_id,
            "agent_progress",
            agent_name,
            {
                "progress": progress,
                "current_activity": current_activity,
                "metrics": metrics or {}
            }
        )
    
    async def publish_agent_completed(
        self,
        session_id: str,
        agent_name: str,
        result: Dict[str, Any]
    ):
        """Notify that agent has completed"""
        await self.publish_event(
            session_id,
            "agent_completed",
            agent_name,
            {
                "status": "completed",
                "result": result
            }
        )
    
    async def publish_agent_failed(
        self,
        session_id: str,
        agent_name: str,
        error: str
    ):
        """Notify that agent has failed"""
        await self.publish_event(
            session_id,
            "agent_failed",
            agent_name,
            {
                "status": "failed",
                "error": error
            }
        )
    
    async def publish_workflow_completed(
        self,
        session_id: str
    ):
        """Notify that entire workflow has completed"""
        await self.publish_event(
            session_id,
            "workflow_completed",
            "orchestrator",
            {
                "status": "completed",
                "message": "All agents have finished processing"
            }
        )

# Global streaming service instance
streaming_service = StreamingService()