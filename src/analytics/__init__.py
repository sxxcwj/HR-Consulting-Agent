"""Deterministic V0.4 descriptive HR analytics."""

from .compensation import (
    ANALYZE_COMPENSATION_SUMMARY_TOOL,
    analyze_compensation_summary,
)
from .missing import ANALYZE_MISSING_DATA_TOOL, analyze_missing_data
from .performance import (
    ANALYZE_PERFORMANCE_SUMMARY_TOOL,
    analyze_performance_summary,
)
from .turnover import CALCULATE_TURNOVER_ANALYSIS_TOOL, calculate_turnover_analysis
from .workforce import CALCULATE_HEADCOUNT_TOOL, calculate_headcount

ANALYSIS_TOOLS = [
    CALCULATE_HEADCOUNT_TOOL,
    ANALYZE_COMPENSATION_SUMMARY_TOOL,
    CALCULATE_TURNOVER_ANALYSIS_TOOL,
    ANALYZE_PERFORMANCE_SUMMARY_TOOL,
    ANALYZE_MISSING_DATA_TOOL,
]

ANALYSIS_FUNCTIONS = {
    "calculate_headcount": calculate_headcount,
    "analyze_compensation_summary": analyze_compensation_summary,
    "calculate_turnover_analysis": calculate_turnover_analysis,
    "analyze_performance_summary": analyze_performance_summary,
    "analyze_missing_data": analyze_missing_data,
}

__all__ = [
    "ANALYSIS_FUNCTIONS",
    "ANALYSIS_TOOLS",
    "analyze_compensation_summary",
    "analyze_missing_data",
    "analyze_performance_summary",
    "calculate_headcount",
    "calculate_turnover_analysis",
]
