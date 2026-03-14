# app/api/routes/orchestrator.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any
from pydantic import BaseModel
from app.agents.orchestrator import orchestrator
from app.agents.base_agent import AgentRequest
from app.core.memory import session_manager, context_engineer
from app.core.background import execute_workflow_background
import uuid
import redis.asyncio as redis
from app.config import get_settings
import pandas as pd
import io
from loguru import logger

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])
settings = get_settings()

class QueryRequest(BaseModel):
    query: str
    session_id: str | None = None
    user_id: str
    context: Dict[str, Any] = {}
    parameters: Dict[str, Any] = {}

class QueryResponse(BaseModel):
    request_id: str
    session_id: str
    orchestration_plan: Dict[str, Any]
    message: str
    status: str  # "planned" | "executing" | "completed" | "failed"

@router.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest, background_tasks: BackgroundTasks):
    """
    Returns plan immediately, executes agents in background.
    
    Phase 3: Plan now includes execution_levels for parallel dispatch,
    cost estimates, and structured intent analysis.
    """
    try:
        request_id = str(uuid.uuid4())
        
        # Create or get session
        if not request.session_id:
            request.session_id = str(uuid.uuid4())
            await session_manager.create_session(request.user_id, request.session_id)
        
        logger.info(f"📥 Query received: {request.query[:50]}... (session: {request.session_id})")
        
        # CRITICAL: Load dataset if dataset_id provided
        if "dataset_id" in request.context and "dataset" not in request.context:
            dataset_id = request.context["dataset_id"]
            try:
                redis_client = await redis.from_url(settings.REDIS_URL)
                data_bytes = await redis_client.get(f"dataset:{dataset_id}")
                await redis_client.close()
                
                if data_bytes:
                    df = pd.read_json(io.BytesIO(data_bytes), orient='records')
                    
                    # Convert datetime columns to strings
                    for col in df.select_dtypes(include=['datetime64']).columns:
                        df[col] = df[col].astype(str)
                    
                    request.context["dataset"] = df.to_dict('records')
                    logger.info(f"✅ Loaded dataset: {len(df)} rows, {len(df.columns)} cols")
                else:
                    logger.warning(f"⚠ Dataset {dataset_id} not found in Redis")
            except Exception as e:
                logger.error(f"⚠ Error loading dataset: {e}")
        
        # Build context using memory
        memory_context = await context_engineer.build_context(
            session_id=request.session_id,
            user_id=request.user_id,
            current_query=request.query
        )
        
        # Merge contexts (request context takes precedence)
        context = {**memory_context, **request.context}
        
        # Create agent request
        agent_request = AgentRequest(
            query=request.query,
            context=context,
            session_id=request.session_id,
            user_id=request.user_id,
            parameters=request.parameters
        )
        
        # ===== CREATE PLAN (IntentAnalyzer + WorkflowPlanner) =====
        logger.info(f"🧠 Creating orchestration plan...")
        orchestrator_response = await orchestrator.create_plan(agent_request)
        
        if not orchestrator_response.success:
            return QueryResponse(
                request_id=request_id,
                session_id=request.session_id,
                orchestration_plan={},
                message=f"Planning failed: {orchestrator_response.error}",
                status="failed"
            )
        
        plan = orchestrator_response.data["plan"]
        
        n_agents = len(plan.get('agents', []))
        n_levels = len(plan.get('execution_levels', []))
        est_ms = plan.get('estimated_duration_ms', 0)
        logger.info(f"✅ Plan created: {n_agents} agents in {n_levels} levels (~{est_ms}ms)")
        
        # Save query to session
        await session_manager.add_message(
            request.session_id,
            "user",
            request.query
        )
        
        # ===== EXECUTE IN BACKGROUND (parallel by levels) =====
        background_tasks.add_task(
            execute_workflow_background,
            plan=plan,
            agent_request=agent_request,
            request_id=request_id
        )
        
        logger.info(f"🚀 Background execution started for request {request_id}")
        
        # ===== RETURN PLAN IMMEDIATELY =====
        return QueryResponse(
            request_id=request_id,
            session_id=request.session_id,
            orchestration_plan=plan,
            message=f"Plan created: {n_agents} agents in {n_levels} parallel levels. Executing in background.",
            status="executing"
        )
        
    except Exception as e:
        logger.error(f"❌ Query error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))