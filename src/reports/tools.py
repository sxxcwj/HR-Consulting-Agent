"""Public V0.9 report function and Responses API tool schema."""

from __future__ import annotations

from typing import Any

from .generator import ReportGenerator, SOURCE_TYPES


_DEFAULT_GENERATOR: ReportGenerator | None = None


def _generator() -> ReportGenerator:
    global _DEFAULT_GENERATOR
    if _DEFAULT_GENERATOR is None:
        _DEFAULT_GENERATOR = ReportGenerator()
    return _DEFAULT_GENERATOR


def generate_hr_report(
    title: str,
    executive_summary: str,
    problem_assessment: list[str],
    evidence: list[str],
    possible_causes: list[str],
    missing_information: list[str],
    recommendations: list[str],
    next_actions: list[str],
    assumptions_and_limitations: list[str],
    source_references: list[dict[str, str]],
) -> dict[str, Any]:
    return _generator().generate(
        title=title,
        executive_summary=executive_summary,
        problem_assessment=problem_assessment,
        evidence=evidence,
        possible_causes=possible_causes,
        missing_information=missing_information,
        recommendations=recommendations,
        next_actions=next_actions,
        assumptions_and_limitations=assumptions_and_limitations,
        source_references=source_references,
    )


STRING_LIST = {
    "type": "array",
    "items": {"type": "string"},
    "minItems": 1,
    "maxItems": 50,
}
SOURCE_REFERENCE = {
    "type": "object",
    "properties": {
        "source_type": {"type": "string", "enum": list(SOURCE_TYPES)},
        "source_id": {"type": "string"},
        "description": {"type": "string"},
    },
    "required": ["source_type", "source_id", "description"],
    "additionalProperties": False,
}


GENERATE_HR_REPORT_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "generate_hr_report",
    "description": (
        "仅当用户明确要求把已经取得、可追溯的 HR 分析生成报告时使用。"
        "调用前先用正确的上游工具取得所需事实；此工具只校验、排版并保存 Markdown 草稿，"
        "不会读取 Excel、知识库、State 或 Memory，也不得补写缺失证据。"
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "executive_summary": {"type": "string"},
            "problem_assessment": STRING_LIST,
            "evidence": STRING_LIST,
            "possible_causes": STRING_LIST,
            "missing_information": STRING_LIST,
            "recommendations": STRING_LIST,
            "next_actions": STRING_LIST,
            "assumptions_and_limitations": STRING_LIST,
            "source_references": {
                "type": "array",
                "items": SOURCE_REFERENCE,
                "minItems": 1,
                "maxItems": 50,
            },
        },
        "required": [
            "title",
            "executive_summary",
            "problem_assessment",
            "evidence",
            "possible_causes",
            "missing_information",
            "recommendations",
            "next_actions",
            "assumptions_and_limitations",
            "source_references",
        ],
        "additionalProperties": False,
    },
}

REPORT_TOOLS = [GENERATE_HR_REPORT_TOOL]
