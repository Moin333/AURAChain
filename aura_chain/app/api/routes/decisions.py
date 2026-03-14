# app/api/routes/decisions.py
"""
Decision API — list, retrieve, record outcomes for decisions.

Endpoints:
    GET  /decisions              → List recent decisions
    GET  /decisions/stats        → Accuracy statistics  
    GET  /decisions/{id}         → Get specific decision
    POST /decisions/{id}/outcome → Record outcome for a decision
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/decisions", tags=["decisions"])


class OutcomeRequest(BaseModel):
    expected_outcome: str
    actual_outcome: str
    accuracy_score: float  # 0.0-1.0, computed by caller
    feedback: str = ""


@router.get("/")
async def list_decisions(
    limit: int = Query(20, ge=1, le=100),
    decision_type: Optional[str] = Query(None, description="Filter by type")
):
    """List recent decisions (newest first)."""
    from app.core.decision_memory import decision_memory
    
    decisions = await decision_memory.get_decision_history(
        limit=limit, decision_type=decision_type
    )
    return {
        "count": len(decisions),
        "decisions": [d.model_dump() for d in decisions]
    }


@router.get("/stats")
async def decision_stats():
    """Get aggregate accuracy statistics."""
    from app.core.decision_memory import decision_memory
    return await decision_memory.get_accuracy_stats()


@router.get("/{decision_id}")
async def get_decision(decision_id: str):
    """Get a specific decision record."""
    from app.core.decision_memory import decision_memory
    
    record = await decision_memory.get_decision(decision_id)
    if not record:
        raise HTTPException(status_code=404, detail="Decision not found")
    return record.model_dump()


@router.post("/{decision_id}/outcome")
async def record_outcome(decision_id: str, body: OutcomeRequest):
    """Record the actual outcome for a past decision."""
    from app.core.decision_memory import decision_memory
    
    record = await decision_memory.record_outcome(
        decision_id=decision_id,
        expected_outcome=body.expected_outcome,
        actual_outcome=body.actual_outcome,
        accuracy_score=body.accuracy_score,
        feedback=body.feedback
    )
    
    if not record:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    return {"status": "outcome_recorded", "decision": record.model_dump()}
