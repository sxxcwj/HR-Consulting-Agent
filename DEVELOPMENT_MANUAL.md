# HR Consultant Agent 开发复盘与操作手册

适用版本：V1.0 Release Candidate（`1.0.0rc1`）  
本次维护范围：M21，开发复盘、现有功能加固与操作文档  
编制日期：2026-09-30

## 1. 结论与使用定位

这个项目已经从“五段式 HR 顾问问答”，发展为具备确定性计算、Excel 描述统计、文件知识库、本地 RAG、显式项目 State、显式 Memory 和 Markdown 报告的单 Agent CLI。

当前适用于本地单用户、虚构或获得授权的匿名化数据、有人复核的咨询辅助；不等于企业生产系统，不应直接处理未经授权的员工敏感资料，也不得自动决定录用、淘汰、调薪或处分。

本手册以当前源码、规格、PLAN、Git 记录和留存测试证据为依据。版本能力不代表真实业务效果；自动测试通过不代表不存在任何幻觉、安全漏洞或合规风险。历史验收与本次验收分开记录，见第 12 节。

阅读路径：首次使用看第 4—5 节；理解开发过程看第 2 节；维护代码看第 3、6—8 节；发布和排障看第 9—11 节。

## 2. 整个项目的开发过程

### 2.1 先确定产品，再逐版本增加能力

最初没有立即写代码，而是先建立产品与行为契约，再按 Milestone 实现。其价值是把“顾问应怎样回答”“软件应实现什么”“开发到哪里停止”分开管理。

| 阶段 | 核心交付 | 解决的问题 | 保留的边界 |
|---|---|---|---|
| 需求设计 | PRODUCT_SPEC、AGENT_SPEC、WORKFLOW、AGENTS、PLAN | 先定义目标、角色、流程、规则与验收 | 不随意加功能 |
| V0.1，M1—M8 | Python CLI、API 连接、独立 Prompt、错误处理、测试 | 用户输入 HR 问题，得到结构化分析 | 不编造数据，信息不足说明；五段回答 |
| V0.2，M9 | `calculate_turnover_rate` | 离职率由代码精确计算，不由模型心算 | 缺分母不猜测 |
| V0.3，M10 | Excel Reader、20 条虚构样例 | 读取 Sheet、字段、类型、缺失和预览 | Reader 不作业务分析，敏感预览脱敏 |
| V0.4，M11 | 五类 Analytics | 人数、薪酬、离职、绩效和缺失的基础统计 | 统计事实不等于管理结论，不修改原数据 |
| V0.5，M12 | Loader、Parser、Registry、Reader | 回答“企业文件里写了什么” | 实际读取才引用；同名/版本冲突需确认 |
| V0.6，M13 | 分块、本地中文 Embedding、向量检索 | 跨文件找相关内容，附来源与范围 | 不把相似度当制度有效性；不做复杂检索 |
| V0.7，M14 | 显式项目 State | 保存咨询项目目标、阶段、确认事实和引用 | 用户明确要求才保存，不保存完整聊天 |
| V0.8，M15 | 显式长期 Memory | 保存稳定偏好、组织背景、术语、长期约束 | 不自动提取；不保存敏感员工信息 |
| V0.9，M16 | Markdown 报告草稿 | 把已取得的证据与建议形成可追溯交付物 | Generator 不读取上游、不创造事实、不自动发送 |
| V1.0 RC，M17 | Git、CLI 安装、权限、注册表、依赖锁、跨版本评测、CI | 从“能运行”变为“能安装、能验证、能维护” | 不新增业务能力，不宣称生产认证 |
| 项目 Skill | 薪酬诊断方法包 | 将顾问方法拆为可复用开发指导 | 当前不是 Python 自动加载的运行时 Skill |
| M18 | Responses API Streaming、终端颜色 | 区分输入与回答，保留最终结果与工具调用 | 不打印 SDK 内部事件 |
| M19 | 16 案例合成模拟试点、差距报告 | 从真实模型执行中找稳定性问题 | 不把模拟试点当真实客户试点 |
| M20 | 两个 P0 修复、相同案例连续三轮复验 | 修复中间工具轮文本泄露与流式格式恢复缺陷 | 48/48 是当时冻结版本证据 |
| M21，本次 | 格式修复禁用 Tool、保留工具证据、解析错误兜底、此手册 | 防止修复时重复写入；使开发过程可复用 | 不新增 Tool、不升级生产权限 |

### 2.2 技术路线的实际演变

原始需求提出 OpenAI 官方 Python SDK，随后按用户要求使用 DeepSeek 密钥与模型。当前实现是 **OpenAI 官方 Python SDK + DeepSeek OpenAI 兼容 Responses API + 本地 Function Calling 循环**，不是 OpenAI Agents SDK。

因此不要把 `Runner.run_streamed()` 的示例机械复制进当前代码。现有非流式入口是 `HRConsultant.ask()`，流式入口是 `HRConsultant.ask_streamed(..., on_text_delta=...)`，底层使用 `client.responses.create()` / `client.responses.stream()`。

本地 RAG 默认用 `BAAI/bge-small-zh-v1.5`，不需要 OpenAI Embedding 密钥。向量索引存在 `knowledge/vector_index.sqlite3`，是 V0.6 已有、可重建的本地缓存，不是企业业务数据库；V1.0 禁止新增业务数据库或外部向量服务，并非要求删除已有索引。

### 2.3 开发中出现的典型问题及经验

