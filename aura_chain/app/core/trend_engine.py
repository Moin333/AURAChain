import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Any
from loguru import logger
import asyncio

class LayeredTrendEngine:
    """
    Systematically resolves trends by advancing through layers:
      - Layer 1: Internal indicators (linear regression, CV, anomalies)
      - Layer 2: DuckDB/demand_velocity mapping
      - Layer 3: External fetch_global_trends via ToolRegistry
    """
    
    def __init__(self, agent):
        """
        agent is a reference to the invoking agent (e.g. TrendAnalystAgent) 
        to access its execute_tool method.
        """
        self.agent = agent

    def _safe_float(self, val: Any) -> float:
        try:
            if pd.isna(val) or np.isinf(val):
                return 0.0
            return float(val)
        except:
            return 0.0

    def _layer1_internal_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Layer 1: Analyze internal data patterns using linear regression and statistics."""
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        trends = {}
        
        for col in numeric_cols:
            series = df[col].dropna()
            
            if len(series) < 2:
                continue
            
            x = np.arange(len(series))
            try:
                slope, intercept, r_value, p_value, std_err = stats.linregress(x, series)
            except Exception:
                slope, intercept, r_value, p_value, std_err = 0, 0, 0, 1, 0
            
            mean_val = series.mean()
            std_val = series.std()
            cv = (std_val / mean_val) * 100 if mean_val != 0 else 0
            
            z_scores = np.abs(stats.zscore(series))
            if np.isnan(z_scores).all():
                anomalies = 0
            else:
                anomalies = (z_scores > 2).sum()
            
            if len(series) > 1 and series.iloc[0] != 0:
                growth_rate = ((series.iloc[-1] - series.iloc[0]) / series.iloc[0]) * 100
            else:
                growth_rate = 0
            
            trends[col] = {
                "trend_direction": "increasing" if slope > 0 else "decreasing",
                "slope": self._safe_float(slope),
                "r_squared": self._safe_float(r_value ** 2),
                "p_value": self._safe_float(p_value),
                "significance": "significant" if p_value < 0.05 else "not significant",
                "statistics": {
                    "mean": self._safe_float(mean_val),
                    "std": self._safe_float(std_val),
                    "coefficient_of_variation": self._safe_float(cv),
                    "min": self._safe_float(series.min()),
                    "max": self._safe_float(series.max()),
                    "growth_rate_pct": self._safe_float(growth_rate)
                },
                "anomalies_detected": int(anomalies),
                "volatility": "high" if cv > 30 else "medium" if cv > 15 else "low"
            }
        return trends

    async def _layer2_demand_velocity(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Layer 2: Discover recent trajectory variance via demand_velocity tool if date column exists."""
        # Auto-detect date and value columns
        date_cols = df.select_dtypes(include=['datetime64', 'object']).columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        if len(date_cols) == 0 or len(numeric_cols) == 0:
            return {"status": "skipped", "reason": "Missing date or numeric columns"}
            
        date_col = next((c for c in date_cols if 'date' in c.lower() or 'time' in c.lower()), date_cols[0])
        value_col = next((c for c in numeric_cols if 'sales' in c.lower() or 'revenue' in c.lower() or 'demand' in c.lower()), numeric_cols[0])
        
        try:
            velocity_data = await self.agent.execute_tool(
                "demand_velocity",
                df=df,
                date_column=date_col,
                value_column=value_col,
                freq='W'
            )
            return velocity_data
        except Exception as e:
            logger.warning(f"Layer 2 demand_velocity failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def _layer3_external_trends(self, keywords: List[str]) -> Dict[str, Any]:
        """Layer 3: Query external fetch_global_trends tool with circuit-breaker protection."""
        if not keywords:
            return {}
            
        try:
            external_data = await self.agent.execute_tool(
                "fetch_global_trends",
                keywords=keywords
            )
            
            # Check if circuit breaker blocked the request
            if isinstance(external_data, dict) and external_data.get("error"):
                logger.warning(f"Layer 3 external trends skipped/failed: {external_data.get('message')}")
                # We do NOT raise an exception. The engine gracefully downgrades.
                return external_data
                
            return external_data
        except Exception as e:
            logger.warning(f"Layer 3 external trends tool execution failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def analyze(self, df: pd.DataFrame, keywords: List[str]) -> Dict[str, Any]:
        """Executes the layered trend resolution pipeline."""
        logger.info("Executing LayeredTrendEngine...")
        
        # CPU-Bound internal statistical processing
        loop = asyncio.get_event_loop()
        layer1_stats = await loop.run_in_executor(None, self._layer1_internal_stats, df)
        
        # Time-series velocity
        layer2_velocity = await self._layer2_demand_velocity(df)
        
        # External Google Trends validation
        layer3_external = await self._layer3_external_trends(keywords)
        
        return {
            "internal_statistics": layer1_stats,
            "demand_velocity": layer2_velocity,
            "external_market_trends": layer3_external
        }
