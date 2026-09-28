"""Validated Markdown report generation for HR Consultant V0.9."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.knowledge.knowledge_reader import redact_sensitive_text


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_ROOT = PROJECT_ROOT / "reports" / "generated"
SOURCE_TYPES = (
    "user_input",
    "project_state",
    "memory",
    "document",
    "rag",
    "excel_analysis",
    "tool_result",
)
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(
        r"(?:api[ _-]?key|access[ _-]?token|password|密码|密钥|令牌)"
        r"\s*[:=：]\s*[^\s,，;；]{6,}",
        re.IGNORECASE,
    ),
)


class ReportValidationError(ValueError):
    """The structured report draft violates the V0.9 contract."""


class ReportWriteError(RuntimeError):
    """The report could not be safely written."""


def _error(code: str, message: str, **details: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": False,
        "error": {"code": code, "message": message},
    }
    result.update(details)
    return result


def _text(value: Any, field_name: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise ReportValidationError(f"{field_name} 必须是字符串。")
    normalized = " ".join(value.split())
    if not normalized:
        raise ReportValidationError(f"{field_name} 不能为空。")
    if len(normalized) > maximum:
        raise ReportValidationError(f"{field_name} 不能超过 {maximum} 个字符。")
    return normalized


def _items(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ReportValidationError(f"{field_name} 必须是非空字符串列表。")
    if len(value) > 50:
        raise ReportValidationError(f"{field_name} 最多包含 50 项。")
    return [_text(item, field_name, maximum=2000) for item in value]


def _sources(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise ReportValidationError("source_references 必须是非空来源列表。")
    if len(value) > 50:
        raise ReportValidationError("source_references 最多包含 50 项。")
    result: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ReportValidationError("每项 source_reference 必须是对象。")
        unknown = sorted(set(item) - {"source_type", "source_id", "description"})
        if unknown:
            raise ReportValidationError(
                f"source_reference 包含不支持的字段：{', '.join(unknown)}。"
            )
        try:
            source_type = item["source_type"]
            source_id = _text(item["source_id"], "source_id", maximum=500)
            description = _text(item["description"], "description", maximum=1000)
        except KeyError as exc:
            raise ReportValidationError(
                f"source_reference 缺少字段：{exc.args[0]}。"
            ) from exc
        if source_type not in SOURCE_TYPES:
            raise ReportValidationError(
                f"source_type 必须是：{', '.join(SOURCE_TYPES)}。"
            )
        result.append(
            {
                "source_type": source_type,
                "source_id": source_id,
                "description": description,
            }
        )
    return result


def _sensitive_labels(value: Any) -> list[str]:
    labels: list[str] = []
    if isinstance(value, str):
        _, detected = redact_sensitive_text(value)
        labels.extend(detected)
        if any(pattern.search(value) for pattern in SECRET_PATTERNS):
            labels.append("密钥或凭据")
    elif isinstance(value, list):
        for item in value:
            labels.extend(_sensitive_labels(item))
    elif isinstance(value, dict):
        for item in value.values():
            labels.extend(_sensitive_labels(item))
    return sorted(set(labels))


def _slug(title: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", title, flags=re.UNICODE)
    slug = slug.strip("-_")[:60]
    return slug or "hr-report"


def _table_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|")


class ReportGenerator:
    """Validate and save report drafts without reading any upstream source."""

    def __init__(self, root: str | Path = DEFAULT_REPORT_ROOT) -> None:
        self.root = Path(root).expanduser()

    def generate(
        self,
        *,
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
        try:
            normalized = {
                "title": _text(title, "title", maximum=200),
                "executive_summary": _text(
                    executive_summary, "executive_summary", maximum=4000
                ),
                "problem_assessment": _items(
                    problem_assessment, "problem_assessment"
                ),
                "evidence": _items(evidence, "evidence"),
                "possible_causes": _items(possible_causes, "possible_causes"),
                "missing_information": _items(
                    missing_information, "missing_information"
                ),
                "recommendations": _items(recommendations, "recommendations"),
                "next_actions": _items(next_actions, "next_actions"),
                "assumptions_and_limitations": _items(
                    assumptions_and_limitations, "assumptions_and_limitations"
                ),
                "source_references": _sources(source_references),
            }
        except ReportValidationError as exc:
            return _error("invalid_report", str(exc))

        sensitive = _sensitive_labels(normalized)
        if sensitive:
            return _error(
                "sensitive_report_content",
                "报告不保存密钥或员工级敏感信息，请先删除或匿名化。",
                detected_sensitive_types=sensitive,
            )

        created_at = datetime.now(timezone.utc).isoformat()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        report_id = f"RPT-{stamp}-{uuid4().hex[:8].upper()}"
        file_name = f"{report_id}_{_slug(normalized['title'])}.md"
        file_path = self.root / file_name
        temporary = file_path.with_suffix(".md.tmp")

        sections: list[tuple[str, list[str]]] = [
            ("问题判断", normalized["problem_assessment"]),
            ("已知事实与依据", normalized["evidence"]),
            ("可能原因", normalized["possible_causes"]),
            ("需要补充的信息", normalized["missing_information"]),
            ("建议措施", normalized["recommendations"]),
            ("下一步行动", normalized["next_actions"]),
            ("假设与限制", normalized["assumptions_and_limitations"]),
        ]
        lines = [
            f"# {normalized['title']}",
            "",
            "> 自动生成草稿：本报告仅基于所列来源，不代表正式管理决定或法律意见。",
            "",
            f"- 报告编号：`{report_id}`",
            f"- 生成时间：`{created_at}`",
            "- 文件格式：Markdown",
            "- 状态：草稿",
            "",
            "## 执行摘要",
            "",
            normalized["executive_summary"],
            "",
        ]
        for heading, items in sections:
            lines.extend([f"## {heading}", ""])
            lines.extend(f"- {item}" for item in items)
            lines.append("")
        lines.extend(
            [
                "## 来源索引",
                "",
                "| 来源类型 | 来源标识 | 说明 |",
                "| --- | --- | --- |",
            ]
        )
        for source in normalized["source_references"]:
            lines.append(
                "| "
                + " | ".join(
                    _table_text(source[key])
                    for key in ("source_type", "source_id", "description")
                )
                + " |"
            )
        content = "\n".join(lines).rstrip() + "\n"

        try:
            self.root.mkdir(parents=True, exist_ok=True)
            if file_path.exists():
                raise ReportWriteError("目标报告文件已存在，已停止以避免覆盖。")
            temporary.write_text(content, encoding="utf-8")
            temporary.replace(file_path)
        except (OSError, ReportWriteError) as exc:
            return _error("report_write_error", f"报告写入失败：{exc}")

        return {
            "success": True,
            "status": "generated",
            "report_id": report_id,
            "file_name": file_name,
            "file_path": str(file_path.resolve()),
            "format": "markdown",
            "created_at": created_at,
            "section_count": 9,
            "source_count": len(normalized["source_references"]),
            "draft": True,
        }
