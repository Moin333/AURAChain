# app/agents/forecaster.py
from app.agents.base_agent import BaseAgent, AgentRequest, AgentResponse, ConfidenceScore
from app.core.api_clients import groq_client
from app.core.streaming import streaming_service
from app.config import get_settings
import pandas as pd
import numpy as np
from prophet import Prophet
from prophet.plot import plot_plotly
import holidays
import json
from typing import Dict, List
from datetime import datetime, timedelta
import scipy.stats as stats
from loguru import logger

settings = get_settings()


class ForecasterAgent(BaseAgent):
    """
    Advanced forecasting using Facebook Prophet.
    
    Phase 5: Reasoning-enabled agent.
    Evaluates forecast quality (MAPE, confidence) and can retry.
    """
    
    max_reasoning_attempts = 2
    min_acceptable_score = 0.5
    
    def __init__(self):
        super().__init__(
            name="Forecaster",
            model=settings.FORECASTER_MODEL,
            api_client=groq_client
        )
    
    def should_reason(self) -> bool:
        return True
        
    def should_react(self) -> bool:
        return True
        
    def get_react_tools(self) -> List[str]:
        return ["sql_query", "detect_outliers"]

    async def _run_react_loop(self, request: AgentRequest) -> AgentResponse:
        """Phase 5: Autonomous ReAct EDA + Procedural Core IP"""
        logger.info(f"Starting autonomous ReAct pre-processing for Forecaster.")
        
        # 1. Run the base ReAct loop for EDA
        eda_request = AgentRequest(
            query=f"Analyze the dataset for anomalies using detect_outliers and sql_query. Provide a summary of data shape and anomalies before Prophet runs. Original query: {request.query}",
            context=request.context,
            session_id=request.session_id,
            user_id=request.user_id,
            workflow_id=request.workflow_id
        )
        eda_result = await super()._run_react_loop(eda_request)
        
        # 2. Run the procedural Prophet math
        response = await self.process(request)
        
        # 3. Inject EDA findings
        if eda_result.success and response.success and response.data:
            if "interpretation" in response.data:
                 response.data["interpretation"] = f"**Pre-processing EDA Findings:**\n{json.dumps(eda_result.data)}\n\n**Prophet Forecast:**\n" + response.data["interpretation"]
                 
        return response
    
    def evaluate_output(self, output: Dict, request: AgentRequest) -> tuple[float, list]:
        """Check forecast data quality and confidence scores."""
        from app.core.evaluation import agent_evaluator
        result = agent_evaluator.evaluate("forecaster", output, success=True)
        return result.score, result.issues
    
    def compute_confidence(self, output: Dict, eval_score: float) -> ConfidenceScore:
        """Compute confidence from MAPE and data coverage."""
        metadata = output.get("metadata", {})
        mape = metadata.get("mape", 50.0)
        model_confidence = metadata.get("confidence_score", eval_score)
        
        factors = {
            "evaluation_score": eval_score,
            "model_confidence": model_confidence,
            "mape_penalty": max(0, 1.0 - (mape / 100))
        }
        
        # Weighted average
        score = (eval_score * 0.3 + model_confidence * 0.4 + factors["mape_penalty"] * 0.3)
        score = max(0.0, min(1.0, score))
        
        return ConfidenceScore(
            score=round(score, 2),
            justification=f"MAPE: {mape:.1f}%, model confidence: {model_confidence:.2f}",
            factors=factors
        )
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        """Main process - updated to pass session_id"""
        try:
            # Validate input
            if "dataset" not in request.context:
                return AgentResponse(
                    agent_name=self.name,
                    success=False,
                    error="No dataset provided in context"
                )
            
            df = pd.DataFrame(request.context["dataset"])
            forecast_periods = request.parameters.get("periods", 30)
            
            logger.info(f"Starting forecast for {forecast_periods} periods")
            
            # Detect date and value columns
            date_col, value_cols = self._detect_columns(df)
            
            if not date_col or not value_cols:
                return AgentResponse(
                    agent_name=self.name,
                    success=False,
                    error="Could not detect date or numeric columns for forecasting"
                )
            
            # Prepare data for Prophet
            df[date_col] = pd.to_datetime(df[date_col])
            
            # Generate forecasts for each numeric column
            forecasts_data = {}
            
            # Extract locale from context or query
            locale = "US"
            query_lower = request.query.lower()
            if "india" in query_lower or " in " in query_lower:
                if "india" in query_lower: locale = "IN"
                elif "uk" in query_lower: locale = "UK"
                elif "australia" in query_lower: locale = "AU"
            
            for col in value_cols[:3]:  # Limit to 3 columns for performance
                logger.info(f"Forecasting column: {col}")
                forecast_result = await self._forecast_column(
                    df, date_col, col, forecast_periods,
                    session_id=request.session_id,
                    locale=locale
                )
                forecasts_data[col] = forecast_result
            
            # Get upstream TrendAnalyst findings for enriched interpretation
            trend_findings = await self.get_upstream_findings(
                request.workflow_id, "TrendAnalyst"
            )
            
            # Get LLM interpretation (enriched with trend context)
            interpretation = await self._get_interpretation(
                forecasts_data, request.query, trend_findings
            )
            
            # Format response for frontend
            response_data = {
                "forecast_periods": forecast_periods,
                "forecasts": forecasts_data,
                "interpretation": interpretation,
                "metadata": {
                    "date_column": date_col,
                    "forecasted_columns": value_cols[:3],
                    "model": "Facebook Prophet",
                    "includes_holidays": True,
                    "generated_at": datetime.utcnow().isoformat(),
                    "enriched_with_trends": bool(trend_findings)
                }
            }
            
            # Publish curated findings for downstream agents
            forecast_findings = {
                "predictions_summary": {},
                "confidence_scores": {},
                "overall_trend": "stable"
            }
            for col, data in forecasts_data.items():
                preds = data.get("predictions", [])
                if preds:
                    forecast_findings["predictions_summary"][col] = {
                        "start_value": round(preds[0]["value"], 2),
                        "end_value": round(preds[-1]["value"], 2),
                        "trend": data.get("metrics", {}).get("trend", "unknown")
                    }
                forecast_findings["confidence_scores"][col] = round(
                    data.get("confidence_score", 0), 2
                )
            # Determine overall trend
            trends = [v.get("trend", "stable") for v in forecast_findings["predictions_summary"].values()]
            if trends:
                forecast_findings["overall_trend"] = max(set(trends), key=trends.count)
            
            await self.publish_findings(request.workflow_id, forecast_findings)
            
            logger.info("Forecast completed successfully")
            
            return AgentResponse(
                agent_name=self.name,
                success=True,
                data=response_data
            )
            
        except Exception as e:
            logger.error(f"Forecaster error: {str(e)}")
            return AgentResponse(
                agent_name=self.name,
                success=False,
                error=str(e)
            )
    
    def _detect_columns(self, df: pd.DataFrame) -> tuple:
        """Detect date and numeric columns"""
        date_col = None
        value_cols = []
        
        # Find date column
        for col in df.columns:
            if df[col].dtype == 'object':
                try:
                    pd.to_datetime(df[col])
                    date_col = col
                    break
                except:
                    continue
            elif 'date' in col.lower() or 'time' in col.lower():
                date_col = col
                break
        
        # Find numeric columns (exclude date and IDs)
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        value_cols = [
            col for col in numeric_cols 
            if col != date_col and 'id' not in col.lower() and 'price' not in col.lower()
        ]
        
        # Fallback if filtered too aggressively
        if not value_cols:
             value_cols = [col for col in numeric_cols if col != date_col]

        return date_col, value_cols
    
    async def _forecast_column(
        self, 
        df: pd.DataFrame, 
        date_col: str, 
        value_col: str, 
        periods: int,
        session_id: str = None,
        locale: str = "US"
    ) -> Dict:
        """Generate Prophet forecast for a single column with streaming progress"""
        
        # Notify start of forecasting
        if session_id:
            await streaming_service.publish_agent_progress(
                session_id,
                self.name,
                10,
                f"Preparing data for {value_col}",
                {"column": value_col}
            )
        
        # --- FIX: Aggregate duplicates (Sum values per day) ---
        # This handles the case where you have multiple products per date
        grouped_df = df.groupby(date_col)[value_col].sum().reset_index()
        
        # Prepare Prophet dataframe
        prophet_df = pd.DataFrame({
            'ds': grouped_df[date_col],
            'y': grouped_df[value_col]
        })
        
        # Remove any NaN values
        prophet_df = prophet_df.dropna()
        
        # Notify model training
        if session_id:
            await streaming_service.publish_agent_progress(
                session_id,
                self.name,
                30,
                f"Training Prophet model for {value_col}",
                {"rows": len(prophet_df)}
            )
        
        # Detect seasonality dynamically via FFT
        seasonalities = self._detect_prophet_seasonality(prophet_df, 'y')
        
        # Decide growth model
        # If variance is low and data seems bounded, use logistic
        cv = prophet_df['y'].std() / prophet_df['y'].mean() if prophet_df['y'].mean() > 0 else 1.0
        
        # Fit model
        import asyncio
        loop = asyncio.get_event_loop()
        
        def _train_prophet():
            growth = 'linear'
            if cv < 0.3 and len(prophet_df) > 30:
                growth = 'logistic'
                prophet_df['cap'] = prophet_df['y'].max() * 1.5
                prophet_df['floor'] = max(0, prophet_df['y'].min() * 0.5)
                
            model = Prophet(
                growth=growth,
                yearly_seasonality=seasonalities.get("yearly_seasonality", False),
                weekly_seasonality=seasonalities.get("weekly_seasonality", False),
                daily_seasonality=False,
                holidays=self._create_holiday_df(prophet_df['ds'].min(), prophet_df['ds'].max(), locale),
                interval_width=0.95
            )
            model.fit(prophet_df)
            return model, growth
            
        model, growth_type = await loop.run_in_executor(None, _train_prophet)
        
        # Notify prediction
        if session_id:
            await streaming_service.publish_agent_progress(
                session_id,
                self.name,
                70,
                f"Generating {periods}-day forecast",
                {"periods": periods}
            )
        
        # Create future dataframe
        future = model.make_future_dataframe(periods=periods)
        if growth_type == 'logistic':
            future['cap'] = prophet_df['y'].max() * 1.5
            future['floor'] = max(0, prophet_df['y'].min() * 0.5)
        
        # Generate forecast
        forecast = await loop.run_in_executor(None, model.predict, future)
        
        # Extract forecast data (only future periods)
        future_forecast = forecast.tail(periods)
        
        # Format predictions for frontend
        predictions = []
        for _, row in future_forecast.iterrows():
            predictions.append({
                "date": row['ds'].strftime('%Y-%m-%d'),
                "value": float(row['yhat']),
                "lower": float(row['yhat_lower']),
                "upper": float(row['yhat_upper'])
            })
        
        # Extract seasonality components
        seasonality = {
            "weekly": self._extract_weekly_pattern(model, forecast),
            "yearly": self._extract_yearly_pattern(model, forecast)
        }
        
        # Calculate metrics
        # Use the AGGREGATED actuals vs predicted
        historical_actual = prophet_df['y'].values
        historical_predicted = forecast.head(len(prophet_df))['yhat'].values
        
        # Avoid division by zero
        with np.errstate(divide='ignore', invalid='ignore'):
            mape = np.mean(np.abs((historical_actual - historical_predicted) / historical_actual)) * 100
            if np.isnan(mape) or np.isinf(mape):
                mape = 0.0
                
        # Notify completion
        if session_id:
            await streaming_service.publish_agent_progress(
                session_id,
                self.name,
                90,
                f"Forecast complete for {value_col}",
                {"confidence": float(1 - (mape / 100))}
            )
        
        return {
            "predictions": predictions,
            "seasonality": seasonality,
            "confidence_score": float(1 - (mape / 100)) if mape < 100 else 0.0,
            "metrics": {
                "mape": float(mape),
                "trend": "increasing" if predictions[-1]["value"] > predictions[0]["value"] else "decreasing",
                "volatility": float(np.std([p["value"] for p in predictions]))
            }
        }
    
    def _detect_prophet_seasonality(self, df: pd.DataFrame, value_col: str) -> Dict[str, bool]:
        """Use FFT to autonomously detect if time-series has weekly or yearly cyclicality"""
        seasonalities = {"weekly_seasonality": False, "yearly_seasonality": False}
        series = df[value_col].values
        if len(series) < 14:
            return seasonalities
            
        # Detrend
        x = np.arange(len(series))
        slope, intercept, _, _, _ = stats.linregress(x, series)
        detrended = series - (slope * x + intercept)
        
        # Compute FFT
        fft_values = np.fft.fft(detrended)
        frequencies = np.fft.fftfreq(len(series))
        
        pos_mask = frequencies > 0
        freqs = frequencies[pos_mask]
        magnitudes = np.abs(fft_values)[pos_mask]
        
        if len(freqs) == 0:
            return seasonalities
            
        top_indices = np.argsort(magnitudes)[-3:]
        top_freqs = freqs[top_indices]
        
        # Convert frequencies to periods (assuming daily data index)
        top_periods = 1 / top_freqs
        
        for period in top_periods:
            if 6.0 <= period <= 8.0:
                seasonalities["weekly_seasonality"] = True
            elif 350.0 <= period <= 380.0:
                seasonalities["yearly_seasonality"] = True
                
        logger.info(f"Autonomously detected seasonalities: {seasonalities}")
        return seasonalities

    def _create_holiday_df(self, start_date, end_date, context_locale: str = "US") -> pd.DataFrame:
        """Create locale-aware holiday dataframe"""
        try:
            import holidays
            try:
                country_holidays = holidays.country_holidays(context_locale, years=range(start_date.year, end_date.year + 2))
            except NotImplementedError:
                # Fallback to US if context locale is not supported
                country_holidays = holidays.country_holidays("US", years=range(start_date.year, end_date.year + 2))
                
            holiday_list = []
            for date, name in country_holidays.items():
                if start_date <= pd.Timestamp(date) <= end_date + pd.Timedelta(days=365):
                    holiday_list.append({
                        'ds': pd.Timestamp(date),
                        'holiday': name
                    })
            return pd.DataFrame(holiday_list) if holiday_list else pd.DataFrame(columns=['ds', 'holiday'])
        except ImportError:
            return pd.DataFrame(columns=['ds', 'holiday'])
    
    def _extract_weekly_pattern(self, model, forecast) -> Dict:
        """Extract weekly seasonality pattern"""
        if 'weekly' in forecast.columns:
            weekly = forecast['weekly'].values
            return {
                "pattern": "weekly",
                "peak_day": int(np.argmax(weekly[:7])),
                "low_day": int(np.argmin(weekly[:7])),
                "average_effect": float(np.mean(np.abs(weekly)))
            }
        return {}
    
    def _extract_yearly_pattern(self, model, forecast) -> Dict:
        """Extract yearly seasonality pattern"""
        if 'yearly' in forecast.columns:
            yearly = forecast['yearly'].values
            return {
                "pattern": "yearly",
                "peak_month": int(np.argmax(yearly[:12]) + 1),
                "low_month": int(np.argmin(yearly[:12]) + 1),
                "average_effect": float(np.mean(np.abs(yearly)))
            }
        return {}
    
    async def _get_interpretation(self, forecasts_data: Dict, query: str, trend_findings: Dict = None) -> str:
        """Get LLM interpretation of forecast results, enriched with upstream trend data"""
        
        # Prepare summary for LLM
        summary = {
            "forecasted_metrics": {},
            "trends": {},
            "confidence": {}
        }
        
        for col, data in forecasts_data.items():
            first_pred = data["predictions"][0]["value"]
            last_pred = data["predictions"][-1]["value"]
            # Avoid division by zero
            if first_pred != 0:
                change = ((last_pred - first_pred) / first_pred) * 100
            else:
                change = 0.0
            
            summary["forecasted_metrics"][col] = {
                "start_value": round(first_pred, 2),
                "end_value": round(last_pred, 2),
                "change_percentage": round(change, 2)
            }
            summary["trends"][col] = data["metrics"]["trend"]
            summary["confidence"][col] = round(data["confidence_score"], 2)
        
        # Inject upstream trend context if available
        trend_context = ""
        if trend_findings:
            trend_context = f"""

Upstream Trend Analysis (from TrendAnalyst agent):
- Trend Directions: {json.dumps(trend_findings.get('trend_directions', {}))}
- Volatility: {json.dumps(trend_findings.get('volatility', {}))}
- Market Sentiment: {trend_findings.get('market_sentiment', 'unknown')}

Use this trend context to validate or explain your forecast predictions."""
        
        prompt = f"""Analyze these forecast results and provide business insights:

Forecast Data:
{json.dumps(summary, indent=2)}
{trend_context}

User Query: {query}

Provide a clear, actionable interpretation covering:
1. Key trends and what's driving them
2. Confidence in predictions
3. Business recommendations
4. Potential risks or opportunities

Keep it concise and business-focused."""
        
        try:
            response = await self.api_client.generate_content(
                model_name=self.model,
                prompt=prompt,
                temperature=0.6,
                max_tokens=500
            )
            
            return response.get("text", "Forecast generated successfully")
        except Exception as e:
            logger.warning(f"LLM interpretation failed: {e}")
            return "Forecast completed. See detailed predictions above."