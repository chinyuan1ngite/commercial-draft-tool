# Collection navigation blocked by native dialogs

Date: 2026-09-11
Status: resolved
Review baseline: 4aac3db

Continue the user-authorized repair/test/package workflow for the supplied
AlertExistsError at collect_with_browser -> navigate_with_alert_recovery -> Page.navigate.

## Acceptance

1. Source collection uses a separate available debugging port instead of attaching
   to the seller browser on the shared default port, while preserving its configured
   buyer profile and login persistence.
2. Navigate a fresh owned tab so a restored tab's persistent beforeunload handler
   cannot block collection. Do not accept arbitrary confirmation or leave dialogs.
3. Close only the browser created for collection, retaining the existing cleanup
   behavior within that owned session. Report browser startup failures clearly.
4. Bounded alert retries that are exhausted raise a controlled PopupRecoveryError
   handled by the collector CLI, instead of leaking the original AlertExistsError.
5. A browser navigation that returns False is not treated as successful collection.
6. Keep other collection parsing, media, seller configuration and publish behavior
   unchanged. Verify regressions, review and the packaged validation build.

## Evidence limits

The user's trace omits dialog type/text. Persistent beforeunload reproduces the
exact failing call chain; it is a confirmed defect, not proof of the original
dialog's type. No real seller/source session is modified by the isolated tests.
