from typing import Dict, Any, List
import pandas as pd
import numpy as np
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from loguru import logger

class AnalysisTools:
    """Statistical and ML analysis tools"""
    
    @staticmethod
    def auto_eda(df: pd.DataFrame) -> Dict[str, Any]:
        """Automatically profile the dataset for schema, nulls, skewness, and cardinality."""
        try:
            profile = {
                "rows": len(df),
                "columns": len(df.columns),
                "schema": {},
                "insights": []
            }
            
            for col in df.columns:
                series = df[col]
                dtype = str(series.dtype)
                null_pct = series.isnull().mean() * 100
                cardinality = series.nunique()
                
                col_profile = {
                    "dtype": dtype,
                    "null_percentage": round(float(null_pct), 2),
                    "unique_values": int(cardinality)
                }
                
                if pd.api.types.is_numeric_dtype(series) and not series.empty:
                    try:
                        col_profile["skewness"] = round(float(series.skew()), 2)
                    except Exception:
                        col_profile["skewness"] = 0.0
                
                profile["schema"][col] = col_profile
                
                if null_pct > 20:
                    profile["insights"].append(f"Column '{col}' has high missing values ({null_pct:.1f}%).")
                if dtype == "object" and 0 < cardinality < min(len(df) * 0.05, 50):
                    profile["insights"].append(f"Column '{col}' might be categorical (unique values: {cardinality}).")
                    
            return profile
        except Exception as e:
            logger.error(f"AutoEDA error: {str(e)}")
            return {"error": str(e)}
    
    @staticmethod
    async def detect_outliers(
        df: pd.DataFrame,
        column: str,
        method: str = "iqr"
    ) -> Dict[str, Any]:
        """
        Detect outliers in data
        
        Methods: 'iqr', 'zscore'
        """
        try:
            series = df[column].dropna()
            
            if method == "iqr":
                Q1 = series.quantile(0.25)
                Q3 = series.quantile(0.75)
                IQR = Q3 - Q1
                lower = Q1 - 1.5 * IQR
                upper = Q3 + 1.5 * IQR
                outliers = df[(df[column] < lower) | (df[column] > upper)]
            
            elif method == "zscore":
                z_scores = np.abs(stats.zscore(series))
                outliers = df[z_scores > 3]
            
            return {
                "outlier_count": len(outliers),
                "outlier_percentage": (len(outliers) / len(df)) * 100,
                "outlier_indices": outliers.index.tolist()
            }
            
        except Exception as e:
            logger.error(f"Outlier detection error: {str(e)}")
            raise
    
    @staticmethod
    async def correlation_analysis(
        df: pd.DataFrame,
        columns: List[str] = None
    ) -> Dict[str, Any]:
        """Calculate correlations between numeric columns"""
        try:
            if columns:
                df_numeric = df[columns]
            else:
                df_numeric = df.select_dtypes(include=[np.number])
            
            correlation_matrix = df_numeric.corr()
            
            # Find strong correlations
            strong_correlations = []
            for i in range(len(correlation_matrix.columns)):
                for j in range(i+1, len(correlation_matrix.columns)):
                    corr_value = correlation_matrix.iloc[i, j]
                    if abs(corr_value) > 0.7:
                        strong_correlations.append({
                            "column1": correlation_matrix.columns[i],
                            "column2": correlation_matrix.columns[j],
                            "correlation": float(corr_value)
                        })
            
            return {
                "correlation_matrix": correlation_matrix.to_dict(),
                "strong_correlations": strong_correlations
            }
            
        except Exception as e:
            logger.error(f"Correlation analysis error: {str(e)}")
            raise
    
    @staticmethod
    async def segment_customers(
        df: pd.DataFrame,
        features: List[str],
        n_clusters: int = 3
    ) -> Dict[str, Any]:
        """
        Customer segmentation using K-means clustering
        
        Tool for agents to identify customer groups
        """
        try:
            # Prepare data
            X = df[features].dropna()
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            # Cluster
            import asyncio
            kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            loop = asyncio.get_event_loop()
            clusters = await loop.run_in_executor(None, kmeans.fit_predict, X_scaled)
            
            df_copy = df.loc[X.index].copy()
            df_copy['cluster'] = clusters
            
            # Cluster profiles
            profiles = []
            for i in range(n_clusters):
                cluster_data = df_copy[df_copy['cluster'] == i]
                profile = {
                    "cluster_id": i,
                    "size": len(cluster_data),
                    "percentage": (len(cluster_data) / len(df_copy)) * 100,
                    "characteristics": {}
                }
                
                for feature in features:
                    profile["characteristics"][feature] = {
                        "mean": float(cluster_data[feature].mean()),
                        "median": float(cluster_data[feature].median())
                    }
                
                profiles.append(profile)
            
            return {
                "n_clusters": n_clusters,
                "cluster_assignments": clusters.tolist(),
                "profiles": profiles
            }
            
        except Exception as e:
            logger.error(f"Segmentation error: {str(e)}")
            raise

    @staticmethod
    async def demand_velocity(
        df: pd.DataFrame,
        date_column: str,
        value_column: str,
        freq: str = 'W'
    ) -> Dict[str, Any]:
        """
        Calculate rolling sales velocity or demand pacing across temporal axes.
        freq options: 'D' (daily), 'W' (weekly), 'M' (monthly).
        
        Tool definition for LLM:
        {
            "name": "demand_velocity",
            "description": "Calculate rolling sales velocity or demand pacing",
            "parameters": {
                "date_column": "order_date",
                "value_column": "sales_amount",
                "freq": "W"
            }
        }
        """
        try:
            if date_column not in df.columns or value_column not in df.columns:
                return {"error": "Columns not found"}
                
            # Ensure dates are datetime
            df_temp = df.copy()
            df_temp[date_column] = pd.to_datetime(df_temp[date_column], errors='coerce')
            df_temp = df_temp.dropna(subset=[date_column])
            
            # Aggregate to frequency
            agg_df = df_temp.groupby(pd.Grouper(key=date_column, freq=freq))[value_column].sum().reset_index()
            agg_df = agg_df.sort_values(by=date_column)
            
            # Calculate rolling metrics (e.g., 4-period moving average of velocity)
            agg_df['rolling_avg'] = agg_df[value_column].rolling(window=4, min_periods=1).mean()
            agg_df['velocity_change'] = agg_df[value_column].pct_change() * 100
            
            # Handle NaNs created by pct_change
            agg_df = agg_df.fillna(0)
            
            # Convert timestamp to string for serialization
            agg_df[date_column] = agg_df[date_column].astype(str)
            
            return {
                "frequency": freq,
                "data": agg_df.to_dict(orient='records'),
                "current_velocity": float(agg_df['rolling_avg'].iloc[-1]) if not agg_df.empty else 0.0,
                "latest_change_pct": float(agg_df['velocity_change'].iloc[-1]) if not agg_df.empty else 0.0
            }
            
        except Exception as e:
            logger.error(f"Demand velocity error: {str(e)}")
            raise

    @staticmethod
    async def fetch_global_trends(
        keywords: List[str]
    ) -> Dict[str, Any]:
        """
        Fetch external market trends from Google Trends.
        Protected by CircuitBreaker to avoid long bans from 429 Too Many Requests.
        """
        from app.core.api_clients import circuit_breaker
        from app.core.error_handling import CircuitBreakerOpen
        import time
        import asyncio
        from pytrends.request import TrendReq
        from pytrends.exceptions import TooManyRequestsError
        
        if not keywords:
            return {}
            
        provider = "google"
        model = "pytrends"
        
        # 1. Check if circuit is open
        try:
            circuit_breaker.check(provider, model)
        except CircuitBreakerOpen as e:
            logger.warning(f"Skipping pytrends: {e}")
            return {"error": "circuit_breaker_open", "message": str(e)}
            
        try:
            start_time = time.time()
            
            # Since pytrends is synchronous and network-bound, we wrap it in an executor
            loop = asyncio.get_event_loop()
            
            def _fetch_all():
                ptr = TrendReq(hl='en-US', tz=360)
                trends_data = {}
                for keyword in keywords[:3]:
                    logger.info(f"Fetching Google Trends for: {keyword}")
                    ptr.build_payload([str(keyword)], cat=0, timeframe='today 3-m', geo='IN')
                    interest_df = ptr.interest_over_time()
                    
                    if not interest_df.empty and str(keyword) in interest_df.columns:
                        series = interest_df[str(keyword)]
                        current = series.iloc[-1]
                        previous = series.iloc[0]
                        change_pct = ((current - previous) / previous * 100) if previous != 0 else 0
                        
                        top_queries = []
                        try:
                            related = ptr.related_queries()
                            if str(keyword) in related and 'top' in related[str(keyword)]:
                                top_df = related[str(keyword)]['top']
                                if top_df is not None and not top_df.empty:
                                    top_queries = top_df['query'].head(5).tolist()
                        except:
                            pass
                            
                        trends_data[str(keyword)] = {
                            "current_interest": int(current),
                            "trend": "increasing" if change_pct > 5 else "decreasing" if change_pct < -5 else "stable",
                            "change_percentage": float(change_pct),
                            "average_interest": float(series.mean()),
                            "peak_interest": int(series.max()),
                            "related_queries": top_queries
                        }
                    time.sleep(2) # rate limit sleep inside executor
                return trends_data
                
            trends_data = await loop.run_in_executor(None, _fetch_all)
            
            # 2. Record success
            latency_ms = (time.time() - start_time) * 1000
            circuit_breaker.record_success(provider, model, latency_ms)
            
            return trends_data
            
        except TooManyRequestsError as e:
            logger.error(f"pytrends rate limited (429): {e}")
            circuit_breaker.record_failure(provider, model)
            return {"error": "rate_limited", "message": "Google Trends rate limit exceeded"}
        except Exception as e:
            logger.error(f"pytrends error: {e}")
            # Do NOT trip circuit on typical network timeouts/parsing errors unless desired.
            # We'll record failure for general exceptions to be safe.
            circuit_breaker.record_failure(provider, model)
            return {"error": "unknown_error", "message": str(e)}