| 问题 | 原因与解决方法 | 可复用经验 |
|---|---|---|
| 在 `%` 后输入“你好”报 command not found | 当时处于 zsh，不是 Agent；先启动程序 | 区分 shell 命令与 Agent 输入 |
| `.venv/bin/python` 不存在 | 当前目录是用户家目录，不是项目根目录 | 先 `cd`，或使用绝对入口 |
| HTTP 401 与“无法连接”混淆 | 401 是认证类反馈；网络错误与认证错误分别处理 | 不把服务端拒绝统称网络不通 |
| “基于当前项目生成报告”报 project_not_found | 没有选中项目，不能伪造项目上下文 | 显式创建/选择；不是所有报告都必须有 State |
| “平均薪酬最高”被误解为“薪酬不合理” | 统计事实缺岗位、职级和市场依据 | 把数据事实、中性描述、假设、管理结论分层 |
| 原模拟试点 14/16，Tool 都命中 | 算对不代表回答交付成功；流文本与结构也会失败 | 测工具执行、最终结果和可见输出三个层面 |
| 流式工具中间轮与最终结果不一致 | 累计显示了工具调用前说明 | 中间轮完整消费但不显示，只交付最终轮 |
| 坏格式已经写到终端后无法撤回 | 终端显示不可逆 | 当前先缓存、校验/修复，再显示 |
| 格式修复可能再次调用写入 Tool | 修复原来复用完整工具循环 | 本次修复只使用已有证据，不开放 Tool |

### 2.4 Git 历史的证据边界

本仓库首个 Git 基线提交已包含 V0.9；V0.1—V0.8 的阶段依据来自规格、PLAN 和测试，不存在可逐版恢复的独立 Git 提交，不能补造开发日期或声称每版都有 tag。

| Git 提交 | 日期 | 记录 |
|---|---|---|
| `dca39c9` | 2026-09-28 | 建立 V0.9 基线 |
| `803a4c2` | 2026-09-28 | V1.0 RC 加固 |
| `9adfefa` | 2026-09-28 | 薪酬诊断项目 Skill |
| `71f6d58` | 2026-09-28 | CLI 流式输出 |
| `4ab7665` | 2026-09-28 | 终端颜色 |
| `a9574a7` | 2026-09-29 | 匿名化合成试点 |
| `193518e` | 2026-09-29 | 显示前校验与流式 P0 修复 |

本次 M21 是否已提交应以 `git status` / `git log` 为准；本手册不替用户自动提交、打新 tag 或发布。

## 3. 当前架构与职责

### 3.1 核心目录

```text
hr_agent/
├── PRODUCT_SPEC.md / AGENT_SPEC.md / WORKFLOW.md
├── AGENTS.md / PLAN.md / README.md / DEVELOPMENT_MANUAL.md
├── RELEASE_V1.0.md / PILOT_PLAN.md / PRODUCTION_READINESS_GAP_REPORT.md
├── pyproject.toml / requirements.txt / requirements-lock.txt / .env.example
├── src/
│   ├── main.py              # CLI、颜色、环境加载、安全错误提示
│   ├── agent.py             # 模型调用、工具编排、格式校验与结果提交
│   ├── prompts.py           # Agent instructions 与格式修复指令
│   ├── config.py            # 运行数据根目录
│   ├── security.py          # 敏感信息规则、私有目录与原子写入辅助
│   ├── tools/               # 离职率计算、Excel 读取
│   ├── analytics/           # 仅接收内存记录，完成统计
│   ├── knowledge/           # 文档解析/登记/读取，以及独立 RAG 层
│   ├── state/               # 项目 State
│   ├── memory/              # 显式长期 Memory
│   └── reports/             # Markdown 草稿校验与保存
├── tests/                   # 单元、集成、CLI、错误与真实 API 测试
├── evals/                   # 冻结案例、评测器、试点脚本、历史证据
├── data/sample_employees.xlsx
├── knowledge/documents/     # 原文；自带五份完全虚构 Markdown
├── knowledge/parsed/        # 已登记文档的标准化解析结果
├── knowledge/index.json     # 文档 Registry
├── knowledge/vector_index.sqlite3  # 可重建向量索引
├── state/projects.json / state/memories.json
├── reports/generated/       # 生成的 Markdown 草稿
├── .codex/skills/compensation-diagnosis/
└── .github/workflows/tests.yml
```

运行产物不一定都存在于新安装环境中；不要把目录示意当作已成功创建文件的证据。

### 3.2 三条核心数据流

```text
用户问题 → HR Agent → Excel Reader → 内存 records → Analytics → 结构化统计 → Agent解释
用户文件 → Loader → Parser → Document → Registry → Reader 或 RAG → 文件依据 → Agent解释
明确保存请求 → State / Memory；明确报告请求 → 上游证据 → Report Generator → Markdown草稿
```

Agent 是选择与解释层，不是计算器或文件解析器。分析模块不直接读 Excel；Excel Reader 不判断薪酬公平；Report Generator 不偷偷重新检索资料。

对模型开放的 Analytics Tool 接收 `file_path` 等参数；`agent.py` 的适配层先调用 `read_excel_data()`，再把真实 `records` 传给分析函数。它不是把前五行预览当成全量数据。工具轨迹里的 Reader 可以包含模型显式读取和适配层自动读取，所以同一问题出现两次 Reader 不一定是重复统计 Bug。

### 3.3 当前 28 个 Tool

