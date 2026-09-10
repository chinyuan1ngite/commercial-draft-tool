# 0.4.17 Code Review 修复规格

Status: ready-for-agent
Type: bugfix-spec
Created: 2026-09-10
Baseline: 58fa651 (0.4.17)
Review range: 620d2ff...58fa651

## Problem Statement

当前采集到卖家草稿的填写链路存在 7 个独立问题。用户可能看到规格、属性或图片填写失败，也可能在程序报告成功时得到错误的 SKU 图片或重量。现有 103 项测试通过，不能证明这些页面交互正确。

| 标识 | 问题 | Review 证据及影响 |
| --- | --- | --- |
| R1 | 二维销售规格跨维度计数 | 本地 Chrome 页面中，两维各两个值都已填写，但接受数量为 2 + 4 = 6，返回 partial，阻止草稿保存。 |
| R2 | 属性搜索文字被当成已提交选项 | 本地 Chrome 页面中，只输入搜索词、已提交值仍为空，属性填写却返回成功。 |
| R3 | 重量规格身份忽略维度名称 | 目标规格列反转且跨维度值重叠时，已复现应写入 100g、200g，实际写入 200g、100g。 |
| R4 | 缺重 SKU 的已知身份被丢弃 | 三个规格唯一，重量为 300g、500g、缺失时，返回 mapping_ambiguous，三个重量均未填写。 |
| R5 | 意外确认框被自动接受 | 本地原生 confirm 测试中，关闭流程对丢弃修改的确认返回 true。误清空或覆盖是线上潜在风险，未证明已在真实卖家页面发生。 |
| R6 | 图片选择器异常越过错误处理边界 | 查找控件、点击或取得 iframe 的异常可直接传播；异常注入已验证，可中断后续重量和详情填写。 |
| R7 | 图片匹配与确认缺少可靠身份 | 本地页面请求某个图片名时会选中文件名前缀相同的旧图；图片数量增加不能证明 SKU Image 正确。 |

以上证据来自上一轮 review 的代码检查、本地隔离浏览器页面和异常注入，不代表真实卖家页面端到端验收已通过。重量默认说明与实现矛盾属于 R4 的文档部分，不重复计为第八个问题。

## Solution

在现有采集、填写、报告和草稿保存链路内修复上述问题，使成功状态对应可核验的目标页面状态。规格值按维度提交，属性以实际选中结果确认；每个 SKU 的价格、库存、重量和图片保持正确关联。可恢复的图片错误记录后继续独立填写步骤；未知确认框采取取消操作；无法确认身份或存在未决副作用时阻止不可靠的保存。

保持既有采集数据、配置和草稿工作方式兼容。实现采用局部修复及必要的共享身份规则，不扩展为全项目重构。

## User Stories

