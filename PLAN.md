# HR Consultant V1.0 发布计划

本计划依据 `AGENTS.md`、`PRODUCT_SPEC.md`、`AGENT_SPEC.md` 和 `WORKFLOW.md`。V0.1 按 M1 → M8 完成，V0.2 当前只执行 M9；每次只实施用户指定的当前 Milestone。以下 `Files` 是计划在相应阶段创建或修改的文件，`Validation Command` 是该阶段实施后的目标命令；本计划本身不表示这些文件或命令现在已经可用。

状态只允许使用 `TODO`、`IN_PROGRESS`、`DONE`。开始某项工作时将其改为 `IN_PROGRESS`；其 Acceptance Criteria 和验证全部通过后才改为 `DONE`。未完成的验证应保持 `IN_PROGRESS` 并记录原因，不以文档或测试存在代替运行结果。实际代码文件名如需调整，应保持模块职责和验收范围不变，并同步更新本计划。

根据用户最新要求，V0.1 的模型提供方改为 DeepSeek，继续使用 OpenAI 官方 Python SDK 的兼容接口。M1—M8 均已完成；12 个固定案例全部通过结构和范围检查，11/12 通过七维内容质量评审，真实 API 在线测试一次性 14/14 通过。具体证据见 `evals/ACCEPTANCE_REPORT.md`。

V0.2 通过 M9 增加离职率 Tool；V0.3 通过 M10 增加只读 Excel 元数据；V0.4 通过 M11 增加五个描述性分析 Tool；V0.5 通过 M12 增加本地企业文件知识库；V0.6 通过 M13 增加本地 RAG；V0.7 通过 M14 增加显式项目 State；V0.8 通过 M15 增加显式长期 Memory；V0.9 通过 M16 增加 Markdown 报告生成；V1.0 只通过 M17 完成发布加固。

## M1 项目初始化

**Objective**：建立最小 Python 项目结构、依赖声明和测试入口，为后续 Milestone 提供可运行的基础。

**Tasks**：

1. 建立 `src` 包和最小 Python 3.11+ 项目结构。
2. 声明运行和测试所需的最少依赖。
3. 配置忽略本地密钥、虚拟环境和生成文件；提供最简启动说明。
4. 添加包导入与项目配置的烟雾测试，不提前实现 API、Agent 或 CLI 功能。

**Files**：`requirements.txt`、`.env.example`、`src/__init__.py`、`.gitignore`、`README.md`、`tests/test_project_smoke.py`、`PLAN.md`。

**Acceptance Criteria**：Python 包可导入；测试工具能够发现并执行烟雾测试；项目说明能让开发者完成本地安装；仓库不包含 API Key；未引入 V0.1 禁止的能力或基础设施。

**Validation Command**：

```bash
python -m pip install -r requirements.txt
python -m pytest -q tests/test_project_smoke.py
```

**Status**：DONE

## M2 DeepSeek API连接

**Objective**：使用 OpenAI 官方 Python SDK 建立最小的 DeepSeek 兼容 API 请求与响应通道，并能清楚处理配置和连接失败。

**Tasks**：

1. 从运行环境读取 API Key，不在代码、测试、配置或示例中硬编码密钥。
2. 封装一次文本请求和文本响应的最小接口，不引入检索、工具调用或持久化。
3. 为缺少密钥、鉴权失败、超时、网络失败和无有效响应设计可识别的错误结果。
4. 添加不依赖真实网络的单元测试，并在提供有效密钥的环境中完成一次最小真实连接验证。

**Files**：`src/agent.py`、`tests/test_api_client.py`、`tests/test_api_live.py`、`README.md`、`PLAN.md`。

**Acceptance Criteria**：可用环境密钥完成一次真实文本请求并读取响应；错误不会被静默吞掉；测试与日志不暴露密钥；不调用数据库、RAG、MCP 或其他外部业务工具。没有有效密钥或真实连接验证未通过时，M2 不标记为 `DONE`。

**Validation Command**：

```bash
python -m pytest -q tests/test_api_client.py
python -m pytest -q -m live tests/test_api_live.py
```

第二条命令只在运行环境已设置 `DEEPSEEK_API_KEY` 时执行，且须确认得到真实 API 响应；如无法执行，应如实记录未验证状态。

**Status**：DONE

## M3 Agent Instructions

**Objective**：把 `AGENT_SPEC.md` 和 `WORKFLOW.md` 转化为 HR Consultant 的单份、可维护的 Agent 指令。

