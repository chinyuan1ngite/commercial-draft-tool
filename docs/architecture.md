# 当前架构

适用基线：0.4.24。本页描述实际实现，多平台目标目录见 [整理方案](项目整理与多平台演进方案.md)。

## 执行流

```text
launcher.py ──→ platforms/alibaba1688/collector.py ──→ product.json + 本地素材
     │                                  │
     └────────→ cli.py ←────────────────┘
                   ↓
          config.py / quality_gate.py
                   ↓
               workflow.py
       运行副本、Profile 锁、草稿台账
                   ↓
     platforms/alibaba1688/browser_actions.py
  登录/店铺核验 → 填充 → 预览结果
                       或
                保存 → 重开核验
                   ↓
              report.json 等证据
```

CLI 的 `--validate-only` 校验后直接返回。预览/保存进入 workflow 再次校验，准备运行副本，取得 Profile 锁并调用页面执行。只有保存与重开核验成功且报告含草稿 ID 时才更新台账。

## 模块地图

以下文件相对于 `src/draft_tool/`；平台目录约定见 [平台模块指南](platform-adapters.md)：

| 文件 | 当前职责 | 常见排查点 |
| --- | --- | --- |
| `platforms/alibaba1688/collector.py` | 1688 URL/HTML 解析、浏览器采集、详情请求、下载和落盘 | 采不到 SKU/属性、详情源缺失 |
| `cli.py`、`launcher.py` | 参数、Tkinter GUI、配置和子进程输出 | 按钮、日志、退出码 |
| `config.py`、`runtime.py` | 目标/质量/媒体配置与运行目录 | 类目默认值、配置路径 |
| `quality_gate.py` | 商品/本地素材校验、运行副本 | 标题、库存、路径、图片尺寸 |
| `workflow.py` | 编排、Profile 锁和草稿台账 | 重复草稿、运行目录 |
| `platforms/alibaba1688/browser_actions.py` | 1688 卖家页填写、素材处理/选图、SKU/属性/物流、保存与核验 | 选图器生命周期、可见回显、草稿结果 |
| `platforms/alibaba1688/browser_navigation.py` | 1688 原生弹框、已知弹层和导航恢复 | AlertExistsError、页面遮挡 |
| `platforms/alibaba1688/category_capture.py` | 1688 类目捕获与多源证据核对 | catId 冲突 |
| `collector.py` 等四个根模块 | 旧导入和命令入口的兼容别名，不承载新实现 | 旧脚本/patch 路径兼容 |
| `sku_adapter.py` | 规格规范化、行及价格/库存验证 | SKU 错位、维度不一致 |
| `media.py` | SKU 图片引用/身份与本地路径解析 | 图片缺失、规格关联冲突 |
| `sku_upload.py`、`media_verification.py` | 上传回执关联、平台派生图和内容验证 | 上传成功但图片不能确认 |
| `security.py` | 下载限制、原子写入、Windows 锁、SQLite 台账 | 并发、下载、写入完整性 |

## 持久化与副作用

- 采集按 offer ID 落盘，重复采集使用同一商品目录；草稿运行按商品 ID/运行 ID 隔离。
- GUI 数据位于 LOCALAPPDATA 或 DRAFT_TOOL_HOME；CLI 目录由配置决定。
- 买家与卖家 Profile 分开；同一卖家 Profile 同时只允许一个受管任务。
- 草稿台账键为店铺可见识别文本与 source offer ID，尚无多平台命名空间。
- 预览可能上传素材；点击保存后即使核验失败，也可能已经产生草稿。未知结果不能盲目重试。

## 既有设计约束

术语以 [CONTEXT](../CONTEXT.md) 为准：

- [ADR 0001](adr/0001-media-identity-and-role-boundaries.md)：区分来源归属、媒体角色、SKU 身份与图片内容。
- [ADR 0002](adr/0002-media-manifest-compatibility.md)：媒体清单增加时保持 assets/detail_assets 兼容。
- [ADR 0003](adr/0003-video-rollout-and-retry-policy.md)：视频策略及未知结果的重试限制；视频计划不代表已启用。
- [ADR 0004](adr/0004-safe-sku-image-projection.md)：图片向销售属性投影时不能丢失 SKU 差异。

## 下一步提取位置

1688 页面实现已迁入平台命名空间。下一步从其中的 `browser_actions.py` 提取完整选图器生命周期或草稿核验职责，保留跨域浏览器回归。`workflow.py` 当前仍通过构造 argv 调用 1688 `browser_actions.main`，这只是现有执行接口，并非通用平台接口。

商品目录、台账及类目回退都依赖 1688。多平台需要来源/目标身份和显式转换；不得把新增几个平台分支当作已实现通用支持。
