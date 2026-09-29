"""Run the anonymous V1.0 pilot against the real configured model.

All persistent runtime data is isolated in a temporary directory. The script
records model answers and tool names, but never records API credentials.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = PROJECT_ROOT / "evals" / "pilot_cases.json"
DEFAULT_RESULTS = PROJECT_ROOT / "evals" / "pilot_results.json"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _load_cases(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not value:
        raise ValueError("pilot cases must be a non-empty JSON array")
    return value


def _evaluate_case(
    case: dict[str, Any],
    *,
    answer: str,
    tool_calls: list[str],
    stream_text: str,
    error: str | None,
) -> dict[str, bool]:
    from src.agent import ResponseFormatError, validate_analysis
    from src.security import detect_sensitive_labels

    expected = set(case.get("expected_tools", []))
    forbidden = set(case.get("forbidden_tools", []))
    actual = set(tool_calls)
    required_groups = case.get("required_any", [])
    required_patterns = case.get("required_patterns", [])
    checks = {
        "completed_without_error": error is None,
        "expected_tools_called": expected.issubset(actual),
        "forbidden_tools_not_called": actual.isdisjoint(forbidden),
        "required_text_present": all(
            any(str(term) in answer for term in group) for group in required_groups
        ),
        "required_patterns_present": all(
            re.search(str(pattern), answer, flags=re.IGNORECASE | re.DOTALL) is not None
            for pattern in required_patterns
        ),
        "forbidden_text_absent": all(
            str(term) not in answer for term in case.get("forbidden_text", [])
        ),
        "stream_matches_final": stream_text == answer,
        "no_sensitive_data_detected": not detect_sensitive_labels(
            {"question": case.get("question", ""), "answer": answer}
        ),
    }
    if case.get("response_contract") == "five_sections" and error is None:
        try:
            validate_analysis(answer)
        except ResponseFormatError:
            checks["five_sections_valid"] = False
        else:
            checks["five_sections_valid"] = True
    return checks


def _prepare_knowledge_base() -> dict[str, Any]:
    from src.knowledge import KnowledgeRegistry, RAGService

    registry = KnowledgeRegistry()
    registrations: list[dict[str, Any]] = []
    for path in sorted((PROJECT_ROOT / "knowledge" / "documents").glob("*.md")):
        result = registry.register_file(str(path))
        registrations.append(
            {
                "file_name": path.name,
                "success": bool(result.get("success")),
                "status": result.get("status"),
                "error": result.get("error"),
            }
        )
    index_result = RAGService(registry=registry).build_index()
    return {
        "registrations": registrations,
        "index": index_result,
    }


def run_pilot(cases_path: Path, results_path: Path) -> dict[str, Any]:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    if not os.getenv("DEEPSEEK_API_KEY", "").strip():
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

    cases = _load_cases(cases_path)
    started_at = _now()
    os.chdir(PROJECT_ROOT)
    with tempfile.TemporaryDirectory(prefix="hragent-pilot-") as runtime_dir:
        os.environ["HR_AGENT_HOME"] = runtime_dir

        # Import only after selecting the isolated application root.
        from src.agent import HRConsultant
        knowledge_categories = {"企业文件读取", "RAG检索"}
        preparation = (
            _prepare_knowledge_base()
            if any(case.get("category") in knowledge_categories for case in cases)
            else {"skipped": True, "reason": "selected cases do not require knowledge tools"}
        )
        results: list[dict[str, Any]] = []
        for case in cases:
            agent = HRConsultant()
            chunks: list[str] = []
            error: str | None = None
            started = time.perf_counter()
            try:
                answer = agent.ask_streamed(
                    str(case["question"]),
                    on_text_delta=chunks.append,
                )
            except Exception as exc:  # noqa: BLE001 - pilot must record failures
                answer = ""
                error = f"{type(exc).__name__}: {exc}"
            duration_seconds = round(time.perf_counter() - started, 3)
            stream_text = "".join(chunks)
            final_response_text = getattr(agent.last_response, "output_text", None)
            checks = _evaluate_case(
                case,
                answer=answer,
                tool_calls=agent.last_tool_calls,
                stream_text=stream_text,
                error=error,
            )
            results.append(
                {
                    "id": case["id"],
                    "category": case["category"],
                    "question": case["question"],
                    "answer": answer,
                    "tool_calls": agent.last_tool_calls,
                    "duration_seconds": duration_seconds,
                    "answer_characters": len(answer),
                    "error": error,
                    "partial_stream_text": stream_text if error else None,
                    "final_response_text": final_response_text if error else None,
                    "checks": checks,
                    "passed": all(checks.values()),
                }
            )
            print(
                f"{case['id']}: {'PASS' if all(checks.values()) else 'FAIL'} "
                f"({duration_seconds:.3f}s, tools={agent.last_tool_calls})",
                flush=True,
            )

        passed = sum(bool(item["passed"]) for item in results)
        durations = [float(item["duration_seconds"]) for item in results]
        expected_tool_cases = [case for case in cases if case.get("expected_tools")]
        expected_tool_hits = sum(
            set(case.get("expected_tools", [])).issubset(
                set(next(item for item in results if item["id"] == case["id"])["tool_calls"])
            )
            for case in expected_tool_cases
        )
        forbidden_call_count = sum(
            len(
                set(item["tool_calls"])
                & set(next(case for case in cases if case["id"] == item["id"])["forbidden_tools"])
            )
            for item in results
        )
        summary = {
            "pilot_type": "anonymous_synthetic_internal_pilot",
            "started_at": started_at,
            "completed_at": _now(),
            "model": os.getenv("DEEPSEEK_MODEL", "deepseek-flash"),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "runtime_isolated": True,
            "runtime_retained": False,
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "pass_rate": round(passed / len(results), 4),
            "expected_tool_case_count": len(expected_tool_cases),
            "expected_tool_hit_count": expected_tool_hits,
            "expected_tool_hit_rate": round(
                expected_tool_hits / len(expected_tool_cases), 4
            )
            if expected_tool_cases
            else 1.0,
            "forbidden_tool_call_count": forbidden_call_count,
            "average_duration_seconds": round(sum(durations) / len(durations), 3),
            "max_duration_seconds": max(durations),
            "knowledge_preparation": preparation,
            "cases": results,
        }
        results_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the anonymous HR Agent pilot")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    args = parser.parse_args()
    try:
        summary = run_pilot(args.cases.resolve(), args.results.resolve())
    except Exception as exc:  # noqa: BLE001 - CLI entry reports a concise failure
        print(f"Pilot failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                key: summary[key]
                for key in (
                    "total",
                    "passed",
                    "failed",
                    "pass_rate",
                    "expected_tool_hit_rate",
                    "forbidden_tool_call_count",
                    "average_duration_seconds",
                    "max_duration_seconds",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
