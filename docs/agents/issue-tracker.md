# Issue Tracker

私有 GitHub 远端建立后，GitHub Issues 是任务状态、负责人、标签和讨论的唯一入口。`.scratch/` 保留可随代码评审的规格、验收证据和历史记录，但不与 Issue 重复维护状态。

## GitHub 工作流

- 故障使用 Bug report 表单，平台能力使用 Platform feature 表单；禁用无结构空白 Issue。
- 新 Issue 默认 `needs-triage`。维护者按 [标签映射](triage-labels.md) 改为 `needs-info`、`ready-for-agent`、`ready-for-human` 或 `wontfix`。
- 用 Assignee 表示当前负责人；用关联 Issue/PR 和 GitHub 的 blocked-by 关系表达依赖。
- PR 使用 `Closes #<number>` 关联实现任务。合并后由 GitHub 关闭 Issue，不在本地另建完成状态。
- 页面故障必须区分隔离浏览器回归与真实页面验收；没有授权店铺证据时保留对应限制。

## 仓库内规格

需要跨文件设计、兼容迁移或长期证据时，在 `.scratch/<feature-slug>/spec.md` 记录规格，并从 Issue 链接。稳定架构决策进入 `docs/adr/`；公开接口和格式进入正式文档。规格应写明基线、范围、验收条件和验证，不包含账号或现场数据。

现有 `.scratch/*/issues/` 是迁移前历史，可以继续引用但不创建新的本地执行票。没有 GitHub 远端的离线副本可临时在规格中记录进度，联网后应同步回已有 Issue，避免创建两个任务身份。

## 数据边界

Issue、PR 和规格只使用合成或脱敏证据。不得上传 Cookie、令牌、浏览器 Profile、整个运行目录、未脱敏卖家页面、本机用户路径或不必要的商品数据。完整报告留在授权机器；提交最小错误类型、阶段和必要字段。
