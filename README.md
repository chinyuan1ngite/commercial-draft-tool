# 1688 自动草稿工具

采集 1688 商品，校验数据与素材，填写卖家页面并保存草稿。正式发布由人工审核后操作。

当前版本 **0.4.24，测试构建**。详情选图器修复已通过隔离 Chrome 回归，真实店铺验收仍待补齐。支持范围以 [兼容性与已知问题](docs/compatibility.md) 为准，版本变化见 [CHANGELOG](CHANGELOG.md)。

## 选择你的入口

| 你要做什么 | 从这里开始 |
| --- | --- |
| 使用 Windows 工具 | [操作说明](docs/操作说明.md)、[环境配置](docs/环境配置.md) |
| 不登录账号，了解输入和校验结果 | [离线样例](examples/README.md) |
| 安装源码、调试、运行测试 | [开发指南](docs/development.md) |
| 接手项目、查看待办和历史证据 | [交接清单](docs/handover.md)、[路线图](ROADMAP.md) |
| 理解代码和商品格式 | [当前架构](docs/architecture.md)、[数据说明](docs/data-model.md) |
| 报告问题或提交修改 | [贡献指南](CONTRIBUTING.md) |

## 当前能力

- 1688 采集：标题、属性、价格/库存、SKU、主图、详情图与可信的 SKU 图片关联。
- 数据校验、预览填充、保存草稿和保存后重开核验。
- Windows 桌面启动器与 CLI；买家和卖家浏览器会话隔离。

视频、抖音、拼多多及其他目标平台尚未实现。多平台方向见 [整理方案](docs/项目整理与多平台演进方案.md)，其中的目标架构不是当前实现。

## Windows 包

使用维护者提供的版本 ZIP，解压后双击 `Commercial1688DraftTool.exe`。源码克隆不包含 `dist` 和 EXE；GitHub 下载地址将在私有仓库建立后补充。

程序不依赖 Python 或 Codex，但需要 Chrome。默认数据目录为 `%LOCALAPPDATA%\Commercial1688DraftTool`，包含配置、商品、浏览器 Profile、草稿台账及日志。

## 源码快速开始

在含 `pyproject.toml` 的仓库根目录运行 Windows PowerShell，建议 Python 3.12：

```powershell
python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw '创建环境失败' }
.\.venv\Scripts\python.exe -m pip install -e .
if ($LASTEXITCODE -ne 0) { throw '安装失败' }
.\.venv\Scripts\python.exe examples\make_offline_example.py
if ($LASTEXITCODE -ne 0) { throw '生成样例失败' }
.\.venv\Scripts\python.exe -m draft_tool.cli --product .local\handover-example\product.json --config .local\handover-example\settings.example.json --validate-only
if ($LASTEXITCODE -ne 0) { throw '样例校验失败' }
```

预期 `passed: true`，主图 1 张、详情图 1 张、SKU 2 个、SKU 图片 2 张。该示例只使用本地合成数据；演示配置不能用于真实页面填充。

真实操作启动桌面界面：

```powershell
.\.venv\Scripts\python.exe -m draft_tool.launcher
```

CLI 的 `--validate-only` 只校验本地数据；`--preview-only` 会操作卖家页面并可能上传图片，但不保存草稿；**两者都不指定时会尝试保存草稿**。真实操作命令见操作说明。

## 协作状态

按“先私有协作、整理后公开”推进。任务当前仍使用 `.scratch` Markdown；GitHub 协作、CI、发布自动化和许可决策列在路线图中。参与开发不需要 Codex 或个人技能包。
