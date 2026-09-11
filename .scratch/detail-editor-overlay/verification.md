# Property overlay diagnosis and verification

Date: 2026-09-11
Baseline: 839415d

## Observed evidence

- User-supplied runs for offer 839937633920 at 09:49 and 10:08 both prepared
  15 source detail images into six local upload images, with no rejected images.
- The component attempt/retry returned text_component=false, saved=false,
  retry_allowed=true, without reaching detail-image upload batches.
- Both saved page snapshots show `.cat-prop-apply-modal` (property application),
  with Cancel and Submit Application buttons but no modal close button.
- The new editor preview still contains its empty-state prompt and zero images.
  The legacy iframe resides under a display:none container, although the report
  counts 15 image elements in that hidden document after fallback. Its JavaScriptError
  is a secondary fallback failure; it does not establish visible detail completion.
- Existing cleanup already runs before the SKU and description stages, but only
  recognized close controls. It therefore left this blocking dialog on the page.

## Feedback loop and controls

- Debug harness: `.local/diagnose_detail_overlay.py --overlay`. It runs the actual
  component function in isolated headless Chrome with the observed dialog classes,
  Cancel/Submit controls and blocking mask. Upload responses are fulfilled locally.
- With overlay: failed in 12.841s with the same empty component result as the user
  report; zero text commits, uploads and image commits; application not submitted.
- Same fixture with only Cancel clicked: passed in 8.968s, one text commit and
  one confirmed image. Without overlay: passed in 9.284s. These controls isolate
  the blocking overlay from an editor or image-asset failure in this reproduction.
- Formal regression `test_detail_recovers_property_application_overlay_before_filling`
  first failed in 13.230s, then passed in 9.331s after the cancellation repair.
- `test_legacy_hidden_editor_is_not_written` first failed because the hidden body
  received text/image HTML; after the visibility guard it passed in 2.106s.
- `test_detail_blocks_property_overlay_without_enabled_cancel` passed in 4.357s;
  the known dialog is explicitly blocked without submitting or uploading anything.

## Repair

- Cancel only a unique visible enabled button with normalized label 取消 in the
  known property-application dialog; preserve active pickers/schema editors.
- Check that the dialog disappears within a bounded wait before proceeding, and
  report property_application_cancelled or a specific blocking error.
- Decline a hidden legacy editor before any DOM/media write. Identity verification,
  uncertain-upload handling and source-order confirmation remain unchanged.

## Limits

The saved real-page artifacts and isolated replay establish this blocker. No real
seller interaction, upload, draft save or reopen was performed during diagnosis.
Native frame-detach warnings and other reported SKU/required-field issues are not
claimed resolved by this bounded repair. Final test/review/package evidence follows.

## Full suite and independent review

- `DRAFT_BROWSER_TESTS=1 python -m unittest discover -s tests -v`: 169 tests
  passed in 263.294s, exit code 0, including 51 isolated Chrome DOM tests.
- Log: `.local/full-suite-0.4.21.log`. Syntax validation and diff check passed.
- Independent Standards review of `839415d...d32e463`: 0 findings, no documented
  breaches or actionable baseline smells. Independent Spec review: 0 findings,
  no missing implementation requirements or scope creep. Packaging remained the
  delivery step after review.

## Final reproduction and package

- Re-ran `.local/diagnose_detail_overlay.py --overlay` with the caller's existing
  popup-recovery step: passed in 9.464s. It reported property_application_cancelled:1,
  confirmed text and one image, and no property application submission. Debug
  artifacts remain in `.local`; no debug instrumentation was added to production.
- Built 0.4.21 with `scripts/build.ps1` in the previously verified Tcl-capable
  environment, using existing local dependencies and PIP_NO_INDEX=1. Build exit 0.
- `dist/Commercial1688DraftTool-0.4.21-win64.zip`: 29,295,884 bytes, 18 entries.
- Archive SHA-256: `BCE516F50C4AC81F2E8971F636F4A4C0F942E100523F6B8F72F3FC3E66FA175D`.
- EXE SHA-256: `2D95504DEAEB0BF0C6FCFECE01838DD51F716E04DA28D62354F40F731412B328`.
- CRCs, required files, version, executable digest and absence of runtime data
  passed `.local/verify_release_0_4_21.py`. Extracted EXE --smoke-test returned
  version 0.4.21 in a fresh isolated runtime; --cli --help exited 0.
- Detailed result: `.local/package-verification-0.4.21.json`. Old versioned
  packages are preserved; no real seller upload/save/reopen was performed.
