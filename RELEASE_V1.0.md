# HR Consultant V1.0 Release Candidate

## Release scope

V1.0 RC 完整继承 V0.1—V0.9，不增加新的 HR 业务 Tool。此次发布只加固版本控制、最小文件权限、共享敏感信息检测、工具执行注册表、可安装 CLI、依赖锁定、跨版本评测、CI 与运行文档。

## Release checklist

- [x] V0.9 基线 commit 与 `v0.9.0` annotated tag 已建立；
- [x] 28 个业务 Tool 保持唯一注册，简单 Tool 使用统一执行注册表；
- [x] State、Memory、Knowledge 与 Report 共用敏感信息和私有文件辅助模块；
- [x] 新建运行时目录使用 `0700`，持久化文件使用 `0600`（POSIX）；
- [x] `pyproject.toml` 提供 `hragent` 入口，Python 要求为 3.11+；
- [x] `requirements-lock.txt` 记录本次验证环境的精确依赖；
- [x] GitHub Actions 配置 Python 3.11、3.12、3.13 离线测试矩阵；
- [x] V0.2—V0.9 各 3 个跨版本能力评测案例和确定性检查器已建立；
- [x] README 已披露发送给 DeepSeek 的内容、本地文件边界和权限边界；
- [x] 完整离线测试通过；
- [x] 完整真实 DeepSeek API 测试通过；
- [x] `hragent` 与 `python -m src.main` 均完成启动/退出验证；
- [x] 依赖检查、源码编译、密钥扫描和发布差异检查通过；
- [x] 创建 `v1.0.0-rc1` annotated tag。

本次本地验证结果：`245 passed, 21 deselected`；真实 DeepSeek 回归 `21 passed, 245 deselected`；Python 3.11、3.12、3.13 源码编译检查通过。完整离线测试在本机 Python 3.13 执行，其他版本由 CI 矩阵持续验证。

## Installation and validation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install ".[dev]"
python -m pip check
python -m pytest -q
hragent
```

真实 API 测试仅在安全配置 `DEEPSEEK_API_KEY` 的本地环境运行：

```bash
python -m pytest -q -m live
```

## Security and privacy position

这是本地单用户 Release Candidate，不是企业级生产系统。目录与文件权限仅降低同一设备上其他普通系统用户直接读取的风险，不等于加密、租户隔离、权限审批或完整审计。DeepSeek 会收到当前问题、进程内对话、工具定义和相关工具结果；文件不作为附件自动上传，但成功读取或检索的文本片段、统计、State、Memory 和报告上游内容可能被发送。处理真实员工信息前必须完成企业自己的授权、数据最小化、API 服务条款、保存期限和删除流程审查。

## Known limitations

- 仅本地单用户 CLI；
- 不支持数据库、Web UI、多 Agent、MCP、云同步或多人权限；
- RAG 不支持 OCR、混合检索、重排序或外部向量数据库；
- 报告仅为 Markdown 自动生成草稿；
- 不执行自动员工标签、自动人事决策或复杂因果/预测分析；
- 精确依赖锁来自 macOS / Python 3.13 验证环境，跨平台兼容性以 `pyproject.toml` 与 CI 为准；
- 真实客户试点尚未完成，发布后应按 `PILOT_PLAN.md` 使用匿名化案例验证。

## Rollback

如 V1.0 RC 出现回归，可通过 `v0.9.0` tag 恢复已验证的功能基线。State、Memory、知识库 Registry、解析文件、向量索引和生成报告均应先单独备份；Git tag 不包含被 `.gitignore` 排除的运行时数据。
