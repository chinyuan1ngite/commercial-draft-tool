# 04: 安全关闭意外弹窗并保护当前页面操作

Status: resolved
Type: bug
Priority: P1
Spec: [0.4.17 Code Review 修复规格](../spec.md)
Findings: R5
Acceptance: AC10, AC11

## What to Build

让采集或填写过程中出现的意外弹窗得到有界处理，同时避免自动同意丢弃、清空或覆盖。通知框可以关闭，未知确认框和输入提示框应取消；用户当前正在使用的图片选择器、详情编辑器等操作界面不被误关。

## Dependencies

无前置任务，可立即开始。通过原生弹窗与页面覆盖层 fixture 验证，不依赖图片事务或素材身份修复。

## Context and Boundaries

Review 已在本地 confirm 测试中观察到关闭逻辑返回 true，相当于确认丢弃修改。真实线上误清空仍属于潜在后果，不把本地复现描述成已经发生的线上事故。

导航恢复和填写阶段恢复必须遵循一致的确认策略。只关闭可见且识别为无关的覆盖层；清理范围属于当前操作。是否属于预期操作应依赖上下文，不能根据提示文字包含某个宽泛关键词就自动接受。

## Acceptance Criteria

- [ ] AC10：原生 alert 被关闭；未知 confirm 返回取消；未知 prompt 被取消且没有写入虚构内容，fixture 中的破坏性动作没有执行。
- [ ] AC10：空文本弹窗也得到处理；仅在业务上下文明确预期的情况下允许接受确认。
- [ ] AC11：可见无关覆盖层得到关闭；隐藏关闭按钮、当前图片选择器及详情编辑器不被误触。
- [ ] 导航恢复和填写阶段均执行相同策略，不能由另一条恢复入口重新引入无条件接受。
- [ ] 恢复尝试和等待有界；持续阻塞产生可定位的受控失败，记录处理结果而不是无限重试或吞错后宣称成功。
- [ ] 用隔离浏览器真实 alert、confirm、prompt 和覆盖层验证，检查实际返回值与界面状态，而非只断言调用次数。
- [ ] 相关旧测试通过，完成两轴 Code Review，记录失败到通过证据后再标记 resolved。

## Verification Evidence

完成时在 `## Answer` 中记录命令、版本、弹窗类型、采取的动作、实际返回值、受保护窗口状态、有界失败结果和 review 结论。报告不得包含登录凭据或敏感会话数据。

## Comments

任务已创建，尚未开始实现或执行新的修复验收。

## Answer

2026-09-10：实现提交 271025c，登录测试边界补齐 96024be。未知原生对话统一有界取消，包括导航、填写及保存后恢复；保护当前图片/详情窗口，只触发可见无关关闭控件。探测或取消失败返回受控状态并写 report.json，不再读取阻塞页面截图。采集和类目入口同步处理。

失败到通过：原 confirm fixture 返回 true，修复后 false；新增 probe 异常测试原抛 RuntimeError，现为受控 PopupRecoveryError。DRAFT_BROWSER_TESTS=1 的 test_browser_dom.py 21 项通过（含 5 项真实弹窗场景）；test_browser_actions.py 43 项、test_security_and_collector.py 28 项、test_login_wait.py 3 项、test_category_capture.py 2 项通过；compileall 与 git diff --check 通过。空 alert/prompt、连续弹窗有界停止和当前编辑窗口保留均已在隔离 Chrome/DrissionPage 4.1.1.4 验证。

Review：独立 Standards 审查没有规范/结构问题，另发现保存后旧 accept=True 入口与导航异常吞错，均已修复；Spec 轴由主代理本地复核 AC10/AC11 和调用链，没有剩余已知阻断。不把本地 Spec 复核称为独立子代理审查，真实卖家集成留在任务 07。
