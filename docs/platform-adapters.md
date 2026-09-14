# 平台模块指南

当前只有一个真实实现：1688 来源采集与 1688 卖家草稿。代码已集中到 `src/draft_tool/platforms/alibaba1688/`，但尚未为了未来平台建立抽象基类；第二个真实实现出现后，再从两组行为中确定共同接口。

## 当前模块

| 模块 | 负责的 1688 知识 | 当前主要入口 |
| --- | --- | --- |
| `collector.py` | 商品 URL、页面/内嵌数据解析、详情接口、来源素材与采集落盘 | `main`、`parse_html`、`collect_with_browser`、`save_collection` |
| `browser_actions.py` | 卖家发布页、属性/SKU/媒体/物流填写、预览、保存和重开核验 | `main` |
| `browser_navigation.py` | 1688 页面原生提示框和已知遮挡弹层恢复 | `navigate_with_alert_recovery`、`dismiss_unexpected_popups` |
| `category_capture.py` | 1688 卖家类目选择页及 catId 多源核对 | `main`、`read_category_snapshot` |

共享模块仍在 `draft_tool/` 根包：`media`、`sku_adapter`、`quality_gate`、`config`、`runtime`、`security` 和 `workflow`。这些模块仍含少量当前产品假设，不能仅凭目录位置认定已经平台无关。

## 兼容接口

- `draft-collect` 仍指向 `draft_tool.collector:main`。
- GUI 的采集和类目捕获参数、CLI 保存流程及退出码不变。
- `draft_tool.collector`、`draft_tool.browser_actions`、`draft_tool.browser_navigation`、`draft_tool.category_capture` 是对应新模块的模块别名。
- 旧导入和 monkeypatch 路径与新实现共享同一组全局状态；兼容文件中不得新增业务逻辑。

新仓库代码直接导入 `draft_tool.platforms.alibaba1688`。兼容别名的移除需要单独版本策略，目前没有删除计划。本次移动不改变 `product.json`、媒体清单、配置、报告、运行目录和 SQLite 台账。旧字段读取规则继续遵循 [数据说明](data-model.md) 和 [媒体兼容 ADR](adr/0002-media-manifest-compatibility.md)。

## 下一步提取

`browser_actions.py` 仍然过大。后续按完整行为提取其内部职责，优先选择选图器生命周期或草稿重开核验：调用者只传商品、页面和策略，模块返回结构化结果；选择器、轮询和 DOM 细节留在实现内部。每次只移动一组有现成回归的行为，旧入口继续调用新实现。

商品身份、目标店铺身份和台账键仍采用现有 1688 约定。它们需要在接入第二来源或第二目标平台前单独设计迁移，不能在纯目录整理中顺带改写旧数据。

## 增加第二个平台

1. 先确定它是来源采集、目标草稿或两者，并记录授权接入方式和支持类目。
2. 用平台自己的合成样例实现一条小范围完整流程，不复制 1688 URL、DOM 或错误状态。
3. 保留平台特有来源证据，转换到共同商品含义时显式报告缺失和不支持映射。
4. 有两个真实实现后比较重复行为，再决定共享接口；不要建立要求每个平台实现所有字段的巨型基类。
5. 为预览、保存、重开和正式发布分别声明能力。当前正式发布保护不能因新增平台而移除。
