# app/core/synthesizer.py
"""
Response Synthesizer — collects all agent artifacts and produces a
unified business-focused narrative via LLM.

This is the "quick answer" stage. The ReportEngine (report_engine.py)
handles the structured executive report separately.

Flow:
    ArtifactStore.get_all(workflow_id) → sanitize → LLM → SynthesisResult
"""

import json
import sys
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
from loguru import logger
from app.core.artifacts import artifact_store
from app.core.api_clients import groq_client
from app.config import get_settings

settings = get_settings()

# Max size (in characters) for any single artifact field sent to LLM
MAX_FIELD_CHARS = 2000
# Fields that should be stripped entirely (heavy payloads)
STRIP_FIELDS = {"chart_html", "chart_json", "processed_data", "dataset", "raw_data"}


class SynthesisResult(BaseModel):
    """Output of the ResponseSynthesizer."""
    workflow_id: str
    summary: str                        # Concise unified narrative
    key_insights: List[str]             # Bullet-point insights
    agents_used: List[str]              # Agents that contributed
    agent_performance: Dict[str, Any]   # Per-agent timing + success
    generated_at: str
    

class ResponseSynthesizer:
    """Collects agent outputs and produces a unified narrative."""
    
    def __init__(self):
        self.api_client = groq_client
        self.model = settings.ORCHESTRATOR_MODEL
    
    async def synthesize(
        self,
        workflow_id: str,
        execution_order: Optional[List[str]] = None
    ) -> SynthesisResult:
        """
        Synthesize all agent outputs into a unified business narrative.
        
        Args:
            workflow_id: The workflow to synthesize
            execution_order: Optional ordered list of agent names for
                             consistent ordering. Derived from execution_levels.
        """
        # 1. Fetch all artifacts
        all_artifacts = await artifact_store.get_all(workflow_id)
        
        if not all_artifacts:
            logger.warning(f"No artifacts found for workflow {workflow_id}")
            return SynthesisResult(
                workflow_id=workflow_id,
                summary="No agent outputs available for synthesis.",
                key_insights=[],
                agents_used=[],
                agent_performance={},
                generated_at=datetime.utcnow().isoformat()
            )
        
        # 2. Order artifacts by execution_order if provided
        if execution_order:
            ordered_names = [n for n in execution_order if n in all_artifacts]
            # Add any unordered agents at the end
            remaining = [n for n in all_artifacts if n not in ordered_names]
            ordered_names.extend(remaining)
        else:
            ordered_names = sorted(all_artifacts.keys())
        
        # 3. Sanitize artifacts for LLM context
        sanitized = self._sanitize_artifacts(all_artifacts, ordered_names)
        
        # 4. Extract performance metadata
        agent_performance = {}
        for name in ordered_names:
            artifact = all_artifacts[name]
            agent_performance[name] = {
                "success": artifact.get("success", False),
                "duration_ms": artifact.get("duration_ms", 0),
                "timestamp": artifact.get("timestamp", "")
            }
        
        # 5. Run LLM synthesis
        summary, key_insights = await self._llm_synthesize(sanitized, workflow_id)
        
        return SynthesisResult(
            workflow_id=workflow_id,
            summary=summary,
            key_insights=key_insights,
            agents_used=ordered_names,
            agent_performance=agent_performance,
            generated_at=datetime.utcnow().isoformat()
        )
    
    def _sanitize_artifacts(
        self,
        artifacts: Dict[str, Dict],
        ordered_names: List[str]
    ) -> Dict[str, Any]:
        """
        Strip heavy payloads and truncate large fields.
        
        This prevents LLM context overflow. Only business-relevant
        data is passed through.
        """
        sanitized = {}
        
        for name in ordered_names:
            artifact = artifacts[name]
            data = artifact.get("data", {})
            
            if not isinstance(data, dict):
                sanitized[name] = {"result": str(data)[:MAX_FIELD_CHARS]}
                continue
            
            clean = {}
            for key, value in data.items():
                # Skip heavy fields entirely
                if key in STRIP_FIELDS:
                    clean[key] = f"[{key}: stripped for synthesis]"
                    continue
                
                # Serialize and check size
                try:
                    serialized = json.dumps(value, default=str)
                except (TypeError, ValueError):
                    serialized = str(value)
                
                if len(serialized) > MAX_FIELD_CHARS:
                    # Truncate with indicator (BUG FIX: do not attempt to json.loads a mid-sliced string)
                    clean[key] = serialized[:MAX_FIELD_CHARS] + "...[truncated]"
                else:
                    clean[key] = value
            
            sanitized[name] = clean
        
        return sanitized
    
    async def _llm_synthesize(
        self,
        sanitized_artifacts: Dict[str, Any],
        workflow_id: str
    ) -> tuple[str, List[str]]:
        """Run structured two-step LLM synthesis.
        
        BUG-5 fix: Instead of one giant JSON response, we split into:
          Step 1: Generate plain-text summary (no JSON envelope → no truncation risk)
          Step 2: Generate key insights as a JSON array
        
        This structural approach eliminates the 'Unterminated string' crash
        that occurred when max_tokens cut off mid-JSON.
        """
        
        # Build per-agent summaries
        agent_sections = []
        for name, data in sanitized_artifacts.items():
            section = f"**{name}**:\n{json.dumps(data, indent=2, default=str)}"
            agent_sections.append(section)
        
        agents_text = "\n\n".join(agent_sections)
        
        # ── STEP 1: Generate summary as plain text ──
        summary_prompt = f"""You are a business analyst writing for an MSME business owner.

Below are the outputs from multiple AI agents in execution order:

{agents_text}

Write a clear, actionable summary (2-4 paragraphs) that combines all findings into a coherent business narrative.
- Write in plain English, no jargon
- Focus on what the business owner should know and do
- Include specific numbers and trends where available

Output ONLY the summary text, no JSON wrapping, no markdown headers."""

        summary = ""
        try:
            response = await self.api_client.generate_content(
                model_name=self.model,
                prompt=summary_prompt,
                temperature=0.4,
                max_tokens=2000
            )
            summary = response.get("text", "").strip()
            if not summary:
                summary = f"Workflow completed with agents: {', '.join(sanitized_artifacts.keys())}."
        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")
            summary = f"Analysis completed by {len(sanitized_artifacts)} agents: {', '.join(sanitized_artifacts.keys())}."
        
        # ── STEP 2: Generate key insights as JSON array ──
        insights_prompt = f"""Based on the following analysis results, extract 3-7 key insights as bullet points.

{agents_text}

Output ONLY a JSON array of strings. Example:
["Insight 1", "Insight 2", "Insight 3"]

No explanation, no wrapping — just the JSON array."""

        key_insights = []
        try:
            response = await self.api_client.generate_content(
                model_name=self.model,
                prompt=insights_prompt,
                temperature=0.3,
                max_tokens=800
            )
            content = response.get("text", "[]").strip()
            
            # Strip markdown fences if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # Parse JSON array
            try:
                parsed = json.loads(content, strict=False)
                if isinstance(parsed, list):
                    key_insights = [str(item) for item in parsed]
                elif isinstance(parsed, dict) and "key_insights" in parsed:
                    key_insights = [str(item) for item in parsed["key_insights"]]
            except json.JSONDecodeError:
                # Try repair
                repaired = content.rstrip()
                if repaired.count('"') % 2 != 0:
                    repaired += '"'
                diff = repaired.count('[') - repaired.count(']')
                repaired += ']' * max(0, diff)
                try:
                    parsed = json.loads(repaired, strict=False)
                    key_insights = [str(item) for item in parsed] if isinstance(parsed, list) else []
                except json.JSONDecodeError:
                    logger.warning("Could not parse insights JSON, falling back to line split")
                    key_insights = [line.strip("- •").strip() for line in content.split("\n") if line.strip()]
        except Exception as e:
            logger.warning(f"Insights generation failed: {e}")
            key_insights = [f"{name} completed successfully" for name in sanitized_artifacts.keys()]
        
        return summary, key_insights


# Global instance
response_synthesizer = ResponseSynthesizer()

