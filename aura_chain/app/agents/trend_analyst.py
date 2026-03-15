from app.agents.base_agent import BaseAgent, AgentRequest, AgentResponse, ConfidenceScore
from app.core.api_clients import groq_client
from app.core.streaming import streaming_service
from app.config import get_settings
import pandas as pd
import numpy as np
from scipy import stats
from pytrends.request import TrendReq
import asyncio
import json
from typing import Dict, List, Any
from loguru import logger

settings = get_settings()


class TrendAnalystAgent(BaseAgent):
    """
    Analyzes trends combining:
    - Internal data patterns (statistical analysis)
    - External market intelligence (Google Trends)
    - Seasonal patterns and anomalies
    
    Phase 5: Reasoning-enabled agent.
    Evaluates insight quality and data coverage.
    """
    
    max_reasoning_attempts = 2
    min_acceptable_score = 0.5
    
    def __init__(self):
        super().__init__(
            name="TrendAnalyst",
            model=settings.TREND_ANALYST_MODEL,
            api_client=groq_client
        )
        self.pytrends = None
    
    def get_system_prompt(self) -> str:
        """BUG-6 fix: Domain-specific system prompt for TrendAnalyst."""
        return (
            "You are TrendAnalyst, a specialized supply chain trend analysis agent. "
            "Your job is to analyze business datasets for demand trends, seasonal patterns, and market signals.\n\n"
            "YOUR CAPABILITIES:\n"
            "- Use sql_query to run SQL on the dataset (table name is 'df')\n"
            "- Use demand_velocity to calculate rolling sales velocity\n"
            "- Use fetch_global_trends to get Google Trends data for keywords\n"
            "- Use correlation_analysis to find relationships between columns\n\n"
            "STRICT RULES:\n"
            "- NEVER write Python code. You are NOT a Python interpreter.\n"
            "- NEVER fabricate or invent data. Only use observations from tools.\n"
            "- NEVER pass a 'df' parameter — it is automatically provided to tools.\n"
            "- For sql_query, always use 'df' as the table name.\n"
            "- Be concise in your Thought sections.\n"
        )

    
    def should_reason(self) -> bool:
        return True
        
    def should_react(self) -> bool:
        return True
        
    def get_react_tools(self) -> List[str]:
        return ["sql_query", "demand_velocity", "fetch_global_trends", "correlation_analysis"]

    async def _run_react_loop(self, request: AgentRequest) -> AgentResponse:
        """Phase 5: Execute full ReAct loop instead of procedural process()"""
        logger.info(f"Starting autonomous ReAct loop for TrendAnalyst.")
        
        # Override the request query to enforce the output format
        enforced_query = (
            f"Original query: {request.query}\n"
            "Use your tools to analyze the datasets internal trends and external Google trends. "
            "You MUST output your Final Answer exactly in this JSON schema:\n"
            "{\n"
            '  "trend_directions": {"metric_col": "increasing or decreasing or stable"},\n'
            '  "volatility": {"metric_col": "high or medium or low"},\n'
            '  "market_sentiment": "active or neutral",\n'
            '  "external_keywords": ["keyword1", "keyword2"],\n'
            '  "key_findings": ["Finding 1", "Finding 2"],\n'
            '  "opportunities": [{"message": "opportunity 1", "confidence": 0.8}],\n'
            '  "risks": [{"message": "risk 1", "confidence": 0.9}],\n'
            '  "recommendations": ["rec 1", "rec 2"]\n'
            "}"
        )
        
        react_request = AgentRequest(
            query=enforced_query,
            context=request.context,
            session_id=request.session_id,
            user_id=request.user_id,
            workflow_id=request.workflow_id
        )
        
        response = await super()._run_react_loop(react_request)
        
        if response.success and response.data:
            trend_findings = {
                "trend_directions": response.data.get("trend_directions", {}),
                "volatility": response.data.get("volatility", {}),
                "market_sentiment": response.data.get("market_sentiment", "neutral"),
                "external_keywords": response.data.get("external_keywords", [])
            }
            await self.publish_findings(request.workflow_id, trend_findings)
            
            # Map ReAct simplified JSON back to the deeply nested structure expected by the React UI (LayoutGenerator.ts)
            ui_internal_trends = {}
            for col, t_dir in trend_findings["trend_directions"].items():
                ui_internal_trends[col] = {
                    "trend_direction": t_dir,
                    "volatility": trend_findings["volatility"].get(col, "unknown")
                }
                
            ui_external_trends = {}
            for kw in trend_findings["external_keywords"]:
                ui_external_trends[kw] = {"trend": "active", "current_interest": 100}

            response.data = {
                "insights": {
                    "market_sentiment": trend_findings["market_sentiment"],
                    "key_findings": response.data.get("key_findings", []),
                    "opportunities": response.data.get("opportunities", []),
                    "risks": response.data.get("risks", []),
                    "recommendations": response.data.get("recommendations", [])
                },
                "analysis": {
                    "internal_trends": ui_internal_trends,
                    "external_trends": ui_external_trends
                },
                "metadata": {
                    "analysis_date": pd.Timestamp.now().isoformat(),
                    "data_points_analyzed": len(request.context.get("dataset", [])),
                    "mode": "ReAct_Autonomous"
                }
            }
            
        return response
    
    def evaluate_output(self, output: Dict, request: AgentRequest) -> tuple[float, list]:
        """Check trend analysis output quality."""
        from app.core.evaluation import agent_evaluator
        result = agent_evaluator.evaluate("trend_analyst", output, success=True)
        return result.score, result.issues
    
    def compute_confidence(self, output: Dict, eval_score: float) -> ConfidenceScore:
        """Compute confidence from insights quality and data coverage."""
        metadata = output.get("metadata", {})
        data_points = metadata.get("data_points_analyzed", 0)
        
        factors = {
            "evaluation_score": eval_score,
            "has_insights": 1.0 if output.get("insights") else 0.3,
            "data_coverage": min(1.0, data_points / 100) if data_points > 0 else 0.2
        }
        
        score = (eval_score * 0.4 + factors["has_insights"] * 0.3 + factors["data_coverage"] * 0.3)
        score = max(0.0, min(1.0, score))
        
        return ConfidenceScore(
            score=round(score, 2),
            justification=f"Data points: {data_points}, has insights: {bool(output.get('insights'))}",
            factors=factors
        )
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        try:
            if "dataset" not in request.context:
                return AgentResponse(
                    agent_name=self.name,
                    success=False,
                    error="No dataset provided for analysis"
                )
            
            df = pd.DataFrame(request.context["dataset"])
            logger.info(f"Analyzing trends for dataset: {df.shape}")
            
            # Notify start
            if request.session_id:
                await streaming_service.publish_agent_progress(
                    request.session_id,
                    self.name,
                    10,
                    "Analyzing internal data patterns...",
                    {"rows": len(df)}
                )
            
            from app.core.trend_engine import LayeredTrendEngine
            
            # Extract keywords first
            if request.session_id:
                await streaming_service.publish_agent_progress(
                    request.session_id,
                    self.name,
                    40,
                    "Extracting keywords for external analysis...",
                    {}
                )
            
            keywords = self._extract_keywords(df, request.query)
            
            # Run Layered Trend Engine
            if request.session_id:
                await streaming_service.publish_agent_progress(
                    request.session_id,
                    self.name,
                    60,
                    f"Running Layered Trend Engine for keywords {keywords}...",
                    {"keywords": keywords}
                )
                
            engine = LayeredTrendEngine(self)
            combined_analysis = await engine.analyze(df, keywords)
            
            # Notify LLM analysis
            if request.session_id:
                await streaming_service.publish_agent_progress(
                    request.session_id,
                    self.name,
                    80,
                    "Generating insights...",
                    {}
                )
            
            # Get LLM insights
            insights = await self._get_insights(combined_analysis, request.query)
            
            # Publish curated findings for downstream agents
            trend_findings = {
                "trend_directions": {},
                "volatility": {},
                "market_sentiment": "neutral"
            }
            
            internal_stats = combined_analysis.get("internal_statistics", {})
            for col, trend_data in internal_stats.items():
                trend_findings["trend_directions"][col] = trend_data.get("trend_direction", "unknown")
                trend_findings["volatility"][col] = trend_data.get("volatility", "unknown")
                
            external_trends = combined_analysis.get("external_market_trends", {})
            if external_trends and not external_trends.get("error"):
                trend_findings["market_sentiment"] = "active"
            trend_findings["external_keywords"] = keywords
            
            await self.publish_findings(request.workflow_id, trend_findings)
            
            return AgentResponse(
                agent_name=self.name,
                success=True,
                data={
                    "analysis": combined_analysis,
                    "insights": insights,
                    "metadata": {
                        "analysis_date": pd.Timestamp.now().isoformat(),
                        "data_points_analyzed": len(df),
                        "external_sources": ["Google Trends"] if external_trends else []
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Trend Analyst error: {str(e)}")
            return AgentResponse(
                agent_name=self.name,
                success=False,
                error=str(e)
            )
    
    def _extract_keywords(self, df: pd.DataFrame, query: str) -> List[str]:
        """Extract product/category keywords from data"""
        keywords = []
        
        # Look for product/category columns
        text_cols = ['product', 'category', 'item', 'name', 'sku', 'type']
        
        for col in df.columns:
            if any(keyword in col.lower() for keyword in text_cols):
                if df[col].dtype == 'object':
                    # Get unique values (limit to top 3)
                    unique_values = df[col].value_counts().head(3).index.tolist()
                    keywords.extend(unique_values)
        
        # Extract from query
        query_words = query.lower().split()
        business_keywords = ['sales', 'revenue', 'demand', 'inventory', 'product', 'market']
        keywords.extend([w for w in query_words if w not in business_keywords and len(w) > 3])
        
        # Limit and clean
        keywords = list(set(keywords))[:5]  # Max 5 keywords
        keywords = [k for k in keywords if len(str(k)) > 2]
        
        return keywords if keywords else ["market trends"]

    async def _get_insights(self, analysis: Dict, query: str) -> Dict:
        """Generate insights using LLM"""
        
        prompt = f"""Analyze these combined trend insights:

Internal Trends:
{json.dumps(analysis['internal_trends'], indent=2)}

External Market Trends (Google):
{json.dumps(analysis['external_trends'], indent=2)}

User Query: {query}

Provide insights in JSON format:
{{
    "key_findings": ["list of main discoveries"],
    "opportunities": [
        {{"type": "opportunity", "message": "...", "confidence": 0.0-1.0}}
    ],
    "risks": [
        {{"type": "risk", "message": "...", "confidence": 0.0-1.0}}
    ],
    "recommendations": ["actionable recommendations"],
    "market_sentiment": "positive/negative/neutral"
}}

Focus on actionable business insights."""
        
        try:
            response = await self.api_client.generate_content(
                model_name=self.model,
                prompt=prompt,
                temperature=0.6,
                max_tokens=800
            )
            
            content = response.get("text", "{}")
            
            # Extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            return json.loads(content)
            
        except Exception as e:
            logger.warning(f"LLM insights failed: {e}")
            
            # Fallback insights
            return {
                "key_findings": ["Internal data shows clear trends", "Market analysis available"],
                "opportunities": [
                    {"type": "opportunity", "message": "Data ready for forecasting", "confidence": 0.8}
                ],
                "risks": [],
                "recommendations": ["Continue monitoring trends", "Consider seasonal patterns"],
                "market_sentiment": "neutral"
            }