1. As an operator, I want each sales-property dimension to retain its own values, so that a two-dimensional product generates the intended SKU combinations.
2. As an operator, I want equal text in different dimensions to remain distinct, so that one dimension does not suppress values in another.
3. As an operator, I want prefilled values and repeat runs to be handled correctly, so that retries neither duplicate values nor misreport completion.
4. As an operator, I want source dimensions matched to target labels, so that a changed target order cannot silently exchange dimensions.
5. As an operator, I want an attribute reported as filled only after its value is committed, so that a search term does not leave a required attribute empty.
6. As an operator, I want text fields, single selects, and multiple selects to keep working, so that fixing one control type does not break another.
7. As an operator, I want attribute readback to exclude search and duplicate display wrappers, so that reports describe the actual selection once.
8. As an operator, I want package weights associated with complete SKU identities, so that target row or column reordering does not change which weight belongs to which SKU.
9. As an operator, I want validated merchant-code aliases retained for logistics mapping, so that rows without source SKU IDs can still be matched safely.
10. As an operator, I want missing weights to use my configured value or 1000g, so that known SKUs are not left empty merely because collection missed their weights.
11. As an operator, I want collected weights to take precedence over fallback values, so that a missing weight on one SKU does not overwrite valid weights on others.
12. As an operator, I want ambiguous identities reported before weights are written, so that a default does not hide an incorrect association.
13. As an operator, I want unexpected confirmation dialogs cancelled, so that recovery cannot approve discarding or overwriting my work.
14. As an operator, I want the active media picker and detail editor preserved, so that popup recovery does not close a legitimate transaction.
15. As an operator, I want recoverable SKU image errors isolated, so that later images, weights, and detail steps can still run when the page is safe to continue.
16. As an operator, I want each SKU Image verified against its intended Source Media, so that an old image with a similar filename cannot be accepted.
17. As an operator, I want stale picker selections and old upload messages excluded from confirmation, so that an interrupted run does not contaminate the next one.
18. As an operator, I want already confirmed images reused without duplication, so that replacement and repeat runs can succeed even when image counts do not increase.
19. As an operator, I want required and optional image failures treated according to Media Requirement, so that missing optional media and unsafe operations are not confused.
20. As an operator, I want a saved draft reopened and checked by SKU identity, so that a successful save response does not conceal lost or swapped data.
21. As a maintainer, I want repeatable regressions for the observed browser failures, so that passing tests provide evidence beyond mocked success values.
22. As a maintainer, I want each repair independently verifiable and reviewed, so that interrupted work can resume without losing its acceptance criteria.

## Implementation Decisions

### Scope and Domain Boundaries

- Use the existing collection model, normalized SKU model, browser actions, browser navigation, media resolution, reports, and save/reopen checks. Prefer existing testable entry points; introduce only the smallest helpers required to express shared identity or transaction behavior.
- Respect ADR 0001 through ADR 0004. SKU Identity means source platform SKU ID, or an unambiguous complete specification combination. Media Identity means content SHA-256, not filename. Preserve the distinction between a SKU identity and an uploaded platform media identity.
- Keep current source-to-manifest association behavior, including evidence-backed images from sale-property values and rejection of conflicting associations. This repair does not introduce new media collection roles.
- Merchant code may serve as a validated logistics alias for a source SKU. It does not redefine the canonical SKU Identity used by media. Accept an alias only when its association is known and unique; a field that merely resembles a code is insufficient.
- Preserve existing data consumers and result fields where possible. Any needed transaction evidence or failure detail is additive; update all affected callers and tests together. Do not silently relax manifest compatibility or path checks.

### R1: Sales Dimensions and SKU Completion

- Resolve the target block by its dimension label and supported page evidence, not only by position or placeholder. Missing, duplicate, or ambiguous labels must produce an explicit unsupported or incomplete result unless other reliable evidence resolves them.
- Scope value lookup, insertion, deduplication, blur/commit, and readback to that block. Identical placeholders and identical value text across dimensions must work independently.
- Count committed requested values for each dimension. Compare the accepted set and intended SKU combinations, not a sum gathered from the entire form. Unexpected combinations or conflicting prefilled values must be surfaced rather than silently accepted.
- Use bounded waits for the generated SKU table. Success requires both committed dimensions and validated target rows. Repeat execution must preserve correct values without duplication.

### R2: Attribute Commitment and Readback

- Separate editable search text from committed enum selections. Filling a search field only filters candidates; commit a valid option and confirm the resulting selected value after the control settles.
- Read selected options or tags for enum fields. Read the actual input value for plain text fields. Preserve direct-text custom controls only where the target explicitly supports that behavior.
- Read each committed value once from the appropriate rendered node. Do not repair duplicated wrapper text by blindly deleting repeated character sequences, which can corrupt legitimate labels.
- Preserve plain-text certification fields, single-select behavior, multi-select removal of conflicting prefilled values, and asynchronous menus. Report unmatched or uncommitted required values as failures.

### R3 and R4: Package Weight Identity and Fallback

