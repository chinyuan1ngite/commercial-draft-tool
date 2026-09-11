# Native navigation diagnosis

Date: 2026-09-11
Baseline: 4aac3db

## Reproduction and controls

- `.local/diagnose_navigation_alert.py --mode beforeunload` reproduces the user's
  exact call chain and AlertExistsError in isolated headless Chrome: failed in 9.831s.
- A one-time beforeunload handler passed in 2.786s; an ordinary existing alert
  passed in 2.743s. Cancelling a persistent leave confirmation leaves the old page
  in place, so the second navigation creates another prompt and exhausts recovery.
- Both collector and seller options used DrissionPage's default 127.0.0.1:9222.
  This provides a route for the collector to attach to the existing seller browser
  instead of starting its configured buyer profile. The user's trace alone does
  not establish whether this happened in the original run.

## Regression evidence

- `test_collection_navigates_new_tab_despite_restored_beforeunload` exercises the
  actual collector with a real isolated browser and locally fulfilled product URL.
  Browser construction is injected at the external library boundary to supply a
  restored tab with sticky user activation and beforeunload. It first failed with
  AlertExistsError in 7.174s, then passed in 15.855s with target HTML/body after repair.
  It also checks a non-default connection port and unchanged configured profile.
- `test_navigation_reports_persistent_leave_dialog_without_raw_error` first failed
  with raw AlertExistsError in 8.038s, then passed in 8.108s with a controlled
  navigation_blocked_by_native_dialog result. It cancels the pending dialog and
  leaves acceptance decisions unchanged.
- `test_failed_navigation_does_not_report_success` first failed because False was
  accepted as success; the shared navigation boundary now rejects that result.

## Scope and limits

No real browser session, store upload, draft save or publish was performed.
Debug scripts stay under `.local`; no debugging instrumentation enters production.

## Final validation

- Full suite: 172 tests passed in 285.425s, including 53 isolated Chrome DOM tests.
- Standards and specification reviews of 4aac3db...2d58f98 each reported zero findings.
- Offline PyInstaller build completed for 0.4.22, with Tcl initialization checked.
- Packaged ZIP: 19 files, 29,299,053 bytes; all CRCs and required files verified.
- ZIP SHA256: ADADEA9C9CC0CE59B18B168701481328F83881EF09EBAF728757D727C9A2B4BF.
- Executable SHA256: FDFD65F6C0C848CA29382247AB87543BBF004654B3136A5A1E7077686D0077C7;
  matches the internal SHA256SUMS.txt.
- Extracted executable passed --smoke-test (version 0.4.22, isolated runtime)
  and --cli --help. Package contains no user configuration, profiles or collected data.
- Full machine-readable verification: `.local/package-verification-0.4.22.json`.
