# app/agents/visualizer.py
"""
Visualization Agent — Semantic Intent Architecture (Option B)

Generates a lightweight chart specification + raw data array for
frontend-side rendering with Recharts. No server-side chart rendering.

Previous architecture sent fig.to_html() (~2MB) over SSE which caused
JSON truncation errors. This version sends ~5-50KB payloads.
"""
from app.agents.base_agent import BaseAgent, AgentRequest, AgentResponse
from app.core.api_clients import groq_client
from app.core.streaming import streaming_service
from app.config import get_settings
from typing import Dict, List, Any
from loguru import logger
import pandas as pd
import json

settings = get_settings()

# Maximum rows to include in SSE chart payload
MAX_CHART_DATA_ROWS = 500


class VisualizerAgent(BaseAgent):
    """Creates visualization specifications for frontend rendering."""
    
    def __init__(self):
        super().__init__(
            name="Visualizer",
            model=settings.VISUALIZER_MODEL,
            api_client=groq_client
        )
    
    def get_system_prompt(self) -> str:
        return """You are a data visualization expert. Create chart specifications in JSON format.

Supported chart types:
- line, bar, scatter, pie, area, histogram, box

Response format:
{
    "chart_type": "line",
    "title": "Chart Title",
    "x_axis": "column_name",
    "y_axis": "column_name",
    "color_by": "optional_column",
    "aggregation": "sum",
    "additional_params": {}
}

IMPORTANT:
- x_axis and y_axis MUST be exact column names from the dataset.
- color_by is optional — only include if grouping/coloring by a category is meaningful.
- aggregation is required when y_axis values need to be combined per x_axis group.
  Use "sum", "mean", "count", "max", or "min". Omit if showing raw data points.
- For bar or pie charts with a categorical x_axis, you almost always need aggregation.
- For time series (line/area), if there are multiple rows per date, use aggregation.
- chart_type must be one of: line, bar, scatter, pie, area, histogram, box."""
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        try:
            if "dataset" not in request.context:
                return AgentResponse(
                    agent_name=self.name,
                    success=False,
                    error="No dataset provided"
                )
                
            # Notify start
            if request.session_id:
                await streaming_service.publish_agent_progress(
                    request.session_id,
                    self.name,
                    20,
                    "Analyzing data structure...",
                    {}
                )
            
            df = pd.DataFrame(request.context["dataset"])
            
            prompt = f"""{self.get_system_prompt()}

Create a visualization for: {request.query}

Dataset columns: {list(df.columns)}
Sample data: {df.head(3).to_dict('records')}

Provide chart specification in JSON format."""

            # Notify LLM call
            if request.session_id:
                await streaming_service.publish_agent_progress(
                    request.session_id,
                    self.name,
                    50,
                    "Generating chart specification...",
                    {}
                )
            
            response = await self.api_client.generate_content(
                model_name=self.model,
                prompt=prompt,
                temperature=0.3
            )
            
            content = response.get("text", "{}")
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            chart_spec = json.loads(content)
            
            # Validate and fix column names from LLM output
            chart_spec = self._validate_columns(df, chart_spec)
            
            # Notify chart data preparation
            if request.session_id:
                await streaming_service.publish_agent_progress(
                    request.session_id,
                    self.name,
                    80,
                    "Preparing chart data...",
                    {"chart_type": chart_spec.get("chart_type", "unknown")}
                )
            
            # Publish curated findings for downstream agents
            await self.publish_findings(request.workflow_id, {
                "chart_type": chart_spec.get("chart_type", "unknown"),
                "title": chart_spec.get("title", ""),
                "x_axis": chart_spec.get("x_axis", ""),
                "y_axis": chart_spec.get("y_axis", "")
            })
            
            # Prepare lightweight chart data for frontend rendering (Recharts)
            chart_data = self._prepare_chart_data(df, chart_spec)
            
            logger.info(
                f"📊 Visualizer: sending {len(chart_data)} data points "
                f"for {chart_spec.get('chart_type', 'unknown')} chart"
            )
            
            return AgentResponse(
                agent_name=self.name,
                success=True,
                data={
                    "chart_spec": chart_spec,
                    "chart_data": chart_data
                }
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Visualizer JSON parse error: {e}")
            return AgentResponse(
                agent_name=self.name,
                success=False,
                error=f"Failed to parse chart specification from LLM: {e}"
            )
        except Exception as e:
            logger.error(f"Visualizer error: {e}")
            return AgentResponse(
                agent_name=self.name,
                success=False,
                error=str(e)
            )
    
    def _validate_columns(self, df: pd.DataFrame, spec: Dict) -> Dict:
        """
        Validate that LLM-specified column names exist in the DataFrame.
        Falls back to best-guess columns if names don't match.
        """
        available = list(df.columns)
        
        for col_key in ['x_axis', 'y_axis', 'color_by']:
            col_name = spec.get(col_key)
            if col_name and col_name not in available:
                # Try case-insensitive match
                match = next(
                    (c for c in available if c.lower() == col_name.lower()),
                    None
                )
                if match:
                    logger.info(f"Column '{col_name}' → '{match}' (case fix)")
                    spec[col_key] = match
                elif col_key == 'color_by':
                    # color_by is optional — just remove it
                    logger.warning(f"Removing invalid color_by column: '{col_name}'")
                    del spec[col_key]
                else:
                    # For required axes, fall back to first available column
                    fallback = available[0] if col_key == 'x_axis' else (
                        available[1] if len(available) > 1 else available[0]
                    )
                    logger.warning(
                        f"Column '{col_name}' not found for {col_key}, "
                        f"falling back to '{fallback}'"
                    )
                    spec[col_key] = fallback
        
        return spec
    
    def _prepare_chart_data(
        self, df: pd.DataFrame, spec: Dict
    ) -> List[Dict[str, Any]]:
        """
        Prepare a lightweight, chart-ready data array for frontend Recharts.

        Key behaviors:
        - Aggregates when the LLM specifies aggregation or when the chart
          type + data shape logically requires it (bar/pie with categorical x).
        - For time-series with multiple rows per date, aggregates by date.
        - Caps at MAX_CHART_DATA_ROWS.
        - Converts datetimes to strings for JSON safety.
        """
        x_col = spec.get('x_axis')
        y_col = spec.get('y_axis')
        color_col = spec.get('color_by')
        chart_type = spec.get('chart_type', 'bar').lower()
        agg_func = spec.get('aggregation')  # sum, mean, count, max, min

        # Determine which columns to include
        cols_needed = set()
        for col in [x_col, y_col, color_col]:
            if col and col in df.columns:
                cols_needed.add(col)

        if not cols_needed:
            cols_needed = set(df.columns)

        subset = df[list(cols_needed)].copy()

        # Drop rows where y-axis is NaN (can't chart missing values)
        if y_col and y_col in subset.columns:
            subset[y_col] = pd.to_numeric(subset[y_col], errors='coerce')
            subset = subset.dropna(subset=[y_col])

        # ── Decide whether aggregation is needed ──
        needs_agg = False
        if agg_func:
            needs_agg = True
        elif chart_type in ('bar', 'pie'):
            # Bar/pie charts with categorical x-axis almost always need aggregation
            if x_col and x_col in subset.columns:
                if not pd.api.types.is_numeric_dtype(subset[x_col]):
                    needs_agg = True
                    agg_func = agg_func or 'sum'
        elif chart_type in ('line', 'area'):
            # Time-series with duplicate x values → aggregate
            if x_col and x_col in subset.columns:
                if subset[x_col].duplicated().any():
                    needs_agg = True
                    agg_func = agg_func or 'sum'

        # ── Perform aggregation ──
        if needs_agg and x_col and y_col:
            agg_func = agg_func or 'sum'
            valid_aggs = {'sum', 'mean', 'count', 'max', 'min'}
            if agg_func not in valid_aggs:
                agg_func = 'sum'

            group_cols = [x_col]
            if color_col and color_col in subset.columns and color_col != x_col:
                group_cols.append(color_col)

            try:
                subset = (
                    subset.groupby(group_cols, as_index=False)
                    .agg({y_col: agg_func})
                    .sort_values(x_col)
                )
                logger.info(
                    f"📊 Aggregated by {group_cols} using {agg_func}: "
                    f"{len(subset)} groups"
                )
            except Exception as e:
                logger.warning(f"Aggregation failed ({e}), using raw data")

        # ── Cap rows ──
        subset = subset.head(MAX_CHART_DATA_ROWS)

        # ── Round numeric columns for cleaner display ──
        for col in subset.select_dtypes(include=['float64', 'float32']).columns:
            subset[col] = subset[col].round(2)

        # ── Convert datetimes to strings ──
        for col in subset.select_dtypes(include=['datetime64', 'datetimetz']).columns:
            subset[col] = subset[col].astype(str)

        for col in subset.select_dtypes(include=['object']).columns:
            subset[col] = subset[col].apply(
                lambda x: x.isoformat() if isinstance(x, pd.Timestamp) else x
            )

        return subset.to_dict('records')