**Tasks**：

1. 固化 Agent Name、Role、Goal、四项职责和三条核心边界。
2. 写入范围判断、信息不足、不确定结论、高风险与敏感信息的处理规则。
3. 写入五段固定输出协议及当前对话中补充信息后的更新规则。
4. 测试指令文本是否包含关键约束，并通过真实 API 请求检查指令可被使用。

**Files**：`src/prompts.py`、`tests/test_instructions.py`、`tests/test_instructions_live.py`、`PLAN.md`。

**Acceptance Criteria**：指令与两份规格及工作流程一致；不声称读取未提供的文件或拥有 V0.1 禁止能力；在信息不足时要求明确说明缺口；真实请求能使用该指令得到文本回复。本阶段不承担 CLI 输入或最终输出校验的实现。

**Validation Command**：

```bash
python -m pytest -q tests/test_instructions.py
python -m pytest -q -m live tests/test_instructions_live.py
```

真实请求验证需要已配置的 `DEEPSEEK_API_KEY`；未通过时不将 M3 标记为 `DONE`。

**Status**：DONE

## M4 CLI用户输入

**Objective**：让用户通过命令行输入自然语言 HR 问题，并在当前进程内进行连续对话。

**Tasks**：

1. 提供最小命令行入口，接收用户文本并交给 Agent 请求流程。
2. 保留当前进程中的对话上下文，使用户补充信息时能够更新分析；退出后不保存对话。
3. 对空输入、退出指令和输入中断作明确处理。
4. 测试单轮输入、连续输入和退出路径。

**Files**：`src/main.py`、`tests/test_cli.py`、`README.md`、`PLAN.md`。

**Acceptance Criteria**：命令行可启动并接受至少一轮输入；同一进程可继续输入补充信息；退出或中断可正常结束；不会跨会话保存信息，也不依赖 Web UI。此阶段可直接显示 M3 的原始文本响应，输出协议的独立检查留在 M5。

**Validation Command**：

```bash
python -m pytest -q tests/test_cli.py
python -m src.main
```

第二条命令用于手动检查输入、续问和退出；应在具备有效 API 配置的环境执行。

**Status**：DONE

## M5 Agent输出

**Objective**：确保正式分析按五个固定标题输出，并在发送前完成结构与关键内容检查。

**Tasks**：

1. 将 API 文本回复接入 CLI 的显示流程。
2. 对可识别 HR 问题的回复检查五个一级标题的名称、顺序和数量。
3. 检查信息不足的回复仍保留五段，补充信息后重新形成完整五段分析。
4. 对结构不合格或内容为空的回复给出明确错误处理，不把不合格内容伪装成合格分析。
5. 添加正常结构、标题缺失、标题错序和空响应测试。

**Files**：`src/agent.py`、`src/main.py`、`tests/test_output.py`、`tests/test_agent.py`、`PLAN.md`。

**Acceptance Criteria**：正式分析只使用“问题判断 → 可能原因 → 需要补充的信息 → 建议措施 → 下一步行动”五个一级标题；非 HR 交流不强制五段；用户能看到完整、非空的文本结果；结构错误有明确处理。内容质量仍需 M7、M8 的案例检验，不能仅凭标题检查宣称通过。

**Validation Command**：

```bash
python -m pytest -q tests/test_output.py tests/test_agent.py
python -m src.main
```

第二条命令使用至少一个正常 HR 问题和一个信息不足的问题进行手动检查。

**Status**：DONE

## M6 Error Handling

**Objective**：统一处理 V0.1 已有路径中的可预见错误，使失败可见、可理解且不泄露密钥。

**Tasks**：

1. 核对 API 配置、鉴权、限额、网络、超时和响应异常的处理。
2. 核对 CLI 空输入、中断、退出和 Agent 输出不合格的处理。
3. 对用户显示简洁可理解的错误提示；保留必要的排查信息，不输出 API Key 或敏感原文。
4. 增加故障注入测试，确认错误没有被静默吞掉或误报为成功。

**Files**：`src/agent.py`、`src/main.py`、`tests/test_errors.py`、`PLAN.md`。

**Acceptance Criteria**：上述错误均有可识别处理路径；用户不会收到虚构的分析结果；程序在可恢复输入错误后可继续使用，遇不可恢复错误时明确结束；密钥不出现在错误文本或日志中。

**Validation Command**：

```bash
python -m pytest -q tests/test_errors.py
python -m src.main
```