- Resolve target identities from source SKU ID, validated logistics aliases, or complete named specifications. Obtain specification dimension meaning from headers or other reliable target metadata. Normalize names and values consistently with existing complete-specification rules.
- Identity comparison must be independent of source dictionary insertion order, target column order, and target row order. Repeated values in different dimensions remain distinguishable by their dimension names.
- Build identities from all source SKUs, including those without collected weights. Establish identity before looking up weight; absence from the weight table does not make a known SKU unknown.
- Weight precedence is collected applicable weight, then valid explicitly configured fallback, then 1000g. A product-wide collected weight is applicable only when the source represents it as product-wide. The configured value replaces the default, not valid per-SKU collected weights.
- Fully missing source weights can use a uniform configured/default value. A proven common source weight can use the existing uniform-fill path. Neither case requires inventing per-SKU associations.
- When differing per-SKU weights cannot be mapped safely, validate before writing and report mapping ambiguity. Do not convert an ambiguous association into an apparently successful all-default fill.
- Preserve grams in target inputs and keep reports explicit about the unit and the collected/configured/default origin of each chosen weight. Reopen verification compares weight by resolved identity, not raw row position.
- Update user-facing weight guidance to distinguish missing data from ambiguous mapping. Preserve existing valid numeric constraints; invalid values are not valid collected evidence.

### R5: Unexpected Dialog Handling

- Ordinary native alerts can be dismissed. Unknown confirm and prompt dialogs must be cancelled without approving their proposed action or entering fabricated input. Acceptance requires an explicit, currently expected business operation.
- Apply the same policy to existing navigation recovery and fill-stage recovery so one route cannot reintroduce unconditional acceptance.
- Close only visible, identified unrelated overlays. Preserve the active image picker, detail editor, and other dialogs owned by the current operation. Scope cleanup to the transaction that opened the UI.
- Recovery must be bounded and account for empty dialog text. Record what was handled and whether continuation is safe; persistent blocking dialogs produce a controlled failure rather than an endless retry.

### R6: SKU Image Error Boundaries and Recovery

- The per-image transaction covers row resolution, control lookup, click, iframe acquisition, upload/selection, commit, readback, and cleanup. Expected interaction failures in any stage must become a recorded result rather than an uncaught whole-run traceback.
- On element replacement, reacquire the row by validated identity before continuing or confirming. Do not reuse a stale positional association.
- Preserve the original error and failed stage if cleanup also fails. Record the affected SKU and recovery outcome without including credentials or sensitive session data.
- If the operation has definitively failed and the page is safe, continue later independent work. Missing optional media is a warning; required media remains a save blocker.
- If upload or commit may have occurred but the final state is unknown, use the existing Indeterminate Upload policy: pause automatic retry and draft saving until the state is reconciled. Exception handling must not manufacture a known failure or success from an unknown state.

### R7: SKU Image Identity and Confirmation

- Carry the intended Media Reference and content identity through the operation together with the resolved target SKU Identity. A local path alone is insufficient evidence of which remote image was selected.
- Exact normalized titles may help locate candidates, but neither exact names nor prefixes prove Media Identity. Reuse requires a confirmed content-to-platform-media association; fresh uploads require transaction-specific evidence linking the intended local asset to the resulting platform media record.
- Use existing transaction or store-scoped evidence where available. Establish the minimum association needed for correct confirmation; this spec does not require a new general-purpose media platform. Without reliable evidence, report unconfirmed instead of selecting an arbitrary candidate.
- Clear or reconcile the picker selection pool before selection. Verify that the final pool contains exactly the intended image for that SKU before submitting.
- Distinguish this upload's progress and completion from stale success text or a previous upload counter. Wait within a bounded deadline; late or uncertain results must follow the indeterminate-state rule.
- Verify the intended platform image on the correctly resolved row after commit. Increased image count is neither necessary nor sufficient: replacements and already correct images may keep the count unchanged, while wrong images may increase it.
- Reuse a confirmed image on retry without reuploading or duplicating selection. Verify the same association on draft reopen; a count of rows containing any image cannot confirm correctness.
- Preserve existing supported file-input and add-button paths. If the page only supports property-value images, apply existing capability and safe-projection decisions; expanding support to a new target mapping is outside this repair.

