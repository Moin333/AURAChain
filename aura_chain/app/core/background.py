# app/core/background.py
from typing import Dict, Any
from app.agents.base_agent import AgentRequest
from app.agents.orchestrator import orchestrator
from app.core.streaming import streaming_service
from app.core.memory import session_manager
from loguru import logger


async def execute_workflow_background(
    plan: Dict[str, Any],
    agent_request: AgentRequest,
    request_id: str
):
    """
    Execute the agent workflow in the background.
    
    This function is called by FastAPI's BackgroundTasks and runs
    after the HTTP response has been sent to the client.
    
    Args:
        plan: The orchestration plan (already created)
        agent_request: The original agent request with context
        request_id: Unique ID for this execution
    """
    session_id = agent_request.session_id
    
    try:
        logger.info(f"🎬 Starting background workflow for request {request_id}")
        
        # 1. Notify SSE clients that workflow has started
        if session_id:
            await streaming_service.publish_workflow_started(session_id, plan)
        
        # 2. Execute agents sequentially (this is the slow part)
        agent_responses = await orchestrator.route_to_agents(plan, agent_request)
        
        # 3. Save final results to session
        response_content = "\n\n".join([
            f"{r.agent_name}: {r.data if r.success else r.error}"
            for r in agent_responses
        ])
        
        if session_id:
            await session_manager.add_message(
                session_id,
                "assistant",
                response_content
            )
        
        logger.info(f"✅ Background workflow completed for request {request_id}")
        
    except Exception as e:
        logger.error(f"❌ Background workflow failed for request {request_id}: {str(e)}")
        
        # Notify clients of failure
        if session_id:
            await streaming_service.publish_event(
                session_id,
                "workflow_failed",
                "orchestrator",
                {
                    "status": "failed",
                    "error": str(e),
                    "request_id": request_id
                }
            )