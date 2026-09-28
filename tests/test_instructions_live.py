"""Optional real model instruction check."""

import os

import pytest

from src.agent import AgentError, HRConsultant, validate_analysis


@pytest.mark.live
def test_live_hr_response_uses_five_sections() -> None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY is not configured in this environment")

    try:
        response = HRConsultant().ask("团队绩效目标不清晰，我该从哪里开始检查？")
        validate_analysis(response)
    except AgentError as exc:
        failure = str(exc)
    else:
        return

    pytest.fail(failure, pytrace=False)