第二条命令用于实际检查正常退出与至少一种可恢复输入错误；API 故障通过受控测试验证。

**Status**：DONE

## M7 Test Cases

**Objective**：建立覆盖 V0.1 核心行为的固定测试案例集和可重复执行的检查方式。

**Tasks**：

1. 按 `PRODUCT_SPEC.md` 第 8.4 节准备 12 个固定案例：六类各 2 个，同一案例不重复计入多类。
2. 为每个案例记录用户输入、连续对话补充内容（如适用）、预期行为和禁止行为。
3. 增加可自动检查的结构、范围与关键边界测试；保留需要人工判断的相关性、逻辑性、审慎性和可执行性检查点。
4. 覆盖信息充分、信息不足、多模块、主观归因、高风险和更新判断六类情况。

**Files**：`evals/acceptance_cases.json`、`evals/README.md`、`tests/test_cases.py`、`tests/test_cases_live.py`、`PLAN.md`。

**Acceptance Criteria**：固定案例总数为 12，每类恰好 2 个；包含连续对话案例；每例有可检查的预期点；自动检查可运行，人工质量项有清晰判定依据；不依赖真实企业隐私数据、Excel、数据库或外部知识库。

**Validation Command**：

```bash
python -m pytest -q tests/test_cases.py
python -m pytest -q
```

**Status**：DONE

## M8 Acceptance Test

**Objective**：按产品和 Agent 规格完成 V0.1 的最终功能、质量与范围验收，并记录证据。

**Tasks**：

1. 运行全套自动测试和可用环境中的 CLI 实际交互。
2. 使用 M7 冻结的 12 个案例执行正式分析；连续对话案例检查其中每次正式回复。
3. 逐例检查五段结构、事实与假设区分、建议依据、风险边界、下一步行动和范围控制。
4. 按 `PRODUCT_SPEC.md` 的七个质量维度逐例人工评审并记录具体证据；产品规格建议条件允许时由两名评审者独立判定，无法取得第二名评审者时不得虚构评审人，应如实记录实际评审方式。
5. 修复失败项并重新执行相关测试及受影响案例；形成验收记录。

**Files**：`evals/ACCEPTANCE_REPORT.md`、`PLAN.md`；发现缺陷时仅修改其所属的现有代码或测试文件。

**Acceptance Criteria**：12 个案例的所有正式分析均通过基础功能和范围控制检查；至少 10 个案例同时通过七个质量维度；不存在编造关键事实、无依据确定性高风险结论或虚假工具调用。程序和测试运行通过，验收报告记录每例结果及未通过项的修复与复验。未达到上述条件时 M8 保持 `IN_PROGRESS`。

**Validation Command**：

```bash
python -m pytest -q
python -m src.main
```

此外，按固定案例执行并记录人工评审；CLI 命令使用有效 API 配置进行实际交互。

**Status**：DONE

## M9 V0.2 Employee Turnover Rate Function Tool

**Objective**：在现有 Responses API 架构中注册并执行 `calculate_turnover_rate`，让离职率计算由本地确定性 Tool 完成，Agent 继续负责判断、解释和建议。

**Tasks**：

1. 在 `src/tools/turnover.py` 实现计算、参数校验和结构化结果；
2. 在 `src/agent.py` 通过 Responses API function calling 注册、执行并回传 Tool 结果；
3. 更新 Agent instructions，明确调用条件、缺失信息和结果完整性规则；
4. 增加 Tool 单元测试和 A/B/C 三类 Agent 集成测试；
5. 更新产品、行为、流程和运行文档；
6. 运行新增测试、完整回归测试和真实 API 工具调用验证。

**Files**：`src/tools/turnover.py`、`src/agent.py`、`src/prompts.py`、`tests/test_tools.py`、`tests/test_tool_integration.py`、`tests/test_tool_live.py`、相关规格文档、`README.md`、`PLAN.md`。

**Acceptance Criteria**：Tool 两种合法口径计算准确；缺少或非法人数时清晰失败；完整数据触发 Tool；非计算请求不调用；缺少人数不猜测；工具结果可被五段回复正确解释；V0.1 回归测试全部通过；不新增其他 Tool 或禁止能力。

**Validation Command**：

```bash
python -m pytest -q tests/test_tools.py tests/test_tool_integration.py
python -m pytest -q -m live tests/test_tool_live.py
python -m pytest -q
python -m src.main
```