| 工具组 | 注册的 Tool 名称 | 职责与限制 |
|---|---|---|
| 公式计算，1 | `calculate_turnover_rate` | 有足够人数依据才算离职率 |
| Excel，1 | `read_excel_metadata` | 元数据与脱敏预览，不做业务统计 |
| Analytics，5 | `calculate_headcount`、`analyze_compensation_summary`、`calculate_turnover_analysis`、`analyze_performance_summary`、`analyze_missing_data` | 描述统计、基础分组与明确公式 |
| Knowledge，4 | `register_knowledge_document`、`list_knowledge_documents`、`get_document_metadata`、`read_knowledge_document` | 解析登记、精确读取与来源 |
| RAG，3 | `build_knowledge_index`、`get_knowledge_index_status`、`search_knowledge_base` | 本地分块/向量/检索，不裁决制度版本 |
| State，6 | `create_project_state`、`list_project_states`、`get_project_state`、`select_project_state`、`update_project_state`、`archive_project_state` | 显式项目上下文，不自动写入 |
| Memory，7 | `save_memory`、`list_memories`、`get_memory`、`search_memories`、`update_memory`、`archive_memory`、`forget_memory` | 显式稳定上下文，搜索为关键词匹配 |
| Report，1 | `generate_hr_report` | 保存可追溯 Markdown 草稿，不自动发送 |

工具定义集中汇入 `src/agent.py:REGISTERED_TOOLS`；简单执行器由 `SIMPLE_TOOL_HANDLER_NAMES` 映射；计算和 Analytics 有专门适配。保留名称唯一性，不为每个文档新建 Tool。

### 3.4 证据层级与输出协议

一般 HR 分析使用五个非空一级标题，名称和顺序固定：问题判断、可能原因、需要补充的信息、建议措施、下一步行动。纯文件列表、元数据、State、Memory、报告结果等有既有专项输出协议；不能要求所有操作结果都硬套五段，也不能用内部前缀绕过正式分析校验。

| 类型 | 可以表达 | 不能直接推出 |
|---|---|---|
| FACT / USER_CLAIM | 用户提供事实与用户观点分开标记 | 用户主张已经被外部核验 |
| DATA FACT | Tool 算出的记录数、均值、离职率 | 部门管理好坏、员工应被淘汰 |
| DOCUMENT_FACT | 成功读取的制度条文 | 企业现实中已经按条文执行 |
| PROJECT_CONTEXT | 用户确认保存的项目输入 | 外部调查或业务验证结论 |
| MEMORY_CONTEXT | 曾明确保存的稳定上下文 | 当前仍有效，或可覆盖真实文件证据 |
| HYPOTHESIS | 待验证的可能原因 | 确定原因或因果关系 |
| RECOMMENDATION | 有边界的管理建议 | 正式法律意见或自动人事决定 |

来源优先级与事实等级是两个维度：企业文件优先回答“我们公司规定什么”，但文件内容本身仍不是实际执行证据。

### 3.5 Skill、Prompt、Tool 的区别

`.codex/skills/compensation-diagnosis/` 是给 Codex 开发协作使用的方法包；其目录位置符合项目 Skill 的发现习惯。当前 Python Runtime 没有扫描或自动加载这个目录，相关测试检查方法包文件与契约，并不证明运行中的模型自动执行了 Skill。

`src/prompts.py` 才是当前模型实际收到的 instructions；Tool 是确实执行的 Python 函数。不要把“已建 Skill 文件夹”写成“已增加自动诊断业务能力”，也不要为了目录美观新增运行时 Skill 框架。

## 4. 安装与启动操作

### 4.1 新环境

以下命令在项目根目录执行。先确认 Python 3.11+。

```bash
cd /path/to/hr_agent
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install ".[dev]"
python -m pip check
```

开发时可用 `python -m pip install -e ".[dev]"`，让源码修改直接生效；普通非 editable 安装后，修改源码并不会同步更新已安装包，需重新执行安装命令。不要仅修改仓库然后误测旧的 `hragent`。

`pyproject.toml` 是包依赖与入口的主要来源；`requirements.txt` 兼容旧安装习惯；`requirements-lock.txt` 是已验证 macOS/Python 3.13 的精确版本快照，不保证能在所有平台照搬。

复现该锁定环境：先安装 `requirements-lock.txt`，再 `python -m pip install . --no-deps`。本次环境依赖已完整存在，因此重新安装本项目时使用 `--no-deps --no-build-isolation`；初次安装不要随意使用这两个参数。

### 4.2 密钥与运行目录

若 `.env` 已存在，直接编辑，**不要覆盖**。若不存在，可复制模板并限制权限：

```bash
cp -n .env.example .env
chmod 600 .env
```

用本地编辑器填写 `DEEPSEEK_API_KEY`，不要把密钥发到聊天、写进源码、终端记录或测试结果。此前公开过的密钥应在服务商侧吊销并重新生成。

| 变量 | 当前含义 |
|---|---|
| `DEEPSEEK_API_KEY` | 必需的 Agent API 密钥，不是 OpenAI 密钥 |
| `DEEPSEEK_MODEL` | 模型配置，当前代码默认 `deepseek-flash` |
| `HR_AGENT_HOME` | 所有运行数据与 CLI `.env` 查找的根目录 |
| `HR_AGENT_EMBEDDING_MODEL` | 可选本地 Sentence Transformers 模型 |
| `NO_COLOR` | 设置后关闭终端颜色 |

环境变量优先于 `.env`。只配置 `OPENAI_API_KEY` 不能让当前 DeepSeek Agent 工作；本地 Embedding 不需要新增密钥。首次模型下载可能需要网络与磁盘空间。

`HR_AGENT_HOME` 应在启动 Python 前设置，因为根目录在模块导入时确定。未设置时：当前项目根目录 → 可识别的源码根目录 → 安装包在其他目录运行时使用 `~/.hragent`。

