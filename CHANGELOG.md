# Changelog

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