**Validation Results**：Tool 独立运行通过；新增离线单元与编排测试通过；完整离线回归 `51 passed, 17 deselected`；真实 API 的 Case A、B、C 三项均通过；CLI 启动、输入提示与退出正常；编译检查通过。

**Status**：DONE

## M10 V0.3 Excel Metadata Reader

**Objective**：注册只读 `read_excel_metadata` Tool，使 Agent 能描述 `.xlsx` 文件结构和脱敏预览，同时以程序边界禁止任何 Excel 数据分析。

**Tasks**：

1. 将 Tool 模块调整为包并保持 V0.2 导入兼容；
2. 实现 Excel 文件、Sheet、行列、字段、类型、缺失值、敏感字段和预览读取；
3. 实现多 Sheet、文件、解析和隐私错误处理；
4. 创建 20 条虚构数据的样例工作簿；
5. 注册 Tool，并对禁止的数据分析请求实施不调用 Tool 的固定边界；
6. 增加单元与 Agent 集成测试，并执行实际工具读取验证；
7. 更新规格、流程、运行说明并完成 V0.1/V0.2 回归。

**Files**：`src/tools/`、`src/agent.py`、`src/prompts.py`、`data/sample_employees.xlsx`、`tests/test_excel_reader.py`、`tests/test_excel_tool_integration.py`、相关规格文档、`README.md`、`requirements.txt`、`PLAN.md`。

**Acceptance Criteria**：用户要求的元数据均可读取；敏感字段预览脱敏；多 Sheet 不擅自选择；失败不伪装成功；禁止的数据分析不调用 Tool；V0.1/V0.2 回归通过；不增加其他能力。

**Validation Command**：

```bash
python -m pytest -q tests/test_excel_reader.py tests/test_excel_tool_integration.py
python -m pytest -q
python -m src.main
```

**Validation Results**：Excel Reader 专项、Agent 编排和 V0.2 回归测试通过；完整离线回归 `78 passed, 17 deselected`；样例工作簿实际读取为 20 行、8 列、单 Sheet，缺失值与 5 行预览返回正确；敏感字段测试确认姓名、邮箱和地址预览脱敏；多 Sheet、文件、解析与空 Sheet 错误路径通过；CLI 启动、输入提示与退出正常；依赖检查通过。真实外部 API 未接收本地工作簿数据，工具选择和回传链路由模拟 Responses API 验证。

**Status**：DONE

## M11 V0.4 Descriptive HR Data Analysis

**Objective**：在 V0.3 Reader 基础上增加人数、薪酬、离职、绩效和缺失数据统计，不引入复杂分析或自动人事决策。

**Tasks**：

1. 创建独立 `src/analytics/`，实现五个只接收内存记录的分析函数；
2. 扩展 Excel Reader 的内部完整记录读取，但不增加业务计算；
3. 在 Agent 调度层组合 Reader 与一个分析函数，只向模型返回聚合结果；
4. 增加字段、类型、空数据、缺失、分组和小样本处理；
5. 实现 DATA FACT、描述性观察和管理结论边界；
6. 完成模块单元测试、A—G 集成测试和 V0.1—V0.3 回归；
7. 更新规格、流程、运行说明和验收证据。

**Files**：`src/analytics/`、`src/tools/excel_reader.py`、`src/agent.py`、`src/prompts.py`、相关测试、规格文档、`README.md`、`PLAN.md`。

**Acceptance Criteria**：三层职责分离；五个 Tool 可用；输入错误明确；Agent 可组合读取与统计；不根据 preview 计算；不把统计升级为无依据管理结论；A—G 和 V0.1—V0.3 回归通过。

**Validation Command**：

```bash
python -m pytest -q tests/test_*_analytics.py tests/test_analytics_integration.py
python -m pytest -q
python -m src.main
```

**Validation Results**：五个分析模块与 A—G 集成场景通过；V0.1—V0.3 完整离线回归 `113 passed, 17 deselected`；真实 API 在线回归 `17 passed, 113 deselected`；虚构样例的真实链路依次完成 Excel Reader、`analyze_compensation_summary` 和 Agent 解释，财务部平均月薪 15268.75 为当前数据最高，未升级为薪酬合理性结论；CLI 启动与退出正常；依赖检查、密钥扫描和分层架构检查通过。

**Status**：DONE

## M12 V0.5 File Knowledge Base

**Objective**：新增与 Excel 数据链路分离的本地企业文件知识库，使 Agent 能导入、解析、登记、列出和受控读取明确指定的企业文档，并基于真实文件内容标注来源回答。

**Tasks**：

