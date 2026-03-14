# app/api/routes/reports.py
"""
Report API — retrieve executive reports and synthesis summaries.

Endpoints:
    GET /api/v1/reports/{workflow_id}         → Full structured report
    GET /api/v1/reports/{workflow_id}/summary → Quick synthesis summary only
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from pydantic import BaseModel, Field
from app.core.report_engine import report_engine, REPORT_AGENT_NAME
from app.core.artifacts import artifact_store
from loguru import logger

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportResponse(BaseModel):
    workflow_id: str
    title: str
    generated_at: str
    sections: list
    overall_confidence: float
    agents_contributing: list
    total_duration_ms: float


class SummaryResponse(BaseModel):
    workflow_id: str
    summary: str
    key_insights: list
    agents_used: list
    generated_at: str


@router.get("/{workflow_id}", response_model=ReportResponse)
async def get_report(workflow_id: str):
    """
    Retrieve the full executive report for a completed workflow.
    
    The report is auto-generated after all agents complete and is
    stored in ArtifactStore. Returns 404 if not yet generated.
    """
    try:
        report = await report_engine.get_report(workflow_id)
        
        if not report:
            raise HTTPException(
                status_code=404,
                detail=f"Report not found for workflow {workflow_id}. "
                       f"It may still be generating or the workflow hasn't completed."
            )
        
        return ReportResponse(
            workflow_id=report.workflow_id,
            title=report.title,
            generated_at=report.generated_at,
            sections=[s.model_dump() for s in report.sections],
            overall_confidence=report.overall_confidence,
            agents_contributing=report.agents_contributing,
            total_duration_ms=report.total_duration_ms
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}/summary", response_model=SummaryResponse)
async def get_summary(workflow_id: str):
    """
    Retrieve just the synthesis summary for a completed workflow.
    
    This is the lightweight version — returns the quick answer
    without the full 6-section report.
    """
    try:
        # Try to get the report (summary is embedded in it)
        artifact = await artifact_store.get(workflow_id, REPORT_AGENT_NAME)
        
        if not artifact:
            raise HTTPException(
                status_code=404,
                detail=f"Summary not found for workflow {workflow_id}."
            )
        
        report_data = artifact.get("data", {})
        
        # Extract executive summary section
        sections = report_data.get("sections", [])
        exec_summary = ""
        key_findings = ""
        for section in sections:
            if section.get("title") == "Executive Summary":
                exec_summary = section.get("content", "")
            elif section.get("title") == "Key Findings":
                key_findings = section.get("content", "")
        
        return SummaryResponse(
            workflow_id=workflow_id,
            summary=exec_summary or "Report available but summary extraction failed.",
            key_insights=[key_findings] if key_findings else [],
            agents_used=report_data.get("agents_contributing", []),
            generated_at=report_data.get("generated_at", "")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
