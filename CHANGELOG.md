# Changelog

## Unreleased

- Reorganized the README around user, developer and maintainer entry points.
- Added architecture, data, development, compatibility, handover, contribution and roadmap documentation for private collaboration.
- Added deterministic offline product and media fixtures with one passing and one focused failing validation example.
- Documented the current 1688-only implementation separately from the proposed source/target platform model.

## 0.4.24 - 2026-09-11 (Validation Build)

- Validation: 175 tests passed, including 56 isolated Chrome tests.
- Waited through the detail picker's initial `about:blank` document until the real picture-manager controls are available in the cross-origin iframe target.
- Prevented the observed prepare-stage `ContextLostError` that left a saved text component with five requested images, zero inserted images and zero visible preview images.
- Added a deterministic dual-origin Chrome regression that fails on 0.4.23 and passes twice with this repair.
- Preserved upload receipt, media identity, source order, visible-preview confirmation and indeterminate-side-effect safeguards.

## 0.4.23 - 2026-09-11 (Validation Build)

- Validation: 174 tests passed, including 55 isolated Chrome tests.
- Reacquired the current detail picture-picker iframe after album-tab and album-search actions replace its document.
- Prevented the observed text-only result where four prepared detail images failed before the first upload with ContextLostError.
- Kept retries before media side effects; uncertain uploads and inserts remain blocked from automatic retry and draft saving.
- Added deterministic Chrome regressions for iframe replacement during album navigation and search, requiring verified image readback in the visible detail preview.

## 0.4.22 - 2026-09-11 (Validation Build)

- Validation: 172 tests passed, including 53 isolated Chrome DOM tests; independent Standards and Spec reviews have no findings.

- Allocated a separate available browser debugging port for collection while preserving the configured buyer profile, avoiding attachment to the seller's default-port session.
- Collected in a fresh tab so a restored page's recurring leave confirmation cannot block source navigation.
- Converted exhausted native-dialog retries and explicit navigation failure into controlled errors handled by the collection CLI.
- Reported collection-browser startup failures without leaking an unhandled browser-library traceback.
- Reproduced the reported navigation stack with a persistent beforeunload dialog; the original report does not identify the actual dialog type.

## 0.4.21 - 2026-09-11 (Validation Build)

- Cancelled the known property-application modal before continuing seller-page actions, including dialogs without a close button.
- Required a unique enabled Cancel control and verified the blocking dialog closed; unavailable cancellation stops the workflow.
- Kept active image pickers and schema editors protected during popup recovery.
- Refused writes to a hidden legacy editor, preventing invisible fallback content from being mistaken for visible detail progress.
- Reproduced the user-reported empty component result with the observed blocking overlay; cancelling that overlay restored isolated text and image insertion.
- Validation: 169 tests passed, including 51 isolated Chrome DOM tests; independent Standards and Spec reviews have no findings.
- Real seller upload/save/reopen acceptance and unrelated SKU/required-field errors remain outside this validation result.

## 0.4.20 - 2026-09-11 (Validation Build)

- Inserted detail images through correlated upload receipts and the verified automatic selection, even when the album has not refreshed or titles are truncated.
- Verified rendered detail image identities and source order while preserving existing preview content; rejected wrong or extra selections and incorrect preview images.
- Stopped subsequent image operations and automatic description retries when an upload or insertion is uncertain.
- Reported text commitment separately from complete description success, preventing incomplete detail images from passing preview and save gates.
- Preserved strict original-byte verification for uploads without a correlated receipt.
- Required explicit image confirmation at the shared save gate; legacy URL-only writes now report indeterminate images and cannot pass as complete descriptions.
- Waited for the reopened picker document and reacquired stale frame references before uploads, fixing intermittent failure on the second detail image.
- Validation: 166 tests passed, including 48 isolated Chrome DOM tests; six consecutive two-image insertion checks passed. Independent Standards and Spec reviews have no remaining findings. Real seller upload/save/reopen acceptance remains pending.
- Known limitation: persistent receipt reuse across runs remains outside this repair. This is a test build, not a stable release.

