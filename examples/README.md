# 离线合成样例

本目录提供可公开、可重复生成的商品输入，用于确认安装、数据格式和质量门禁。它不访问网络、不启动 Chrome，也不操作卖家页面。

在仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe examples\make_offline_example.py
if ($LASTEXITCODE -ne 0) { throw '生成样例失败' }
```

默认生成到被 Git 忽略的 `.local/handover-example/`：

```text
.local/handover-example/
  product.json
  product-invalid.json
  settings.example.json
  assets/main.png
  detail-assets/detail.png
  sku-assets/red.png
  sku-assets/blue.png
```

校验正向样例：

```powershell
.\.venv\Scripts\python.exe -m draft_tool.cli `
  --product .local\handover-example\product.json `
  --config .local\handover-example\settings.example.json `
  --validate-only
if ($LASTEXITCODE -ne 0) { throw '正向样例校验失败' }
```

预期退出码为 0，输出包含：

```json
{
  "passed": true,
  "summary": {
    "offer_id": "synthetic-1688-001",
    "main_images": 1,
    "detail_images": 1,
    "sku_count": 2,
    "sku_images": 2
  }
}
```

实际输出还包含完整标题、目标配置、issues 和 warnings；上面的片段只列稳定的验收字段。

校验负向样例：

```powershell
.\.venv\Scripts\python.exe -m draft_tool.cli `
  --product .local\handover-example\product-invalid.json `
  --config .local\handover-example\settings.example.json `
  --validate-only
if ($LASTEXITCODE -ne 4) { throw '负向样例应返回 4' }
```

预期 `passed` 为 false，issues 包含 `缺少商品标题`。负向样例只改变标题，以便新维护者看到一个明确失败，不把多个问题混在一起。

可用 `--output-dir D:\path` 指定其他生成目录。每次执行会覆盖该目录中由本脚本管理的同名样例文件；不要把输出目录指向真实商品目录。

这些文件只用于 `--validate-only`。示例配置中的类目与店铺标识均为虚构值，不能用于 `--preview-only` 或保存草稿。
