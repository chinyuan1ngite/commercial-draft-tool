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