1. 建立 `src/knowledge/`，实现 TXT、Markdown、DOCX 和文本型 PDF 的 Loader、Parser 与统一 Document；
2. 使用 `knowledge/index.json` 和 `knowledge/parsed/` 实现简单 Registry，不引入数据库；
3. 实现精确文件选择、metadata、分段读取、敏感标识脱敏和版本冲突提示；
4. 注册导入、列表、metadata 和读取工具，增加 DOCUMENT_FACT、来源与“文件规定不等于实际执行”边界；
5. 创建五份完全虚构且有明确可验证内容的 HR Markdown 文件；
6. 覆盖格式、错误、Registry、Reader、冲突、范围和 Agent Case A—E；
7. 更新产品、行为、流程、运行说明，并执行 V0.1—V0.4 回归。

**Files**：`src/knowledge/`、`knowledge/`、`tests/test_document_loader.py`、`tests/test_document_parser.py`、`tests/test_knowledge_registry.py`、`tests/test_knowledge_reader.py`、`tests/test_knowledge_integration.py`、`src/agent.py`、`src/prompts.py`、`requirements.txt`、相关规格文档、`README.md`、`PLAN.md`。

**Acceptance Criteria**：四种格式可解析，扫描 PDF 明确失败；Registry 和范围读取可用；Agent 以真实文件为依据并标注来源；缺失依据不编造；冲突不裁决；不含 Embedding、Vector DB、Semantic Search 或 Top-K；V0.1—V0.4 回归通过。

**Validation Command**：

```bash
python -m pytest -q tests/test_document_loader.py tests/test_document_parser.py tests/test_knowledge_registry.py tests/test_knowledge_reader.py tests/test_knowledge_integration.py
python -m pytest -q
python -m src.main
```

**Status**：DONE

**Implemented**：Document Loader、四格式 Parser、统一 Document、JSON Registry、范围 Reader、敏感标识脱敏、四个知识库 Function Tools、五份虚构 HR 文件及 Case A—E 已实现。

**Tests**：V0.5 新增 29 项离线测试（Loader 7、Parser 4、Registry 5、Reader 5、Agent 集成 7、instructions 1）全部通过；完整离线回归 `142 passed, 17 deselected`；既有真实 API 回归 `17 passed, 140 deselected`。真实 CLI 依次完成知识库列表与《薪酬管理制度》读取回答，来源、七月调薪规则和“文件规定不等于实际执行”边界均正确；Registry 验证仍仅含 5 份虚构示例文件。

**Known Limitations**：无 OCR、无正文语义搜索、无 Embedding/Vector DB/Top-K；只能按明确 document_id、文件名、标题和 metadata 有限选择；不自动判断冲突版本的效力。

## M13 V0.6 Local RAG

**Objective**：在 V0.5 Registry 上增加可追溯的文档分块、本地中文 Embedding、本地持久化向量索引和 Top-K 语义检索，使 Agent 能基于真实检索片段回答跨文档企业知识问题并标注来源。

**Tasks**：

1. 实现确定性 Document Chunker，保留来源、字符范围和稳定 chunk_id；
2. 封装可注入的 Embedding 接口和延迟加载的本地中文模型；
3. 使用本地 SQLite 保存向量、片段和索引 metadata，并检查缺失/过期文档；
4. 实现索引构建、状态和 Top-K 检索服务及 Function Tools；
5. 更新 Agent 指令和编排，使跨文档知识请求调用检索、给出来源、保留冲突和无依据边界；
6. 增加分块、Embedding、向量存储、RAG 服务和 Agent 集成测试；
7. 使用真实本地模型完成一次索引构建与中文检索，并执行 V0.1—V0.5 全量回归；
8. 更新产品、行为、流程和运行文档，不进入未来版本能力。

**Files**：`src/knowledge/chunking.py`、`src/knowledge/embeddings.py`、`src/knowledge/vector_store.py`、`src/knowledge/rag.py`、`src/knowledge/__init__.py`、`src/agent.py`、`src/prompts.py`、相关测试、`requirements.txt`、`.gitignore`、核心规格文档、`README.md`、`PLAN.md`。

**Acceptance Criteria**：本地模型与索引可用；中文 Top-K 返回可追溯来源；状态可识别缺失/过期；Agent 不根据未检索内容回答；无依据和冲突处理正确；敏感内容脱敏；真实本地模型验证与 V0.1—V0.5 回归全部通过；不增加混合检索、reranker、OCR、托管向量库、Memory、多 Agent 或自动人事决策。

