# Detail Image Receipt Verification

Baseline: c934662e504645eda6e0f9c9aecd48fccd406f0f
Date: 2026-09-11

## Red / Green

All browser commands use `DRAFT_BROWSER_TESTS=1` and isolated headless Chrome.

- `python -m unittest discover -s tests -p test_browser_dom.py -k test_detail_upload_inserts -v`:
  failed with inserted=0 and `detail image not visible in album`, then passed with
  one confirmed processed image, one upload and one commit, without album entry.
- `python -m unittest discover -s tests -p test_browser_dom.py -k test_detail_text_success -v`:
  failed because saved=true with zero images, then passed with text_saved=true,
  saved=false, retry_allowed=false, indeterminate images and preview_partial.
- `python -m unittest discover -s tests -p test_browser_dom.py -k test_detail_without_receipt -v`:
  album-only original-byte upload first failed, then passed with verified content.
- All eight detail browser tests passed in 42.973s. They cover ordered two-image
  component insertion, existing preview preservation, unrelated request identity,
  wrong/extra pool items, wrong preview despite count increase, and legacy byte
  verification. External upload and image responses are fulfilled locally.
- Five media report tests passed, including incomplete and complete description
  preview/save classification. Syntax validation and `git diff --check` passed.

## Limits

No real seller upload/save/reopen was performed. Genuine cross-origin frame and
editor-generated additional derivative URLs still require live acceptance.
Broader SKU transaction and persistent store ledger tasks are not closed here.
Full-suite, independent review and package evidence will be appended below.

## Resumed review and verification (2026-09-11)

- Resumed from clean implementation commit `a748e6f`; the previous full-suite
  command (`DRAFT_BROWSER_TESTS=1 python -m unittest discover -s tests -v`)
  completed successfully with exit code 0 in 251.506s, as recorded in the original task.
- Both earlier review agents had stopped on quota errors. Two independent reviews
  were rerun against baseline `c934662e504645eda6e0f9c9aecd48fccd406f0f`.
- Standards: 0 findings. Spec: one P2 found and fixed. The shared gate previously
  treated absent image status as confirmed, accepting legacy fallback's unverified
  counts (51 requested URLs could produce 50 elements and still pass preview/save).
- Added a report-boundary regression: unverified legacy counts first passed the
  gate incorrectly (red), then returned blocked_incomplete_description (green).
- Added an isolated legacy-editor regression: invalid image URLs first yielded
  saved=true and inserted=51 (red), then text_saved=true, saved=false, inserted=0,
  indeterminate images and preview_partial (green). The editor has no image-identity
  readback, so URL-only writes cannot be treated as confirmed media.
- Legacy write outcomes are retained in the final description report, and retries
  are disabled before the write begins. Shared gates require explicit confirmation.
- Browser startup failed in the restricted sandbox; the authorized isolated
  headless Chrome regression passed outside it. No signed-in browser was used.
- Independent follow-up reviews of the implementation and working changes:
  Standards 0 findings; Spec 0 remaining findings, prior P2 closed.
- Updated release metadata to 0.4.20. Source launcher smoke test reports 0.4.20
  using an isolated `.local/source-smoke-0.4.20` runtime; compileall and diff check pass.

## Picker reopen timing repair

- First resumed full suite ran 166 tests in 252.133s and found one failure in
  `test_detail_components_confirm_two_images_in_source_order`: the second image
  failed during prepare with ElementLostError, after the first image was confirmed.
- Debug-only `.local/diagnose_detail_reopen.py` repeats that public-boundary test
  six times. Before the fix it reproduced twice in 51.482s. Targeted exception
  traces located both failures in `_picker_pool_count`, called by `_picker_clear_pool`
  immediately after reopening the picker. Neither failure had uploaded image two.
- Reopening changes the iframe document while the prior frame reference can still
  be returned. Preparation now waits for document load and reacquires a lost frame
  at most three times, only for ElementLostError/ContextLostError before media writes.
  Upload or submission operations remain outside the recovery loop.
- The same six-run repro passed in 54.705s after the fix, with two confirmed images
  in source order on every run. Instrumentation stayed in the ignored debug harness;
  no production logging was added.
- Independent incremental review: Standards 0 findings; Spec 0 findings.

## Final full suite

- `DRAFT_BROWSER_TESTS=1 python -m unittest discover -s tests -v`: 166 tests
  passed in 252.276s (48 isolated Chrome DOM tests), exit code 0.
- Full log: `.local/full-suite-0.4.20-final.log`. Earlier failed-run and repeated
  reproduction logs are preserved separately for diagnosis history.

## Build and package verification

- Initial sandbox build omitted tkinter after PyInstaller reported Tcl initialization
  unavailable. The packaged launcher failed before main with ModuleNotFoundError:
  tkinter (confirmed with an isolated console diagnostic build). Old 0.4.19 started
  successfully under the same startup harness, ruling out a general launch failure.
- The virtualenv's `tkinter.Tcl()` fails in the restricted sandbox but succeeds
  outside it (Tcl 8.6.13). Added a build-script preflight that fails explicitly before
  packaging if Tcl cannot initialize. Independent Standards/Spec reviews: 0 findings.
- Rebuilt with `scripts/build.ps1` outside the sandbox using existing dependencies,
  `PIP_NO_INDEX=1` and a workspace PyInstaller cache. The final build includes
  `_tkinter` and `pyi_rth__tkinter.py`. Build exit code 0; log in
  `.local/build-0.4.20-final.log`.
- Final archive: `dist/Commercial1688DraftTool-0.4.20-win64.zip`, 29,293,217 bytes.
- Archive SHA-256: `FB76B0DBE113AC3FB5E6316346885D3F56FD7B0C025CE6818E33ECBBC0A8711D`.
- Executable SHA-256: `263E7A1A0284E8FD8C21BC95004F381BFF3873FD6DC312D0949A46A6C046763B`.
- `.local/verify_release_0_4_20.py` checks all archive CRCs, required files, version,
  executable hash, absence of runtime/profile/config data, then extracts to a fresh
  temporary workspace directory. All 17 entries passed. Packaged `--smoke-test`
  returned version 0.4.20 with the isolated runtime; packaged `--cli --help` exited 0.
- Verification result: `.local/package-verification-0.4.20.json`. Old versioned
  packages were preserved. No real seller upload, draft save or reopen was performed.
