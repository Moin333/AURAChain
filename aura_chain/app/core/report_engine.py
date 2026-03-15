# app/core/report_engine.py
"""
Report Engine — generates structured executive reports from agent artifacts.

Takes the SynthesisResult (quick answer) + raw artifacts and produces a
6-section executive report via LLM. The report is saved to ArtifactStore
as a special artifact with agent_name="__report__".

Report Sections:
    1. Executive Summary
    2. Key Findings
    3. Deep Analysis (per-agent, in execution order)
    4. Risks & Opportunities
    5. Recommended Actions
    6. Confidence Assessment
"""

import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
from loguru import logger
from app.core.artifacts import artifact_store
from app.core.synthesizer import SynthesisResult
from app.core.api_clients import groq_client
from app.config import get_settings

settings = get_settings()

# Reserved agent name for the report artifact
REPORT_AGENT_NAME = "__report__"


class ReportSection(BaseModel):
    """A single section of the executive report."""
    title: str
    content: str


class ExecutiveReport(BaseModel):
    """The full structured executive report."""
    workflow_id: str
    title: str
    generated_at: str
    sections: List[ReportSection]
    overall_confidence: float           # 0.0-1.0
    agents_contributing: List[str]
    total_duration_ms: float


class ReportEngine:
    """Generates and persists structured executive reports."""
    
    def __init__(self):
        self.api_client = groq_client
        self.model = settings.ORCHESTRATOR_MODEL
    
    async def generate(
        self,
        workflow_id: str,
        synthesis: SynthesisResult,
        execution_order: Optional[List[str]] = None
    ) -> ExecutiveReport:
        """
        Generate a full executive report.
        
        Args:
            workflow_id: The workflow to report on
            synthesis: The SynthesisResult from ResponseSynthesizer
            execution_order: Ordered agent names for consistent deep analysis section
        """
        # 1. Fetch all artifacts for deep analysis
        all_artifacts = await artifact_store.get_all(workflow_id)
        
        # 2. Order by execution_order
        if execution_order:
            ordered_names = [n for n in execution_order if n in all_artifacts]
            remaining = [n for n in all_artifacts if n not in ordered_names]
            ordered_names.extend(remaining)
        else:
            ordered_names = sorted(all_artifacts.keys())
        
        # 3. Build deep analysis per agent (in execution order)
        agent_summaries = self._build_agent_summaries(all_artifacts, ordered_names)
        
        # 4. Calculate metrics
        total_duration = sum(
            a.get("duration_ms", 0) for a in all_artifacts.values()
        )
        
        success_count = sum(
            1 for a in all_artifacts.values() if a.get("success", False)
        )
        overall_confidence = success_count / len(all_artifacts) if all_artifacts else 0
        
        # 5. Generate report sections via LLM
        sections = await self._generate_sections(
            synthesis=synthesis,
            agent_summaries=agent_summaries,
            ordered_names=ordered_names,
            overall_confidence=overall_confidence
        )
        
        # 6. Build report
        report = ExecutiveReport(
            workflow_id=workflow_id,
            title=f"Workflow Analysis Report",
            generated_at=datetime.utcnow().isoformat(),
            sections=sections,
            overall_confidence=round(overall_confidence, 2),
            agents_contributing=ordered_names,
            total_duration_ms=total_duration
        )
        
        # 7. Persist report to ArtifactStore
        await self._save_report(workflow_id, report)
        
        logger.info(f"📊 Report generated for workflow {workflow_id} ({len(sections)} sections)")
        
        return report
    
    def _build_agent_summaries(
        self,
        artifacts: Dict[str, Dict],
        ordered_names: List[str]
    ) -> Dict[str, str]:
        """Build concise per-agent summaries for the deep analysis section."""
        summaries = {}
        
        for name in ordered_names:
            artifact = artifacts.get(name, {})
            data = artifact.get("data", {})
            success = artifact.get("success", False)
            duration = artifact.get("duration_ms", 0)
            
            if not isinstance(data, dict):
                summaries[name] = f"Completed ({'success' if success else 'failed'}) in {duration:.0f}ms"
                continue
            
            # Extract key metrics for each known agent type
            summary_parts = [f"Status: {'✅ Success' if success else '❌ Failed'}", f"Duration: {duration:.0f}ms"]
            
            # Agent-specific extraction
            if name == "data_harvester":
                meta = data.get("metadata", {})
                summary_parts.append(f"Rows: {meta.get('rows_processed', '?')}")
                summary_parts.append(f"Quality: {meta.get('quality_score', '?')}")
            
            elif name == "trend_analyst":
                meta = data.get("metadata", {})
                summary_parts.append(f"Data points: {meta.get('data_points_analyzed', '?')}")
                if data.get("insights"):
                    summary_parts.append(f"Insights: {str(data['insights'])[:300]}")
            
            elif name == "forecaster":
                meta = data.get("metadata", {})
                summary_parts.append(f"Model: {meta.get('model', '?')}")
                if data.get("interpretation"):
                    summary_parts.append(f"Interpretation: {str(data['interpretation'])[:300]}")
            
            elif name == "mcts_optimizer":
                savings = data.get("expected_savings", {})
                summary_parts.append(f"Savings: {savings.get('percentage', 0):.1f}%")
                action = data.get("optimal_action", {})
                summary_parts.append(f"Reorder point: {action.get('reorder_point', '?')}")
                if data.get("interpretation"):
                    summary_parts.append(f"Interpretation: {str(data['interpretation'])[:300]}")
            
            elif name == "visualizer":
                spec = data.get("chart_spec", {})
                summary_parts.append(f"Chart: {spec.get('chart_type', '?')}")
            
            elif name == "order_manager":
                if data.get("plan"):
                    summary_parts.append(f"Plan: {str(data['plan'])[:300]}")
            
            elif name == "notifier":
                summary_parts.append(f"Channel: {data.get('channel', '?')}")
            
            summaries[name] = "\n".join(summary_parts)
        
        return summaries
    
    async def _generate_sections(
        self,
        synthesis: SynthesisResult,
        agent_summaries: Dict[str, str],
        ordered_names: List[str],
        overall_confidence: float
    ) -> List[ReportSection]:
        """Generate report sections via LLM."""
        
        # Build agent context for the prompt
        agent_context = "\n\n".join([
            f"### {name}\n{agent_summaries.get(name, 'No data')}"
            for name in ordered_names
        ])
        
        insights_text = "\n".join([f"- {i}" for i in synthesis.key_insights])
        
        prompt = f"""You are a business report writer for an MSME supply chain platform.

Generate a structured executive report from these inputs:

## SYNTHESIS SUMMARY
{synthesis.summary}

## KEY INSIGHTS
{insights_text}

## AGENT DETAILS (in execution order)
{agent_context}

## METRICS
- Agents used: {len(ordered_names)}
- Overall confidence: {overall_confidence:.0%}

Generate exactly 6 sections in JSON format:

{{
    "executive_summary": "One paragraph overview for C-level audience",
    "key_findings": "3-5 bullet points of most critical discoveries",
    "deep_analysis": "Per-agent breakdown using the agent details above, in execution order",
    "risks_and_opportunities": "Business risks identified and opportunities to exploit",
    "recommended_actions": "Prioritized list of 3-5 actionable next steps",
    "confidence_assessment": "Assessment of data quality, model confidence, and reliability"
}}

Write for an MSME business owner. Be specific, actionable, and data-driven."""
        
        try:
            response = await self.api_client.generate_content(
                model_name=self.model,
                prompt=prompt,
                temperature=0.3,
                max_tokens=2500
            )
            
            content = response.get("text", "{}")
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # Try parsing with strict=False (LLM output may contain control chars)
            try:
                result = json.loads(content, strict=False)
            except json.JSONDecodeError:
                # Attempt to repair truncated JSON
                repaired = content.rstrip()
                if repaired.count('"') % 2 != 0:
                    repaired += '"'
                for open_ch, close_ch in [('[', ']'), ('{', '}')]:
                    diff = repaired.count(open_ch) - repaired.count(close_ch)
                    repaired += close_ch * max(0, diff)
                result = json.loads(repaired, strict=False)
            
            # Map JSON keys → section titles
            section_map = [
                ("executive_summary", "Executive Summary"),
                ("key_findings", "Key Findings"),
                ("deep_analysis", "Deep Analysis"),
                ("risks_and_opportunities", "Risks & Opportunities"),
                ("recommended_actions", "Recommended Actions"),
                ("confidence_assessment", "Confidence Assessment"),
            ]
            
            sections = []
            for key, title in section_map:
                content_text = result.get(key, "No data available.")
                # LLM sometimes returns a list of bullet points instead of a string
                if isinstance(content_text, list):
                    content_text = "\n".join(str(item) for item in content_text)
                elif not isinstance(content_text, str):
                    content_text = str(content_text)
                sections.append(ReportSection(title=title, content=content_text))
            
            return sections
            
        except Exception as e:
            logger.error(f"Report generation LLM failed: {e}")
            return self._fallback_sections(synthesis, agent_summaries, ordered_names, overall_confidence)
    
    def _fallback_sections(
        self,
        synthesis: SynthesisResult,
        agent_summaries: Dict[str, str],
        ordered_names: List[str],
        overall_confidence: float
    ) -> List[ReportSection]:
        """Deterministic fallback when LLM fails."""
        insights = "\n".join([f"• {i}" for i in synthesis.key_insights]) or "No insights available."
        
        deep_analysis = "\n\n".join([
            f"**{name}**\n{agent_summaries.get(name, 'No data')}"
            for name in ordered_names
        ])
        
        return [
            ReportSection(title="Executive Summary", content=synthesis.summary),
            ReportSection(title="Key Findings", content=insights),
            ReportSection(title="Deep Analysis", content=deep_analysis),
            ReportSection(title="Risks & Opportunities", content="Manual review recommended."),
            ReportSection(title="Recommended Actions", content="Review individual agent outputs for detailed recommendations."),
            ReportSection(title="Confidence Assessment", content=f"Overall confidence: {overall_confidence:.0%}. Based on {len(ordered_names)} agents."),
        ]
    
    async def _save_report(self, workflow_id: str, report: ExecutiveReport) -> None:
        """Save the report as a special artifact in ArtifactStore."""
        report_data = report.model_dump()
        
        await artifact_store.save(
            workflow_id=workflow_id,
            agent_name=REPORT_AGENT_NAME,
            data=report_data,
            duration_ms=0,
            success=True
        )
        
        logger.debug(f"Report saved as artifact '{REPORT_AGENT_NAME}' for workflow {workflow_id}")
    
    async def get_report(self, workflow_id: str) -> Optional[ExecutiveReport]:
        """Retrieve a previously generated report."""
        artifact = await artifact_store.get(workflow_id, REPORT_AGENT_NAME)
        
        if not artifact:
            return None
        
        try:
            report_data = artifact.get("data", {})
            return ExecutiveReport(**report_data)
        except Exception as e:
            logger.error(f"Failed to deserialize report: {e}")
            return None


# Global instance
report_engine = ReportEngine()
