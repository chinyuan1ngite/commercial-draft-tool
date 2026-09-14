# Extract the existing 1688 implementation into a platform package

Status: resolved

Baseline: `98345c6`

## Goal

Concentrate code that knows 1688 source and seller-page protocols under `draft_tool.platforms.alibaba1688`, while preserving every existing executable entry point, import path, product format, runtime directory, report field, and ledger key.

## Scope

- Move the existing collector, seller browser actions, navigation recovery, and category capture implementations into the 1688 package.
- Keep `draft_tool.collector`, `draft_tool.browser_actions`, `draft_tool.browser_navigation`, and `draft_tool.category_capture` as module aliases for compatibility.
- Make new internal callers use the canonical 1688 package.
- Document the current platform module interface and the next extraction steps.

## Non-goals

- No generic platform base class or speculative adapter interface before a second implementation exists.
- No product/schema/config/report/ledger migration.
- No selector, upload, save, reopen, or formal-publish behavior change.
- No version bump or Windows package rebuild.

## Acceptance criteria

- The four old import paths and four new import paths resolve to the same module objects.
- Existing patch paths continue to replace globals used by the moved implementation.
- `draft-collect`, launcher collection/category capture, and workflow execution keep their current arguments and results.
- Old `product.json` fixtures pass unchanged and the full non-browser suite has no regressions.
- Isolated browser tests remain opt-in and the existing real-page acceptance limitation remains documented.

## Verification

- `python -m unittest tests.test_platform_namespace tests.test_workflow tests.test_category_capture tests.test_security_and_collector -v`: 36 passed.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`: 186 discovered, 130 executed and passed, 56 browser tests skipped by design.
- The same command with `-Browser`, run outside the restricted sandbox so it could start isolated headless Chrome: 186/186 passed, including all 56 browser tests.
- Legacy `draft-collect`, `python -m draft_tool.collector`, `python -m draft_tool.browser_actions`, and `python -m draft_tool.category_capture` help/smoke entry points passed.
- A local wheel built without network isolation contains all four legacy aliases, all four canonical 1688 implementation modules, and both package initializers.
- `git diff --check` passed. Version remains 0.4.24 and no Windows release package was rebuilt.
