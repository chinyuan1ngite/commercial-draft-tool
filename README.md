# 1688 自动草稿工具

交付边界固定为：采集商品、校验数据、自动保存草稿、人工审核并手动上架。程序不会点击正式发布按钮。

本目录是独立工程，不读取原项目的 `data/` 或浏览器登录目录。生产运行数据、登录会话、配置和报告均被 `.gitignore` 排除。

## 安装

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
Copy-Item config\settings.example.json config\settings.local.json
```

在 `config/settings.local.json` 中明确填写目标类目、店铺身份校验文本、发货地址、运费模板、发货承诺和重量。`store_identity_text` 应是发布页稳定可见且能唯一识别当前店铺的文字，用于防止登录错账号。

不同类目的规则放在 `category_rules.by_category.<类目ID>` 下。每个类目可配置 `labels`（属性标签到值）、`properties`（属性 ID 到值）和 `manual_required`（必须人工确认的属性 ID）。程序不会猜测缺失的必填属性。

## 先校验再运行

```powershell
draft-tool --product "D:\path\product.json" --config config\settings.local.json --validate-only
draft-tool --product "D:\path\product.json" --config config\settings.local.json --preview-only
draft-tool --product "D:\path\product.json" --config config\settings.local.json
```

最后一条命令会尝试保存草稿，但不会正式上架。每次运行输出 `quality-gate.json`、`runtime-config.json`、页面报告和截图，可据此捕获并固化当前店铺/类目配置。

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

打开卖家后台前会检查：采集校验结果、商品编号、标题长度、目标类目、物流配置、价格、库存、SKU 结构、素材归属、图片可读性、图片尺寸与大小。任何错误都会返回非零状态且不启动发布流程。

主图仅从 1688 页面结构化商品图库字段采集，下载只允许 HTTPS 的 1688/阿里图片域名，并限制重定向、响应类型、单文件大小及总量。`product.json` 中的素材必须是当前商品目录下 `assets/` 或 `detail-assets/` 的相对路径；绝对路径、目录穿越和符号链接会被阻断。

页面运行期间还会检查主图实际插入数、SKU 回显、必填属性、详情内容和草稿重新打开后的关键字段。未确认的必填属性会阻断保存。

## 普通启动器适配

CLI 已保持无 Codex 依赖并提供稳定退出码，后续可直接包装成 Windows 启动器或桌面界面。启动器只需负责：选择商品文件、编辑店铺配置、先执行校验、展示待人工处理项、启动可见浏览器，以及读取 JSON 报告显示最终状态。

当前程序不依赖 Codex，CLI 可由普通 Windows 启动器直接调用。封装前仍建议增加配置编辑与凭据存储界面、浏览器版本检查、安装包签名、自动升级签名和日志脱敏。不要把浏览器 profile 打进安装包；每个店铺应使用独立 profile，并由操作者完成登录和验证码。
