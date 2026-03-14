# app/api/routes/health.py
"""
Health Dashboard — comprehensive system, agent, LLM, and workflow monitoring.

Endpoints:
    GET /health/           → Quick liveness check
    GET /health/detailed   → Full dashboard with all subsystems
    GET /health/metrics    → Prometheus metrics
"""

from fastapi import APIRouter
from datetime import datetime
from typing import Dict, Any
import time
import sys
import os
from loguru import logger

router = APIRouter(prefix="/health", tags=["health"])

# Track server start time for uptime
_server_start_time = time.time()


@router.get("/")
async def health_check():
    """Quick liveness check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "MSME Agent Platform",
        "uptime_s": round(time.time() - _server_start_time)
    }


@router.get("/detailed")
async def detailed_health():
    """
    Comprehensive health dashboard.
    
    Returns system, agents, LLM, workflows, and Redis status.
    """
    from app.core.api_clients import circuit_breaker
    from app.core.registry import agent_registry
    from app.core.checkpoints import workflow_checkpoint
    from app.core.rate_limiter import rate_limiter
    from app.core.artifacts import artifact_store
    
    result: Dict[str, Any] = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    # ── System ──
    result["system"] = {
        "uptime_s": round(time.time() - _server_start_time),
        "python_version": sys.version.split()[0],
        "pid": os.getpid(),
    }
    
    # ── Agents ──
    try:
        agents = agent_registry.list_agents()
        result["agents"] = {
            "registered_count": len(agents),
            "registered": [
                {
                    "name": a.name,
                    "can_run_without_data": a.can_run_without_data,
                    "estimated_duration_ms": a.estimated_duration_ms
                }
                for a in agents
            ]
        }
    except Exception as e:
        result["agents"] = {"error": str(e)}
    
    # ── LLM Providers ──
    try:
        result["llm"] = circuit_breaker.get_status()
    except Exception as e:
        result["llm"] = {"error": str(e)}
    
    # ── Rate Limiter ──
    try:
        rate_status = {}
        for provider in ["groq", "google", "openai", "anthropic"]:
            rate_status[provider] = await rate_limiter.get_status(provider)
        result["rate_limiter"] = rate_status
    except Exception as e:
        result["rate_limiter"] = {"error": str(e)}
    
    # ── Workflows / Checkpoints ──
    try:
        result["workflows"] = await workflow_checkpoint.get_stats()
    except Exception as e:
        result["workflows"] = {"error": str(e)}
    
    # ── Redis ──
    try:
        if artifact_store.redis_client:
            info = await artifact_store.redis_client.info("keyspace")
            connected = True
        else:
            info = {}
            connected = False
        
        result["redis"] = {
            "connected": connected,
            "keyspace": info
        }
    except Exception as e:
        result["redis"] = {"connected": False, "error": str(e)}
    
    return result


@router.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from fastapi.responses import Response
    
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )