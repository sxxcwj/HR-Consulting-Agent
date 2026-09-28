"""Agent orchestration tests for the V0.3 Excel Reader tool."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.agent import EXCEL_ANALYSIS_UNSUPPORTED_MESSAGE, REGISTERED_TOOLS, HRConsultant

from .conftest import FakeClient


SAMPLE_PATH = Path(__file__).resolve().parents[1] / "data" / "sample_employees.xlsx"


def _excel_function_call() -> SimpleNamespace:
    return SimpleNamespace(
        output_text="",
        output=[
            {
                "type": "function_call",
                "name": "read_excel_metadata",
                "call_id": "call_excel_1",
                "arguments": json.dumps(
                    {
                        "file_path": str(SAMPLE_PATH),
                        "sheet_name": None,
                        "preview_rows": 5,
                    }
                ),
            }
        ],
    )


def test_excel_metadata_request_executes_reader_tool() -> None:
    final = 'EXCEL_METADATA:{"success": true, "file_name": "sample_employees.xlsx"}'
    fake = FakeClient([_excel_function_call(), final])
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    answer = agent.ask(f"请读取 {SAMPLE_PATH}，这个Excel有哪些字段？")

    assert json.loads(answer)["file_name"] == "sample_employees.xlsx"
    assert agent.last_tool_calls == ["read_excel_metadata"]
    assert fake.responses.calls[0]["tools"] == REGISTERED_TOOLS
    tool_result = json.loads(fake.responses.calls[1]["input"][-1]["output"])
    assert tool_result["success"] is True
    assert tool_result["row_count"] == 20
    assert tool_result["column_count"] == 8
    assert tool_result["columns"][0] == "employee_id"


def test_complex_excel_analysis_request_is_refused_without_tool_call() -> None:
    fake = FakeClient([])
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    answer = agent.ask(f"请读取 {SAMPLE_PATH}，哪些员工工资异常？")

    assert answer == EXCEL_ANALYSIS_UNSUPPORTED_MESSAGE
    assert agent.last_tool_calls == []
    assert len(fake.responses.calls) == 0


def test_model_analysis_boundary_marker_is_also_supported() -> None:
    fake = FakeClient(
        [f"EXCEL_ANALYSIS_UNSUPPORTED:{EXCEL_ANALYSIS_UNSUPPORTED_MESSAGE}"]
    )
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    answer = agent.ask("请根据表格做一项当前边界未列出的数据推断")

    assert answer == EXCEL_ANALYSIS_UNSUPPORTED_MESSAGE
    assert agent.last_tool_calls == []


@pytest.mark.parametrize(
    "question",
    [
        "哪些员工工资异常？",
        "哪个部门离职率最高？",
        "绩效和工资有没有关系？",
        "请做复杂异常值识别。",
    ],
)
def test_required_analysis_examples_are_refused_before_api(question: str) -> None:
    fake = FakeClient([])
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    assert agent.ask(question) == EXCEL_ANALYSIS_UNSUPPORTED_MESSAGE
    assert fake.responses.calls == []


def test_excel_tool_error_is_returned_to_model(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.xlsx"
    first = SimpleNamespace(
        output_text="",
        output=[
            {
                "type": "function_call",
                "name": "read_excel_metadata",
                "call_id": "call_excel_missing",
                "arguments": json.dumps(
                    {
                        "file_path": str(missing_path),
                        "sheet_name": None,
                        "preview_rows": 5,
                    }
                ),
            }
        ],
    )
    fake = FakeClient([first, "EXCEL_METADATA:文件不存在。"])
    agent = HRConsultant(client=fake)  # type: ignore[arg-type]

    answer = agent.ask(f"请读取 {missing_path}，有哪些字段？")

    tool_result = json.loads(fake.responses.calls[1]["input"][-1]["output"])
    assert tool_result["success"] is False
    assert tool_result["error"]["code"] == "file_not_found"
    assert answer == "文件不存在。"
