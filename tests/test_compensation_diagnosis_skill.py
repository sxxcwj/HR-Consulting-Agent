"""Contract tests for the project-local compensation diagnosis skill."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".codex" / "skills" / "compensation-diagnosis"
SKILL_PATH = SKILL_ROOT / "SKILL.md"
EVALS_PATH = SKILL_ROOT / "evals" / "evals.json"
EXPECTED_DESCRIPTION = (
    "Diagnose enterprise compensation issues including internal equity, external "
    "competitiveness, salary compression or inversion, pay structure, position-level "
    "differences, and compensation adjustment needs. Use when the user asks whether "
    "pay is fair or competitive, why employees are dissatisfied with pay, whether "
    "salary inversion exists, or how to investigate compensation problems."
)


def _skill_parts() -> tuple[dict[str, str], str]:
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, front_matter, body = text.split("---", maxsplit=2)
    metadata: dict[str, str] = {}
    for line in front_matter.strip().splitlines():
        key, value = line.split(":", maxsplit=1)
        metadata[key.strip()] = value.strip()
    return metadata, body


def test_skill_front_matter_and_location() -> None:
    assert SKILL_PATH.is_file()
    metadata, _ = _skill_parts()

    assert metadata == {
        "name": "compensation-diagnosis",
        "description": EXPECTED_DESCRIPTION,
    }


def test_skill_has_required_diagnostic_and_decision_boundaries() -> None:
    _, body = _skill_parts()

    for phrase in (
        "## 何时使用（When to use）",
        "## 不应使用（Do not use）",
        "Internal Equity",
        "External Competitiveness",
        "Pay Compression",
        "Salary Inversion",
        "DATA_FACT",
        "2—4 个假设",
        "目前无法判断外部竞争力",
        "存在差异不等于不公平",
        "不得直接决定谁应涨薪",
    ):
        assert phrase in body


def test_skill_preserves_agent_output_and_tool_separation() -> None:
    _, body = _skill_parts()

    headings = [
        "`# 问题判断`",
        "`# 可能原因`",
        "`# 需要补充的信息`",
        "`# 建议措施`",
        "`# 下一步行动`",
    ]
    assert [body.index(heading) for heading in headings] == sorted(
        body.index(heading) for heading in headings
    )
    assert "Skill**：选择诊断问题" in body
    assert "Tool**：读取允许使用的数据或执行确定性计算" in body
    assert "`analyze_compensation_summary` 不能识别薪酬倒挂" in body
    assert "不代表它们目前存在" in body


def test_skill_eval_set_covers_requested_trigger_boundaries() -> None:
    payload = json.loads(EVALS_PATH.read_text(encoding="utf-8"))

    assert payload["skill_name"] == "compensation-diagnosis"
    assert [case["id"] for case in payload["evals"]] == [1, 2, 3, 4, 5, 6]
    assert len({case["prompt"] for case in payload["evals"]}) == 6
    assert all(case["expectations"] for case in payload["evals"])
    assert "品牌战略" in payload["evals"][-1]["prompt"]
    assert "不触发" in payload["evals"][-1]["expected_output"]
