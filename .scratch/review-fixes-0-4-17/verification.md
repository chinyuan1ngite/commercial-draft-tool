# Review Repair Verification

Date: 2026-09-10
Product version: 0.4.17 (unchanged)
Baseline: 58fa651b4c1afa2353dc101215e2f594af25bd87
Implementation range before final review fixes: 58fa651...4c43485

## Automated Evidence

Command from repository root (PowerShell):

```powershell
$env:DRAFT_BROWSER_TESTS='1'
$env:PYTHONIOENCODING='utf-8'
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m compileall -q src tests
git diff --check
```

4c43485: 141 tests passed in 109.566s, including 30 isolated headless Chrome DOM tests, using DrissionPage 4.1.1.4. No seller account was used by these tests. The browser library emitted a subprocess ResourceWarning during startup; fixtures call page.quit at teardown. This warning is not represented as proof of a leaked process.

After review fixes: full suite 143 tests passed in 116.526s, including 31 browser DOM tests. One subsequent additional browser regression (correct existing image without an upload control) was demonstrated red, fixed, and passed in 3.147s; the 7 transaction fault tests passed again afterward. The repository now contains 144 tests; the last added case was run separately, not included in the 143-test full-suite count. Final compileall and git diff --check passed.

| Acceptance | Evidence | Remaining |
| --- | --- | --- |
| AC01-03 | Named dimensions, equal values, reversed order, repetition, ambiguous/prefilled dimensions and actual SKU combinations in sale-properties.html | Live seller coverage in 07 |
| AC04-05 | Search-only enum rejected, asynchronous selected options, multi-select replacement, plain text/textarea/custom blur | Live seller coverage in 07 |
| AC06-09 | Named weight mapping, 300/500/missing fallback, explicit fallback, common weight, conflicts and aliases | Live seller coverage in 07 |
| AC10-11 | Actual native alert/confirm/prompt, empty text, repeated dialogs, protected picker/editor and hidden controls | Live seller coverage in 07 |
| AC12-13 | Seven browser-boundary fault tests plus actual optional failure followed by weight/detail actions; required and indeterminate save gates | Full seller workflow not run |
| AC14-16 | Actual picker collisions, exact pool, stale counter/stalled upload, correct existing image, wrong-content count increase, unchanged-count replacement | Platform transformation/original identity association unresolved |
| AC17 | Read-only row reorder passes and swapped image/weight fails in DOM fixtures | Actual draft save and reopen not run |
| AC18 | Component-level multi-price, stock, weight, image and committed attribute coverage | Full representative seller workflow not run |

## Standards

Independent final Standards review identified:

1. Confirmed SHA-256 content could be reuploaded under another filename, conflicting with ADR 0003. Fixed by sharing verified platform candidates by content digest during the run; two SKU/different filename fixture now asserts one upload and two commits.
2. Maintenance risk: transaction dictionaries are mutated by the orchestrator and picker across stage, status, side-effect and recovery fields. Keep this as a follow-up risk; no broad refactor was performed during the repair. Existing transaction/save-gate tests constrain the supported transitions.

Earlier independent dialog review found the remaining save-time accept=True path and swallowed PopupRecoveryError; both were fixed. Tasks 02-03 and local completion checks for 04-05 recorded local two-axis review, not independent reviews.

## Spec

Independent media Spec review identified:

1. Temporary remote verification failures were cached permanently for the run. Fixed: only obtained content hashes are cached; bounded caller readback can retry a failed fetch. Added a network-boundary test with timeout followed by correct bytes.
2. Potential platform compatibility risk: displayed thumbnail/reencoded bytes may differ from the original. Current identity verifier fails closed, but there is no proven adapter from original content to platform identity to derived display media. Remains unresolved pending authentic platform evidence; task 06 stays claimed. Do not replace verification with filename, image count or a guessed thumbnail URL rewrite.

## Live Acceptance Blockers

- Browser inventory returned `Codex auth token is unavailable`; no seller tab state was available for this acceptance attempt.
- Local settings did not configure target.category_id, target.store_identity_text or target.delivery_promise. Do not infer a store, invent shipping configuration or bypass platform validation.
- The separate visible-description bug was not tested against a live editor. A visible TinyMCE fixture passed after optional image failure, which does not prove the actual component editor works.
- No live upload, draft save/reopen, formal publish, version bump or binary package was performed.

Tasks 06 and 07 are not complete. These automated results are not a stable-release claim.