**Validation Command**：

```bash
python -m pytest -q tests/test_chunking.py tests/test_embeddings.py tests/test_vector_store.py tests/test_rag.py tests/test_rag_integration.py
python -m pytest -q
python -m src.knowledge.rag_cli build
python -m src.knowledge.rag_cli search "年度调薪什么时候进行" --top-k 3
python -m src.main
```

**Status**：DONE

**Implemented**：已实现确定性分块、可注入 Embedding 接口、延迟加载的 `BAAI/bge-small-zh-v1.5`、本地 SQLite 向量索引、索引状态/过期检测、Top-K 检索、敏感信息脱敏、版本冲突提示、三项 RAG Function Tools、维护 CLI 和 Agent 有来源回答。Excel、V0.5 Reader、RAG Retriever 与 Agent 解释职责保持分离。

**Tests**：V0.6 新增 32 项测试（31 项离线、1 项真实 DeepSeek + 本地 RAG）；专项离线 `31 passed, 1 deselected`，完整离线回归 `171 passed, 18 deselected`，完整在线回归 `18 passed, 170 deselected`，最终 RAG 在线复验 `1 passed`。真实本地模型将 5 份文档建立为 10 个 512 维片段；“年度调薪什么时候进行”Top-1 命中《02_薪酬管理制度》，得分 `0.671703`，并返回 document_id 和字符范围。CLI 启动/退出、索引状态、依赖安装、编译检查与密钥扫描均通过。

**Known Limitations**：无 OCR、无 BM25/混合检索、无 reranker、无查询改写、无自动冲突裁决、无自动 HR 诊断；相似度只作候选片段排序，不作为制度效力或现实执行证明。首次使用本地模型需要下载依赖与模型文件。

## M14 V0.7 Project State

**Objective**：增加显式、项目级、JSON 持久化的 HR 咨询 State，使用户可跨进程创建、选择、查看、更新和归档项目上下文，同时避免自动长期记忆。

**Tasks**：

1. 定义统一 ProjectState 数据结构、阶段、状态和更新时间；
2. 实现原子 JSON Store、单 active project、损坏/版本错误处理；
3. 实现创建、列表、读取、选择、更新和归档接口；
4. 注册六个 Function Tools，增加 PROJECT_CONTEXT 与显式持久化边界；
5. 拒绝明显员工敏感信息，State 只保存上下文和文件引用；
6. 增加 Store、Tool、Agent 集成和跨实例持久化测试；
7. 更新规格与 README，并执行 V0.1—V0.6 全量回归和真实 API 验证。

**Files**：`src/state/`、`state/`、`src/agent.py`、`src/prompts.py`、`tests/test_project_state_store.py`、`tests/test_project_state_tools.py`、`tests/test_project_state_integration.py`、相关规格文档、`.gitignore`、`README.md`、`PLAN.md`。

**Acceptance Criteria**：六项操作可用；单 active project；跨实例持久化；归档不可继续更新；损坏和非法输入明确失败；敏感信息拒绝保存；普通问答不自动写 State；引用不冒充读取；V0.1—V0.6 回归通过；不增加自动记忆、聊天存档、数据库、云同步或完整项目管理。

**Validation Command**：

```bash
python -m pytest -q tests/test_project_state_store.py tests/test_project_state_tools.py tests/test_project_state_integration.py
python -m pytest -q
python -m src.main
```

**Status**：DONE

**Implemented**：已实现统一 `ProjectState`、原子 JSON Store、单一当前项目选择、创建/列表/读取/选择/更新/归档六项操作及对应 Function Tools；State 仅在用户明确要求时写入，区分 `PROJECT_CONTEXT`、`DOCUMENT_FACT` 与 `DATA FACT`，文件和数据引用不会冒充已读取；归档可保留记录但不可继续选择或更新；明显员工级敏感信息会被拒绝。规格、Agent instructions、工作流、README、CLI 版本信息和忽略规则均已同步。

**Tests**：V0.7 共 23 项专项测试（22 项离线、1 项真实 DeepSeek）全部通过；完整离线回归 `194 passed, 19 deselected`；完整在线回归 `19 passed, 194 deselected`。CLI 启动/退出、源码与测试编译、依赖完整性、密钥扫描和临时目录中的“创建 → 更新 → 跨 Store 实例读取 → 归档”生命周期均通过；未创建真实用户项目 State。