要从任意目录继续使用本项目已有资料，在自己的 shell 配置中设置一次：

```bash
export HR_AGENT_HOME='/path/to/hr_agent'
```

### 4.3 最简单的启动方式

激活虚拟环境后：

```bash
hragent
```

未激活时，在项目目录：

```bash
.venv/bin/python -m src.main
```

任意目录也可以使用完整可执行路径：

```bash
HR_AGENT_HOME='/path/to/hr_agent' /path/to/hr_agent/.venv/bin/hragent
```

等到“请输入企业人力资源管理问题：”出现再输入 HR 问题；不要把这个提示文本当成 shell 命令。支持 `退出`、`exit`、`quit`、`q` 结束。当前进程内成功问答会成为后续上下文，退出后不保存完整聊天。

### 4.4 Streaming 的真实行为

当前完整消费 SDK 流，只收集 `ResponseTextDeltaEvent`，对应 `response.output_text.delta`。工具调用中间轮的文字不显示；最终轮先完成前缀处理、结构校验及最多一次修复，再按原 delta 顺序显示。

**这是原生流式传输加安全缓存，不是“模型生成一个 token 就立即显示一个 token”。** 首字仍需等待最终轮完成。不要把它宣传为即时逐字体验。

修复请求携带本轮实际 Tool 结果，但 `tools=[]`；若服务仍返回 Function Call，本地拒绝执行。SDK 严格参数解析失败最多做一次兼容重试，本地参数验证不会放宽；再次失败返回简洁错误。成功后保留 `last_response` 与 `last_final_output`。

交互式 TTY 中输入青色、回答绿色；管道、重定向或 `NO_COLOR=1 hragent` 使用纯文本。

## 5. 各功能的实际操作

### 5.1 HR 问答与离职率

```text
我们公司大约200人，最近销售人员离职明显增加，管理层认为是薪酬问题，应该如何分析？
公司年初200人，年末180人，全年离职30人，离职率是多少？
今年离职30人，离职率是多少？
```

第一个问题必须区分用户主张和原因假设；第二个问题实际 Tool 返回平均人数 190、离职率 15.79%；第三个问题缺分母，应询问平均人数，或同时补充期初/期末人数，不猜测。

开发者可独立验证确定性 Tool，无需 API 密钥：

```bash
python -c "from src.tools import calculate_turnover_rate; print(calculate_turnover_rate(leavers=30, starting_headcount=200, ending_headcount=180))"
```

统计期间与人数口径仍由用户确认；算式正确不代表统计口径正确。

### 5.2 Excel 读取与分析

提供绝对文件路径，多 Sheet 时同时指定名称：

```text
请读取 /path/to/hr_agent/data/sample_employees.xlsx，这个文件有哪些字段？
请读取同一文件，各部门有多少人？
请读取同一文件，各部门 monthly_salary 的平均工资是多少？
请读取同一文件，各部门 performance_score 的平均分是多少？
请读取同一文件，哪些字段有缺失值？
```

“同一文件”依赖当前会话已提供的路径；新进程重新提供。Reader 只支持 `.xlsx`，不会写回原文件。样例是 20 条完全虚构记录、8 个字段，并有人为缺失。

| 分析函数的 Python 输入 | 主要输出 | 解释约束 |
|---|---|---|
| `calculate_headcount(data, group_by=None)` | `total_headcount`、`groups`、计数规则 | 每条记录计一人，不自动去重或推定在职总数 |
| `analyze_compensation_summary(data, salary_field, group_by=None)` | count、mean、median、min、max、missing_count | 缺失薪酬不参加均值，保留总记录数与缺失数 |
| `calculate_turnover_analysis(data, ..., average_headcount=None, starting_headcount=None, ending_headcount=None)` | 在职/离职/未知状态人数、各部门离职人数、可选离职率 | 不从静态快照推测期间平均人数；不提供自动期间筛选 |
| `analyze_performance_summary(data, performance_field, group_by=None)` | 有效样本、缺失、均值、中位数和极值 | 不自动标记低绩效员工或决定淘汰 |
| `analyze_missing_data(data, fields=None)` | 各字段缺失数量与比例 | 不自动填补数据 |

分析数据有多条时期记录、重复员工或不明确的状态口径时，先说明限制。当前人数 Tool 不做员工 ID 唯一性去重；“20 条记录”不能在所有文件中都等同于“20 位独立在职员工”。

### 5.3 企业文件：放入、登记、读取

支持 `.txt`、`.md`、`.docx`、文本型 `.pdf`。不支持扫描 PDF OCR，也不把 `.xlsx` 作为企业文档解析。

放入 `knowledge/documents/` **不等于登记成功**。Agent 中可明确请求导入；也可直接登记模拟文件：

```bash
python -c "from src.knowledge import register_document; print(register_document('knowledge/documents/02_薪酬管理制度.md'))"
python -c "from src.knowledge import list_documents; print(list_documents())"
```

登记会解析原文，生成统一 `Document`，把 metadata 放入 `knowledge/index.json`，解析文本放入 `knowledge/parsed/`。Document 含 `document_id`、`file_name`、`file_type`、`title`、`text`、`character_count`、`created_at`、`source_path`、`metadata`、`parse_status`；metadata 包含内容摘要、文件大小与时间等。

```text
知识库里有哪些文件？
根据薪酬管理制度，年度调薪是什么时候？请说明来源。
绩效制度规定多久进行一次绩效沟通？
```

来源应来自实际读取结果，不是模型一般知识。Reader 默认单次 4000 字符，最多 6000 字符；超过时按 `start` / `end` 分段继续，不把截断结果误作整份制度。

