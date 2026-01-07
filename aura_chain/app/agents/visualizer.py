# app/agents/visualizer.py
from app.agents.base_agent import BaseAgent, AgentRequest, AgentResponse
from app.core.api_clients import groq_client
from app.config import get_settings
from typing import Dict
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json

settings = get_settings()

class VisualizerAgent(BaseAgent):
    """Creates visualizations using Gemini Flash"""
    
    def __init__(self):
        super().__init__(
            name="Visualizer",
            model=settings.VISUALIZER_MODEL,
            api_client=groq_client
        )
    
    def get_system_prompt(self) -> str:
        return """You are a data visualization expert. Create chart specifications in JSON format.

Supported chart types:
- line, bar, scatter, pie, heatmap, box, violin, histogram

Response format:
{
    "chart_type": "line",
    "title": "Chart Title",
    "x_axis": "column_name",
    "y_axis": "column_name",
    "color_by": "optional_column",
    "additional_params": {}
}"""
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        try:
            if "dataset" not in request.context:
                return AgentResponse(
                    agent_name=self.name,
                    success=False,
                    error="No dataset provided"
                )
            
            df = pd.DataFrame(request.context["dataset"])
            
            prompt = f"""{self.get_system_prompt()}

Create a visualization for: {request.query}

Dataset columns: {list(df.columns)}
Sample data: {df.head(3).to_dict('records')}

Provide chart specification in JSON format."""
            
            response = await self.api_client.generate_content(
                model_name=self.model,
                prompt=prompt,
                temperature=0.3
            )
            
            content = response.get("text", "{}")
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            
            chart_spec = json.loads(content)
            
            # Generate chart using plotly
            fig = self._create_chart(df, chart_spec)
            
            return AgentResponse(
                agent_name=self.name,
                success=True,
                data={
                    "chart_spec": chart_spec,
                    "chart_json": fig.to_json(),
                    "chart_html": fig.to_html()
                }
            )
            
        except Exception as e:
            return AgentResponse(
                agent_name=self.name,
                success=False,
                error=str(e)
            )
    
    def _create_chart(self, df: pd.DataFrame, spec: Dict) -> go.Figure:
        """Create plotly chart from specification"""
        chart_type = spec.get("chart_type", "line")
        
        if chart_type == "line":
            fig = px.line(df, x=spec["x_axis"], y=spec["y_axis"], title=spec["title"])
        elif chart_type == "bar":
            fig = px.bar(df, x=spec["x_axis"], y=spec["y_axis"], title=spec["title"])
        elif chart_type == "scatter":
            fig = px.scatter(df, x=spec["x_axis"], y=spec["y_axis"], title=spec["title"])
        elif chart_type == "pie":
            fig = px.pie(df, names=spec["x_axis"], values=spec["y_axis"], title=spec["title"])
        else:
            fig = px.line(df, x=spec["x_axis"], y=spec["y_axis"], title=spec["title"])
        
        return fig