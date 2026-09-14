# 开发指南

在包含 `pyproject.toml` 的仓库根目录运行命令。源码位于 `src/draft_tool`，不依赖上层旧脚本。

## 环境与安装

使用 Windows 10/11 64 位和 Python 3.12。项目声明 Python >=3.11；历史验证环境为 Python 3.12.2、DrissionPage 4.1.1.4。浏览器测试需要 Chrome。Profile 锁使用 Windows `msvcrt`，没有 Linux/macOS 支持承诺。

首次安装需下载依赖。无需激活虚拟环境或修改 PowerShell 执行策略：

```powershell
python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw '创建环境失败' }
.\.venv\Scripts\python.exe -m pip install -e .
if ($LASTEXITCODE -ne 0) { throw '安装失败' }
.\.venv\Scripts\python.exe -m pip check
if ($LASTEXITCODE -ne 0) { throw '依赖检查失败' }
```

依赖范围见 `pyproject.toml`，目前没有发布依赖锁定文件。记录实际环境：

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip show commercial-1688-draft-tool DrissionPage Pillow beautifulsoup4
```

## 第一次运行：离线样例

```powershell
.\.venv\Scripts\python.exe examples\make_offline_example.py
if ($LASTEXITCODE -ne 0) { throw '生成样例失败' }
.\.venv\Scripts\python.exe -m draft_tool.cli --product .local\handover-example\product.json --config .local\handover-example\settings.example.json --validate-only
if ($LASTEXITCODE -ne 0) { throw '正向样例失败' }
.\.venv\Scripts\python.exe -m draft_tool.cli --product .local\handover-example\product-invalid.json --config .local\handover-example\settings.example.json --validate-only
if ($LASTEXITCODE -ne 4) { throw '负向样例应返回 4' }
```

第一条校验通过；第二条报告“缺少商品标题”。数据位于 Git 忽略的 `.local/handover-example`，格式见 [样例说明](../examples/README.md)。

启动器烟雾检查会创建配置，使用进程级变量隔离并恢复原值：

```powershell
$previousDraftHome = $env:DRAFT_TOOL_HOME
try {
  $env:DRAFT_TOOL_HOME = Join-Path $PWD '.local/handover-smoke'
  .\.venv\Scripts\python.exe -m draft_tool.launcher --smoke-test
  if ($LASTEXITCODE -ne 0) { throw '烟雾检查失败' }
} finally {
  $env:DRAFT_TOOL_HOME = $previousDraftHome
}
```

预期输出版本和隔离目录，不打开 GUI 或浏览器。GUI 默认用 LOCALAPPDATA 配置；独立 CLI 使用 `--config` 文件，两者不自动同步。

## 测试

无浏览器回归：

```powershell
$previousBrowserTests = $env:DRAFT_BROWSER_TESTS
try {
  Remove-Item Env:DRAFT_BROWSER_TESTS -ErrorAction SilentlyContinue
  .\.venv\Scripts\python.exe -m compileall -q src tests examples
  if ($LASTEXITCODE -ne 0) { throw '编译检查失败' }
  .\.venv\Scripts\python.exe -m unittest discover -s tests -v
  if ($LASTEXITCODE -ne 0) { throw '单元测试失败' }
} finally {
  $env:DRAFT_BROWSER_TESTS = $previousBrowserTests
}
```

0.4.24 基线共 175 项，56 项浏览器测试默认跳过；跳过不等于通过。

页面操作变更需安装 Chrome 并执行：

```powershell
$previousBrowserTests = $env:DRAFT_BROWSER_TESTS
try {
  $env:DRAFT_BROWSER_TESTS = '1'
  .\.venv\Scripts\python.exe -m unittest discover -s tests -v
  if ($LASTEXITCODE -ne 0) { throw '浏览器回归失败' }
} finally {
  $env:DRAFT_BROWSER_TESTS = $previousBrowserTests
}
```

自定义 Chrome 路径用当前进程 `CHROME_BINARY` 指定。测试使用独立端口/临时会话和合成页面或拦截响应，不需要真实店铺；不要连接已有卖家 Profile。

可缩小到详情图片：`.\.venv\Scripts\python.exe -m unittest tests.test_browser_dom -k detail -v`，同样需启用浏览器开关和检查退出码。隔离测试不能替代真实页面验收。

## 定位与构建

先看校验 stdout/`quality-gate.json`，再看 `report.json.result` 和 `fields`。文件对应 [架构地图](architecture.md)，字段见 [数据说明](data-model.md)。

`--validate-only` 不访问页面；预览可能上传媒体；无预览/校验标志时尝试保存。详情 `text_saved` 不代表图片或整个草稿成功。结果未知时先检查平台状态，不能仅增加重试次数。

构建命令：`powershell -NoProfile -File .\scripts\build.ps1`。需要安装 PyInstaller 及可初始化的 Tcl/Tk；生成 `dist/Commercial1688DraftTool-<VERSION>-win64.zip`。

当前构建会覆盖同版本本地 ZIP 并复制整个 `docs`，不能作为已发布产物的替换流程。本批不重打 0.4.24 包。包验证脚本目前仍有逻辑在忽略目录 `.local`，新克隆不可依赖它。

已有 `scripts/test.ps1` / `install.ps1` 未完整传播每一步原生命令错误，本指南使用显式退出码检查。脚本统一、依赖固定和文档打包清单属于 [下一批](../ROADMAP.md)。