同名文件、多个版本或相互冲突的制度：先展示候选来源与 metadata，再让用户确认有效版本。不能仅凭文件名含“2026”就认定有效；文件规定也不代表实际执行。

### 5.4 RAG：登记之后再建立索引

```bash
python -m src.knowledge.rag_cli build
python -m src.knowledge.rag_cli status
python -m src.knowledge.rag_cli search "年度调薪什么时候进行" --top-k 3
```

默认分块大小 500 字符、重叠 80 字符；CLI 可指定 `--chunk-size` 和 `--overlap`。登记新增、变更或删除后检查状态，过期时重新 `build`。源文件修改后应重新登记，不能以旧解析副本证明已读取最新原文。

```text
公司制度里关于绩效奖金有什么规定？请引用实际来源。
请在所有文件中找与年度调薪相关的5段内容。
```

明确文件优先精确 Reader；跨文件或未指定文件才使用 RAG。返回来源、document_id、片段字符范围；相似度只排序，不证明文件有效、规定合规或已执行。

### 5.5 Project State：项目专属上下文

```text
请创建一个项目，名称是销售离职诊断，目标是识别销售人员离职增加的原因，公司约200人。
把“销售人员离职增加是管理层观察，尚未核实离职率”保存到当前项目。
把“需要统计期间和平均销售人数”记录为待补信息。
有哪些项目？
继续当前项目，请显示状态。
```

创建后自动选中；已有项目切换时使用列表实际返回的 `project_id`，不能把示例 `PRJ-XXXXXXXXXXXX` 当真实 ID。JSON 位于 `state/projects.json`。归档不删除源文档，也不能继续更新归档项目。

`project_not_found` 表示没有相应项目/当前选择，并非 API 失效。用户只是普通提问时不要自动创建项目。读取 State 后的内容属于 PROJECT_CONTEXT，不是新取得的文件/数据证据。

### 5.6 Memory：跨项目稳定上下文

```text
请记住：回答默认用简洁中文。
请记住：我们将员工称为伙伴，这是内部术语。
你记住了什么？
你记得我们公司的考勤口径吗？
```

支持 `preference`、`organization`、`terminology`、`standing_instruction` 四类，位于 `state/memories.json`。更新、归档、彻底忘记均用真实 memory_id 且需明确请求。

不要把项目进度写进 Memory；不要把 Excel 数据、制度全文、员工个人工资、处分或投诉保存进去。Memory 检索是关键词匹配，不是 RAG；可能过期内容先核实。

### 5.7 Markdown 报告

```text
请根据我刚才提供的信息生成一份销售离职诊断报告；离职增加尚未核实，薪酬只是管理层假设。
请基于当前项目生成HR报告。
请读取薪酬管理制度，并根据实际内容生成制度摘要报告。
```

第一类可基于当前用户输入，不必强制创建项目；第二类必须有可读取的当前项目；第三类必须实际读取文件。找不到项目时可以选择/创建项目，或由用户明确改为基于本轮输入，不能悄悄换报告依据。

Generator 输入：title、executive_summary、problem_assessment、evidence、possible_causes、missing_information、recommendations、next_actions、assumptions_and_limitations、source_references。

报告固定九部分：执行摘要、问题判断、已知事实与依据、可能原因、需要补充的信息、建议措施、下一步行动、假设与限制、来源索引。成功返回真实 report_id 与绝对路径，保存在 `reports/generated/`；标记为自动生成草稿，仅支持 Markdown。

### 5.8 完整链路示例：Excel → Analytics → Agent

输入：读取样例文件，询问各部门平均工资。

本次独立执行 Reader 与 `analyze_compensation_summary(..., salary_field='monthly_salary', group_by='department')`，实际取得：

| 部门 | 有效样本数 | 缺失薪酬数 | 平均月薪 |
|---|---:|---:|---:|
| 销售部 | 4 | 0 | 7566.75 |
| 技术部 | 3 | 1 | 9596.83 |
| 运营部 | 4 | 0 | 11417.75 |
| 人力资源部 | 4 | 0 | 13343.25 |
| 财务部 | 4 | 0 | 15268.75 |

这是虚构样例的统计事实，不是真实客户的薪酬现状。Agent 可以中性说明财务部平均月薪最高；不能直接说财务部过度支付。技术部均值仅含 3 个有效样本，缺失值未填补。真实模型完整链路结果留存于本次模拟复验 JSON，见第 12 节。

## 6. 开发标准操作流程

每次只做一个当前授权 Milestone，不因为现有目录方便就增加未来能力。

1. 阅读 `AGENTS.md`、产品相关章节、`AGENT_SPEC.md`、`WORKFLOW.md`、当前 PLAN 和 README。
2. `git status --short` 核对用户已有修改；保留无关改动，不 reset 或覆盖。
3. 记录 Milestone：Objective、Tasks、Files、Acceptance Criteria、Validation Command、Status。未开始 TODO，执行中 IN_PROGRESS，验证完成才 DONE。
4. 运行改动相关基线测试；明确要修复的失败、边界与证据，不能仅凭印象改 Prompt。
5. 最新用户要求与旧规格冲突时先同步适用规格，再做最小实现。
6. 在正确职责层修改：Reader 读、Analytics 算、RAG 检索、State/Memory 显式保存、Report 排版、Agent 编排、CLI 显示。
7. 先验证程序行为，再运行新增/相关测试、错误路径和全量离线回归。
8. 涉及模型编排时追加真实 API 验证，使用虚构数据和隔离运行目录，保留失败证据。
9. 对照 Acceptance Criteria、Agent 边界和工作流；失败先修复，不降低门槛或删测试。
10. 更新 README、PLAN、评测记录和已知限制；如实报告未验证项，完成后停止。

