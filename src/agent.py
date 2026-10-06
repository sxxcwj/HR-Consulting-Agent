"""DeepSeek-backed HR Consultant, tool orchestration, and response validation."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)
from openai.types.responses import ResponseTextDeltaEvent

from .analytics import ANALYSIS_FUNCTIONS, ANALYSIS_TOOLS
from .knowledge import (
    KNOWLEDGE_TOOLS,
    RAG_TOOLS,
    build_knowledge_index,
    get_document_metadata,
    get_knowledge_index_status,
    list_documents,
    read_knowledge_document,
    register_document,
    search_knowledge_base,
)
from .memory import (
    MEMORY_TOOLS,
    archive_memory,
    forget_memory,
    get_memory,
    list_memories,
    save_memory,
    search_memories,
    update_memory,
)
from .prompts import AGENT_INSTRUCTIONS, FORMAT_REPAIR_INSTRUCTIONS
from .reports import REPORT_TOOLS, generate_hr_report
from .state import (
    PROJECT_STATE_TOOLS,
    archive_project_state,
    create_project_state,
    get_project_state,
    list_project_states,
    select_project_state,
    update_project_state,
)
from .tools import (
    EXCEL_READER_TOOL,
    TURNOVER_RATE_TOOL,
    TurnoverRateInputError,
    calculate_turnover_rate,
    read_excel_data,
    read_excel_metadata,
)


HEADINGS = (
    "问题判断",
    "可能原因",
    "需要补充的信息",
    "建议措施",
    "下一步行动",
)
HEADING_PATTERN = re.compile(r"^# (.+?)\s*$", re.MULTILINE)
DEFAULT_MODEL = "deepseek-flash"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
OUT_OF_SCOPE_PREFIX = "OUT_OF_SCOPE:"
OUT_OF_SCOPE_MESSAGE = "此请求不属于 HR Consultant V1.0 的企业 HR 管理分析范围。"
EXCEL_METADATA_PREFIX = "EXCEL_METADATA:"
EXCEL_ANALYSIS_UNSUPPORTED_PREFIX = "EXCEL_ANALYSIS_UNSUPPORTED:"
DATA_ANALYSIS_PREFIX = "DATA_ANALYSIS:"
KNOWLEDGE_ANSWER_PREFIX = "KNOWLEDGE_ANSWER:"
RAG_ANSWER_PREFIX = "RAG_ANSWER:"
PROJECT_STATE_PREFIX = "PROJECT_STATE:"
MEMORY_PREFIX = "MEMORY:"
REPORT_PREFIX = "REPORT:"
INTERNAL_OUTPUT_PREFIXES = (
    OUT_OF_SCOPE_PREFIX,
    EXCEL_METADATA_PREFIX,
    EXCEL_ANALYSIS_UNSUPPORTED_PREFIX,
    DATA_ANALYSIS_PREFIX,
    KNOWLEDGE_ANSWER_PREFIX,
    RAG_ANSWER_PREFIX,
    PROJECT_STATE_PREFIX,
    MEMORY_PREFIX,
    REPORT_PREFIX,
)
COMPENSATION_JUDGMENT_MESSAGE = (
    "当前基础统计不能直接判断哪个部门的工资设计最不合理。还需要岗位、职级、"
    "市场薪酬、内部薪酬带宽和岗位价值等数据，并明确比较口径。"
)
PERSONNEL_DECISION_MESSAGE = (
    "不能根据基础统计直接决定谁应该被淘汰、辞退、晋升或调薪。人员决策还需要岗位要求、"
    "持续绩效证据、能力与行为事实、改进支持记录及合规程序，并应由管理者审慎决策。"
)
EXCEL_ANALYSIS_UNSUPPORTED_MESSAGE = (
    "V0.4只支持描述性统计、基础分组统计和明确公式计算；当前请求涉及复杂异常检测、"
    "相关性、预测、因果判断或数据不足的管理结论，暂不支持。"
)
MAX_TOOL_CALLS_PER_REQUEST = 7
REGISTERED_TOOLS = [
    TURNOVER_RATE_TOOL,
    EXCEL_READER_TOOL,
    *ANALYSIS_TOOLS,
    *KNOWLEDGE_TOOLS,
    *RAG_TOOLS,
    *PROJECT_STATE_TOOLS,
    *MEMORY_TOOLS,
    *REPORT_TOOLS,
]
# The OpenAI SDK eagerly JSON-parses strict function arguments when a stream
# completes. DeepSeek can occasionally return truncated arguments; a retry with
# non-strict transport metadata lets our existing validator return the error to
# the model instead of crashing before tool execution.
STREAMING_PARSE_FALLBACK_TOOLS = [
    {**tool, "strict": False} for tool in REGISTERED_TOOLS
]
SIMPLE_TOOL_HANDLER_NAMES = {
    "read_excel_metadata": "read_excel_metadata",
    "register_knowledge_document": "register_document",
    "list_knowledge_documents": "list_documents",
    "get_document_metadata": "get_document_metadata",
    "read_knowledge_document": "read_knowledge_document",
    "build_knowledge_index": "build_knowledge_index",
    "get_knowledge_index_status": "get_knowledge_index_status",
    "search_knowledge_base": "search_knowledge_base",
    "create_project_state": "create_project_state",
    "list_project_states": "list_project_states",
    "get_project_state": "get_project_state",
    "select_project_state": "select_project_state",
    "update_project_state": "update_project_state",
    "archive_project_state": "archive_project_state",
    "save_memory": "save_memory",
    "list_memories": "list_memories",
    "get_memory": "get_memory",
    "search_memories": "search_memories",
    "update_memory": "update_memory",
    "archive_memory": "archive_memory",
    "forget_memory": "forget_memory",
    "generate_hr_report": "generate_hr_report",
}
NO_ARGUMENT_TOOLS = {
    "list_knowledge_documents",
    "get_knowledge_index_status",
    "list_project_states",
}
EXCEL_ANALYSIS_PATTERNS = (
    re.compile(r"哪些员工.*(?:工资|薪酬).*(?:异常|离群)"),
    re.compile(r"(?:绩效.*工资|工资.*绩效).*(?:关系|相关)"),
    re.compile(r"哪个部门.*离职率.*(?:最高|最低)"),
    re.compile(r"(?:复杂异常|异常值识别|相关性分析|因果推断|预测模型|机器学习)"),
)


class AgentError(Exception):
    """An error safe to explain to a terminal user."""


class ResponseFormatError(AgentError):
    """The model did not return a complete five-part analysis."""


class _VisibleTextDelta:
    """Hide internal routing prefixes while forwarding only visible text deltas."""

    def __init__(self, emit: Callable[[str], None]) -> None:
        self._emit_callback = emit
        self._prefix_buffer = ""
        self._trailing_whitespace = ""
        self._resolved_prefix = False
        self._visible_parts: list[str] = []

    @property
    def text(self) -> str:
        return "".join(self._visible_parts)

    def feed(self, delta: str) -> None:
        if not delta:
            return
        if self._resolved_prefix:
            self._emit_without_trailing_whitespace(delta)
            return

        self._prefix_buffer += delta
        candidate = self._prefix_buffer.lstrip()
        if not candidate:
            return
        if any(prefix.startswith(candidate) for prefix in INTERNAL_OUTPUT_PREFIXES):
            return

        visible = candidate
        for prefix in INTERNAL_OUTPUT_PREFIXES:
            if candidate.startswith(prefix):
                visible = candidate[len(prefix) :].lstrip()
                break
        self._resolved_prefix = True
        self._prefix_buffer = ""
        self._emit_without_trailing_whitespace(visible)

    def finish(self) -> None:
        if not self._resolved_prefix and self._prefix_buffer:
            candidate = self._prefix_buffer.lstrip()
            for prefix in INTERNAL_OUTPUT_PREFIXES:
                if candidate.startswith(prefix):
                    candidate = candidate[len(prefix) :].lstrip()
                    break
            self._resolved_prefix = True
            self._prefix_buffer = ""
            self._emit_without_trailing_whitespace(candidate)
        # Match the non-streaming API, which returns stripped final text.
        self._trailing_whitespace = ""

    def _emit_without_trailing_whitespace(self, text: str) -> None:
        combined = self._trailing_whitespace + text
        match = re.search(r"\s*$", combined)
        trailing_start = match.start() if match else len(combined)
        visible = combined[:trailing_start]
        self._trailing_whitespace = combined[trailing_start:]
        if visible:
            self._visible_parts.append(visible)
            self._emit_callback(visible)


def validate_analysis(text: str) -> None:
    """Require five populated level-one sections in the specified order."""
    if not text.strip():
        raise ResponseFormatError("模型返回了空内容，请重试。")

    matches = list(HEADING_PATTERN.finditer(text))
    if tuple(match.group(1) for match in matches) != HEADINGS:
        raise ResponseFormatError("模型回复未遵循五部分结构，请重试。")

    preamble = text[: matches[0].start()].strip()
    if preamble and len(preamble.splitlines()) != 1:
        raise ResponseFormatError("模型回复的标题前说明过长，请重试。")

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        if not text[match.end() : end].strip():
            raise ResponseFormatError("模型回复存在空白部分，请重试。")


def is_unsupported_excel_analysis(question: str) -> bool:
    """Identify analysis beyond V0.4's descriptive-statistics boundary."""
    normalized = question.strip().lower()
    return any(pattern.search(normalized) for pattern in EXCEL_ANALYSIS_PATTERNS)


