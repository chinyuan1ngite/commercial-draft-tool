# 维护指南

本指南适用于私有 GitHub 仓库的维护者。当前产品只做到采集、校验、预览、保存草稿和重开核验，正式发布继续由人工执行。

## Issue 与分诊

新问题必须使用 Issue 表单。先确认版本、阶段、来源/目标平台、类目和页面模式，再检查复现是否使用最小合成数据。包含 Profile、Cookie、令牌、完整运行目录、真实店铺页面或多余商品数据的附件应先移除并要求脱敏替代。

初始标签为 `needs-triage`。复现资料不足改为 `needs-info`；范围与验收明确后改为 `ready-for-agent`；必须使用授权账户或人工判断时改为 `ready-for-human`。不实施时记录理由并使用 `wontfix`。标签含义见 [映射表](agents/triage-labels.md)。

## 页面变化故障

1. 从 `report.json.result`、`fields` 和 `quality-gate.json` 确认失败阶段，不用最终布尔值代替各字段证据。
2. 保存脱敏 DOM 片段、合成 HTML 或拦截响应，先构造能稳定失败的最小回归。
3. 保留真实页面机制，例如跨域 iframe、弹层、异步换页和原生提示框；不要用简化页面掩盖机制。
4. 同一复现通过后运行相关单元测试和隔离 Chrome 套件，记录通过和跳过数。
5. 由授权人员执行预览、保存和重开；上传或保存结果不确定时停止，不盲目重试。
6. 更新 [兼容性文档](compatibility.md)，明确自动证据和真实页面证据各自覆盖范围。

## 依赖升级

运行依赖范围在 `pyproject.toml`，构建依赖在 `requirements-build.txt`。一次只升级一组相关依赖，记录升级前后版本；先执行 `pip check` 和无浏览器测试，再按影响范围运行隔离浏览器测试。DrissionPage、Chrome 或 Pillow 变化会影响页面控制或媒体验证，需要相应回归。构建依赖升级后必须重新执行完整包验证。

## CI 与评审

`CI` 在 main 推送和 PR 上运行 Windows/Python 3.12 无浏览器套件。`Browser regression` 由维护者手动触发，只使用临时会话和合成/拦截页面。`Release package validation` 手动构建、执行包内烟雾检查并上传短期 artifact；它不创建 GitHub Release，也不发布商品。

main 应通过 PR 合并，要求 CI 成功并至少一名维护者评审；禁止强推和删除。团队账号确定后再添加 CODEOWNERS。CI 日志和 artifact 不能包含本地配置、Profile 或现场报告。

## 发布步骤

1. 确认目标提交已通过 PR、CI 和所需浏览器/真实页面验收，工作树干净。
2. 同步修改 `VERSION`、`pyproject.toml` 和 `draft_tool.__version__`，新增对应版本说明及 CHANGELOG；运行 `scripts/check_version.py`。
3. 在干净克隆安装工程与 `requirements-build.txt`，运行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`；页面改动另加 `-Browser`。
4. 运行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build.ps1`。若同版本产物已存在，应递增版本；`-OverwriteLocalBuild` 只用于明确的本地重建。
5. 保留 `scripts/verify_release.py` 生成的 JSON、ZIP 和 `.sha256`，独立核对哈希。发布验证必须包含 EXE 烟雾与 CLI 帮助，不能使用跳过选项。
6. 先在私有范围交付并记录提交、版本、验证环境和已知限制。GitHub Release 或公开分发需要所有者另行决定。

PyInstaller 构建可重复执行，但不承诺不同机器或时间生成字节完全相同的 EXE/ZIP；可信依据是来源提交、依赖版本、CI 记录、结构检查、包内 EXE 哈希和行为烟雾检查。

## 回滚与数据备份

代码回滚通过新的 PR 恢复到已知提交并发布更高版本，不覆盖或删除已交付的同版本 ZIP。发生现场故障时先停止自动操作，保存脱敏报告，核对平台是否已经产生草稿或上传，再决定人工清理。

升级或迁移前退出程序并备份 `%LOCALAPPDATA%\Commercial1688DraftTool`。其中含配置、商品、浏览器 Profile、草稿台账和日志，只能存入受控本地备份，不能提交 Git。恢复时先保留故障副本，在隔离目录验证旧版本能读取所需数据，再替换生产目录；台账与平台草稿状态必须同时核对，避免重复创建。
