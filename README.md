# HR Consultant V1.0 Release Candidate

面向企业组织与人力资源问题的单 Agent 命令行顾问。运行环境为 Python 3.11 或更新版本。V1.0 不新增业务能力，完整保留 V0.1—V0.9 的 HR 问答、计算、Excel 分析、企业文件读取、本地 RAG、项目 State、显式长期 Memory 和基于证据的 Markdown 报告生成，并补齐安装、权限、测试、评测和发布加固。

## 安装

先在终端进入包含本文件的项目根目录。当前电脑上的路径为：

```bash
cd /Users/wangjian/Documents/ChatGPT/hr_agent
```

如果项目已移动，请改用实际路径。下文所有命令都在该目录执行。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install ".[dev]"
```

开发与跨版本安装以 `pyproject.toml` 为准；`requirements-lock.txt` 记录本次 V1.0 RC 在 macOS / Python 3.13 上实际验证的精确依赖版本。若需要完全复现该环境，可在新虚拟环境运行 `python -m pip install -r requirements-lock.txt` 后再运行 `python -m pip install . --no-deps`。

从 `.env.example` 查看变量名称。可在运行终端设置 `DEEPSEEK_API_KEY`，也可把 `.env.example` 复制为项目根目录下的 `.env`，仅在 `.env` 中填入真实密钥，并执行 `chmod 600 .env` 限制本机读取权限。`.env` 已被 Git 忽略；不要把密钥写入 `.env.example` 或提交到仓库。可选用 `DEEPSEEK_MODEL` 指定模型，默认使用 `deepseek-flash`。已有环境变量优先于 `.env` 中的值。

在当前终端设置环境变量后再运行程序，例如：

```bash
export DEEPSEEK_API_KEY='YOUR_KEY'
hragent
```

将占位符替换为未在聊天或仓库公开的 DeepSeek API 密钥。如果选择 `.env` 方式，直接运行 `python -m src.main` 即可。企业问题文本会发送至 DeepSeek API。完整对话历史只在当前进程内保留；退出程序后不会保存聊天记录。只有用户明确要求写入的项目 State 或长期 Memory 会保存在本地 JSON 文件中。

## 运行

```bash
hragent
```

也可以继续使用兼容入口：

```bash
python -m src.main
```

程序会提示“请输入企业人力资源管理问题：”。在同一进程中继续输入可补充信息；输入 `退出` 或 `exit` 结束会话。V1.0 不自动保存聊天记录、提取记忆或生成报告；只有用户明确创建或更新的项目 State、明确要求保存的长期 Memory，以及明确要求生成的 Markdown 报告会跨进程保留。文件 Registry 保存已登记文档的 metadata 和解析文本，RAG 索引只保存可重建的本地片段与向量。

运行数据根目录优先使用环境变量 `HR_AGENT_HOME`；未设置时，如果当前目录或源码目录是本项目根目录，则使用该项目；安装后从其他目录运行时，回退到当前用户的 `~/.hragent` 私有目录。要让任意目录中的 `hragent` 继续使用本项目现有知识库、State、Memory 和报告，请在 shell 配置中设置：

```bash
export HR_AGENT_HOME='/Users/wangjian/Documents/ChatGPT/hr_agent'
```

`HR_AGENT_HOME` 会改变所有本地运行数据和 `.env` 的查找位置，应指向你明确控制的专用目录。

### API 数据边界

Agent 使用 OpenAI 官方 Python SDK 连接 DeepSeek 的 OpenAI 兼容接口。每轮请求会把系统 instructions、本轮问题、当前进程中的成功对话历史、模型请求的 Function Tool 定义，以及实际工具返回结果发送给 DeepSeek。需要文件、RAG、Excel、State、Memory 或报告上游证据时，本地工具先执行，随后相关的脱敏文本片段、结构化统计、项目上下文或记忆内容会作为 Tool 结果发送给 DeepSeek，供其解释和继续编排。程序不会把本地文件作为附件自动上传，但被工具读取并返回的内容可能进入 API 请求；因此不要处理未经授权的真实员工敏感数据。API 的存储、留存和合规政策由所使用的 DeepSeek 服务与账户约定决定。

本地 `.env`、State、Memory、解析文件、向量索引和生成报告应只允许当前系统用户访问。程序新建这些目录和文件时在 POSIX 系统使用目录 `0700`、文件 `0600`；从旧版本升级后也建议运行 `chmod -R go-rwx state knowledge/parsed reports/generated`，并单独保护企业原始文件目录。该权限模型是单机单用户保护，不是企业级访问控制或加密存储。

当问题包含离职人数和平均员工人数，或者包含离职人数、期初人数与期末人数，并要求计算离职率时，Agent 会调用本地计算工具。例如：

```text
公司年初200人，年末180人，全年离职30人，离职率是多少？
```

Tool 只负责计算；Agent 仍按“问题判断、可能原因、需要补充的信息、建议措施、下一步行动”解释结果。人数信息不足时不会估算。

## Excel 元数据读取

在问题中提供本地 `.xlsx` 文件路径，例如：

```text
请读取 /Users/wangjian/Documents/ChatGPT/hr_agent/data/sample_employees.xlsx，这个Excel有哪些字段？
```

可询问文件名、Sheet、指定 Sheet、行列数、字段名、字段类型、缺失值数量、敏感字段和前 5 行预览。单 Sheet 可默认读取；多个 Sheet 时必须指定，Agent 不会自行选择。姓名、身份证号、手机号、邮箱、地址等敏感字段可以显示字段名，但预览值会脱敏。

V0.4 支持总人数和分组人数、薪酬描述性统计、基础离职人数、绩效描述性统计和缺失比例。例如：

```text
请读取 /Users/wangjian/Documents/ChatGPT/hr_agent/data/sample_employees.xlsx，各部门平均工资是多少？
```

Excel Reader 只读取，`src/analytics/` 只计算，HR Agent 只解释。V0.4 数据链路不使用 RAG，也不支持复杂异常检测、相关性、预测、因果推断、复杂薪酬合理性判断、员工标签或自动人事决策。

请等上述中文提示出现后再输入问题；如果看到的是 `zsh` 的 `%` 提示符，说明程序尚未运行。未激活虚拟环境时，也可以在项目根目录使用 `.venv/bin/python -m src.main`。若提示密钥认证失败，检查 `DEEPSEEK_API_KEY`；若提示无法连接，检查网络和 DNS；若提示余额不足，检查 DeepSeek 账户额度。

## V0.5 File Knowledge Base

V0.5 支持 `.txt`、`.md`、`.docx` 和带机器可读文本层的 `.pdf`。Excel 文件仍走现有 Excel Reader，不要把 `.xlsx` 放入 Document Loader。PDF 扫描件不做 OCR，未提取到文本时会明确返回 `scanned_or_unreadable_pdf`。

默认企业文件目录为 `knowledge/documents/`。可把企业文件复制到该目录，也可以使用其他本地路径；放入目录本身不等于已经登记。启动 Agent 后可输入：

```text
请把 /绝对路径/薪酬管理制度.docx 导入企业知识库。
```

也可不经过模型，直接在项目根目录登记已有文件：

```bash
python -c "from src.knowledge import register_document; print(register_document('knowledge/documents/02_薪酬管理制度.md'))"
```

Registry metadata 位于 `knowledge/index.json`，标准化解析文本位于 `knowledge/parsed/`。删除 Registry 记录不会自动删除用户原文件。查看文件列表可以在 Agent 中输入“知识库里有哪些文件？”，也可以运行：

```bash
python -c "from src.knowledge import list_documents; print(list_documents())"
```

读取明确文件时可输入“打开薪酬管理制度”“根据薪酬管理制度，年度调薪是什么时候？”等问题。程序会按文件名、标题或 `document_id` 定位已登记文件；长文档使用字符范围分段读取，不主动把整份长文件交给模型。文件问答会说明来源，并区分“制度中这样规定”和“现实中确实这样执行”。

V0.5 文件链路继续负责导入、解析、metadata、精确选择和受控读取；V0.6 RAG 只在它之后做分块、向量化和检索。多份文件冲突时会列出候选和 metadata，请用户确认有效版本，不自行决定。身份证号、手机号和邮箱会在送入模型前脱敏；仍请勿把不必要的真实员工敏感资料放入测试目录。

## V0.6 Local RAG

V0.6 默认使用本地中文模型 `BAAI/bge-small-zh-v1.5`。Embedding 不调用 DeepSeek 或 OpenAI，因此不需要 `OPENAI_API_KEY`，也不需要新增模型密钥；只有 Agent 最终解释仍需要现有 `DEEPSEEK_API_KEY`。首次构建索引会从 Hugging Face 下载模型，之后复用本机缓存。可通过 `HR_AGENT_EMBEDDING_MODEL` 改用兼容的本地 Sentence Transformers 模型。

登记文件后，在项目根目录构建索引：

```bash
python -m src.knowledge.rag_cli build
```

查看状态和直接测试检索：

```bash
python -m src.knowledge.rag_cli status
python -m src.knowledge.rag_cli search "年度调薪什么时候进行" --top-k 3
```

索引默认写入 `knowledge/vector_index.sqlite3`，它是可重建的运行产物并已被 Git 忽略。每次新增、删除或重新登记文档后，状态会显示缺失、过期或孤立文档；重新运行 `build` 即可原子重建全部 ready 文档的索引。

在 Agent 中可以输入：

```text
公司制度里年度调薪是什么时候？
请在所有文件中找与绩效奖金最相关的5段内容。
```

对于明确指定的文件，Agent 仍优先使用 V0.5 精确 Reader；对于未指定文件或跨文档问题，Agent 使用 `search_knowledge_base`。回答只把返回片段直接支持的内容视为企业文件事实，并标注文件名、`document_id` 和字符范围。相似度只用于排序，不代表制度有效性或现实执行。检索没有足够依据时会明确说明；不同版本冲突时不会自动裁决。

当前限制：不支持扫描 PDF OCR、BM25/混合检索、reranker、查询改写、托管向量数据库、自动制度诊断或自动人事决策。RAG 只解决“文件中与问题相关的内容是什么”，不会证明制度已经执行。

## V0.7 Project State

项目 State 用于保存一个 HR 咨询项目的必要上下文：项目名称、目标、组织背景、当前阶段、用户已确认事实、待补信息、已确认决定，以及选中的知识库 document_id 和数据文件路径引用。它不会保存完整聊天记录，也不会自动记住普通问答。

在 Agent 中可直接输入：

```text
请创建一个项目，名称是“销售离职诊断”，目标是识别销售离职增加的原因，公司约200人。
把“最近销售离职人数明显增加”保存为当前项目事实。
把“还需要统计期间平均销售人数”记录为待补信息。
当前有哪些项目？
继续当前项目，告诉我现在的状态。
归档项目 PRJ-XXXXXXXXXXXX。
```

创建项目后会自动成为当前项目。同一时间只有一个项目被选中，但可以保留多个未归档项目。State 默认写入 `state/projects.json`，采用原子替换并已被 Git 忽略；归档只改变状态，不物理删除数据。归档项目不能继续更新或重新选择。

只有“创建、保存、更新、切换、归档”等明确请求才会写入 State。普通 HR 分析、Excel 工具和 RAG 检索不会自动持久化。State 中保存的内容属于用户确认的 `PROJECT_CONTEXT`，不等于外部核验事实；document_id 和文件路径也只是引用，需要内容时仍会调用 Reader/RAG 或 Analytics。

项目 State 不应包含身份证号、手机号、邮箱、住址、医疗信息、个人薪酬、处分或投诉记录。检测到明显员工级敏感信息时会拒绝保存并要求匿名化。V0.7 不支持对话自动摘要、任务调度、云同步、多人权限、附件复制或自动项目报告。

## V0.8 Explicit Long-term Memory

Memory 用于保存跨会话、跨项目仍可能有用的稳定上下文，支持四类内容：个人输出偏好 `preference`、稳定组织背景 `organization`、内部术语 `terminology` 和长期约束 `standing_instruction`。它与项目 State 分开，不保存项目进度、完整聊天、模型推断、文件全文或 Excel 数据。

在 Agent 中可以输入：

```text
请记住：回答默认使用简洁中文。
请记住：我们把员工称为伙伴，这是内部术语。
你记住了什么？
你记得我们公司的考勤口径吗？
更正记忆 MEM-XXXXXXXXXXXX：考勤分析统一按自然月口径。
归档记忆 MEM-XXXXXXXXXXXX。
请彻底忘记记忆 MEM-XXXXXXXXXXXX。
```

Memory 默认写入 `state/memories.json`，采用原子替换并已被 Git 忽略。新增、更正、归档和遗忘都必须由用户明确提出；普通问答、项目 State、Excel、文件读取和 RAG 不会自动写入。关键词查找只做文本匹配，不是 Embedding 或语义搜索。

Agent 使用已保存内容时会标记为 `MEMORY_CONTEXT`，并说明 `memory_id` 和更新时间。它表示用户过去明确保存的上下文，不是外部核验事实；员工人数、组织结构、制度口径等可能变化的信息仍需确认是否有效。归档会保留记录但默认不参与检索；“彻底忘记”会按唯一 `memory_id` 物理删除指定记录。

Memory 不接受 API Key、密码、令牌、身份证号、手机号、邮箱、住址、医疗信息、个人薪酬、处分或投诉等敏感内容。V0.8 不支持自动记忆提取、聊天摘要持久化、Memory Embedding、语义 Memory 检索、云同步、多人共享或用户画像推断。

## V0.9 HR Report Generation

V0.9 可以把 Agent 已经取得、可追溯的 HR 分析保存为标准化 Markdown 报告草稿。Report Generator 只校验结构、排版和写文件；它不会自行读取 Excel、知识库、RAG、Project State 或 Memory，也不会自行新增事实、原因或建议。

在 Agent 中可以输入：

```text
请根据我刚才提供的信息生成一份销售离职诊断报告。
请基于当前项目生成HR报告。
请读取薪酬管理制度，并根据实际文件内容生成制度摘要报告。
请分析 data/sample_employees.xlsx 的各部门人数，并生成报告。
```

当报告需要项目、Memory、文件或 Excel 数据时，Agent 会先调用对应上游工具，再把实际取得的结果交给 `generate_hr_report`。报告中的已知事实必须对应来源索引；可能原因仍标记为待验证假设；缺少的重要信息会保留在报告中。

报告默认写入：

```text
reports/generated/
```

文件名由唯一 `report_id` 和安全化标题组成，不接受用户指定的任意输出路径，也不会覆盖已有文件。生成成功后，Agent 会返回真实的 `report_id`、Markdown 格式和绝对文件路径。报告固定包含：执行摘要、问题判断、已知事实与依据、可能原因、需要补充的信息、建议措施、下一步行动、假设与限制及来源索引。

所有报告均标记为“自动生成草稿”，不代表正式管理决定或法律意见。报告拒绝保存 API Key、密码、令牌和员工个人敏感信息。V0.9 不支持 Word、PDF、HTML、PPT、图表、品牌模板、批量生成、自动发送、审批签署、自动更新或报告 Registry。

## 测试

```bash
python -m pytest -q
```

默认测试只运行离线测试，在线测试会被排除，以免意外产生 API 请求。真实 API 测试需要在执行环境中设置 `DEEPSEEK_API_KEY`；测试命令不会自动加载 `.env`。单元测试使用模拟客户端，不会发起网络请求。

配置密钥后可运行 `python -m pytest -q -m live`，检查真实连接与固定验收案例。V0.9 报告测试位于 `tests/test_report_*.py`；V0.8 Memory、V0.7 State、V0.6 RAG、V0.5 文件与 V0.4 分析测试继续保留。`evals/acceptance_cases.json` 是 12 个 V0.1 正式验收案例，`evals/test_cases.json` 是补充人工评测案例，`evals/v1_capability_cases.json` 则覆盖 V0.2—V0.9 的工具能力契约。GitHub Actions 会在 Python 3.11、3.12 和 3.13 上运行离线测试；真实 API 测试不进入 CI，避免使用密钥和产生费用。

## V1.0 发布边界

V1.0 RC 是本地单用户试点版本，不等于已经完成生产级安全、法务和隐私合规认证。它没有数据库、Web UI、多 Agent、MCP、云同步、多人权限、审计服务、加密密钥管理或自动人事决策。正式处理真实员工数据前，应由企业确认数据授权、最小化范围、DeepSeek API 数据政策、保存期限、设备权限和删除流程。发布检查见 `RELEASE_V1.0.md`，匿名化试点方案见 `PILOT_PLAN.md`。