## 0.4.19 - 2026-09-10 (Validation Build)

- Correlated picker upload responses with validated local assets using unique multipart filenames.
- Verified platform-processed images using the exact media ID and URLs declared by the correlated success response.
- Confirmed the automatically selected single image before inserting it, rejecting wrong or extra selections.
- Reused confirmed processed media across SKUs within one run; retained strict content verification for uploads without receipts.
- Added bounded album lookup and explicit not-started reporting when uncertain SKU media blocks later details/weight stages.
- Validation: 154 tests passed, including 39 isolated Chrome DOM tests. Real seller-frame upload, full details and save/reopen acceptance remain pending.
- Known limitation: confirmed receipt reuse is not persisted across runs; repeated runs can upload the same processed asset again. This is a test build, not a stable release.

## 0.4.18 - 2026-09-10 (Validation Build)

- Scoped sales dimensions by label and verified generated SKU combinations.
- Verified committed attribute values instead of editable search text.
- Matched weights by complete SKU identity and preserved the 1000g missing-weight fallback.
- Cancelled unexpected native dialogs with bounded recovery and protected active editors.
- Contained SKU image transaction errors and blocked saving on uncertain outcomes.
- Verified SKU image content and row association, including replacement, repeat runs and draft readback.
- Reused verified picker media across local filenames and allowed recovery from transient content-fetch failures.
- Known limitation: platform thumbnails, recompression or transcoding can prevent content verification. Live seller save/reopen acceptance remains incomplete; this is not a stable-release certification.
- Video support and shipping-time configuration remain outside this repair.

## 0.4.17 - 2026-09-09

- Fixed the SKU image add-button picker to use a valid CSS locator.

## 0.4.16 - 2026-09-09

- Recognized two-dimensional SKU sale properties by spec blocks instead of placeholder keywords.
- Filled plain-text properties directly and stopped double-committing searchable select values.
- Dismissed unexpected native dialogs and unrelated overlays between fill steps.

## 0.4.15 - 2026-09-09

- Mapped per-SKU package weights through the seller logistics spec column when rows expose no SKU id or merchant code.
- Configured SKU images through the seller row-level add-button picture picker in addition to direct file inputs.

## 0.4.14 - 2026-09-09

- Collected SKU images from `skuModel.skuProps` sale-property values.
- Used seller-row merchant codes as a validated fallback for per-SKU package weights.
- Restored the unified 1000g fallback when source weights are unavailable or cannot be reliably mapped.

## 0.4.13 - 2026-09-09

- Added SKU image collection and per-SKU seller-page configuration with source SKU ID and unique specification matching.
- Added read-only SKU image capability probing and fail-closed handling for unsupported row-level controls.
- Added SKU image quality-gate validation, content-hash reuse, media-manifest structure validation, and launcher switches for collection/configuration.
- Video collection and configuration remain deferred.

## 0.4.12 - 2026-09-08

- Fixed required multi-select properties by removing conflicting seller-page prefill values and avoiding mutually exclusive `不限` selections.
- Applied the seller form's documented `是否IP授权=否` default only when the source listing has no IP-license value; other missing required attributes remain blocked.
- Retried async searchable enum options after entering the requested value.

## 0.4.11 - 2026-09-08

- Fixed required enum properties such as `玩具材质` remaining empty after a direct-text fallback; selection now uses the active dropdown and requires a confirmed selected value.
- Fixed `最小起订量` values that were visible in the DOM but missing from the Ant form state by reacquiring the remounted control and validating its numeric/error state.

## 0.4.10 - 2026-09-08