关键函数使用 type hints，代码清晰、职责单一；复杂约束写简洁注释。密钥不得硬编码；Tool 错误应是清晰结构化结果，Agent/CLI 错误应为安全可理解文本。

### 6.1 按改动选择测试

| 修改对象 | 至少检查 |
|---|---|
| CLI / 颜色 / 启动 | `test_cli.py`、`test_project_smoke.py`、真实入口 |
| API / 格式恢复 / Streaming | `test_agent.py`、`test_api_client.py`、`test_errors.py`、`test_streaming.py` |
| 计算 / Excel / Analytics | 对应单元测试 + `test_*integration.py` + 样例链路 |
| 文档 / RAG | Loader/Parser/Registry/Reader、chunking/embeddings/vector_store、RAG 集成 |
| State / Memory / Report | store/generator 与工具单元测试、集成测试、隐私和写入失败 |
| Prompt / 行为规格 | instructions、固定案例、真实模型、人工证据复核 |
| 打包 / 配置 / 依赖 | release_hardening、源码与已安装 CLI、项目外目录、pip check |

这不是只跑对应测试的免责清单；现有完整离线回归仍应通过。

### 6.2 以后若授权新增 Tool

先更新版本范围和规格，再编写独立函数与输入验证、结构化输出、错误处理；定义 Function schema 与清晰调用条件；接入现有注册/适配机制；测正确调用、无需调用、缺信息、恶意或错误参数、工具失败及原功能回归。

目前 V1.0 不授权新增业务 Tool，也不预建下一版接口。禁止为了“完善”擅自加入数据库、多人系统、Web UI、MCP、机器学习、复杂薪酬诊断或 Word/PDF 报告。

## 7. 测试与评测操作

### 7.1 离线测试与静态检查

```bash
python -m pytest -q
python -m pytest -q tests/test_agent.py tests/test_streaming.py tests/test_errors.py tests/test_api_client.py
python -m compileall -q src tests evals
python -m pip check
git diff --check
```

默认 pytest 排除 live 测试，模拟客户端不请求远程模型。没有报错不等于测试运行过；检查通过数、跳过/排除数与退出码。

### 7.2 真实 API 测试

会产生真实 API 调用与费用；使用虚构测试问题。当前测试不会自动加载 `.env`，CLI 才会。若密钥仅在 `.env`，在项目目录运行：

```bash
python -c 'from dotenv import load_dotenv; load_dotenv(".env", override=False); import pytest; raise SystemExit(pytest.main(["-q", "-m", "live"]))'
```

如果已配置进程环境变量，直接 `python -m pytest -q -m live`。RAG 在线测试需要已准备好的本地模拟索引；测试可能跳过，不应把 skipped 写成通过。

在线 State/Memory/Report 选择测试替换写入执行器以免修改正式资料；它们证明模型选择了 Tool，不单独证明真实持久化已经完成。完整持久化链路由离线临时目录测试和隔离模拟试点补充。

### 7.3 四套案例的不同用途

| 案例文件 | 数量 | 用途 |
|---|---:|---|
| `acceptance_cases.json` | 12 | V0.1 固定验收，含连续对话 |
| `test_cases.json` | 24 | 八类 HR 问题，人工七维质量复核 |
| `v1_capability_cases.json` | 24 | V0.2—V0.9 工具选择和边界契约 |
| `pilot_cases.json` | 16 | 真实模型、匿名化合成场景、流式/最终结果完整链路 |

不要将案例数量和 pytest 项目数量相加称为“独立样本总数”，其中存在重复覆盖。

已有跨能力回答可用 `python -m evals.evaluator --cases evals/v1_capability_cases.json --results /实际路径/recorded_results.json` 做确定性检查。评测器不替你运行 Agent，也不以关键词匹配代替人工判断。

### 7.4 安全执行模拟试点

```bash
python -m evals.pilot_runner --cases evals/pilot_cases.json --results evals/pilot_results_new_run.json
```

`new_run` 是命名示例，每次改成新的唯一名称，**不要覆盖历史证据**。脚本自动加载项目 `.env`，在导入业务模块前设置临时 `HR_AGENT_HOME`，登记五份虚构文档并构建本地索引，运行16个案例。临时 State、Memory、索引与报告结束后清理；正式目录不受影响。

检查完成无异常、预期 Tool、禁止 Tool、必要/禁止文本、五部分结构、stream/final 一致性与明显敏感信息。原始回答有随机性；一次16/16不能替代连续三轮门槛，更不能替代真实用户试点。

### 7.5 连续三轮门槛如何执行

在计划进入授权真实业务试点前，冻结代码、Prompt、案例和预期契约；相同16案例连续执行三轮，各自使用新临时目录与独立结果文件。每轮16/16、合计48/48，无阻断失败、禁止 Tool 为0。保存执行时间、模型、代码/案例摘要与结果摘要。

任何修复后的旧失败不能删掉；中途修改代码要重新冻结并重跑完整三轮。历史48/48只对其记录的源码摘要有效。本次改变 `agent.py` 后，不能将历史三轮算作当前代码的三轮验证；具体本次结果见第12节。未完成新的三轮与业务授权前，不启动真实业务试点。

## 8. 本次功能完善：具体改了什么

本次没有增加业务能力、Prompt、Skills 或 Tool；只补现有编排与异常控制。

