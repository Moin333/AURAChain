# app/core/evaluation.py
"""
Rule-based Agent Evaluator — post-execution quality checks.

Performs deterministic validation of agent outputs. No LLM calls.
Each agent type has specific quality checks beyond the generic ones.

Used by the reasoning loop to decide whether to retry.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from loguru import logger


class EvaluationResult(BaseModel):
    """Result of evaluating an agent's output."""
    passed: bool
    score: float                    # 0.0-1.0
    issues: List[str]               # What failed
    suggestions: List[str]          # How to improve on retry


class AgentEvaluator:
    """Rule-based quality checker for agent outputs."""
    
    def evaluate(
        self,
        agent_name: str,
        output: Dict[str, Any],
        success: bool
    ) -> EvaluationResult:
        """
        Evaluate an agent's output for quality.
        
        Runs generic checks first, then agent-specific checks.
        Returns score 0.0-1.0 and list of issues.
        """
        issues = []
        suggestions = []
        score = 1.0
        
        # ── Generic checks ──
        if not success:
            issues.append("Agent reported failure")
            score -= 0.5
        
        if not output:
            issues.append("Output is empty")
            return EvaluationResult(
                passed=False, score=0.0,
                issues=issues, suggestions=["Agent produced no output"]
            )
        
        if "error" in output and output["error"]:
            issues.append(f"Output contains error: {output['error']}")
            score -= 0.3
        
        # ── Agent-specific checks ──
        specific_check = self._agent_checks.get(agent_name)
        if specific_check:
            specific_issues, specific_suggestions, score_penalty = specific_check(output)
            issues.extend(specific_issues)
            suggestions.extend(specific_suggestions)
            score -= score_penalty
        
        # Clamp score
        score = max(0.0, min(1.0, score))
        passed = score >= 0.5 and len(issues) == 0
        
        return EvaluationResult(
            passed=passed,
            score=score,
            issues=issues,
            suggestions=suggestions
        )
    
    @property
    def _agent_checks(self):
        """Registry of agent-specific check functions."""
        return {
            "forecaster": self._check_forecaster,
            "mcts_optimizer": self._check_mcts_optimizer,
            "trend_analyst": self._check_trend_analyst,
            "data_harvester": self._check_data_harvester,
            "visualizer": self._check_visualizer,
        }
    
    def _check_forecaster(self, output: Dict) -> tuple[List[str], List[str], float]:
        """Forecaster must have forecast results with confidence."""
        issues, suggestions = [], []
        penalty = 0.0
        
        if "forecasts" not in output and "forecast_results" not in output:
            issues.append("No forecast results in output")
            suggestions.append("Ensure Prophet model produces forecast data")
            penalty += 0.4
        
        metadata = output.get("metadata", {})
        if metadata:
            mape = metadata.get("mape")
            if mape is not None and mape > 50:
                issues.append(f"MAPE too high: {mape:.1f}%")
                suggestions.append("Consider different forecast parameters or more data")
                penalty += 0.2
            
            confidence = metadata.get("confidence_score", 1.0)
            if confidence < 0.3:
                issues.append(f"Very low confidence: {confidence:.2f}")
                suggestions.append("Data may be insufficient for reliable forecasting")
                penalty += 0.1
        
        return issues, suggestions, penalty
    
    def _check_mcts_optimizer(self, output: Dict) -> tuple[List[str], List[str], float]:
        """MCTSOptimizer must have optimal_action and non-negative savings."""
        issues, suggestions = [], []
        penalty = 0.0
        
        if "optimal_action" not in output:
            issues.append("No optimal_action in output")
            suggestions.append("MCTS simulation may need more iterations")
            penalty += 0.4
        else:
            action = output["optimal_action"]
            if not isinstance(action, dict):
                issues.append("optimal_action is not a dictionary")
                penalty += 0.3
        
        savings = output.get("expected_savings", {})
        if isinstance(savings, dict):
            pct = savings.get("percentage", 0)
            if pct < 0:
                issues.append(f"Negative savings: {pct}%")
                suggestions.append("Review optimization constraints")
                penalty += 0.2
        
        return issues, suggestions, penalty
    
    def _check_trend_analyst(self, output: Dict) -> tuple[List[str], List[str], float]:
        """TrendAnalyst must have insights and analyzed data points."""
        issues, suggestions = [], []
        penalty = 0.0
        
        if "insights" not in output:
            issues.append("No insights in output")
            suggestions.append("Ensure trend analysis produces LLM insights")
            penalty += 0.3
        elif isinstance(output["insights"], str) and len(output["insights"]) < 20:
            issues.append("Insights too short")
            suggestions.append("Request more detailed trend interpretation")
            penalty += 0.1
        
        metadata = output.get("metadata", {})
        if metadata:
            points = metadata.get("data_points_analyzed", 0)
            if points == 0:
                issues.append("No data points analyzed")
                suggestions.append("Verify dataset has analyzable columns")
                penalty += 0.3
        
        return issues, suggestions, penalty
    
    def _check_data_harvester(self, output: Dict) -> tuple[List[str], List[str], float]:
        """DataHarvester must have processed data."""
        issues, suggestions = [], []
        penalty = 0.0
        
        metadata = output.get("metadata", {})
        if metadata:
            quality = metadata.get("quality_score", 1.0)
            if quality < 0.3:
                issues.append(f"Very low data quality: {quality:.2f}")
                suggestions.append("Dataset may need manual cleaning")
                penalty += 0.2
        
        return issues, suggestions, penalty
    
    def _check_visualizer(self, output: Dict) -> tuple[List[str], List[str], float]:
        """Visualizer must have chart specification."""
        issues, suggestions = [], []
        penalty = 0.0
        
        if "chart_spec" not in output and "chart_html" not in output:
            issues.append("No chart output")
            suggestions.append("Verify LLM produced valid Plotly specification")
            penalty += 0.3
        
        return issues, suggestions, penalty
    
    # ── Phase 7: Quantitative Metrics ──
    
    def compute_metrics(self, agent_name: str, output: Dict[str, Any]) -> List["MetricResult"]:
        """
        Compute quantitative quality metrics for an agent's output.
        
        Returns structured MetricResult objects that feed into
        ConfidenceScore, Report Engine, and ExperimentLogger.
        """
        metric_fn = self._metric_functions.get(agent_name)
        if metric_fn:
            return metric_fn(output)
        return []
    
    @property
    def _metric_functions(self):
        return {
            "data_harvester": self._metrics_data_harvester,
            "trend_analyst": self._metrics_trend_analyst,
            "forecaster": self._metrics_forecaster,
            "mcts_optimizer": self._metrics_mcts_optimizer,
            "visualizer": self._metrics_visualizer,
        }
    
    def _metrics_data_harvester(self, output: Dict) -> List["MetricResult"]:
        metadata = output.get("metadata", {})
        quality = metadata.get("quality_score", 0)
        completeness = metadata.get("completeness", 0)
        rows = metadata.get("rows_processed", 0)
        
        results = []
        if completeness or quality:
            score = completeness if completeness else quality
            interp = "good" if score > 0.8 else ("fair" if score > 0.5 else "poor")
            results.append(MetricResult(
                metric_name="data_completeness",
                value=round(score * 100, 1),
                unit="percentage",
                interpretation=interp
            ))
        if rows:
            results.append(MetricResult(
                metric_name="rows_processed",
                value=float(rows),
                unit="count",
                interpretation="good" if rows > 50 else "fair"
            ))
        return results
    
    def _metrics_trend_analyst(self, output: Dict) -> List["MetricResult"]:
        metadata = output.get("metadata", {})
        results = []
        
        p_value = metadata.get("trend_p_value")
        if p_value is not None:
            interp = "good" if p_value < 0.05 else ("fair" if p_value < 0.1 else "poor")
            results.append(MetricResult(
                metric_name="trend_significance",
                value=round(p_value, 4),
                unit="p_value",
                interpretation=interp
            ))
        
        points = metadata.get("data_points_analyzed", 0)
        if points:
            results.append(MetricResult(
                metric_name="data_points_analyzed",
                value=float(points),
                unit="count",
                interpretation="good" if points > 30 else "fair"
            ))
        
        return results
    
    def _metrics_forecaster(self, output: Dict) -> List["MetricResult"]:
        metadata = output.get("metadata", {})
        results = []
        
        mape = metadata.get("mape")
        if mape is not None:
            interp = "good" if mape < 15 else ("fair" if mape < 30 else "poor")
            results.append(MetricResult(
                metric_name="forecast_accuracy_mape",
                value=round(mape, 2),
                unit="percentage",
                interpretation=interp
            ))
        
        confidence = metadata.get("confidence_score")
        if confidence is not None:
            results.append(MetricResult(
                metric_name="model_confidence",
                value=round(confidence, 3),
                unit="ratio",
                interpretation="good" if confidence > 0.7 else "fair"
            ))
        
        return results
    
    def _metrics_mcts_optimizer(self, output: Dict) -> List["MetricResult"]:
        results = []
        
        savings = output.get("expected_savings", {})
        if isinstance(savings, dict):
            pct = savings.get("percentage", 0)
            interp = "good" if pct > 10 else ("fair" if pct > 0 else "poor")
            results.append(MetricResult(
                metric_name="cost_improvement",
                value=round(pct, 2),
                unit="percentage",
                interpretation=interp
            ))
        
        if "optimal_action" in output:
            results.append(MetricResult(
                metric_name="solution_found",
                value=1.0,
                unit="boolean",
                interpretation="good"
            ))
        
        return results
    
    def _metrics_visualizer(self, output: Dict) -> List["MetricResult"]:
        results = []
        has_chart = "chart_spec" in output or "chart_html" in output
        results.append(MetricResult(
            metric_name="chart_validity",
            value=1.0 if has_chart else 0.0,
            unit="boolean",
            interpretation="good" if has_chart else "poor"
        ))
        return results


class MetricResult(BaseModel):
    """Quantitative quality metric for an agent's output."""
    metric_name: str
    value: float
    unit: str           # "percentage", "p_value", "ratio", "count", "boolean"
    interpretation: str # "good", "fair", "poor"


# Global instance
agent_evaluator = AgentEvaluator()

