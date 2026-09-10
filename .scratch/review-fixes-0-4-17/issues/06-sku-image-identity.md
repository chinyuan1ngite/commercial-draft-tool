# 06: 按媒体身份选择、确认并持久化正确 SKU 图片

Status: claimed
Type: bug
Priority: P1
Blocked by: 05
Spec: [0.4.17 Code Review 修复规格](../spec.md)
Findings: R7
Acceptance: AC14, AC15, AC16, AC17

## What to Build

让每个目标 SKU 得到其对应的 Source Media，并在选择、填写回显和草稿重开后验证相同关联。同名前缀旧图、残留选择和旧上传提示不能产生假成功；已经确认的正确图片可以复用，替换图片不要求数量增加。

## Dependencies

依赖 [05：SKU 图片事务异常恢复](05-sku-image-error-recovery.md)。本任务在该事务边界内携带身份与确认依据，并使用确定失败、成功和未决结果的处理方式，避免另建一套冲突的恢复流程。05 resolved 后方可开始。

## Context and Boundaries

Review 已复现：目标图片名会匹配带有额外后缀的旧图，而数量增长检查发现不了错图。Media Identity 是内容 SHA-256；文件名可用于定位候选，但不能证明媒体身份。保持 SKU Identity、Media Reference 与平台素材身份的区别。

复用已有清单与事务证据；建立当前任务需要的最小内容身份到平台素材的确认关联。没有可信证据时报告未确认，不能任意选图。遵守 ADR 0001-0004，保留已有采集关联、版本与路径边界，不新增视频能力或未支持的属性值图片投影适配器。

## Acceptance Criteria

- [ ] AC14：同名前缀、完全同名但身份不明的旧图、多个候选都不能单凭名称被选择或确认；正确素材必须有可信内容身份到平台素材的关联证据。
- [ ] AC15：开始选择前清理或核对残留选择池；提交前确认池中恰好是该 SKU 的目标图片，不夹带旧项。
- [ ] AC15：旧“上传成功”文本和旧计数不能确认本次上传；使用本次事务进展及结果证据，超时或迟到且无法判定的结果走未决状态。
- [ ] AC16：按可靠 SKU Identity 获取当前行并验证目标素材；替换后数量不变、正确图已存在、行节点重建均可获得正确结论。
- [ ] AC16：已经确认的相同图片被复用，重复执行不重复上传或叠加选择；数量增长但素材错误时必须失败。
- [ ] AC17 的图片部分：重开草稿后重新匹配 SKU 和平台素材；行重排不影响判断，图片交换或缺失即使总数量不变也不能通过。
- [ ] 现有文件输入和“添加”选择器两条支持路径均保持正确；对不支持或歧义的映射返回清晰结果，并遵守必填及未决保存门禁。
- [ ] 真实 DOM fixture 覆盖候选匹配、选择池、上传状态和回显；相关旧测试通过，完成两轴 Code Review，记录失败到通过证据后再标记 resolved。

## Verification Evidence

完成时在 `## Answer` 中记录命令、版本、SKU 到 Media Reference 及平台素材的确认依据、池内结果、重跑行为、重开检查和 review 结论。只保留必要的脱敏证据；不能以文件名或图片数量作为最终正确性证据。

## Comments

任务已创建，等待任务 05 完成；ready-for-agent 表示任务已明确，不代表可以越过依赖开始执行。

### 2026-09-10 Implementation Progress

实现提交 4c43485：用内容 SHA-256 核对已存在图片、相册候选、选择池及目标 SKU 回显；保留 Media Reference；提交后 iframe 消失可通过只读核对恢复成功，不能重复提交。草稿重开按 SKU 重新检查内容，行重排不影响结果、图片交换必须失败。增加 HTTPS 白名单、大小限制、无 Cookie 的内容核验，未验证素材不会按名称选择。

真实隔离 DOM 覆盖完全同名旧图、前缀图、残留选择池、额外混入项、旧成功计数、停滞上传、图片替换、原图复用、行重建与交换。4c43485 全量 141 项测试通过（30 项浏览器 DOM）；compileall、git diff --check 通过。原已存在图片测试返回 indeterminate，修复后 confirmed 且没有上传。清理关闭 iframe 触发的 ElementLostError 也在真实 fixture 复现后修正。

独立两轴审查发现并已修复：网络临时错误不再作为永久失败缓存；同内容不同本地文件名复用本轮已确认平台候选，新增测试实际观测两 SKU 只上传一次、提交两次。