1. **修复上下文保留**：格式修复携带本轮已取得的 Function Call 与实际 Tool Result，而非仅用用户问题和坏格式文本重新开始。
2. **禁用修复中的 Tool**：正常循环照常注册28个 Tool，修复请求传 `tools=[]`；服务若仍返回调用，本地直接停止，不能重复创建项目、保存 Memory 或生成报告。
3. **保持正式回答合同**：修复后的正式分析仍必须通过五段校验，不能通过改成内部专项前缀绕过。
4. **解析失败受控**：流式 SDK JSON 解析的兼容重试耗尽后转成 `AgentError`，不把原始载荷或 traceback 给普通用户，当前 CLI 允许再输入。
5. **专项回归**：新增7个测试，覆盖流式与非流式证据保留、拒绝写入 Tool、结构绕过、重复解析失败与禁用工具的兼容重试。

不承诺自动回滚：Tool 在最终回答前已经成功写入的 State/Memory/报告，回答失败后可能仍存在；不提交聊天历史不等于写入回滚。用户重试前先列出项目/记忆或检查报告路径，避免重复请求。当前没有跨工具事务或通用幂等机制，不应在本次擅自搭建。

## 9. 安装包与发布操作

1. 在明确授权的版本范围内完成实现，保留 Git diff 和所有原始评测。
2. 全量离线测试、适当在线验证、pip check、compileall、diff check。
3. 普通非 editable 安装重新 `python -m pip install ".[dev]"`，验证安装成功，再测试 `hragent`。
4. 项目根目录测兼容入口，项目外目录用绝对 CLI + 明确 `HR_AGENT_HOME`；核对实际模块路径，防止源码测试/安装包测试混淆。
5. 检查包不含 `.env`、企业原文、解析文本、项目/Memory数据、报告及模型缓存。当前打包范围为 `src*`，样例与文档需作为仓库资料另外取得。
6. 保持精确锁与验证环境一致；升级依赖要明确动机并独立回归，不为消除更新通知而升级所有库。
7. 更新发布说明和已知限制，检查 CI 的实际运行结果；“配置了矩阵”不等于本轮在所有平台执行成功。
8. 只有取得提交/发布授权才 commit、打 tag 或推远端；本手册不自动执行这些外部或版本状态变更。

V1.0 是 RC，仍不授予生产准入。新的企业级权限、安全、治理或部署能力需要新规格与单独计划。

## 10. 数据安全、备份与恢复

### 10.1 API 与本地数据边界

DeepSeek 会收到系统指令、本轮问题、当前进程成功历史、工具定义及工具返回内容。原文件不作为附件自动上传，但文件片段、RAG片段、脱敏预览、统计和显式上下文可能进入 API 请求。

当前只有有限正则/字段脱敏，**不是完整 DLP**；直接输入的用户问题不会得到全面自动匿名化。昵称、组合身份、上下文可再识别信息和非标准敏感字段仍可能遗漏。因此真实试点前先人工匿名化，审查供应商政策并获得企业授权。

POSIX 新建运行目录0700、持久化文件0600，只防普通系统用户访问；不提供静态加密、身份认证、租户隔离或防管理员读取。报告和评测 JSON 也可能含企业信息，应按其敏感程度控制访问，不公开传播。

### 10.2 备份清单

停止正在写入的 Agent，再复制到专用私有备份目录：企业原始文件、Registry、parsed、projects.json、memories.json、已生成报告。`.env` 如需备份，单独加密保管，不进入 Git 或评测资料。索引可重建，复制SQLite时避免同时写入。

Git tag 不包含忽略的运行数据。恢复前先保留当前数据副本，再切换经过验证的代码版本或安装包，检查 schema 与依赖兼容。不要用 `git reset --hard` 恢复用户数据，也不要删整个 workspace。

模拟试点临时报告路径在运行结束后不再存在；其生成事实由执行时的结果和检查证明，不应声称现在仍能打开那个临时文件。

## 11. 常见故障排查

| 现象 | 先检查 | 处理 |
|---|---|---|
| `zsh: command not found: 你好` | 是否只见 `%` 而非中文提示 | 先启动 Agent，再输入问题 |
| `.venv/bin/python` 不存在 | `pwd`、虚拟环境位置 | 进入项目目录或用绝对路径 |
| `hragent` 不存在 | 是否已安装包、激活 `.venv` | 重新安装，或用 `.venv/bin/hragent` |
| 缺依赖 | 当前 Python 与 pip 是否同一环境 | 使用 `python -m pip`，按项目安装，不全局乱装 |
| 缺少密钥 | `.env` 在哪个运行根目录、变量名是否正确 | 配置 DEEPSEEK_API_KEY；不在聊天提交密钥 |
| 401/认证失败 | 密钥所属服务、吊销/失效、环境变量是否覆盖新值 | 安全更新密钥，重新启动；不是换Prompt |
| 402/余额不足 | 账户余额与授权 | 补足额度或稍后重试，不改代码伪装成功 |
| 429/受限 | 请求频率与服务额度 | 降低频率、稍后重试 |
| 无法连接/超时 | 网络、DNS、代理、服务状态 | 修复连接后重试，不假装模型已回答 |
| Excel失败 | 文件路径、扩展名、损坏、多Sheet | 指定可读 `.xlsx` 与正确 Sheet |
| 统计字段失败 | 名称、类型、空数据、全部缺失 | 修正输入或承认无足够统计依据，不填补业务数据 |
| PDF无文本 | 是否扫描件或不可读 | 返回明确错误；当前不支持OCR |
| 找不到制度 | 是否登记、名称/ID、运行根目录 | 列文件、确认候选，再读取 |
| 多版本冲突 | 各来源metadata与用户确认 | 展示冲突，不按语义分数裁决 |
| RAG不可用 | 是否登记、status、模型缓存、索引过期 | 重新登记变更并build；不要假装已检索 |
| project_not_found | 有无当前项目、ID是否存在 | 用户选择或明确创建；不自动补建 |
| Memory不存在 | ID、归档、运行根目录 | 列出实际记录；不编造记忆 |
| 报告无上游证据 | 当前输入/项目/文件/数据是否实际取得 | 补充或读取；缺少的部分保留为缺口 |
| 五段结构错误 | 是否经过唯一修复、Prompt是否漂移 | 保留失败证据；不能放宽格式掩盖问题 |
| 修复阶段请求Tool | 服务是否忽略了tools空列表 | 本地拒绝；检查实际写入状态后再重试 |
| 流式JSON仍无法解析 | 一次兼容重试是否耗尽 | 安全报错，允许重试；不打印敏感载荷 |
| 新代码没生效 | editable与非editable、入口、实际模块位置 | 重装包；区分当前源码与旧安装包 |