### Proposed Delivery Order

The seven work items below preserve the agreed breakdown. R3 and R4 share one complete weight repair; the final item verifies integration rather than adding an eighth defect.

| Item | Deliverable | Blocked by | Review coverage |
| --- | --- | --- | --- |
| 01 | Dimension-scoped filling and correct SKU completion | None | R1 |
| 02 | Committed attribute selection and accurate readback | None | R2 |
| 03 | Safe weight identities and missing-weight fallback | None | R3, R4 |
| 04 | Safe native-dialog and overlay recovery | None | R5 |
| 05 | Complete SKU image transaction error handling | None | R6 |
| 06 | Verified SKU Image selection and persistence | 05 | R7 |
| 07 | Cross-feature regression and draft reopen acceptance | 01, 02, 03, 04, 05, 06 | R1-R7 |

Items 01-05 are independently testable. Their numbering is a suggested work order, not an artificial dependency chain. Item 06 builds on the complete transaction boundary and recovery outcomes delivered by 05. Each implementation item includes its own tests and Code Review; testing is not deferred entirely to 07.

## Testing Decisions

### Test Boundaries

Use the existing page-filling operations as the primary behavioral boundary, with real browser DOM fixtures and observable form state. Exercise the actual selectors, handlers, commits, readback, and reports together. For complete persistence, use the existing draft workflow boundary against representative seller pages.

Pure identity and fallback rules can retain focused unit tests. Use fault injection for element loss, timeout, and cleanup errors, but keep the transaction's own error handling real. A test that stubs the function under test or supplies predetermined successful browser results cannot satisfy the corresponding UI acceptance criterion.

Existing unit tests for SKU normalization, media association, weight fallback, browser actions, navigation, and workflow gates provide regression coverage to preserve. The known weak examples are dimension tests that mock the value-adder's accepted count and attribute tests that mock the selected value. Supplement or replace those assumptions with observable behavior.

The agreed test approach reuses current entry points; no new public testing interface or framework is required by this spec. Keep offline fixtures isolated from the user's running browser and seller session.

### Acceptance Matrix

| ID | Scenario | Required observable result |
| --- | --- | --- |
| AC01 | Two dimensions, two distinct values each | Each dimension reports 2 committed values; total is 4, intended four SKU combinations appear, and dimension validation succeeds. |
| AC02 | Same text across dimensions, identical placeholders, or reversed dimension order | Values are assigned to the correct named dimension with no suppression, overwrite, or positional exchange. |
| AC03 | Correct prefill, repeated run, delayed SKU rendering, or ambiguous blocks | Correct prefill is idempotent; waits are bounded; incomplete or ambiguous state is never reported filled. |
| AC04 | Searchable required enum with typed text but no selected option | Filling is not reported successful and the required-attribute gate remains unsatisfied. |
| AC05 | Asynchronous enum, multi-select, plain-text certification, duplicate display wrappers | Valid values are committed and read once; missing options fail; plain-text and multi-select behavior remains correct. |
| AC06 | Named specifications A=(first:x, second:y), B=(first:y, second:x), with reversed target columns | A receives 100g and B receives 200g regardless of row order or source dictionary order. |
| AC07 | Unique SKU specifications with weights 300g, 500g, missing | Inputs become 300g, 500g, 1000g; configuring a valid 1500g fallback changes only the missing value. |
| AC08 | No collected weights, or a proven uniform source weight | All applicable rows receive the configured/default or source uniform value in grams without invented SKU identities. |
| AC09 | Duplicate aliases, incomplete specifications, conflicting identities, or differing unmappable weights | No guessed per-SKU writes; report ambiguity and keep the save gate unsatisfied. |
| AC10 | Native alert, unknown confirm/prompt, including empty text | Alert is dismissed; confirm/prompt is cancelled; the fixture's destructive action is not executed. |
| AC11 | Visible unrelated overlay alongside hidden controls or an active picker/editor | Only the appropriate visible unrelated overlay is closed; the active transaction survives. Persistent blockers fail within a bound. |
| AC12 | Element loss or failure during lookup, click, frame acquisition, upload, submit, readback, or cleanup | Record stage and SKU, retain the original error, and avoid an uncaught whole-run exception. Continue independent steps only after safe recovery. |
| AC13 | Definite optional image failure versus required image failure versus indeterminate upload | Optional known failure can warn and continue; required failure blocks save; indeterminate state blocks automatic retry and save. |
| AC14 | Exact-name or prefix collisions with old images; multiple matching candidates | No image is selected or confirmed based on a filename alone; only the intended media association is accepted. |
| AC15 | Stale selection pool, old upload-success message, late completion | Reconcile the pool, require current-operation evidence, and avoid committing stale or unrelated images. |
| AC16 | Correct image already present, replacement with unchanged count, or row recreation | Confirm by SKU and media identity, not count increase or an old element handle; repeated execution does not duplicate upload or selection. |
| AC17 | Target row reorder or swapped images after save/reopen | Weight and image checks resolve identities anew; swapped or missing media fails verification even when counts match. |
| AC18 | Representative multi-SKU/multi-price product through the complete workflow | Specification quotation, each SKU's price/stock/weight/image, committed attributes, and draft identity remain correct after reopen. No formal publish action occurs. |

