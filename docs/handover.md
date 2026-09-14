# 维护交接清单

更新日期：2026-09-15。程序基线 `ec97a7e` / 0.4.24。本批新增文档及合成样例，未改商品执行流程，也未重新发布 Windows 包。

## 阅读顺序

1. [README](../README.md)：工具范围和使用入口。
2. [开发指南](development.md) 和 [离线样例](../examples/README.md)：从环境到通过/失败校验。
3. [当前架构](architecture.md) 和 [数据说明](data-model.md)：定位模块与输入/输出。
4. [兼容性与已知问题](compatibility.md)：区分自动回归和真实验收。
5. [贡献指南](../CONTRIBUTING.md)、[路线图](../ROADMAP.md)：任务与下一步。

## 仓库范围

独立工程以含 pyproject.toml 的本目录为根，上层早期脚本、表格及浏览器数据不属于交接源码。dist、build、.venv、.local、data、runtime 和本地 settings 配置被忽略。

本批没有完成全历史敏感内容审计。准备推送时需检查实际分支/标签、文档、样例素材和历史对象；仅有 .gitignore 不代表历史内容已检查。

## 当前接手事项

- 首先完成 0.4.24 真实详情图预览、保存、重开验收，并把范围写入兼容性文档。
- 新开发者可先做文档、离线模型/解析和隔离 Chrome 回归，无需索取真实登录会话。
- 正式发布仍由人工执行，不扩展当前成功状态的含义。
- 下一批建立私有仓库、CI、任务/PR 入口、依赖与包验证流程，详见路线图。

## 历史证据索引

| 事项 | 证据 |
| --- | --- |
| SKU/件重/属性的历史修复 | [验证记录](../.scratch/review-fixes-0-4-17/verification.md) |
| 媒体上传回执与详情确认 | [规格](../.scratch/detail-image-receipts/spec.md)、[验证](../.scratch/detail-image-receipts/verification.md) |
| 属性弹层阻挡详情入口 | [验证](../.scratch/detail-editor-overlay/verification.md) |
| 采集导航与原生提示框 | [验证](../.scratch/collection-native-dialog/verification.md) |
| 相册/搜索后 iframe 更新 | [验证](../.scratch/detail-picker-frame-refresh/verification.md) |
| 初始 about:blank → 跨域选图器 | [规格](../.scratch/detail-picker-cross-origin/spec.md)、[验证](../.scratch/detail-picker-cross-origin/verification.md) |
| 第一批交接资料 | [规格与验收](../.scratch/handover-docs/spec.md) |

历史记录中的本机日志、包和 `.local` 路径不随克隆提供；阅读其中可追溯的结论和测试名称，不依赖作者个人文件。

## 责任与待决策

| 事项 | 当前安排 |
| --- | --- |
| 仓库归属/名称 | 项目所有者待确定 |
| 总维护者/平台维护者/发布者 | 私有仓库建立时指定具体人员；目前不虚构账号 |
| GitHub Issue/PR | 尚未启用，当前使用 [本地任务规则](agents/issue-tracker.md) |
| 开源许可与第三方分发说明 | 公开前由所有者确认 |
| 第二个平台 | 抖音/拼多多及来源/目标优先顺序待决定 |

## 新协作者验收清单

- [ ] 从独立仓库干净副本创建虚拟环境并安装。
- [ ] 正向样例返回 0，负向缺标题样例返回 4，能读懂对应 issues。
- [ ] 不提供真实账号即可跑非浏览器测试，能区分 skipped。
- [ ] 能从报告字段定位 collector、quality_gate、browser_actions 或 workflow。
- [ ] 能解释“预览可能上传媒体”“详情 saved 不等于草稿保存”“未知结果停止重试”。
- [ ] 能找到旧格式兼容约定和未完成的真实页面验收。
- [ ] 完成一次小型修改与维护者评审；GitHub 启用后走 PR。

以上是新协作者本人需完成的操作，自动验证不代替人员交接。当前批次的工具验证结果记录在规格文件中。