不要把整份 `.env`、带员工信息的原文或原始请求贴到排障聊天。正常用户只看简洁错误；详细调试也应控制敏感数据，不能为了排障增加未经授权的永久聊天日志。

## 12. 验证记录与当前剩余工作

### 12.1 历史证据，不覆盖

- M19：16案例首轮14/16；两个失败独立复验0/2，保留原始结果。
- M20：相同16案例连续三轮48/48，预期 Tool36/36，禁止 Tool0，平均9.093秒，最大21.499秒。
- 原始证据：`evals/pilot_results.json`、`pilot_failure_retest.json`、`pilot_results_round_1.json`—`pilot_results_round_3.json`、`pilot_results_3_round_summary.json`。
- 这些记录对应当时冻结代码；本次源码变化不修改它们的摘要或成绩，也不把它们当成当前代码三轮通过。

### 12.2 本次 M21 验证

以下为本次已完成验证，实际环境为 macOS / Python 3.13.5 / DeepSeek `deepseek-flash`；没有将 CI 配置当成其他平台本次执行结果。汇总与源码/结果摘要见 `evals/m21_validation_summary.json`。

- 专项：35项通过。
- 完整离线：273项通过、21项在线测试默认排除。
- `compileall`、`pip check`、`git diff --check`：通过。
- wheel构建及重装：通过，版本仍为1.0.0rc1。
- 源码入口与安装CLI启动、问候、退出：通过。
- 完整真实 API 回归：21项通过、273项离线测试排除，没有在线跳过。
- 项目外目录的已安装 CLI：成功等待输入、问候与退出。
- 首轮模拟：15/16、预期 Tool12/12、禁止 Tool0；`evals/pilot_results_m21.json` 保留完整原始结果。
- 首轮PILOT-16：未调用报告工具，明确“不支持 Word”和“没有……发送能力”，但发送能力拒绝语句未匹配既有正则，故自动契约仍记FAIL；本次技术复核认为是字面检测漏识别，不等于获得第二位独立评审通过。没有改题、改正则或改写成绩。
- 同一代码与未修改标准的完整复验：16/16、预期 Tool12/12、禁止 Tool0；平均9.029秒、最大20.972秒，另存为 `evals/pilot_results_m21_retest.json`。这不消除首轮原始FAIL，也不能拼接历史轮次算成当前48/48。本次未执行新的连续三轮，不满足当前代码的48/48准入门槛。
- 已安装 CLI 在项目外目录实际完成离职率问答：Tool结果平均人数190、离职率15.79%，回答五部分完整，退出正常。

### 12.3 专业建议与优先级

近期不要继续堆业务功能。优先收敛一个真实咨询工作流，例如“销售离职初诊”：确认口径 → 读取匿名化表格与有效制度 → 工具计算 → 区分事实/假设 → 人工复核报告。

1. **真实试点前门槛**：最终代码重新冻结后完成相同16案例连续三轮48/48；这是进入授权试点的技术前提，不是生产准入。
2. **授权匿名化业务试点**：企业明确数据授权、供应商政策、使用人、目的和停止机制；采集真实使用者反馈与两名独立评审，不自动代替他们。
3. **高优先级可靠性欠账**：写入后的错误恢复/重复请求治理、输入与来源的更强约束、上下文长度与调用预算。必须先明确新验收和授权，不把事务/审计系统悄悄塞入当前版本。
4. **体验取舍**：如果仍要求即时token显示，需要重新设计增量输出协议与不可撤回内容风险；当前缓存门是明确的安全选择，不靠模拟逐字输出解决。
5. **生产前独立项目**：身份权限/租户、安全与隐私治理、监控SLO、备份恢复、目标平台依赖验证、人工复核责任与申诉流程。现在的正则脱敏和本地权限不能替代这些控制。

评测契约也有维护欠账：PILOT-16的正则未覆盖“没有发送能力”等同义拒绝。以后可在独立评测版本中增加明确拒绝的正反例，避免将“没有发送限制”等相反含义误判通过；保留原冻结契约与原成绩，新契约仍需重新完整验证，不能借此回改失败分数。

边界未改变：不新增机器学习、预测、复杂异常、因果推断、人员标签、自动人事决策、Web UI、多Agent、MCP或其他报告格式。新的能力需求应从产品规格和Milestone开始，而不是从新增文件夹开始。

可复用的开发原则：**一个版本解决一个真实问题，用工具产生可追溯事实，用测试保护旧行为，用人工复核控制高风险结论。**
