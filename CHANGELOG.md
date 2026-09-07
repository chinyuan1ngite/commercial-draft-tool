# Changelog

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
