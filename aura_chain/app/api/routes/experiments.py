# app/api/routes/experiments.py
"""
Experiment API — list, retrieve, and compare workflow experiments.

Endpoints:
    GET /experiments              → List recent experiments
    GET /experiments/{id}         → Get specific experiment
    GET /experiments/compare      → Compare two experiments by metrics
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("/")
async def list_experiments(limit: int = Query(20, ge=1, le=100)):
    """List recent experiments (newest first)."""
    from app.core.experiments import experiment_logger
    
    experiments = await experiment_logger.list_experiments(limit=limit)
    return {
        "count": len(experiments),
        "experiments": [e.model_dump() for e in experiments]
    }


@router.get("/compare")
async def compare_experiments(
    id1: str = Query(..., description="First experiment ID"),
    id2: str = Query(..., description="Second experiment ID")
):
    """Compare two experiments by metrics and confidence scores."""
    from app.core.experiments import experiment_logger
    
    result = await experiment_logger.compare_experiments(id1, id2)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="One or both experiments not found"
        )
    
    return result.model_dump()


@router.get("/{experiment_id}")
async def get_experiment(experiment_id: str):
    """Get a specific experiment record."""
    from app.core.experiments import experiment_logger
    
    record = await experiment_logger.get_experiment(experiment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    return record.model_dump()
