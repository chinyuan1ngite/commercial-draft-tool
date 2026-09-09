# 1688 自动草稿工具

交付边界固定为：采集商品、校验数据、自动保存草稿、人工审核并手动上架。程序不会点击正式发布按钮。

本目录是独立工程，不读取原项目的 `data/` 或浏览器登录目录。生产运行数据、登录会话、配置和报告均被 `.gitignore` 排除。

## 推荐：直接运行 Windows 版

打开 `dist` 目录中的 `Commercial1688DraftTool.exe`。首次运行会在 `%LOCALAPPDATA%\Commercial1688DraftTool` 创建配置、商品、浏览器 Profile、草稿报告和日志目录，无需 Python，也不依赖 Codex。

完整说明：

- [操作说明](docs/操作说明.md)
- [环境配置](docs/环境配置.md)

## 源码版安装

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python -m draft_tool.launcher
```

也可以运行 `scripts\install.ps1` 后双击 `launcher.bat`。

在 `config/settings.local.json` 中必须填写目标类目和店铺身份校验文本。`store_identity_text` 应是发布页稳定可见且能唯一识别当前店铺的文字，用于防止登录错账号。发货地址匹配文本、运费模板和发货承诺为可选项；包裹重量也可配置统一值，留空时只使用能够可靠映射到 SKU 的源件重，两者都没有时不猜测重量。

可选项不代表平台永远允许缺省：如果当前类目或卖家页面把其中某项标记为必填，页面校验仍会阻止保存草稿，并在运行报告中留下原因。已配置的可选项仍执行严格填充和重开核验；不同 SKU 件重只有在目标行可可靠识别时才会逐行填写。

SKU 图片默认采集并尝试按 SKU 行填写。关联优先使用源 SKU ID，缺少 ID 时仅使用唯一规格组合；卖家页面行级控件既可以是文件上传框，也可以是“添加”按钮打开图片空间，两种都会按行确认图片数量变化，无法确认或没有行级控件时报告 `unsupported_mapping`，不会按页面顺序猜测。可在启动器配置中分别关闭 SKU 图片采集或填写；缺图默认告警，勾选 `require_sku_images` 后阻止保存。重量优先使用源 SKU 件重，目标物流行没有 SKU 编号或货号时会按“颜色”等规格列做唯一匹配；无法采集或可靠映射时统一使用 1000g 默认值，显式包裹重量仍可覆盖该默认值。视频采集与配置暂未启用。

不同类目的规则放在 `category_rules.by_category.<类目ID>` 下。默认使用商品采集结果中的源叶子类目；如需发布到其他类目，可在配置中填写目标类目，或使用启动器的“捕获目标类目”读取并确认卖家页面中的 `catId`，无需手填数字 ID。采集到的源属性（包括新版页面中的材质、功能、包装方式）会按目标页面的属性标签自动匹配，不需要再把已采集值手工写入规则。源页面 `skuMap`/`skuInfoMap` 中的每个 SKU 价格会单独保留；检测到多个不同 SKU 价格时，发布页自动切换为“按产品规格报价”并逐行填价。每个类目仍可配置 `labels`（补充源商品缺失的属性）、`properties`（按属性 ID 覆盖值）和 `manual_required`（明确要求人工确认的属性 ID）。仅当卖家页面对“是否IP授权”明确说明无授权应选“否”时，源数据缺失该属性才使用此安全默认值；其他缺失必填属性仍会阻止保存。

## 先校验再运行

```powershell
draft-tool --product "D:\path\product.json" --config config\settings.local.json --validate-only
draft-tool --product "D:\path\product.json" --config config\settings.local.json --preview-only
draft-tool --product "D:\path\product.json" --config config\settings.local.json
```

最后一条命令会尝试保存草稿，但不会正式上架。卖家预览/保存遇到登录页时默认不限时等待人工登录，完成后自动回到原页面继续；命令行可用 `--login-timeout-seconds N` 设置超时，`0` 表示不限时。每次运行输出 `quality-gate.json`、`runtime-config.json`、页面报告和截图，可据此捕获并固化当前店铺/类目配置。

默认输出按 `商品ID/运行ID` 隔离，运行状态采用原子写入。同一卖家 Profile 同时只能运行一个任务。工具以“店铺身份 + 源 offer_id”为幂等键记录草稿 ID：有台账时更新原草稿；没有台账但发现同标题旧草稿时停止并要求人工确认，不会删除任何历史草稿。

采集入口独立为：

```powershell
draft-collect --url "https://detail.1688.com/offer/商品ID.html" `
  --output-dir data\products --profile-dir .local\buyer-browser `
  --wait-for-challenge 120
```

买家采集 profile 与卖家发布 profile 必须使用不同目录。

命令行参数可覆盖配置文件，例如首次使用某个类目时：

```powershell
draft-tool --product "D:\path\product.json" --config config\settings.local.json `
  --category-id 123456 --category-name "目标叶子类目" `
  --store-identity-text "目标店铺名称" `
  --shipping-address "后台已保存地址的稳定匹配文本" `
  --freight-template-text "目标运费模板名称" `
  --delivery-promise "48小时发货" --package-weight-grams 1000 --preview-only
```

确认页面结果后，将 `runtime-config.json` 中的值回填本地配置。该运行记录不会进入版本库。

## 质量门禁

打开卖家后台前会检查：采集校验结果、商品编号、标题长度、目标类目、价格、库存、SKU 结构、素材归属、图片可读性、图片尺寸与大小（包括 SKU 图片）。物流配置按页面实际回显校验；任何确定的错误都会返回非零状态且不启动发布流程。

主图仅从 1688 页面结构化商品图库字段采集，下载只允许 HTTPS 的 1688/阿里图片域名，并限制重定向、响应类型、单文件大小及总量。`product.json` 中的素材必须是当前商品目录下 `assets/` 或 `detail-assets/` 的相对路径；绝对路径、目录穿越和符号链接会被阻断。

页面运行期间还会检查主图实际插入数、SKU 回显、必填属性、详情内容和草稿重新打开后的关键字段。未确认的必填属性会阻断保存。

## 普通启动器适配

已提供 Windows 图形启动器，支持选择商品、采集链接、编辑配置、数据校验、预览填充、保存草稿、查看运行日志和打开数据目录。CLI 仍保持稳定退出码，便于后续接入任务系统。

当前程序不依赖 Codex。商用部署前仍建议配置企业代码签名证书和受控升级源。不要把浏览器 Profile 打进安装包；每个店铺应使用独立 Profile，并由操作者完成登录和验证码。
