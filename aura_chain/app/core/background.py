# app/core/background.py
"""
Background workflow execution with production hardening:
- Phase 6: Checkpointing after each execution level
- Phase 7: Experiment logging after report generation
- Phase 8: Agent timeout (asyncio.wait_for), decision recording
"""

from typing import Dict, Any, List
from app.agents.base_agent import AgentRequest, AgentResponse
from app.agents.orchestrator import orchestrator
from app.core.streaming import streaming_service
from app.core.memory import session_manager
from app.core.artifacts import artifact_store
from app.core.shared_context import shared_context
from app.core.synthesizer import response_synthesizer
from app.core.report_engine import report_engine
from app.core.checkpoints import workflow_checkpoint
from app.core.experiments import experiment_logger
from app.core.decision_memory import decision_memory
from app.core.evaluation import agent_evaluator
from loguru import logger
import asyncio
import time


async def execute_workflow_background(
    plan: Dict[str, Any],
    agent_request: AgentRequest,
    request_id: str
):
    """
    Execute the agent workflow in the background.
    
    Called by FastAPI's BackgroundTasks after HTTP response sent.
    Includes: checkpointing, timeout, experiment logging, decision recording.
    """
    session_id = agent_request.session_id
    workflow_start = time.time()
    
    try:
        logger.info(f"🎬 Starting background workflow for request {request_id}")
        
        # 1. Create shared context for inter-agent communication
        await shared_context.create_workflow(request_id)
        
        # 2. Set workflow_id on the agent request
        agent_request.workflow_id = request_id
        
        # 3. Save initial checkpoint (level -1 = not started)
        await workflow_checkpoint.save_checkpoint(
            workflow_id=request_id,
            plan=plan,
            completed_level=-1,
            completed_agents=[],
            status="in_progress"
        )
        
        # 4. Notify SSE clients that workflow has started
        if session_id:
            await streaming_service.publish_workflow_started(session_id, plan)
        
        # 5. Execute agents with per-level checkpointing + timeout
        execution_levels = plan.get("execution_levels", [])
        
        if execution_levels:
            agent_responses = await _execute_with_checkpoints(
                plan, agent_request, request_id, execution_levels
            )
        else:
            # Sequential fallback (no execution_levels in plan)
            agent_responses = await orchestrator.route_to_agents(plan, agent_request)
            for response in agent_responses:
                duration_ms = (time.time() - workflow_start) * 1000
                await artifact_store.save(
                    workflow_id=request_id,
                    agent_name=response.agent_name,
                    data=response.data or {},
                    duration_ms=duration_ms,
                    success=response.success
                )
        
        # 6. Extract execution order for report ordering
        execution_order = _extract_execution_order(plan)
        
        # 7. Synthesize unified response
        logger.info(f"📝 Synthesizing response for workflow {request_id}...")
        synthesis = await response_synthesizer.synthesize(request_id, execution_order)
        
        # 8. Generate executive report
        logger.info(f"📊 Generating executive report for workflow {request_id}...")
        report = await report_engine.generate(request_id, synthesis, execution_order)
        
        # 9. Save synthesis summary to session
        if session_id:
            await session_manager.add_message(
                session_id,
                "assistant",
                synthesis.summary
            )
        
        # 10. Notify clients that report is ready
        if session_id:
            await streaming_service.publish_event(
                session_id,
                "report_ready",
                "report_engine",
                {
                    "workflow_id": request_id,
                    "report_sections": len(report.sections),
                    "overall_confidence": report.overall_confidence
                }
            )
        
        # 11. Mark checkpoint as completed
        await workflow_checkpoint.mark_completed(request_id)
        
        # 12. Log experiment (Phase 7)
        execution_time_ms = (time.time() - workflow_start) * 1000
        await _log_experiment(
            request_id, plan, agent_responses, report, execution_time_ms
        )
        
        # 13. Record decision if report has recommended actions (Phase 8)
        await _record_decision_if_applicable(
            request_id, agent_request.query, agent_responses,
            report, execution_time_ms
        )
        
        logger.info(f"✅ Background workflow completed for request {request_id}")
        
    except Exception as e:
        logger.error(f"❌ Background workflow failed for request {request_id}: {str(e)}")
        
        # Mark checkpoint as failed
        await workflow_checkpoint.mark_failed(request_id, str(e))
        
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
    
    finally:
        # Always cleanup shared context (even on failure)
        await shared_context.cleanup_workflow(request_id)


