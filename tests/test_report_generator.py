"""Tests for the V0.9 Markdown report generator."""

from __future__ import annotations

from pathlib import Path

from src.reports import ReportGenerator


def _draft(**updates):
    value = {
        "title": "销售人员离职问题初步诊断报告",
        "executive_summary": "销售人员离职增加已被管理层观察到，但原因仍需数据验证。",
        "problem_assessment": ["当前问题属于人才保留与员工关系诊断。"],
        "evidence": ["用户本轮说明最近销售人员离职率明显增加。"],
        "possible_causes": ["薪酬竞争力可能不足，但目前只是待验证假设。"],
        "missing_information": ["缺少分期间、分团队的离职人数与平均人数。"],
        "recommendations": ["先统一离职率口径并核对离职数据，再验证薪酬假设。"],
        "next_actions": ["HR整理近12个月销售离职数据和平均人数。"],
        "assumptions_and_limitations": ["本报告仅基于用户本轮描述，未读取员工明细。"],
        "source_references": [
            {
                "source_type": "user_input",
                "source_id": "current_request",
                "description": "用户本轮提供的销售离职问题描述",
            }
        ],
    }
    value.update(updates)
    return value


def test_generate_complete_markdown_report(tmp_path) -> None:
    result = ReportGenerator(tmp_path / "generated").generate(**_draft())
    path = Path(result["file_path"])
    content = path.read_text(encoding="utf-8")

    assert result["success"] is True
    assert result["report_id"].startswith("RPT-")
    assert result["format"] == "markdown"
    assert result["draft"] is True
    assert result["section_count"] == 9
    assert path.parent == (tmp_path / "generated").resolve()
    assert "自动生成草稿" in content
    for heading in (
        "执行摘要",
        "问题判断",
        "已知事实与依据",
        "可能原因",
        "需要补充的信息",
        "建议措施",
        "下一步行动",
        "假设与限制",
        "来源索引",
    ):
        assert f"## {heading}" in content
    assert "| user_input | current_request |" in content


def test_reports_are_unique_and_never_overwrite(tmp_path) -> None:
    generator = ReportGenerator(tmp_path / "generated")
    first = generator.generate(**_draft())
    second = generator.generate(**_draft())

    assert first["file_path"] != second["file_path"]
    assert Path(first["file_path"]).exists()
    assert Path(second["file_path"]).exists()


def test_title_cannot_escape_controlled_output_directory(tmp_path) -> None:
    root = tmp_path / "generated"
    result = ReportGenerator(root).generate(**_draft(title="../../外部/报告"))
    path = Path(result["file_path"])

    assert result["success"] is True
    assert path.parent == root.resolve()
    assert ".." not in path.name
    assert "/" not in path.name


def test_empty_required_section_is_rejected_without_writing(tmp_path) -> None:
    root = tmp_path / "generated"
    result = ReportGenerator(root).generate(**_draft(evidence=[]))

    assert result["success"] is False
    assert result["error"]["code"] == "invalid_report"
    assert not root.exists()


def test_missing_or_invalid_source_is_rejected(tmp_path) -> None:
    generator = ReportGenerator(tmp_path / "generated")
    missing = generator.generate(**_draft(source_references=[]))
    invalid = generator.generate(
        **_draft(
            source_references=[
                {
                    "source_type": "internet",
                    "source_id": "x",
                    "description": "不支持的来源",
                }
            ]
        )
    )

    assert missing["error"]["code"] == "invalid_report"
    assert invalid["error"]["code"] == "invalid_report"
    assert "source_type" in invalid["error"]["message"]


def test_sensitive_content_and_credentials_are_rejected(tmp_path) -> None:
    generator = ReportGenerator(tmp_path / "generated")
    phone = generator.generate(**_draft(evidence=["员工手机号为13812345678"]))
    secret = generator.generate(**_draft(evidence=["API_KEY=sk-abcdefghijklmnop"]))

    assert phone["error"]["code"] == "sensitive_report_content"
    assert "手机号" in phone["detected_sensitive_types"]
    assert secret["error"]["code"] == "sensitive_report_content"
    assert "密钥或凭据" in secret["detected_sensitive_types"]


def test_source_table_escapes_pipe_characters(tmp_path) -> None:
    result = ReportGenerator(tmp_path / "generated").generate(
        **_draft(
            source_references=[
                {
                    "source_type": "tool_result",
                    "source_id": "tool|1",
                    "description": "离职率|计算结果",
                }
            ]
        )
    )
    content = Path(result["file_path"]).read_text(encoding="utf-8")
    assert "tool\\|1" in content
    assert "离职率\\|计算结果" in content


def test_write_failure_returns_error_without_success(tmp_path) -> None:
    invalid_root = tmp_path / "not-a-directory"
    invalid_root.write_text("occupied", encoding="utf-8")
    result = ReportGenerator(invalid_root).generate(**_draft())

    assert result["success"] is False
    assert result["error"]["code"] == "report_write_error"