- Unified SKU price-field detection so `批发价` is used consistently during fill, pre-save validation, and reopen verification.
- Preserved missing multi-SKU prices as invalid data instead of silently replacing them with the product-level price.
- Required reliable SKU identifiers before applying different collected package weights; skipped weight filling when neither source data nor an explicit override exists.
- Reported incomplete or invalid previews instead of returning success when SKU, quotation, weight, or page validation checks fail.
- Reduced property-option polling and removed ambiguous substring option matching.

## 0.4.9 - 2026-09-07

- Read per-SKU prices from `skuInfoMap` when 1688 separates prices from the SKU stock/spec map.
- Correctly detect multi-price products and select `按产品规格报价` for those listings.

## 0.4.8 - 2026-09-07

- Recovered pending browser alert dialogs before product collection navigation and retried the navigation once when DrissionPage reports `AlertExistsError`.

## 0.4.7 - 2026-09-07

- Preserved each SKU's own price from the source `skuMap` instead of replacing it with the product-level price.
- Automatically selected `按产品规格报价` and filled row-level prices when a product has multiple distinct SKU prices.

## 0.4.6 - 2026-09-07

- Retried asynchronously rendered category-property options so collected values such as `戏水玩具类别=玩沙工具` are selected reliably.
- Used the logistics batch-weight control for uniform weights, removing unnecessary per-SKU browser round trips and waits.

## 0.4.5 - 2026-09-07

- Collected seller-provided package weights and mapped them to logistics SKU rows.
- Used a validated 1000g fallback when source weights are unavailable, with reopen verification against the actual values written.

## 0.4.4 - 2026-09-07

- Collected structured 1688 decision attributes such as material, function, and packaging method from the newer page layout.
- Canonicalized legacy material labels such as `玩具材质` to `材质` for target-category matching.
- Source-collected attribute values are used automatically; category rules are only needed for missing values or intentional overrides.

## 0.4.3 - 2026-09-07

- Defaulted the publishing category to the collected source leaf category.
- Kept explicitly configured or captured target categories as overrides.
- Added category-source regression coverage.

## 0.4.2 - 2026-09-07

- Fixed hidden total-stock controls from contaminating interval price fields.
- Read interval prices by semantic columns and validate the actual price input.
- Preview runs now keep the browser open for manual review and clearly report that no draft was saved.
- DrissionPage target-detach messages remain diagnostic only; save success is decided by draft ID and reopen verification.

## 0.4.1 - 2026-09-07

- Fixed SKU name cleanup so embedded text such as `（颜色随机）` is preserved.
- Prevented distinct source SKUs from collapsing into duplicate `随机）` combinations.
- Added regression coverage for the cleanup behavior.

## 0.4.0 - 2026-09-07

- Added interactive target-category capture from the seller category selection flow.
- Added URL/DOM/HTML `catId` evidence checks and explicit operator confirmation before configuration write.

## 0.3.0 - 2026-09-06

- Added a standalone Windows GUI for collection, configuration, validation, preview, and draft saving.
- Added per-user runtime initialization under LocalAppData with a configurable `DRAFT_TOOL_HOME` override.
- Added source installation, test, and reproducible PyInstaller build scripts.
- Added operator and environment manuals plus a versioned Windows release package.

## 0.2.0 - 2026-09-06

- Added strict finite price, integer stock, weight, and configuration validation.
- Restricted collected main images to structured 1688 galleries and secured downloads.
- Confined all runtime assets to the product and per-run directories.
- Added fail-closed formal-publish guards and exact SKU/reopen verification.
- Added store-and-offer idempotency ledger, seller-profile locking, unique run IDs, and atomic reports.

## 0.1.0 - 2026-09-06

- Created an isolated draft-only delivery project.
- Added external store/category configuration and per-run configuration records.
- Added a pre-browser product quality gate.
- Split CLI, configuration, quality validation, browser actions, SKU logic, and collection logic.
- Removed silent title truncation and automatic guessing of missing required attributes.
- Added an independent Git repository and packaging metadata.
