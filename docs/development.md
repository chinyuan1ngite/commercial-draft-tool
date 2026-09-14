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

也可运行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`；加 `-Browser` 执行隔离 Chrome 回归。脚本会检查依赖、版本一致性、`src/tests/examples/scripts` 编译并传播任何失败。`Bypass` 只作用于这个子进程，不修改系统策略。跳过浏览器测试不等于通过。

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

构建前安装锁定的构建依赖：`.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt`，再运行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build.ps1`。需要可初始化的 Tcl/Tk；生成 ZIP 和对应 `.sha256`。

构建默认拒绝已有同版本目录、ZIP 或哈希文件，避免覆盖已经交付的产物。本地有意重建可加 `-OverwriteLocalBuild`，正式发布仍应先递增 `VERSION`。包内只包含用户文档清单，不包含内部交接和代理说明。

`scripts/verify_release.py` 会验证 ZIP 路径、必需文件、版本、EXE 哈希、启动器烟雾检查和 CLI 帮助。它会执行包内 EXE，只能用于可信本地或 CI 构建。单元测试专用的 `--skip-executable-smoke` 仅检查结构和哈希，不能作为发布通过证据。完整流程见 [维护指南](maintenance.md)。
