# 01: 按维度填写销售规格并正确验证 SKU 完成状态

Status: resolved
Type: bug
Priority: P1
Spec: [0.4.17 Code Review 修复规格](../spec.md)
Findings: R1
Acceptance: AC01, AC02, AC03

## What to Build

让二维商品的每个销售属性独立填写、提交和回读，生成正确的 SKU 组合，并通过保存前的规格校验。重复运行时保持已正确填写的值，不增加重复值，也不因为其他维度的值误判当前维度完成。

## Dependencies

无前置任务，可立即开始。使用独立页面 fixture 验证本任务，不要求其他属性、重量或图片修复先完成。

## Context and Boundaries

Review 已在本地 Chrome 页面复现：两维各两个值都填写后，接受计数为 2 + 4 = 6，而不是 4，状态成为 partial。根因是已填值的读取范围跨越了不同规格块。

目标维度必须通过标签和可靠页面证据识别。不能把源字典顺序、目标块位置或相同 placeholder 当成维度身份。复用现有填写和 SKU 校验入口，保留价格、库存及 SKU Identity 关联规则；遇到无法确定的维度，不猜测填入。

## Acceptance Criteria

- [x] AC01：两维各两个不同值时，每维接受数量为 2，总数为 4，预期四个 SKU 组合正确出现，返回完成状态且不再被规格完成校验误拦截。
- [x] AC02：不同维度包含相同文字、输入框 placeholder 相同、目标维度顺序变化时，各维度仍得到正确值，没有跨维度去重或覆盖。
- [x] AC03：正确预填值和重复运行不产生重复项；异步生成 SKU 表使用有界等待；缺失、歧义或冲突预填不能被报告为已完成。
- [x] 成功依据包含当前维度的已提交值及实际 SKU 组合；既不只检查输入框文字，也不只检查总行数。
- [x] 保留单维商品的既有行为，规格恢复后价格和库存填写仍绑定正确 SKU。
- [x] 通过真实 DOM fixture 调用实际填写入口，先记录失败再验证修复；不得 mock 值添加函数的接受数量来证明本任务成功。
- [x] 相关旧测试通过，完成 Standards 与 Spec 两轴 Code Review，记录修复前后证据后再标记 resolved。

## Verification Evidence

完成时在 `## Answer` 中记录测试命令、测试版本、失败与通过结果、各维度回读值、目标 SKU 组合和 review 结论。离线浏览器证据与线上卖家验收分别标记；完整线上验收由任务 07 汇总。

## Comments

任务已创建，尚未开始实现或执行新的修复验收。

## Answer

已完成按标签定位规格块、逐维回读计数及真实组合验证，并使共享 SKU 读取保留维度名。价格与库存按完整规格匹配，支持列和行重排。

验证：启用 DRAFT_BROWSER_TESTS=1 后，test_browser_dom.py 的 6 项真实 Chrome fixture 测试通过；相关 browser 测试此前 46 项通过，新增二维价格场景单独纳入上述 6 项。compileall 和 git diff --check 通过。最初单条回归明确失败（接受数量 6、partial），修复后为 4、filled。

Code Review：Standards 轴 0 项；Spec 轴提出 1 项价格/库存真实 DOM 验收缺口，已补单维及二维重排测试并通过。真实卖家页面端到端验收留在任务 07，未宣称线上已验证。
