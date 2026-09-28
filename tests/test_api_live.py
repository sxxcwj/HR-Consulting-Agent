"""Optional real API smoke test."""

import os

import pytest
from openai import OpenAI, OpenAIError

from src.agent import DEFAULT_MODEL, DEEPSEEK_BASE_URL


@pytest.mark.live
def test_live_api_connection() -> None:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        pytest.skip("DEEPSEEK_API_KEY is not configured in this environment")

    client = OpenAI(
        api_key=api_key,
        base_url=DEEPSEEK_BASE_URL,
        timeout=30.0,
        max_retries=2,
    )
    try:
        response = client.responses.create(
            model=os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL),
            input="请只回复：连接成功",
        )
    except OpenAIError as exc:
        failure = f"真实 API 连接失败：{type(exc).__name__}（详情已隐藏）"
    else:
        assert response.output_text.strip()
        return

    pytest.fail(failure, pytrace=False)
