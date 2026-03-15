from typing import Dict, Any, List
import pandas as pd
import numpy as np
import duckdb
from loguru import logger

class DataTools:
    """Collection of data manipulation tools"""
    
    @staticmethod
    async def sql_query(
        df: pd.DataFrame,
        query: str
    ) -> pd.DataFrame:
        """
        Run a SQL query on the dataset using DuckDB.
        The dataframe is accessible as a table named 'df'.
        
        Tool definition for LLM:
        {
            "name": "sql_query",
            "description": "Execute a SQL query against the dataset (table name relates to 'df')",
            "parameters": {
                "query": "SELECT category, SUM(sales) FROM df GROUP BY category"
            }
        }
        """
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            
            def _execute_query():
                # duckdb requires treating the local df variable as a table
                return duckdb.query(query).df()
                
            result_df = await loop.run_in_executor(None, _execute_query)
            logger.info(f"Executed SQL query returning {len(result_df)} rows")
            return result_df
            
        except Exception as e:
            logger.error(f"SQL query error: {str(e)}")
            raise
    
    @staticmethod
    async def filter_data(
        df: pd.DataFrame,
        conditions: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Filter dataset based on conditions
        
        Tool definition for LLM:
        {
            "name": "filter_data",
            "description": "Filter dataset rows based on conditions",
            "parameters": {
                "conditions": {
                    "column_name": {"operator": "gt", "value": 100}
                }
            }
        }
        """
        try:
            filtered_df = df.copy()
            
            for column, condition in conditions.items():
                if column not in df.columns:
                    continue
                
                operator = condition.get("operator", "eq")
                value = condition.get("value")
                
                if operator == "eq":
                    filtered_df = filtered_df[filtered_df[column] == value]
                elif operator == "gt":
                    filtered_df = filtered_df[filtered_df[column] > value]
                elif operator == "lt":
                    filtered_df = filtered_df[filtered_df[column] < value]
                elif operator == "gte":
                    filtered_df = filtered_df[filtered_df[column] >= value]
                elif operator == "lte":
                    filtered_df = filtered_df[filtered_df[column] <= value]
                elif operator == "contains":
                    filtered_df = filtered_df[filtered_df[column].str.contains(value, na=False)]
            
            logger.info(f"Filtered from {len(df)} to {len(filtered_df)} rows")
            return filtered_df
            
        except Exception as e:
            logger.error(f"Filter error: {str(e)}")
            raise
    
    @staticmethod
    async def aggregate_data(
        df: pd.DataFrame,
        group_by: List[str],
        aggregations: Dict[str, str]
    ) -> pd.DataFrame:
        """
        Group and aggregate data
        
        Tool definition:
        {
            "name": "aggregate_data",
            "description": "Group data and perform aggregations",
            "parameters": {
                "group_by": ["category", "region"],
                "aggregations": {
                    "sales": "sum",
                    "quantity": "mean"
                }
            }
        }
        """
        try:
            result = df.groupby(group_by).agg(aggregations).reset_index()
            logger.info(f"Aggregated {len(df)} rows into {len(result)} groups")
            return result
        except Exception as e:
            logger.error(f"Aggregation error: {str(e)}")
            raise
    
    @staticmethod
    async def join_datasets(
        left_df: pd.DataFrame,
        right_df: pd.DataFrame,
        on: str,
        how: str = "inner"
    ) -> pd.DataFrame:
        """Join two datasets"""
        try:
            result = pd.merge(left_df, right_df, on=on, how=how)
            logger.info(f"Joined datasets: {len(result)} rows")
            return result
        except Exception as e:
            logger.error(f"Join error: {str(e)}")
            raise
    
    @staticmethod
    async def calculate_metrics(
        df: pd.DataFrame,
        metrics: List[str]
    ) -> Dict[str, float]:
        """Calculate business metrics"""
        try:
            results = {}
            
            for metric in metrics:
                if metric == "total_revenue":
                    results[metric] = df['revenue'].sum() if 'revenue' in df.columns else 0
                elif metric == "avg_order_value":
                    results[metric] = df['order_value'].mean() if 'order_value' in df.columns else 0
                elif metric == "growth_rate":
                    if 'date' in df.columns and 'revenue' in df.columns:
                        df_sorted = df.sort_values('date')
                        first = df_sorted['revenue'].iloc[0]
                        last = df_sorted['revenue'].iloc[-1]
                        results[metric] = ((last - first) / first) * 100 if first != 0 else 0
            
            return results
        except Exception as e:
            logger.error(f"Metrics calculation error: {str(e)}")
            raise
