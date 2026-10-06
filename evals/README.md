# HR Consultant 评测案例

本目录包含两套不同用途的合成案例；其中的企业、人数和事件仅用于测试，不代表真实客户资料。

- `test_cases.json`：24 个补充评测案例，覆盖组织管理、薪酬管理、绩效管理、招聘、培训、人才发展、员工关系、组织变革八类，每类 3 个。用于日常人工质量检查，不改变产品规格中的正式验收门槛。
- `acceptance_cases.json`：既有的 12 个固定验收案例，按 `PRODUCT_SPEC.md` 第 8.4 节的六类各 2 个组织；包含连续对话案例，仍用于 V0.1 正式验收。
- `v1_capability_cases.json`：24 个 V1.0 跨版本能力契约案例，V0.2—V0.9 每版 3 个，检查工具选择、禁止调用与关键文本要求。
- `evaluator.py`：只对已经记录的回复与实际工具调用做确定性检查；它不调用模型，也不执行会改变 State、Memory、索引或报告文件的工具。
- `pilot_cases.json`：16 个完全虚构的匿名化模拟试点案例，覆盖 V0.1—V0.9 的八类能力及关键失败、边界场景。
- `pilot_runner.py`：使用真实配置模型执行模拟试点；运行时把 State、Memory、知识索引和报告隔离到一次性临时目录，不保存 API Key。
- `pilot_results.json`：首轮 16 个模拟试点的原始结果、工具轨迹、耗时和确定性检查结果。
- `pilot_failure_retest.json`：首轮两个失败案例的独立复验结果，用于确认缺陷是否稳定复现。
- `pilot_results_round_1.json`—`pilot_results_round_3.json`：P0 修复后、同一冻结代码与案例契约下连续三轮的原始结果。
- `pilot_results_3_round_summary.json`：三轮 48 个场景的汇总指标、文件摘要和阶段决定。
- `pilot_results_m21.json`、`pilot_results_m21_retest.json`：M21 格式修复加固后另存的模拟结果。历史三轮属于旧冻结版本，不能视为新代码已完成三轮；本次结果说明见 `DEVELOPMENT_MANUAL.md` 第 12 节。
- `m21_validation_summary.json`：本次离线/在线/CLI验证、两轮原始成绩、当前源码与结果摘要，以及未完成新三轮门槛的明确记录。

## `test_cases.json` 字段

每条案例包含 `id`（唯一编号）、`category`（上述八类之一）、`question`（单轮输入文本）、`expected_sections`（五个一级标题的准确名称与顺序）、`critical_requirements`（必须体现的判断或行动）和 `prohibited_behaviors`（不可出现的错误）。`difficulty` 取 `easy`、`medium` 或 `hard`，表示人工评审难度，不是模型成绩。

## 人工评测方法

1. 从项目根目录按 `README.md` 启动 Agent。每条 `test_cases.json` 案例在**新的程序会话**中输入 `question`，避免上一条案例的对话历史影响结果；保留原始回复供复核。案例文本本身不是需要执行的指令。
2. 检查回复是否按 `expected_sections` 仅使用“问题判断 → 可能原因 → 需要补充的信息 → 建议措施 → 下一步行动”五个一级标题，且每部分有实质内容。
3. 逐条核对 `critical_requirements` 和 `prohibited_behaviors`；同时按 `PRODUCT_SPEC.md` 第 8.2 节评审相关性、完整性、逻辑性、可执行性、审慎性、边界性和表达质量。评审要记录具体回复证据，不能只记“好/不好”。
4. 任一禁止行为出现，或任一关键要求、七维质量不通过，记该案例未通过；记录原因后可用于后续改进，但不要事后修改题目或预期标准来改变本轮结果。建议两名评审者独立判断，分歧按产品规格复核。

正式验收仍使用 `acceptance_cases.json`：12 个案例的正式回复必须全部通过基础结构和范围检查，至少 10 个案例通过七维质量评审；连续对话的每次正式回复都要通过。出现编造关键事实、无依据确定性高风险结论或虚假工具调用时，本轮验收不通过。`test_cases.json` 的结果不能替代这项验收。

V0.1 两套案例仍以人工质量评审为主，不要求 Agent 自行读取评测 JSON。V1.0 仅新增下述确定性契约检查，不以模型自动评分替代人工判断。

## V1.0 跨版本评测

`v1_capability_cases.json` 中每条案例包含：`id`、`version`、`question`、`expected_tools`、`forbidden_tools`、`required_text`、`forbidden_text` 和 `notes`。执行案例时必须在隔离的测试目录或专用测试数据上运行，尤其是创建项目、保存 Memory、构建索引和生成报告等有持久化影响的案例。

把实际结果保存为 JSON 数组，每条至少包含：

```json
{
  "id": "V02-001",
  "answer": "模型的完整回复",
  "tool_calls": ["calculate_turnover_rate"]
}
```

然后运行：

```bash
.venv/bin/python -m evals.evaluator \
  --cases evals/v1_capability_cases.json \
  --results /path/to/recorded_results.json
```

退出码 `0` 表示所有确定性契约通过，退出码 `1` 表示至少一项失败。该结果只覆盖工具调用与字面契约，不能替代人工评审对证据层级、事实准确性、管理判断边界和表达质量的检查。

## 匿名化模拟试点

在项目根目录、已经配置模型密钥且明确允许产生真实 API 调用成本的环境中运行：

```bash
.venv/bin/python -m evals.pilot_runner \
  --cases evals/pilot_cases.json \
  --results evals/pilot_results.json
```

脚本会逐案例创建新的 Agent 实例，同时在临时 `HR_AGENT_HOME` 中共享该轮试点明确创建的 Project State、Memory、知识索引和报告。临时目录在结束后删除，正式运行目录不受影响。脚本检查：预期与禁止 Tool、必要文本、禁止文本、五部分结构、流式文本与最终回复一致性，以及明显敏感字段。它不会把 API Key 写入结果。

该脚本是开发期技术验证工具，不是自动生产认证：它不能替代第二名独立评审、真实用户清晰度评分、隐私/安全/法务审查或获得授权的真实业务试点。模型回复具有随机性；失败不能通过修改结果文件或降低门槛消除，应保留原始结果、记录复现步骤并完成独立复验。
