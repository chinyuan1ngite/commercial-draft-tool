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

## Release verification

- Non-browser suite: 175 tests discovered, 119 passed and 56 opt-in browser
  tests skipped in 1.143 seconds.
- Full suite: 175 tests passed in 315.771 seconds, including 56 isolated
  Chrome tests.
- Offline PyInstaller build completed for 0.4.24 after Tcl initialization passed.
- Packaged ZIP: 21 files and 29,304,560 bytes; archive CRCs, required files and
  path-safety checks passed.
- ZIP SHA256: BA2242BDE8F27F1C319C1B74284071985F1476F66110363EEB584BE10811705A.
- Executable SHA256: 130E2FFC54057ED45DA2B61953BA5E4EFBC756361A5A50D4E6411C85793F584A;
  it matches the packaged `SHA256SUMS.txt`.
- The extracted executable passed `--smoke-test` with version 0.4.24 and an
  isolated runtime, plus `--cli --help`.
- The previous 0.4.23 ZIP still has SHA256
  75C470D83A54B2C5ED8D211E5C7AC6BE19E506F47D4FE016499863C130E0CDA8.
- Machine-readable result: `.local/package-verification-0.4.24.json`.