**Known Limitations**：计划内不包含自动记忆、对话摘要、项目任务调度、云同步、多人权限、附件复制或项目报告。

## M15 V0.8 Explicit Long-term Memory

**Objective**：增加显式、用户可控、JSON 持久化的跨项目长期 Memory，使用户可以保存、查看、关键词检索、更正、归档和明确遗忘稳定上下文，同时避免自动聊天记忆和隐私泄露。

**Tasks**：

1. 定义统一 MemoryEntry、category、状态、来源和时间字段；
2. 实现原子 JSON Store、损坏/版本错误和敏感信息处理；
3. 实现保存、列表、读取、关键词检索、更新、归档和遗忘；
4. 注册七个 Function Tools，增加 MEMORY_CONTEXT 和显式写入边界；
5. 明确 Memory 与 Project State、文件事实和数据事实的职责边界；
6. 增加 Store、Tool、Agent 集成、跨实例持久化和真实模型选择测试；
7. 更新规格与 README，并执行 V0.1—V0.7 全量回归。

**Files**：`src/memory/`、`state/`、`src/agent.py`、`src/prompts.py`、`tests/test_memory_store.py`、`tests/test_memory_tools.py`、`tests/test_memory_integration.py`、`tests/test_memory_live.py`、相关规格文档、`.gitignore`、`README.md`、`PLAN.md`。

**Acceptance Criteria**：七项操作可用；跨实例持久化；普通问答不自动写入；关键词检索不冒充语义检索；Memory 使用可追溯；潜在过期明确提示；敏感信息和密钥拒绝保存；归档默认不参与检索；遗忘只按唯一 id 物理删除；V0.1—V0.7 回归通过；不增加自动聊天记忆、Memory Embedding、云同步或用户画像推断。

**Validation Command**：

```bash
python -m pytest -q tests/test_memory_store.py tests/test_memory_tools.py tests/test_memory_integration.py
python -m pytest -q
python -m src.main
```

**Status**：DONE

**Implemented**：已实现统一 `MemoryEntry`、原子 JSON Store、保存/列表/精确读取/关键词检索/更新/归档/遗忘七项操作及对应 Function Tools；Memory 仅在用户明确要求时写入，区分 `MEMORY_CONTEXT`、`PROJECT_CONTEXT`、`DOCUMENT_FACT` 与 `DATA FACT`。关键词检索只返回 active 记录并明确标识为 keyword；归档保留记录，遗忘按唯一 `memory_id` 物理删除。密钥与明显员工级敏感信息会被拒绝。规格、Agent instructions、工作流、README、CLI 版本信息和忽略规则均已同步。

**Tests**：V0.8 共 24 项专项测试（23 项离线、1 项真实 DeepSeek）全部通过；完整离线回归 `217 passed, 20 deselected`；20 项完整在线回归全部通过。CLI 启动/退出、源码与测试编译、依赖完整性、密钥扫描和临时目录中的“保存 → 关键词检索 → 更新 → 跨 Store 实例读取 → 归档 → 遗忘”生命周期均通过；未创建真实用户 Memory 文件。

**Known Limitations**：只支持显式保存与简单关键词检索；不包含自动提取、语义检索、Embedding、跨设备同步、多人权限、冲突合并或聊天记录恢复。

## M16 V0.9 HR Report Generation

**Objective**：把 Agent 已取得、可追溯的 HR 分析生成标准化 Markdown 报告草稿，并安全保存到本地，不改变既有分析、数据、知识库、State 与 Memory 职责。

**Tasks**：

1. 定义报告输入、来源引用、固定章节和结构化返回；
2. 实现 Markdown Report Generator、安全文件名、唯一 report_id 和原子写入；
3. 实现章节、来源、敏感信息与凭据校验；
4. 注册 `generate_hr_report` Function Tool 和 `REPORT:` 输出协议；
5. 明确 Agent 先取得上游证据、Report Generator 只排版保存；
6. 增加 Generator、Tool、Agent 集成和真实模型选择测试；
7. 更新规格与 README，并执行 V0.1—V0.8 全量回归。

**Files**：`src/reports/`、`reports/`、`src/agent.py`、`src/prompts.py`、`tests/test_report_generator.py`、`tests/test_report_tool.py`、`tests/test_report_integration.py`、`tests/test_report_live.py`、相关规格文档、`.gitignore`、`README.md`、`PLAN.md`。