### Verification and Completion

- For each repair, preserve a repeatable regression command that demonstrates failure before the change and success afterward. Do not mark mock-only selector checks as browser acceptance.
- Run relevant existing tests while implementing, then the full suite and applicable syntax/static checks at integration. Review each item against both project standards and this spec before completing it.
- Final review compares all repair commits against the recorded baseline. Existing agent configuration changes are separate from business repairs and must be preserved.
- Seller-page acceptance covers at least a two-dimensional multi-price product, a product with distinct per-SKU weights, a partial-weight case, and both available SKU image control paths. Use fixtures for unsupported live scenarios and label that evidence accurately.
- Record tested revision, scenario, expected and observed behavior, test outcome, and available sanitized artifacts. Keep automated, fixture-browser, and live seller-page evidence distinct.
- A successful save response is insufficient: identify the intended draft, reopen it, and verify each relevant field by identity. Preserve the existing guard against formal product publication.
- No stable-release claim or final integration completion is allowed while required acceptance remains unverified. Packaging is a later delivery step after acceptance; this spec alone does not assert that 0.4.17 has been fixed.

## Out of Scope

- Main video and detail video collection, downloading, configuration, and new media roles remain deferred.
- Shipping-time business configuration and its known required-field error remain deferred. This does not authorize bypassing seller validation; use an already valid configured acceptance environment or report the blocker.
- The previously reported visible product-detail editor failure is not independently repaired under R1-R7. Ensure image failures no longer skip the detail step, and record whether the existing detail path succeeds during integration. If that separate failure blocks a complete draft test, retain the blocker and open separate work rather than declaring end-to-end success.
- Adding new category adapters, broad architecture refactors, replacing the browser automation library, or hardcoding product IDs, toy types, certificate values, or individual test examples into generic rules.
- Formal product publication, automatic destructive confirmation, creating remote issues, or changing the configured issue tracker.
- Implementing code, creating the individual tickets, bumping versions, building binaries, or committing changes as part of this specification-writing step.

## Further Notes

This specification is the local tracker artifact for the accepted repair scope and is ready to be split into implementation tickets. Proposed work items are not completed or claimed tickets. The next step is to create one ticket per delivery item, carrying the relevant acceptance IDs and blocking edges.

The prior review found no obvious new regression in source sale-property image evidence, conflict rejection, manifest version handling, or local asset boundaries. Preserve those properties during the repair. Prior test success is a baseline observation, not acceptance evidence for the future implementation.

Existing ADRs remain authoritative. In particular, cancelling unknown dialogs and distinguishing definite failures from Indeterminate Upload preserve safety without treating every recoverable optional image error as a global failure. If actual platform behavior requires a conflicting decision, document and resolve that conflict before weakening the acceptance criteria.
