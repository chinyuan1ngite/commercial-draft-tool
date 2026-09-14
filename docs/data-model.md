# 数据说明

适用基线：0.4.24。本页记录现有读取/写入约定，不是新平台的最终 Schema。完整媒体术语见 [CONTEXT](../CONTEXT.md)。可运行输入见 [离线样例](../examples/README.md)。

## 商品目录与 product.json

```text
<商品目录>/
  product.json
  raw.html                 # 真实采集页面，仅保存在本机
  assets/                  # 主图
  detail-assets/           # 详情图
  sku-assets/              # SKU 图片
```

| 字段 | 当前用途与注意事项 |
| --- | --- |
| `schema_version` | 采集器写入字符串 `1.0`；当前不等于完整 JSON Schema 验证器 |
| `source` | platform 固定为 `1688`，offer_id、url、collected_at；多处仍只按 offer_id 使用 |
| `status` / `validation` | 采集状态和采集校验；后续质量门禁还会重新验证，不以采集成功代替素材可用 |
| `category` | 源类目 top_id/second_id/leaf_id/leaf_name；目标未指定时使用源叶子类目 |
| `title` / `attributes` | 标题与属性；标题不会因过长而静默截断 |
| `price` | primary、observed、min_order 等来源价格信息；不能当作跨平台售价规则 |
| `stock` | total_observed 和 sku_values；属于采集时观察值，不是库存同步服务 |
| `skus` | 每行 sku_id、name、properties、price、stock，可带 image_ref |
| `sku_model` | 采集时生成的规范化维度/行；质量门禁会从 skus 重新规范化 |
| `package_weights` | 源件重与规格关联信息；可靠匹配后使用，缺重与映射歧义分开处理 |
| `images` / `description` / `detail_text` | 来源图 URL、详情文本/HTML 等，不代表本地文件已下载或平台已插入 |
| `assets` / `detail_assets` | 主图和详情图下载记录；status 为 saved 且 path 有效才参与本地读取 |
| `media_manifest` | 媒体清单，当前版本整数 1；SKU 图片主要经此解析 |

商品没有主图文件时，即使 images 中有 URL 也不能通过素材门禁。当前主图/详情图仍主要从旧 `assets` / `detail_assets` 读取，不能只写 manifest 而删除这些字段；这是 [兼容 ADR](adr/0002-media-manifest-compatibility.md) 的过渡状态。

## SKU 与媒体

`properties` 优先表达完整命名规格，如 `{"颜色":"红色","尺寸":"大号"}`。没有可靠维度标签时，规范化器可能退化为“规格”单维并产生警告。目标行匹配不能依靠 source_index 或页面顺序。

媒体清单项包含 id、type、role、source_url、local_path、sha256、status、source_evidence。SKU 图片还含 `sku_identities`，每项有 sku_id 和 specification。`skus[].image_ref` 引用清单项 ID。

SHA256 表示本地内容身份；平台上传返回的媒体 ID 和派生图 URL 属于执行证据，不应写回替换源商品身份。清单 ID 在远程阶段可由 URL 派生，已下载 SKU 图片引用会按内容重新关联；不能假定每个清单 ID 一开始就是内容哈希。

媒体版本不为 1 时，当前 SKU 解析报告不支持。商品 Schema 版本、媒体版本、配置版本是不同字段，其校验严格程度目前也不同；不要声称已有统一版本迁移器。

素材路径相对于 product.json：主图限 assets、详情图限 detail-assets、SKU 图片限 sku-assets。拒绝绝对路径、`..`、符号链接和解析后越界；角色不明、关联冲突或缺图不能用任意图片补齐。

## 配置与覆盖顺序

结构见 [配置模板](../config/settings.example.json)：version、target、quality、media、profile_dir、output_root、category_rules。

- target：类目、店铺识别文字、物流可选值、后备包裹重量。
- quality：标题长度、素材数量/尺寸/大小、是否要求详情图/SKU 图。
- media：SKU 图片采集和填写分别开关；开关不同于必填策略。
- category_rules.by_category：按类目 ID 组织 labels/properties/manual_required 等规则。

独立 CLI 显式参数覆盖对应配置值；未指定目标类目时回退到源类目。确认缺重时使用配置的后备值或 1000g，可靠的源件重优先；差异重量映射不清时阻止保存。

配置文件位于 `config/` 时，相对 profile/output 路径按其上一级解析；其他目录中的配置按文件所在目录解析。GUI 使用 runtime 初始化的独立配置，不会自动读取仓库的 config/settings.local.json。

## 报告与成功含义

`--validate-only` 向 stdout 输出 passed、issues、warnings、summary，不自动生成 report.json。常规任务在运行目录写入 quality-gate.json、runtime-config.json、category-rules.json、runtime-product.json；到达页面阶段后才有 report.json，页面安全状态允许时还有 HTML/截图。提前失败时这些文件不一定齐全。

| 字段或值 | 如何理解 |
| --- | --- |
| `passed` | 本地质量校验通过；不说明卖家页面接受这些字段 |
| `result: preview_filled` | 预览通过当前检查，未保存草稿 |
| `result: preview_partial / preview_invalid` | 预览不完整或页面/SKU 校验失败，需要看具体字段 |
| `result: draft_saved_and_reopened_verified` | 保存并重开后的关键检查通过；仍未正式发布 |
| `fields.description.text_saved` | 详情文字结果，不代表图片完成 |
| `fields.description.saved` | 详情组件填充结果，不是整个商品草稿保存状态 |
| `fields.description.images` | requested、inserted、preview_count、status、batches 等详情图片证据 |
| `batches[].stage / error` | 首个失败步骤与错误类型 |
| `side_effect_possible` | 可能已上传或提交；未知结果不可当作“未发生”重试 |

这些是定位摘要，新增阶段可能出现更多字段。顶层 result、字段证据和退出码应一起阅读；退出码也随采集/校验/草稿入口而有差异。

## 台账和兼容约束

`DraftLedger` 使用 SQLite drafts 表，主键为 `(store_identity, source_offer_id)`，保存 draft_id、output_dir、updated_at。台账不是商品主数据，也不是跨次运行的图片上传回执库。

`--output-dir` 更改任务输出根目录，不自动改变配置 output_root 下的台账位置。不要删除台账绕过重复草稿保护。多平台主键及迁移、稳定店铺 ID、独立目标价格等仍见路线图，尚未实现。
