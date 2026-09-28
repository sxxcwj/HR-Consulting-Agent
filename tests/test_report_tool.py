"""Tests for the V0.9 report tool and strict schema."""

from __future__ import annotations

import pytest

from src.reports import REPORT_TOOLS, ReportGenerator
from src.reports import tools as report_tools

from .test_report_generator import _draft


@pytest.fixture
def isolated_generator(tmp_path, monkeypatch: pytest.MonkeyPatch) -> ReportGenerator:
    generator = ReportGenerator(tmp_path / "generated")
    monkeypatch.setattr(report_tools, "_DEFAULT_GENERATOR", generator)
    return generator


def test_only_generate_report_tool_is_registered() -> None:
    assert [tool["name"] for tool in REPORT_TOOLS] == ["generate_hr_report"]
    assert REPORT_TOOLS[0]["strict"] is True


def test_tool_schema_is_strict_and_complete() -> None:
    schema = REPORT_TOOLS[0]["parameters"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    source = schema["properties"]["source_references"]["items"]
    assert source["additionalProperties"] is False
    assert set(source["required"]) == set(source["properties"])


def test_public_tool_generates_report(isolated_generator) -> None:
    result = report_tools.generate_hr_report(**_draft())
    assert result["success"] is True
    assert result["format"] == "markdown"


def test_tool_description_preserves_architecture_boundary() -> None:
    description = REPORT_TOOLS[0]["description"]
    assert "明确要求" in description
    assert "只校验、排版并保存" in description
    assert "不会读取 Excel、知识库、State 或 Memory" in description
