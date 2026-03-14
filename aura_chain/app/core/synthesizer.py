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
                    # Truncate with indicator
                    clean[key] = json.loads(serialized[:MAX_FIELD_CHARS]) if serialized[:1] in ('{', '[') else serialized[:MAX_FIELD_CHARS] + "...[truncated]"
                else:
                    clean[key] = value
            
            sanitized[name] = clean
        
        return sanitized
    
    async def _llm_synthesize(
        self,
        sanitized_artifacts: Dict[str, Any],
        workflow_id: str
    ) -> tuple[str, List[str]]:
        """Run LLM to produce unified narrative + key insights."""
        
        # Build per-agent summaries
        agent_sections = []
        for name, data in sanitized_artifacts.items():
            section = f"**{name}**:\n{json.dumps(data, indent=2, default=str)}"
            agent_sections.append(section)
        
        agents_text = "\n\n".join(agent_sections)
        
        prompt = f"""You are a business analyst synthesizing results from multiple AI agents.

Below are the outputs from each agent in execution order:

{agents_text}

Produce:
1. A **summary** (2-4 paragraphs) that combines all findings into a coherent business narrative. Write for an MSME business owner — clear, actionable, no jargon.
2. A list of **key_insights** (3-7 bullet points) — the most important takeaways.

Respond in JSON:
{{
    "summary": "...",
    "key_insights": ["insight1", "insight2", ...]
}}"""
        
        try:
            response = await self.api_client.generate_content(
                model_name=self.model,
                prompt=prompt,
                temperature=0.4,
                max_tokens=1500
            )
            
            content = response.get("text", "{}")
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            return result.get("summary", "Synthesis complete."), result.get("key_insights", [])
            
        except Exception as e:
            logger.error(f"LLM synthesis failed: {e}")
            # Fallback: simple concatenation
            agent_names = list(sanitized_artifacts.keys())
            return (
                f"Workflow completed with {len(agent_names)} agents: {', '.join(agent_names)}.",
                [f"{name} completed successfully" for name in agent_names]
            )


# Global instance
response_synthesizer = ResponseSynthesizer()