async def _execute_with_checkpoints(
    plan: Dict[str, Any],
    agent_request: AgentRequest,
    request_id: str,
    execution_levels: List[List[str]]
) -> list:
    """
    Execute agents level-by-level with checkpoints + timeout.
    
    Phase 8: Each agent wrapped in asyncio.wait_for() using
    estimated_duration_ms * 3 safety margin.
    """
    from app.core.registry import agent_registry
    
    all_responses = []
    completed_agents = []
    
    for level_idx, level_agents in enumerate(execution_levels):
        logger.info(
            f"🔄 Executing level {level_idx}/{len(execution_levels) - 1}: "
            f"{level_agents}"
        )
        
        # Build tasks with timeout
        tasks = []
        agent_names_in_level = []
        for agent_name in level_agents:
            agent_instance = agent_registry.get_agent(agent_name)
            if agent_instance:
                agent_instance.shared_context = shared_context
                
                # Get timeout from capability (3x safety margin, min 30s)
                capability = agent_registry.get_capability(agent_name)
                if capability:
                    timeout_s = max(30, (capability.estimated_duration_ms / 1000) * 3)
                else:
                    timeout_s = 60  # Default 60s
                
                # Wrap in timeout
                tasks.append(
                    _execute_agent_with_timeout(
                        agent_instance, agent_request, agent_name, timeout_s
                    )
                )
                agent_names_in_level.append(agent_name)
            else:
                logger.warning(f"Agent '{agent_name}' not found in registry, skipping")
        
        if tasks:
            level_start = time.time()
            level_responses = await asyncio.gather(*tasks, return_exceptions=True)
            level_duration_ms = (time.time() - level_start) * 1000
            
            agent_count = max(1, len([r for r in level_responses if not isinstance(r, Exception)]))
            per_agent_ms = level_duration_ms / agent_count
            
            for i, resp in enumerate(level_responses):
                if isinstance(resp, Exception):
                    name = agent_names_in_level[i] if i < len(agent_names_in_level) else "unknown"
                    logger.error(f"Agent {name} in level {level_idx} failed: {resp}")
                    all_responses.append(AgentResponse(
                        agent_name=name,
                        success=False,
                        error=str(resp)
                    ))
                else:
                    all_responses.append(resp)
                    completed_agents.append(resp.agent_name)
                    
                    await artifact_store.save(
                        workflow_id=request_id,
                        agent_name=resp.agent_name,
                        data=resp.data or {},
                        duration_ms=per_agent_ms,
                        success=resp.success
                    )
        
        # Checkpoint after this level completes
        await workflow_checkpoint.save_checkpoint(
            workflow_id=request_id,
            plan=plan,
            completed_level=level_idx,
            completed_agents=list(completed_agents),
            status="in_progress"
        )
        
        logger.info(f"💾 Checkpoint saved after level {level_idx}")
    
    return all_responses


async def _execute_agent_with_timeout(agent, request, agent_name, timeout_s):
    """Execute a single agent with asyncio.wait_for timeout."""
    try:
        return await asyncio.wait_for(
            agent.execute_with_observability(request),
            timeout=timeout_s
        )
    except asyncio.TimeoutError:
        logger.warning(f"⏱️ Agent '{agent_name}' timed out after {timeout_s:.0f}s")
        return AgentResponse(
            agent_name=agent_name,
            success=False,
            error=f"Agent timed out after {timeout_s:.0f}s"
        )


async def _log_experiment(
    workflow_id: str,
    plan: Dict[str, Any],
    agent_responses: list,
    report: Any,
    execution_time_ms: float
) -> None:
    """Log completed workflow as experiment (Phase 7)."""
    try:
        # Gather agent metrics
        agent_metrics = {}
        confidence_scores = {}
        
        for resp in agent_responses:
            if resp.success and resp.data:
                metrics = agent_evaluator.compute_metrics(
                    resp.agent_name, resp.data
                )
                agent_metrics[resp.agent_name] = {
                    m.metric_name: m.value for m in metrics
                }
                # Extract confidence if in metadata
                conf = resp.metadata.get("confidence_score", 0)
                if conf:
                    confidence_scores[resp.agent_name] = conf
        
        # Get planner reasoning from plan
        planner_reasoning = plan.get("reasoning", "No planner reasoning recorded")
        
        await experiment_logger.log_experiment(
            workflow_id=workflow_id,
            dataset_hash=experiment_logger.hash_dataset(
                plan.get("context", {})
            ),
            agent_config={
                "agents_used": [r.agent_name for r in agent_responses],
                "execution_levels": plan.get("execution_levels", [])
            },
            agent_metrics=agent_metrics,
            confidence_scores=confidence_scores,
            overall_confidence=getattr(report, "overall_confidence", 0),
            planner_reasoning=planner_reasoning,
            report_summary=getattr(report, "executive_summary", ""),
            execution_time_ms=execution_time_ms
        )
    except Exception as e:
        logger.warning(f"Failed to log experiment: {e}")


async def _record_decision_if_applicable(
    workflow_id: str,
    query: str,
    agent_responses: list,
    report: Any,
    execution_time_ms: float
) -> None:
    """Record decision only if report has recommended actions (Phase 8)."""
    try:
        # Check if report has recommended_actions
        recommended_actions = []
        decision_type = "analysis"  # Default
        
        if hasattr(report, "sections"):
            for section in report.sections:
                title = getattr(section, "title", "").lower()
                content = getattr(section, "content", "")
                
                if "recommend" in title or "action" in title:
                    if isinstance(content, list):
                        recommended_actions.extend(content)
                    elif isinstance(content, str) and len(content) > 10:
                        recommended_actions.append(content)
                
                # Infer decision type
                if "forecast" in title:
                    decision_type = "forecast"
                elif "inventory" in title or "order" in title:
                    decision_type = "inventory_order"
                elif "optim" in title:
                    decision_type = "optimization"
        
        if not recommended_actions:
            return  # Not a decision — skip recording
        
        # Gather metrics for decision record
        agent_metrics = {}
        for resp in agent_responses:
            if resp.success and resp.data:
                metrics = agent_evaluator.compute_metrics(
                    resp.agent_name, resp.data
                )
                agent_metrics[resp.agent_name] = {
                    m.metric_name: m.value for m in metrics
                }
        
        await decision_memory.record_decision(
            workflow_id=workflow_id,
            decision_type=decision_type,
            query=query,
            recommended_actions=recommended_actions,
            confidence=getattr(report, "overall_confidence", 0),
            agent_metrics=agent_metrics
        )
    except Exception as e:
        logger.warning(f"Failed to record decision: {e}")


def _extract_execution_order(plan: Dict[str, Any]) -> List[str]:
    """Extract flat agent execution order from plan's execution_levels."""
    execution_levels = plan.get("execution_levels", [])
    if execution_levels:
        order = []
        for level in execution_levels:
            order.extend(level)
        return order
    
    # Fallback: extract from execution_plan
    execution_plan = plan.get("execution_plan", [])
    return [step.get("agent", "") for step in execution_plan if step.get("agent")]