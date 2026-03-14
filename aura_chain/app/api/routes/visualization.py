# app/api/routes/visualization.py
"""
Workflow Visualization API — render DAG graphs for debugging.

Endpoints:
    POST /workflows/visualize   → Render a plan as graph + Mermaid
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any

router = APIRouter(prefix="/workflows", tags=["visualization"])


class VisualizePlanRequest(BaseModel):
    plan: Dict[str, Any]


@router.post("/visualize")
async def visualize_workflow(body: VisualizePlanRequest):
    """
    Render a workflow plan as JSON graph, Mermaid diagram, and critical path.
    
    Send a plan object (from the workflow planner) and receive the visualization.
    """
    from app.core.workflow_visualizer import workflow_visualizer
    
    return workflow_visualizer.get_execution_summary(body.plan)
