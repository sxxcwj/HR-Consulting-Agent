"""Check the prompt's product-critical commitments."""

from src.prompts import AGENT_INSTRUCTIONS


def test_identity_and_boundaries_are_present() -> None:
    for phrase in (
        "HR Consultant",
        "资深企业人力资源管理顾问",
        "组织问题诊断",
        "绩效问题诊断",
        "薪酬问题分析",
        "人才管理建议",
        "不得编造企业数据",
        "信息不足必须明确指出",
        "不得假装已读取",
    ):
        assert phrase in AGENT_INSTRUCTIONS


def test_required_headings_follow_product_order() -> None:
    headings = [
        "# 问题判断",
        "# 可能原因",
        "# 需要补充的信息",
        "# 建议措施",
        "# 下一步行动",
    ]
    positions = [AGENT_INSTRUCTIONS.index(heading) for heading in headings]
    assert positions == sorted(positions)


def test_non_hr_request_has_separate_boundary_response() -> None:
    assert "OUT_OF_SCOPE:" in AGENT_INSTRUCTIONS
    assert "不要套用五段结构" in AGENT_INSTRUCTIONS


def test_conciseness_and_unverified_legal_limits_are_present() -> None:
    for phrase in (
        "2 至 4 个最有区分价值的可能原因",
        "不自行给出企业具体期限、人数、比例、样本量或观察周期",
        "不引用具体法规名称、条款",
        "普通组织、绩效、招聘或培训诊断",
    ):
        assert phrase in AGENT_INSTRUCTIONS


def test_turnover_tool_calling_rules_are_present() -> None:
    for phrase in (
        "calculate_turnover_rate",
        "不要自行估算或心算离职率",
        "期初人数和期末人数",
        "不得声称调用工具，除非本轮实际收到工具结果",
        "工具负责计算，你负责判断、解释和建议",
    ):
        assert phrase in AGENT_INSTRUCTIONS


def test_excel_reader_and_analysis_separation_rules_are_present() -> None:
    for phrase in (
        "read_excel_metadata",
        "只读取和描述 Excel",
        "多个 Sheet 且用户未指定时，只呈现 Sheet 列表",
        "不得假装读取成功",
        "calculate_headcount",
        "analyze_compensation_summary",
        "calculate_turnover_analysis",
        "analyze_performance_summary",
        "analyze_missing_data",
        "不得根据 preview 自行计算",
        "只有 Tool 实际返回 sample_size_warning",
        "不得把“数值最高”写成“过高”",
        "不得给员工贴标签或自动作出",
    ):
        assert phrase in AGENT_INSTRUCTIONS


def test_file_knowledge_and_rag_evidence_boundaries_are_present() -> None:
    for phrase in (
        "register_knowledge_document",
        "list_knowledge_documents",
        "get_document_metadata",
        "read_knowledge_document",
        "DOCUMENT_FACT",
        "文件规定”不等于“现实已经执行",
        "当前读取或检索结果没有足够依据",
        "多个或全部文件中查找内容",
        "search_knowledge_base",
        "build_knowledge_index",
        "相似度只用于排序",
        "RAG_ANSWER:",
        "不主动输出整份长文件",
    ):
        assert phrase in AGENT_INSTRUCTIONS


def test_project_state_is_explicit_and_source_aware() -> None:
    for phrase in (
        "create_project_state",
        "get_project_state",
        "update_project_state",
        "archive_project_state",
        "PROJECT_CONTEXT",
        "PROJECT_STATE:",
        "绝对不能自动写入 State",
        "不保存完整对话",
        "只是引用",
        "归档项目不能更新",
        "员工级敏感信息",
    ):
        assert phrase in AGENT_INSTRUCTIONS
