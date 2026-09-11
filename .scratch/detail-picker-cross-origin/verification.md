# Detail picker cross-origin transition verification

Date: 2026-09-11
Baseline: 83c8d66

## Field evidence

- Twelve downloaded detail assets were normalized successfully into five valid
  long images; no source image was rejected.
- The first picker batch failed at `prepare` with `ContextLostError`, before any
  upload side effect. The saved result contained the text component, zero inserted
  images and zero visible preview images.
- The worker log repeatedly recorded detached Chromium targets and failed target
  WebSocket connections, consistent with an iframe target transition.

## Red/green loop

- The previous regressions replaced same-origin iframe documents after album-tab
  and search actions. They did not model the picker's initial cross-origin switch.
- The new fixture serves the parent at `localhost` and the picker at `127.0.0.1`.
  Clicking the image control first exposes `about:blank`, then navigates that iframe
  to the second origin after 250 ms.
- Baseline 83c8d66 failed this test in 8.660 seconds with the field signature:
  text saved, one requested image, zero inserted images, zero preview images,
  `ContextLostError` during `prepare`, and no possible side effect.
- The repaired code passed the identical test twice, in 8.732 and 8.780 seconds.
- All 15 detail-related browser tests passed in 89.822 seconds, including upload
  receipt, album reuse, iframe replacement, source-order and preview verification.

Full-suite and package verification results are added after the release build.