def management_boundary_message(question: str) -> str | None:
    """Return a fixed boundary for unsupported management decisions."""
    normalized = question.strip().lower()
    if re.search(r"(?:工资|薪酬).*(?:设计)?.*(?:最不合理|不合理|过高|过低)", normalized):
        return COMPENSATION_JUDGMENT_MESSAGE
    if re.search(
        r"(?:谁.*(?:淘汰|辞退|晋升|调薪|录用)|(?:淘汰|辞退|晋升|调薪|录用).*谁)",
        normalized,
    ):
        return PERSONNEL_DECISION_MESSAGE
    if re.search(r"(?:哪些员工|哪个员工|这个员工|该员工).*(?:绩效差|表现差|能力差)", normalized):
        return EXCEL_ANALYSIS_UNSUPPORTED_MESSAGE
    if is_unsupported_excel_analysis(normalized):
        return EXCEL_ANALYSIS_UNSUPPORTED_MESSAGE
    return None


class HRConsultant:
    """Keep conversation in-process and use only explicit persistent Memory tools."""

    def __init__(self, *, client: OpenAI | None = None, model: str | None = None) -> None:
        selected_model = model or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)
        if not selected_model.strip():
            raise AgentError("DEEPSEEK_MODEL 不能为空。")
        self.model = selected_model.strip()

        if client is None:
            api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
            if not api_key:
                raise AgentError("未设置 DEEPSEEK_API_KEY，请先在运行环境中配置。")
            client = OpenAI(
                api_key=api_key,
                base_url=DEEPSEEK_BASE_URL,
                timeout=30.0,
                max_retries=2,
            )

        self.client = client
        self.history: list[dict[str, str]] = []
        self.last_tool_calls: list[str] = []
        self.last_response: Any | None = None
        self.last_final_output: str | None = None
        self._last_request_input: list[Any] = []

    def _create_response(self, input_items: list[Any], *, allow_tools: bool = True) -> Any:
        try:
            return self.client.responses.create(
                model=self.model,
                instructions=AGENT_INSTRUCTIONS,
                input=input_items,
                tools=REGISTERED_TOOLS if allow_tools else [],
                parallel_tool_calls=False,
            )
        except AuthenticationError as exc:
            raise AgentError("DeepSeek API 认证失败，请检查 DEEPSEEK_API_KEY。") from exc
        except RateLimitError as exc:
            raise AgentError("DeepSeek API 请求受限，请稍后重试或检查账户额度。") from exc
        except APITimeoutError as exc:
            raise AgentError("DeepSeek API 请求超时，请稍后重试。") from exc
        except APIConnectionError as exc:
            raise AgentError("无法连接 DeepSeek API，请检查网络连接。") from exc
        except APIStatusError as exc:
            if exc.status_code == 402:
                raise AgentError("DeepSeek API 账户余额不足，请检查账户余额。") from exc
            if exc.status_code in (400, 404, 422):
                raise AgentError(
                    f"DeepSeek API 返回错误状态 {exc.status_code}，请检查 DEEPSEEK_MODEL、请求参数与账户权限。"
                ) from exc
            raise AgentError(f"DeepSeek API 返回错误状态 {exc.status_code}，请稍后重试。") from exc
        except OpenAIError as exc:
            raise AgentError("DeepSeek API 请求失败，请稍后重试。") from exc

    def _create_streamed_response(
        self,
        input_items: list[Any],
        *,
        allow_tools: bool = True,
    ) -> tuple[Any, list[str]]:
        """Consume one response stream and retain its text deltas for safe replay."""
        def consume(tools: list[dict[str, Any]]) -> tuple[Any, list[str]]:
            text_deltas: list[str] = []
            with self.client.responses.stream(
                model=self.model,
                instructions=AGENT_INSTRUCTIONS,
                input=input_items,
                tools=tools,
                parallel_tool_calls=False,
            ) as stream:
                for event in stream:
                    if isinstance(event, ResponseTextDeltaEvent):
                        text_deltas.append(event.delta)
                return stream.get_final_response(), text_deltas

        try:
            try:
                return consume(REGISTERED_TOOLS if allow_tools else [])
            except json.JSONDecodeError:
                return consume(STREAMING_PARSE_FALLBACK_TOOLS if allow_tools else [])
        except json.JSONDecodeError as exc:
            raise AgentError("模型返回的流式工具参数无法解析，本次生成已停止，请重试。") from exc
        except AuthenticationError as exc:
            raise AgentError("DeepSeek API 认证失败，请检查 DEEPSEEK_API_KEY。") from exc
        except RateLimitError as exc:
            raise AgentError("DeepSeek API 请求受限，请稍后重试或检查账户额度。") from exc
        except APITimeoutError as exc:
            raise AgentError("DeepSeek API 请求超时，请稍后重试。") from exc
        except APIConnectionError as exc:
            raise AgentError("无法连接 DeepSeek API，请检查网络连接。") from exc
        except APIStatusError as exc:
            if exc.status_code == 402:
                raise AgentError("DeepSeek API 账户余额不足，请检查账户余额。") from exc
            if exc.status_code in (400, 404, 422):
                raise AgentError(
                    f"DeepSeek API 返回错误状态 {exc.status_code}，请检查 DEEPSEEK_MODEL、请求参数与账户权限。"
                ) from exc
            raise AgentError(f"DeepSeek API 返回错误状态 {exc.status_code}，请稍后重试。") from exc
        except OpenAIError as exc:
            raise AgentError("DeepSeek API 请求失败，请稍后重试。") from exc

    @staticmethod
    def _item_value(item: Any, field: str) -> Any:
        if isinstance(item, Mapping):
            return item.get(field)
        return getattr(item, field, None)

    def _tool_calls(self, response: Any) -> list[Any]:
        output = getattr(response, "output", None)
        if not isinstance(output, list):
            return []
        return [
            item
            for item in output
            if self._item_value(item, "type") == "function_call"
        ]

    def _execute_tool_call(self, call: Any) -> dict[str, Any]:
        name = self._item_value(call, "name")
        raw_arguments = self._item_value(call, "arguments")
        try:
            arguments = json.loads(raw_arguments)
            if not isinstance(arguments, dict):
                raise TypeError
        except (json.JSONDecodeError, TypeError):
            return {"error": "工具参数必须是有效的 JSON 对象。"}

        if name == "calculate_turnover_rate":
            self.last_tool_calls.append(name)
            try:
                return calculate_turnover_rate(**arguments)
            except (TurnoverRateInputError, TypeError) as exc:
                return {"error": str(exc)}
        if name in SIMPLE_TOOL_HANDLER_NAMES:
            self.last_tool_calls.append(name)
            if name in NO_ARGUMENT_TOOLS and arguments:
                return {
                    "success": False,
                    "error": {
                        "code": "invalid_arguments",
                        "message": f"{name} 不接受参数。",
                    },
                }
            handler = globals().get(SIMPLE_TOOL_HANDLER_NAMES[name])
            if not callable(handler):
                return {
                    "success": False,
                    "error": {
                        "code": "tool_handler_unavailable",
                        "message": f"{name} 的执行器不可用。",
                    },
                }
            try:
                return handler(**arguments)
            except TypeError as exc:
                return {
                    "success": False,
                    "error": {"code": "invalid_arguments", "message": str(exc)},
                }
        if name in ANALYSIS_FUNCTIONS:
            file_path = arguments.pop("file_path", None)
            sheet_name = arguments.pop("sheet_name", None)
            if not isinstance(file_path, str) or not file_path.strip():
                return {
                    "success": False,
                    "stage": "excel_reader",
                    "error": {
                        "code": "invalid_file_path",
                        "message": "分析请求必须提供有效的 .xlsx 文件路径。",
                    },
                }

            self.last_tool_calls.append("read_excel_metadata")
            reader_result = read_excel_data(file_path, sheet_name=sheet_name)
            if not reader_result.get("success"):
                return {**reader_result, "stage": "excel_reader"}

            self.last_tool_calls.append(name)
            analysis_function = ANALYSIS_FUNCTIONS[name]
            try:
                analysis_result = analysis_function(
                    data=reader_result["records"],
                    **arguments,
                )
            except TypeError as exc:
                analysis_result = {
                    "success": False,
                    "error": {"code": "invalid_arguments", "message": str(exc)},
                }
            return {
                "success": bool(analysis_result.get("success")),
                "stage": "analysis",
                "source": {
                    "file_name": reader_result["file_name"],
                    "sheet_names": reader_result["sheet_names"],
                    "selected_sheet": reader_result["selected_sheet"],
                    "row_count": reader_result["row_count"],
                    "columns": reader_result["columns"],
                },
                "analysis_tool": name,
                "result": analysis_result,
            }
        return {"error": f"不支持的工具：{name or '未命名工具'}。"}

    def _request(self, messages: list[Any], *, allow_tools: bool = True) -> str:
        input_items: list[Any] = list(messages)
        response = self._create_response(input_items, allow_tools=allow_tools)
        tool_call_count = 0

        while tool_calls := self._tool_calls(response):
            if not allow_tools:
                raise ResponseFormatError("格式修复阶段不允许调用工具，本次回答未保存，请重试。")
            if tool_call_count + len(tool_calls) > MAX_TOOL_CALLS_PER_REQUEST:
                raise AgentError("模型请求了过多工具调用，本次分析已停止，请重试。")

            tool_outputs: list[dict[str, str]] = []
            for call in tool_calls:
                call_id = self._item_value(call, "call_id")
                if not isinstance(call_id, str) or not call_id:
                    raise AgentError("模型返回的工具调用缺少 call_id，请重试。")
                result = self._execute_tool_call(call)
                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps(result, ensure_ascii=False),
                    }
                )

            # Responses API expects its function-call items followed by matching
            # outputs. Keeping them in the local input avoids server-side memory.
            response_output = getattr(response, "output", None)
            if not isinstance(response_output, list):
                raise AgentError("模型返回了无效的工具调用响应，请重试。")
            input_items = [*input_items, *response_output, *tool_outputs]
            tool_call_count += len(tool_calls)
            response = self._create_response(input_items, allow_tools=allow_tools)

        self._last_request_input = list(input_items)
        self.last_response = response
        result = getattr(response, "output_text", None)
        if not isinstance(result, str) or not result.strip():
            raise ResponseFormatError("模型未返回可用的文本内容，请重试。")
        return result.strip()

    def _request_streamed(
        self,
        messages: list[Any],
        *,
        allow_tools: bool = True,
    ) -> tuple[str, list[str]]:
        """Run the tool loop and return only the final response round's deltas."""
        input_items: list[Any] = list(messages)
        response, final_deltas = self._create_streamed_response(input_items, allow_tools=allow_tools)
        tool_call_count = 0

        while tool_calls := self._tool_calls(response):
            if not allow_tools:
                raise ResponseFormatError("格式修复阶段不允许调用工具，本次回答未保存，请重试。")
            if tool_call_count + len(tool_calls) > MAX_TOOL_CALLS_PER_REQUEST:
                raise AgentError("模型请求了过多工具调用，本次分析已停止，请重试。")

            tool_outputs: list[dict[str, str]] = []
            for call in tool_calls:
                call_id = self._item_value(call, "call_id")
                if not isinstance(call_id, str) or not call_id:
                    raise AgentError("模型返回的工具调用缺少 call_id，请重试。")
                result = self._execute_tool_call(call)
                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps(result, ensure_ascii=False),
                    }
                )

            response_output = getattr(response, "output", None)
            if not isinstance(response_output, list):
                raise AgentError("模型返回了无效的工具调用响应，请重试。")
            input_items = [*input_items, *response_output, *tool_outputs]
            tool_call_count += len(tool_calls)
            # Text emitted by a tool-calling round is planning commentary, not
            # the final answer. Fully consume it but never expose it to users.
            response, final_deltas = self._create_streamed_response(input_items, allow_tools=allow_tools)

        self._last_request_input = list(input_items)
        self.last_response = response
        result = getattr(response, "output_text", None)
        if not isinstance(result, str) or not result.strip():
            raise ResponseFormatError("模型未返回可用的文本内容，请重试。")
        return result.strip(), final_deltas

    @staticmethod
    def _visible_stream_text(deltas: list[str]) -> str:
        """Normalize retained deltas exactly as they will be shown to users."""
        parts: list[str] = []
        visible_stream = _VisibleTextDelta(parts.append)
        for delta in deltas:
            visible_stream.feed(delta)
        visible_stream.finish()
        return visible_stream.text

    @staticmethod
    def _emit_validated_deltas(
        deltas: list[str],
        answer: str,
        on_text_delta: Callable[[str], None],
    ) -> None:
        """Replay only a validated final answer, preserving provider delta boundaries."""
        if not deltas:
            on_text_delta(answer)
            return
        visible_stream = _VisibleTextDelta(on_text_delta)
        for delta in deltas:
            visible_stream.feed(delta)
        visible_stream.finish()

    @staticmethod
    def _normalize_model_answer(answer: str) -> tuple[str, bool]:
        """Remove internal routing markers and identify five-part analyses."""
        if answer.startswith(OUT_OF_SCOPE_PREFIX):
            boundary = answer[len(OUT_OF_SCOPE_PREFIX) :].strip()
            if boundary == OUT_OF_SCOPE_MESSAGE:
                return boundary, False
        if answer.startswith(EXCEL_ANALYSIS_UNSUPPORTED_PREFIX):
            boundary = answer[len(EXCEL_ANALYSIS_UNSUPPORTED_PREFIX) :].strip()
            if boundary in {
                COMPENSATION_JUDGMENT_MESSAGE,
                PERSONNEL_DECISION_MESSAGE,
                EXCEL_ANALYSIS_UNSUPPORTED_MESSAGE,
            }:
                return boundary, False

        prefixed_outputs = (
            (DATA_ANALYSIS_PREFIX, "模型未返回数据分析内容，请重试。"),
            (EXCEL_METADATA_PREFIX, "模型未返回 Excel 元数据内容，请重试。"),
            (KNOWLEDGE_ANSWER_PREFIX, "模型未返回知识库读取结果，请重试。"),
            (RAG_ANSWER_PREFIX, "模型未返回 RAG 检索回答，请重试。"),
            (PROJECT_STATE_PREFIX, "模型未返回项目 State 结果，请重试。"),
            (MEMORY_PREFIX, "模型未返回 Memory 结果，请重试。"),
            (REPORT_PREFIX, "模型未返回报告生成结果，请重试。"),
        )
        for prefix, error_message in prefixed_outputs:
            if answer.startswith(prefix):
                visible = answer[len(prefix) :].strip()
                if not visible:
                    raise ResponseFormatError(error_message)
                return visible, False
        return answer, True

    def _commit_answer(
        self,
        pending: list[dict[str, str]],
        answer: str,
    ) -> str:
        self.history = [*pending, {"role": "assistant", "content": answer}]
        self.last_final_output = answer
        return answer

    def ask(self, question: str) -> str:
        """Answer once and commit the turn only after a valid reply."""
        if not question.strip():
            raise AgentError("请输入企业人力资源管理问题。")

        self.last_tool_calls = []
        self.last_response = None
        self.last_final_output = None
        self._last_request_input = []
        if boundary := management_boundary_message(question):
            pending = [*self.history, {"role": "user", "content": question.strip()}]
            return self._commit_answer(pending, boundary)

        pending = [*self.history, {"role": "user", "content": question.strip()}]
        raw_answer = self._request(pending)
        answer, needs_validation = self._normalize_model_answer(raw_answer)
        if needs_validation:
            try:
                validate_analysis(answer)
            except ResponseFormatError:
                # Keep acquired evidence, but never repeat side effects just to
                # repair formatting. This context is local to the current run.
                repair = [
                    *self._last_request_input,
                    {"role": "assistant", "content": answer},
                    {"role": "user", "content": FORMAT_REPAIR_INSTRUCTIONS},
                ]
                repaired = self._request(repair, allow_tools=False)
                answer, _ = self._normalize_model_answer(repaired)
                validate_analysis(answer)

        return self._commit_answer(pending, answer)

    def ask_streamed(
        self,
        question: str,
        *,
        on_text_delta: Callable[[str], None],
    ) -> str:
        """Stream visible model text and return the complete validated final output."""
        if not question.strip():
            raise AgentError("请输入企业人力资源管理问题。")

        self.last_tool_calls = []
        self.last_response = None
        self.last_final_output = None
        self._last_request_input = []
        pending = [*self.history, {"role": "user", "content": question.strip()}]
        if boundary := management_boundary_message(question):
            on_text_delta(boundary)
            return self._commit_answer(pending, boundary)

        raw_answer, final_deltas = self._request_streamed(pending)
        answer, needs_validation = self._normalize_model_answer(raw_answer)
        if needs_validation:
            try:
                validate_analysis(answer)
            except ResponseFormatError:
                # Nothing has been displayed yet, so the same single repair
                # used by non-streaming mode remains safe and invisible.
                repair = [
                    *self._last_request_input,
                    {"role": "assistant", "content": answer},
                    {"role": "user", "content": FORMAT_REPAIR_INSTRUCTIONS},
                ]
                repaired, final_deltas = self._request_streamed(repair, allow_tools=False)
                answer, _ = self._normalize_model_answer(repaired)
                validate_analysis(answer)

        streamed_text = self._visible_stream_text(final_deltas)
        if streamed_text and streamed_text != answer:
            raise ResponseFormatError(
                "流式文本与最终响应不一致，本次回答未保存，请重试。"
            )
        if not streamed_text:
            final_deltas = []

        # Terminal output is irreversible. Emit only after the final round has
        # passed prefix normalization and the applicable response contract.
        self._emit_validated_deltas(final_deltas, answer, on_text_delta)

        return self._commit_answer(pending, answer)
