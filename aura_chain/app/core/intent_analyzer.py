# app/core/intent_analyzer.py
"""
LLM-based Intent Analyzer — replaces hardcoded _detect_mode().

The LLM receives the user query + context flags and outputs a structured
WorkflowIntent. Critically, it does NOT output capability names (which
it could hallucinate). Instead it outputs semantic intent fields that
the WorkflowPlanner maps to capabilities deterministically.

Flow:
    User query → LLM → WorkflowIntent → WorkflowPlanner → DAG
"""

import json
from typing import Any, Dict, Optional
from pydantic import BaseModel
from loguru import logger
from app.core.api_clients import groq_client
from app.core.tool_registry import tool_registry
from app.config import get_settings

settings = get_settings()


class WorkflowIntent(BaseModel):
    """Structured output from the Intent Analyzer.
    
    The LLM fills these semantic fields. The WorkflowPlanner then
    maps them to concrete agents — the LLM never names agents directly.
    """
    goal: str                        # "Optimize inventory for next quarter"
    analysis_type: str               # "forecast" | "trend" | "optimization" | "visualization" | "general"
    wants_visualization: bool        # User wants charts/graphs?
    wants_forecast: bool             # User wants future predictions?
    wants_optimization: bool         # User wants MCTS/inventory optimization?
    wants_order: bool                # User explicitly wants to place an order?
    wants_notification: bool         # User wants alerts/notifications?
    has_data: bool                   # Dataset present in context?
    depth: str                       # "quick" | "standard" | "deep"
    confidence: float                # 0.0-1.0 how confident the LLM is
    reasoning: str                   # Why these choices were made


INTENT_SYSTEM_PROMPT = """You are an Intent Analyzer for an MSME supply chain AI platform.

Your job: Understand what the user wants and output a structured intent — NOT an execution plan.

You must NEVER name specific agents or capabilities. Instead, answer these questions:

1. **goal**: What does the user want to achieve? (one sentence)
2. **analysis_type**: What kind of analysis? One of: "forecast", "trend", "optimization", "visualization", "general"
3. **wants_visualization**: Does the user want charts or graphs? (true/false)
4. **wants_forecast**: Does the user want future predictions? (true/false)
5. **wants_optimization**: Does the user want inventory/decision optimization? (true/false)
6. **wants_order**: Does the user explicitly want to place/draft an order? (true/false)
7. **wants_notification**: Does the user want alerts sent? (true/false)
8. **has_data**: Is there a dataset available? (from context, not your guess)
9. **depth**: How deep should the analysis be?
   - "quick" → Simple question, single-agent answer
   - "standard" → Moderate analysis, a few agents
   - "deep" → Full pipeline, comprehensive analysis
10. **confidence**: How confident are you in this interpretation? (0.0-1.0)
11. **reasoning**: Brief explanation of your choices

IMPORTANT RULES:
- If user says "optimize", "forecast", "full analysis", "deep dive", "strategy" → depth = "deep"
- If user asks a simple question like "show me X" or "what are the trends" → depth = "quick" or "standard"
- If no dataset is available, set has_data = false
- If user says "order", "buy", "purchase" → wants_order = true
- wants_notification should only be true if user explicitly asks for alerts

Respond ONLY in JSON matching this exact schema."""


class IntentAnalyzer:
    """Analyzes user queries to produce structured WorkflowIntent."""
    
    def __init__(self):
        self.api_client = groq_client
        self.model = settings.ORCHESTRATOR_MODEL
    
    async def analyze(self, query: str, context: Dict[str, Any]) -> WorkflowIntent:
        """
        Analyze user query and context to produce a WorkflowIntent.
        
        The intent is purely semantic — no agent names, no capability names.
        The WorkflowPlanner handles the mapping to concrete agents.
        """
        has_data = "dataset_id" in context or "dataset" in context
        
        tools_avail = "\n".join(f"- {t.name}: {t.description}" for t in tool_registry.list_tools())
        prompt = f"""{INTENT_SYSTEM_PROMPT}

AVAILABLE TOOLS (do not name agents, tools only):
{tools_avail}

CONTEXT:
- Has Dataset: {"Yes" if has_data else "No"}
- User Query: {query}

Output your JSON analysis:"""
        
        try:
            response = await self.api_client.generate_content(
                model_name=self.model,
                prompt=prompt,
                temperature=0.1,
                max_tokens=800
            )
            
            content = response.get("text", "{}")
            
            # Parse JSON from LLM response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            try:
                intent_data = json.loads(content)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse intent JSON. Raw: {content}")
                return self._fallback_intent(query, has_data)
            
            # Override has_data with ground truth (don't trust LLM)
            intent_data["has_data"] = has_data
            
            # Clamp confidence
            intent_data["confidence"] = max(0.0, min(1.0, intent_data.get("confidence", 0.5)))
            
            intent = WorkflowIntent(**intent_data)
            logger.info(f"🎯 Intent: type={intent.analysis_type}, depth={intent.depth}, confidence={intent.confidence:.2f}")
            
            return intent
            
        except Exception as e:
            logger.error(f"Intent analysis failed: {e}")
            return self._fallback_intent(query, has_data)
    
    def _fallback_intent(self, query: str, has_data: bool) -> WorkflowIntent:
        """Deterministic fallback when LLM fails — mirrors old _detect_mode() logic."""
        query_lower = query.lower()
        
        deep_keywords = ["optimize", "full analysis", "deep dive", "strategy", "forecast", "predict", "bullwhip", "inventory"]
        order_keywords = ["order", "buy", "purchase", "procure"]
        viz_keywords = ["chart", "graph", "plot", "show", "visualize", "display"]
        trend_keywords = ["trend", "pattern", "seasonal", "growth"]
        
        is_deep = any(k in query_lower for k in deep_keywords)
        wants_order = any(k in query_lower for k in order_keywords)
        wants_viz = any(k in query_lower for k in viz_keywords)
        wants_forecast = any(k in query_lower for k in ["forecast", "predict", "future"])
        wants_trend = any(k in query_lower for k in trend_keywords)
        
        if is_deep or wants_order:
            depth = "deep"
            analysis_type = "optimization" if "optim" in query_lower else "forecast"
        elif has_data:
            depth = "standard"
            analysis_type = "trend" if wants_trend else "visualization" if wants_viz else "general"
        else:
            depth = "quick"
            analysis_type = "trend" if wants_trend else "general"
        
        return WorkflowIntent(
            goal=query[:200],
            analysis_type=analysis_type,
            wants_visualization=wants_viz or is_deep,
            wants_forecast=wants_forecast or is_deep,
            wants_optimization="optim" in query_lower or is_deep,
            wants_order=wants_order,
            wants_notification=False,
            has_data=has_data,
            depth=depth,
            confidence=0.6,
            reasoning="Fallback: LLM intent analysis failed, using keyword matching"
        )


# Global instance
intent_analyzer = IntentAnalyzer()
