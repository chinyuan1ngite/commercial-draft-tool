# Detail picker cross-origin transition

Date: 2026-09-11
Status: resolved
Baseline: 83c8d66

Repair the remaining detail-image failure in which the text component is saved,
but the first image fails during picker preparation and no image reaches the
visible detail preview.

## Acceptance

1. Wait for the picker iframe to finish its initial `about:blank` document and
   expose the real picture-manager controls before using it.
2. Support the real same-window transition from a same-origin blank document to
   a cross-origin iframe target.
3. Preserve the existing rule that retries are allowed only before an upload or
   insert side effect may have happened.
4. Confirm requested images from the visible detail preview and keep a text-only
   result incomplete when images were requested.
5. Keep existing picker refresh, upload receipt, media identity, ordering and
   draft-only safeguards unchanged.

## Evidence limit

The field report for offer 908924253446 records five prepared detail images,
zero inserted images, zero preview images and `ContextLostError` at the prepare
stage. The isolated browser test reproduces that state with two local HTTP origins.
It does not upload to or save a real seller account.