**Acceptance Criteria**：可生成包含全部固定章节与来源索引的 Markdown 草稿；文件路径受控且不覆盖；事实与来源可追溯；Report Generator 不读取上游系统；普通问答不生成报告；敏感内容拒绝；失败不伪装成功；V0.1—V0.8 回归通过；不增加 Word/PDF、图表、批量生成、自动分发或 Registry。

**Validation Command**：

```bash
python -m pytest -q tests/test_report_generator.py tests/test_report_tool.py tests/test_report_integration.py
python -m pytest -q
python -m src.main
```

**Status**：DONE

**Implemented**：已实现固定九章节的 Markdown `ReportGenerator`、结构化来源索引、安全唯一文件名、受控输出目录、原子写入、敏感信息与凭据拦截，以及 `generate_hr_report` Function Tool 和 `REPORT:` 输出协议。Agent 只在用户明确要求时生成报告，并在生成前按需读取 State、Memory、知识库/RAG 或 Excel/Analytics；Report Generator 本身不读取任何上游数据、不新增分析结论，也不自动回写 State 或 Memory。规格、Agent instructions、工作流、README、CLI 版本信息和忽略规则均已同步。

**Tests**：V0.9 共 18 项专项测试（17 项离线、1 项真实 DeepSeek）全部通过；完整离线回归 `234 passed, 21 deselected`；完整在线回归 `21 passed, 234 deselected`。CLI 启动/退出、源码与测试编译、依赖完整性、密钥扫描和临时目录中的真实 Markdown 写入均通过；已核对九个固定章节、来源索引、草稿声明与受控路径，正式 `reports/generated/` 未留下验收文件。

**Known Limitations**：只生成 Markdown 草稿；不支持 Word/PDF/HTML/PPT、品牌模板、图表、批量、自动发送、审批、签名、自动更新或报告 Registry。

## M17 V1.0 Release Hardening

**Objective**：不新增业务能力，将 V0.9 加固为可恢复、可安装、可审计和可持续验证的 V1.0 Release Candidate。

**Tasks**：Git 基线与标签；最小文件权限；共享敏感信息检测；Tool 执行注册表；`pyproject.toml` 与 `hragent`；依赖锁定；V0.2—V0.9 跨能力评测与确定性评分；Python 3.11—3.13 CI；API 数据披露；发布与试点文档；完整回归。

**Files**：`src/security.py`、`src/config.py`、`src/agent.py`、`pyproject.toml`、`requirements-lock.txt`、`.github/workflows/tests.yml`、`evals/v1_capability_cases.json`、`evals/evaluator.py`、`RELEASE_V1.0.md`、`PILOT_PLAN.md`、相关源码、测试与规格文档。

**Acceptance Criteria**：满足 `PRODUCT_SPEC.md` 第 17.3 节全部要求，V0.1—V0.9 行为不回退，不新增业务 Tool。

**Validation Command**：

```bash
python -m pytest -q
python -m pytest -q -m live
hragent
python -m src.main
```

**Status**：DONE

**Implemented**：已建立 V0.9 基线 commit 与 `v0.9.0` tag；统一敏感信息/凭据检测和私有原子写入；把简单 Tool 执行改为注册表并保持 28 个 Tool 唯一；增加运行根目录解析，避免安装后把数据写入 `site-packages`；提供标准 wheel 安装、`hragent` 入口、精确依赖锁和 Python 3.11—3.13 CI；增加 V0.2—V0.9 共 24 个跨版本评测案例、确定性检查器、API 数据披露、发布清单和匿名化试点计划。现有 State、知识库、解析产物和报告目录/文件已收紧为仅当前用户访问。

**Tests**：新增 11 项离线加固测试；完整离线回归 `245 passed, 21 deselected`；最终代码状态下完整真实 DeepSeek 回归 `21 passed, 245 deselected`。`hragent`（含项目外目录）与 `python -m src.main` 启动/退出通过，`pip check`、Python 3.11/3.12/3.13 `compileall`、TOML/YAML/JSON 解析、28 Tool 唯一性、精确依赖比对、权限检查、密钥模式扫描和 `git diff --check` 通过。密钥扫描仅命中两条用于拒绝凭据的虚构测试值。

**Known Limitations**：V1.0 仍是本地单用户 CLI，不承诺多人并发、企业级权限、云同步或真实员工敏感数据生产使用。完整测试本地运行环境为 Python 3.13；Python 3.11/3.12 已完成源码编译检查，完整依赖与离线回归由 CI 矩阵验证。真实客户匿名化试点尚未执行，不能把 RC 视为生产合规认证。
