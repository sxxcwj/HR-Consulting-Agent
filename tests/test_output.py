"""Five-part output contract checks."""

import pytest

from src.agent import ResponseFormatError, validate_analysis


def test_valid_analysis_and_one_line_privacy_notice(valid_analysis: str) -> None:
    validate_analysis(valid_analysis)
    validate_analysis("请在后续交流中匿名化员工信息。\n" + valid_analysis)


@pytest.mark.parametrize(
    "invalid",
    [
        "",
        "# 问题判断\n只有这一段",
        "# 摘要\n说明\n" + "# 问题判断\n内容",
    ],
)
def test_incomplete_heading_structure_is_rejected(invalid: str) -> None:
    with pytest.raises(ResponseFormatError):
        validate_analysis(invalid)


def test_empty_section_is_rejected(valid_analysis: str) -> None:
    bad = valid_analysis.replace(
        "请提供目标和实际结果，以便区分原因。", ""
    )
    with pytest.raises(ResponseFormatError, match="空白部分"):
        validate_analysis(bad)
