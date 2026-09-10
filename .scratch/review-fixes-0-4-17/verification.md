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

## Album Lookup Follow-Up (2026-09-10)

Baseline: 83d0fc4479e43b680dc95ca114d73f8fa078b711. Existing uncommitted 0.4.18 packaging edits were preserved and excluded from this implementation.

Red/green commands use DRAFT_BROWSER_TESTS=1 and the same isolated Chrome fixtures:

- `python -m unittest discover -s tests -p test_browser_dom.py -k truncated -v`: initially indeterminate with uploaded_media_identity_unconfirmed; now confirmed, selecting the correct bytes rather than an identically truncated old title.
- `python -m unittest discover -s tests -p test_browser_dom.py -k waits_for_album -v`: initially indeterminate when the album appears 2200ms after upload progress; now confirmed with one upload and one commit.
- `python -m unittest discover -s tests -p test_browser_dom.py -k reports_missing_record -v`: missing record and wrong bytes both remain indeterminate, differentiated by candidate/content-mismatch counts; one upload, no commit in either case.
- `python -m unittest discover -s tests -p test_media_stage_report.py -v`: three report-boundary tests pass, including preservation of existing stage results and no blocked markers for confirmed media.

The lookup fixes do not solve platform recompression. Reads of the four observed original/thumbnail pairs in the supplied run report did not match local uploaded bytes. The actual successful network read was checked separately from the verifier's false result. No guessed URL rewrite, perceptual acceptance, cookie-bearing capture, or new remote upload was used. Authentic transaction-correlated platform identity evidence remains required; tasks 06/07 are still incomplete.

Full-suite result for dd201fa: 150 tests passed in 156.455s, including 35 isolated Chrome DOM tests. `compileall -q src tests` and `git diff --check` passed. DrissionPage again emitted its startup subprocess ResourceWarning; test teardown completed. No static type checker is configured in pyproject.toml; compileall is syntax validation, not type checking.

### Standards Review

Independent review of `git diff 83d0fc4479e43b680dc95ca114d73f8fa078b711...dd201fa`: zero findings. Prefixes remain candidate locators, exact content verification is retained, polling does not reupload, and the report preserves prior results. No product-specific behavior was introduced in production code. Pagination, candidate volume and asynchronous remote search remain verification risks, not demonstrated new defects.

### Spec Review

Independent review of the same range: one pre-existing P1 incomplete requirement, no newly identified definite violation or scope creep. Spec R7 and AC18 still require transaction-specific source-to-platform identity evidence and complete seller/reopen acceptance. Processed platform bytes can still cause indeterminate status and prevent details from executing. Search, polling and not_started reporting are partial repairs, not end-to-end resolution. The new DOM fixture does not establish actual platform search pagination, asynchronous request ordering or processing compatibility. Tasks 06/07 remain incomplete; no release claim is made.

## Correlated Receipt Follow-Up (2026-09-10)

User-supplied upload evidence establishes a single-image success schema with a platform ID and declared original/thumbnail URL pair. Production code uses the endpoint/schema, not the user's particular SKU, image ID or image URL. Unique temporary upload names and multipart filename checks correlate the result to the validated local source. Original source assets are not renamed or changed, and temporary copies are cleaned up. No credentials or complete network packet enter reports.

Red/green: `DRAFT_BROWSER_TESTS=1 python -m unittest discover -s tests -p test_browser_dom.py -k processed_upload_response -v` originally returned indeterminate after an automatically selected processed image. With the receipt path it returns confirmed, one upload/commit, and readback verification succeeds; swapping the displayed image fails. The browser executes a real multipart request with the response fulfilled locally by CDP. It does not contact the seller endpoint or use a seller profile.

Targeted results: four processed-upload tests (including parameterized invalid-response and pool cases) pass; seven original picker regressions and seven fault-boundary regressions pass. Syntax validation passes. Full integration and independent two-axis review results follow below when complete.

Limitations remain explicit: genuine cross-origin seller-frame behavior, full details/save/reopen and persistent store-scoped reuse between runs have not been accepted. Within one configure call, identical media across SKUs uploads once; report-carried receipts support read-only reopen verification. No claim of persistent ledger idempotency or processed direct-file-input support is made.

Full suite for 5bef5f7: 154 tests passed in 209.553s, including 39 isolated Chrome DOM tests. `compileall -q src tests` and `git diff --check 83d0fc4479e43b680dc95ca114d73f8fa078b711...HEAD` passed. The prior DrissionPage startup ResourceWarning appeared; fixture teardown completed. No seller profile or real seller upload was used.

Independent Standards review: zero definite violations and zero actionable baseline smells. Independent Spec review: one P1 partial requirement remains, AC16 cross-run idempotency; receipt reuse is call-scoped, and a later run may upload the same processed asset again. No new definite wrong-media confirmation or scope creep was identified. Genuine cross-origin capture and full seller acceptance remain unverified. Tasks 06/07 remain incomplete.

The user subsequently authorized packaging a test build. Version 0.4.19 is selected to preserve the existing 0.4.18 package. Packaging does not close the remaining acceptance or persistent-reuse gaps.

### Test Package Validation

- Built with `scripts/build.ps1`, PyInstaller 6.22.2 and Python 3.12.2. The optional DrissionRecord hook warning did not stop the build; new `draft_tool.sku_upload` and `draft_tool.media_verification` modules are present in the archive table.
- Artifact: `dist/Commercial1688DraftTool-0.4.19-win64.zip`, 29,287,887 bytes.
- ZIP SHA-256: `3046C8FD7C91DC290CE110BDED51AA281A8545A65AA0A3AD412B80CC96D0932E`.
- EXE SHA-256: `7B554E50EDBE59B6A291263B9AAECD1A2EA927D205AB70F6488691512D3F51EA`, matched the packaged SHA256SUMS.txt after extraction.
- Extracted package VERSION and executable smoke output both report 0.4.19. Release notes are present; no settings.local.json, Cookies, Login Data, product.json or run_report.json was included.
- Extracted executable `--smoke-test` and `--cli --help` both exited 0. DRAFT_TOOL_HOME pointed to an isolated `.local/package-check-0.4.19-d87011ccf5b648ed9f27382d149d3121/smoke-runtime`; no existing user runtime was modified.
- Existing 0.4.18 versioned artifacts were retained. No real seller upload, save, reopen or publishing was performed.
