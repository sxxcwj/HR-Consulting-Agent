"""Deterministic checks for recorded cross-version evaluation results.

This module never calls a model or a project-mutating tool. Evaluators first run
cases manually or in an isolated harness, then provide the captured answer and
actual tool-call names for deterministic contract checks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def evaluate_case(
    case: dict[str, Any], *, answer: str, tool_calls: list[str]
) -> dict[str, Any]:
    """Evaluate tool selection and literal answer requirements for one case."""
    actual_tools = set(tool_calls)
    expected_tools = set(case.get("expected_tools", []))
    forbidden_tools = set(case.get("forbidden_tools", []))
    checks = {
        "expected_tools_called": expected_tools.issubset(actual_tools),
        "forbidden_tools_not_called": actual_tools.isdisjoint(forbidden_tools),
        "required_text_present": all(
            text in answer for text in case.get("required_text", [])
        ),
        "forbidden_text_absent": all(
            text not in answer for text in case.get("forbidden_text", [])
        ),
    }
    return {"id": case["id"], "passed": all(checks.values()), "checks": checks}


def evaluate_results(
    cases: list[dict[str, Any]], results: list[dict[str, Any]]
) -> dict[str, Any]:
    """Match captured results by case id and return a deterministic summary."""
    result_by_id = {result["id"]: result for result in results}
    evaluations: list[dict[str, Any]] = []
    for case in cases:
        recorded = result_by_id.get(case["id"])
        if recorded is None:
            evaluations.append(
                {
                    "id": case["id"],
                    "passed": False,
                    "checks": {"result_recorded": False},
                }
            )
            continue
        evaluations.append(
            evaluate_case(
                case,
                answer=str(recorded.get("answer", "")),
                tool_calls=list(recorded.get("tool_calls", [])),
            )
        )
    passed = sum(item["passed"] for item in evaluations)
    return {
        "total": len(evaluations),
        "passed": passed,
        "failed": len(evaluations) - passed,
        "cases": evaluations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate recorded V1.0 case results")
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    results = json.loads(args.results.read_text(encoding="utf-8"))
    summary = evaluate_results(cases, results)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