后续验证：全量 143 项通过（116.526s）；另一个新增真实 DOM 用例发现已有正确图片但没有上传控件时错误拒绝复用，现已从失败修至通过（单独执行），7 项事务故障回归再次通过。详细范围见 [verification.md](../verification.md)，没有把单独执行的新增用例算进此前全量数量。

仍未满足的验收：当前核验基于可读取的原字节；若真实平台 src 是压缩/转码/缩略图，尚无可信的原图 SHA-256 到平台原素材 ID，再到派生显示图的关联适配。测试使用原字节 data URL，不代表该兼容路径已通过。不能降低哈希校验或仅用名称解决，需要真实页面上传响应/原素材字段证据。保留 claimed，不宣称 AC14-AC17 的全部平台兼容已经完成。

验收环境阻塞：浏览器库存读取返回 `Codex auth token is unavailable`，没有取得可操作的卖家标签页；本地 settings.local.json 未配置 target.category_id、target.store_identity_text、target.delivery_promise。未向真实店铺上传或保存，未绕过发货时间必填，未打包。恢复浏览器连接并明确有效的测试店铺/商品配置后继续验证；已有详情可见编辑器故障仍属于独立范围。

### 2026-09-10 Album Lookup Follow-Up

Baseline: 83d0fc4479e43b680dc95ca114d73f8fa078b711. User confirmed the existing configure_sku_images / verify_sku_images / report test boundaries and this review baseline.

The reported run has 17 locally valid SKU images and five locally valid detail images. The first SKU upload reports progress but cannot confirm an album identity; the early image gate prevents weight and description execution. This is not evidence that detail collection or its editor failed.

Isolated browser regressions reproduce long-name search missing a truncated album title and upload progress preceding album availability. Both now pass: search uses a short prefix, candidate truncation is tolerated only before strict content verification, and a bounded album poll refreshes the search without uploading again. Missing album records and content mismatches now have separate bounded diagnostic counts. The blocked report explicitly marks unstarted weight/detail stages without relaxing the save gate.

Remaining blocker: this run's four main-image records provide observed thumbnail/original URL pairs. Credential-free reads of those exact URLs did not match the local upload SHA-256, including the platform originals (one inspected original returned image/jpeg with 194762 bytes). This establishes a platform byte-identity compatibility gap, not the precise cause of the first SKU failure. Do not guess original URLs or accept image similarity/name as identity. Need a transaction-correlated upload response/platform media ID and the actual picker-to-row association to support processed media safely. No authentic upload response is present in the supplied artifacts; native browser inspection was stopped by the tool's URL-verification policy.

Task remains claimed. No live upload, draft save/reopen, version bump, or new package is part of this follow-up. See verification.md for automated results and review evidence.

### 2026-09-10 Correlated Upload Receipt

The user supplied the successful POST response from `https://picman.1688.com/album/ajax/image_upload_ajax.json` and a screenshot showing automatic selection (1/1). The response schema is `result: success`, one numeric `dataList` media ID, one `imgUrls` original URL and one `miniImgUrls` thumbnail URL. This is source evidence for an adapter, not a reusable hardcoded media mapping.

Fresh picker uploads now listen only for this endpoint in the picker frame. A unique temporary filename with validated original bytes correlates the multipart request to the local SHA-256. Only a successful, single-result, allowlisted response produces a receipt. The automatically populated selection pool must contain exactly the returned media before commit; SKU readback and reopen use the original/thumbnail URLs declared by that receipt, never guessed URL rewrites or filename identity. Without a correlated response, only the legacy original-byte verification path remains available. The original source files are unchanged.

Isolated Chrome regressions exercise a real multipart POST and response listener with the network response fulfilled locally through CDP (no seller session or remote upload). The former processed-image failure now confirms and verifies the rendered row; wrong file names, multiple response records, error responses, untrusted URLs, wrong/extra selections and swapped readback are rejected. Two SKUs sharing one image reuse the receipt within that call and upload once.

Remaining acceptance: genuine cross-origin seller uploader request capture, complete 17-SKU/details run, draft save/reopen, and durable store-scoped reuse across separate runs. The current receipt is carried in the run report and per-call memory; it is not a persistent store media ledger. Unsupported direct-input processing still requires original-byte verification. Keep claimed until the remaining acceptance is completed; no package or stable-release claim.
