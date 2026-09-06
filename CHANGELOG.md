# Changelog

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
