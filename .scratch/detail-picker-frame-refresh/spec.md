# Detail picker frame refresh

Date: 2026-09-11
Status: claimed
Baseline: 3b073b9

Repair the user-reported detail state in which the text component is visible but
all requested detail images remain absent.

## Acceptance

1. Use the current picture-picker iframe after album-tab and album-search actions
   replace its document.
2. Retry only before an upload side effect. Preserve the existing indeterminate
   handling once an upload or insert may have occurred.
3. Confirm each requested image by content identity in the visible detail preview.
4. A text-only component with requested images remains incomplete.
5. Keep source media identity, image ordering, picker ownership and publish guards
   unchanged.

## Evidence limit

The latest two real preview reports identify ContextLostError before the first
upload, with four requested images, zero inserted images and zero preview images.
The isolated browser regression reproduces the same visible result using an iframe
document replacement. It does not upload to or save a real seller account.
