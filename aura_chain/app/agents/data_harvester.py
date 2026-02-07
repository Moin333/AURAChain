from app.agents.base_agent import BaseAgent, AgentRequest, AgentResponse
from app.core.api_clients import groq_client
from app.core.streaming import streaming_service
from app.config import get_settings
import pandas as pd
import numpy as np
import json
from typing import Dict, List, Tuple
from loguru import logger

settings = get_settings()


class DataHarvesterAgent(BaseAgent):
    """
    Ingests and preprocesses data with actual cleaning:
    - Missing value imputation
    - Outlier handling
    - Date parsing
    - Data validation
    """
    
    def __init__(self):
        super().__init__(
            name="DataHarvester",
            model=settings.DATA_HARVESTER_MODEL,
            api_client=groq_client
        )
    
    def get_system_prompt(self) -> str:
        return """You are a data quality expert. Analyze datasets and provide:
1. Data quality assessment (score 0-100)
2. Issues found and fixes applied
3. Recommendations for further improvements
4. Data schema validation

Return results in JSON format."""
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        try:
            if "dataset" not in request.context:
                return AgentResponse(
                    agent_name=self.name,
                    success=False,
                    error="No dataset provided in context"
                )
            
            # Notify start
            if request.session_id:
                await streaming_service.publish_agent_progress(
                    request.session_id,
                    self.name,
                    10,
                    "Loading dataset...",
                    {}
                )
                
            # Load data
            df_original = pd.DataFrame(request.context["dataset"])
            logger.info(f"Processing dataset: {df_original.shape}")
            
            # Store original stats
            original_stats = self._get_dataset_stats(df_original)
            
            # Notify cleaning start
            if request.session_id:
                await streaming_service.publish_agent_progress(
                    request.session_id,
                    self.name,
                    30,
                    f"Cleaning {len(df_original)} rows...",
                    {"rows": len(df_original)}
                )
            
            # Clean the data
            df_cleaned, cleaning_log = self._clean_dataset(df_original)
            
             # Notify analysis
            if request.session_id:
                await streaming_service.publish_agent_progress(
                    request.session_id,
                    self.name,
                    70,
                    "Analyzing data quality...",
                    {"operations": len(cleaning_log)}
                )
            
            # Get cleaned stats
            cleaned_stats = self._get_dataset_stats(df_cleaned)
            
            # Generate profile
            profile = {
                "original": original_stats,
                "cleaned": cleaned_stats,
                "cleaning_operations": cleaning_log,
                "improvement_score": self._calculate_improvement(original_stats, cleaned_stats)
            }
            
            # Use LLM for quality assessment
            analysis = await self._get_quality_analysis(profile, request.query)
            
            # Notify completion
            if request.session_id:
                await streaming_service.publish_agent_progress(
                    request.session_id,
                    self.name,
                    90,
                    "Data cleaning complete",
                    {"quality_score": profile["improvement_score"]}
                )
            
            return AgentResponse(
                agent_name=self.name,
                success=True,
                data={
                    "profile": profile,
                    "analysis": analysis,
                    "processed_data": df_cleaned.to_dict('records'),
                    "metadata": {
                        "rows_processed": len(df_cleaned),
                        "columns_processed": len(df_cleaned.columns),
                        "quality_score": profile["improvement_score"]
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Data Harvester error: {str(e)}")
            return AgentResponse(
                agent_name=self.name,
                success=False,
                error=str(e)
            )
    
    def _clean_dataset(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Apply comprehensive data cleaning"""
        df_clean = df.copy()
        cleaning_log = []
        
        # 1. Parse dates
        df_clean, date_log = self._parse_dates(df_clean)
        cleaning_log.extend(date_log)
        
        # 2. Handle missing values
        df_clean, missing_log = self._handle_missing_values(df_clean)
        cleaning_log.extend(missing_log)
        
        # 3. Handle outliers
        df_clean, outlier_log = self._handle_outliers(df_clean)
        cleaning_log.extend(outlier_log)
        
        # 4. Validate data
        df_clean, validation_log = self._validate_data(df_clean)
        cleaning_log.extend(validation_log)
        
        # 5. Sort by date if present
        date_cols = df_clean.select_dtypes(include=['datetime64']).columns
        if len(date_cols) > 0:
            df_clean = df_clean.sort_values(date_cols[0])
            cleaning_log.append(f"Sorted by {date_cols[0]}")
        
        logger.info(f"Cleaning complete: {len(cleaning_log)} operations")
        return df_clean, cleaning_log
    
    def _parse_dates(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Auto-detect and parse date columns"""
        log = []
        
        for col in df.columns:
            if df[col].dtype == 'object':
                try:
                    # Try parsing as date
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    if df[col].notna().sum() > len(df) * 0.5:  # >50% successfully parsed
                        log.append(f"Parsed '{col}' as datetime")
                    else:
                        # Revert if parsing failed for most values
                        df[col] = df[col].astype(str)
                except Exception as e:
                    pass
        
        return df, log
    
    def _handle_missing_values(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Impute missing values using appropriate strategies"""
        log = []
        
        for col in df.columns:
            missing_count = df[col].isna().sum()
            
            if missing_count == 0:
                continue
            
            missing_pct = (missing_count / len(df)) * 100
            
            # If too many missing (>50%), flag but don't impute
            if missing_pct > 50:
                log.append(f"WARNING: '{col}' has {missing_pct:.1f}% missing values - consider dropping")
                continue
            
            # Numeric columns
            if df[col].dtype in ['int64', 'float64']:
                # Check if time-series (has date column)
                date_cols = df.select_dtypes(include=['datetime64']).columns
                
                if len(date_cols) > 0:
                    # Use interpolation for time-series
                    df[col] = df[col].interpolate(method='linear', limit_direction='both')
                    log.append(f"Interpolated {missing_count} missing values in '{col}'")
                else:
                    # Use mean for non-temporal data
                    df[col] = df[col].fillna(df[col].mean())
                    log.append(f"Filled {missing_count} missing values in '{col}' with mean")
            
            # Categorical columns
            elif df[col].dtype == 'object':
                mode_value = df[col].mode()
                if len(mode_value) > 0:
                    df[col] = df[col].fillna(mode_value[0])
                    log.append(f"Filled {missing_count} missing values in '{col}' with mode")
        
        return df, log
    
    def _handle_outliers(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Cap outliers using IQR method (don't drop)"""
        log = []
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            outliers = ((df[col] < lower_bound) | (df[col] > upper_bound)).sum()
            
            if outliers > 0:
                # Cap values instead of dropping
                df[col] = df[col].clip(lower=lower_bound, upper=upper_bound)
                log.append(f"Capped {outliers} outliers in '{col}' to IQR bounds")
        
        return df, log
    
    def _validate_data(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Validate and fix data quality issues"""
        log = []
        
        # Check for negative values in quantity/price columns
        value_cols = ['price', 'quantity', 'amount', 'sales', 'revenue', 'cost']
        
        for col in df.columns:
            if any(v in col.lower() for v in value_cols):
                if df[col].dtype in ['int64', 'float64']:
                    negative_count = (df[col] < 0).sum()
                    if negative_count > 0:
                        df[col] = df[col].abs()
                        log.append(f"Fixed {negative_count} negative values in '{col}'")
        
        # Remove duplicate rows
        duplicates = df.duplicated().sum()
        if duplicates > 0:
            df = df.drop_duplicates()
            log.append(f"Removed {duplicates} duplicate rows")
        
        return df, log
    
    def _get_dataset_stats(self, df: pd.DataFrame) -> Dict:
        """Get comprehensive dataset statistics"""
        
        # 🔥 FIX 1: Convert datetime columns to strings in sample
        df_sample = df.head(3).copy()
        for col in df_sample.select_dtypes(include=['datetime64']).columns:
            df_sample[col] = df_sample[col].astype(str)
        
        # 🔥 FIX 2: Only describe NUMERIC columns (exclude datetime)
        numeric_df = df.select_dtypes(include=['number'])
        numeric_summary = {}
        if len(numeric_df.columns) > 0:
            # Convert describe() result to safe dict
            desc_dict = numeric_df.describe().to_dict()
            # Ensure all values are JSON-safe
            numeric_summary = {
                col: {
                    stat: float(val) if not pd.isna(val) else None
                    for stat, val in stats.items()
                }
                for col, stats in desc_dict.items()
            }
        
        return {
            "shape": {
                "rows": int(df.shape[0]),
                "columns": int(df.shape[1])
            },
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "missing_values": {col: int(count) for col, count in df.isnull().sum().items()},
            "missing_percentage": {
                col: float((count / len(df)) * 100) 
                for col, count in df.isnull().sum().items()
            },
            "numeric_summary": numeric_summary,  # ← Now safe!
            "sample_data": df_sample.to_dict('records')
        }
    
    def _calculate_improvement(self, original: Dict, cleaned: Dict) -> float:
        """Calculate quality improvement score (0-100)"""
        # Calculate reduction in missing values
        original_missing = sum(original["missing_values"].values())
        cleaned_missing = sum(cleaned["missing_values"].values())
        
        if original_missing == 0:
            missing_improvement = 100
        else:
            missing_improvement = ((original_missing - cleaned_missing) / original_missing) * 100
        
        # Base score: 50 if no missing values, 30 if some remain
        base_score = 50 if cleaned_missing == 0 else 30
        
        # Add improvement points
        total_score = min(100, base_score + (missing_improvement * 0.5))
        
        return round(total_score, 1)
    
    async def _get_quality_analysis(self, profile: Dict, query: str) -> Dict:
        """Get LLM analysis of data quality"""
        
        prompt = f"""Analyze this data quality report:

Original Dataset:
- Rows: {profile['original']['shape']['rows']}
- Missing values: {sum(profile['original']['missing_values'].values())}

Cleaned Dataset:
- Rows: {profile['cleaned']['shape']['rows']}
- Missing values: {sum(profile['cleaned']['missing_values'].values())}

Cleaning Operations:
{json.dumps(profile['cleaning_operations'], indent=2)}

Quality Score: {profile['improvement_score']}/100

User Query: {query}

Provide analysis in JSON format:
{{
    "data_quality_score": 0-100,
    "issues_found": ["list of issues"],
    "fixes_applied": ["list of fixes"],
    "recommendations": ["future improvements"],
    "insights": ["business insights from data"],
    "ready_for_analysis": true/false
}}"""
        
        try:
            response = await self.api_client.generate_content(
                model_name=self.model,
                prompt=prompt,
                temperature=0.5,
                max_tokens=1000
            )
            
            content = response.get("text", "{}")
            
            # Extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            return json.loads(content)
            
        except Exception as e:
            logger.warning(f"LLM analysis failed: {e}")
            return {
                "data_quality_score": profile['improvement_score'],
                "issues_found": [f"Found {sum(profile['original']['missing_values'].values())} missing values"],
                "fixes_applied": profile['cleaning_operations'],
                "recommendations": ["Data is ready for analysis"],
                "ready_for_analysis": True
            }