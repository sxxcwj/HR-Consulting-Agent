"""Optional structural run over the frozen acceptance set."""

import json
import os
from pathlib import Path

import pytest

from src.agent import AgentError, HRConsultant, validate_analysis


CASE_PATH = Path(__file__).resolve().parents[1] / "evals" / "acceptance_cases.json"
CASES = json.loads(CASE_PATH.read_text(encoding="utf-8"))


@pytest.mark.live
@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_live_case_structure(case: dict[str, object]) -> None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY is not configured in this environment")

    agent = HRConsultant()
    for turn in case["turns"]:
        try:
            answer = agent.ask(str(turn))
            validate_analysis(answer)
        except AgentError as exc:
            failure = str(exc)
        else:
            continue

        pytest.fail(failure, pytrace=False)
