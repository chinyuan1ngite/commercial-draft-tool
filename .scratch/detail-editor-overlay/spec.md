# Detail editor blocked by property application overlay

Date: 2026-09-11
Status: resolved
Review baseline: 839415d

Continuation of the user-authorized detail-image repair and validation package.
Evidence: both 839937633920 runs supplied by the user show a visible
`.cat-prop-apply-modal`, no committed text component, and legacy fallback writes
into a hidden TinyMCE iframe while the visible detail preview stays empty.

## Acceptance

1. Existing popup recovery cancels the known property-application dialog via its
   unique enabled Cancel button, including labels with whitespace. Never submit it.
2. Verify the blocking dialog has closed before continuing. A dialog without a
   usable cancellation control blocks the workflow rather than clicking through it.
3. Preserve active image pickers and description schema editors during recovery.
4. Following recovery, the real detail component boundary confirms text and image
   insertion, preserving the existing identity, order and uncertain-write rules.
5. Never populate a hidden legacy editor as a fallback for the visible new editor.
6. Do not change SKU mapping, video, shipping or stored user configuration.
7. Run relevant regression and full-suite checks, independent review and package
   verification before delivering a new validation build. Live seller save/reopen
   remains distinct from isolated replay evidence.
