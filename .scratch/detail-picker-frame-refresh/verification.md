# Detail picker frame refresh verification

Date: 2026-09-11
Baseline: 3b073b9

## Field evidence

- The two latest real preview reports both record `preview_partial`, four requested
  detail images, zero inserted images, zero preview images, and ContextLostError at
  the prepare stage before an upload side effect.
- The source product contains nine downloaded detail assets. They were successfully
  normalized into four valid long images, so missing or rejected source media is not
  the cause.

## Red/green loop

- `test_detail_reacquires_picker_replaced_when_album_tab_opens` failed twice before
  repair with text saved, zero images and ElementLostError, then passed with one
  verified preview image, one upload and one insert.
- `test_detail_reacquires_picker_replaced_by_album_search` failed before repair with
  the same text-only result, then passed with one verified preview image, one upload
  and one insert.
- These are the same DrissionPage lost-frame failure family as the field
  ContextLostError. The fixture replaces the picker iframe document deterministically.
- Non-browser suite: 174 tests discovered, 119 passed and 55 opt-in browser tests
  skipped in 1.017s.

- Full suite: 174 tests passed in 309.928s, including 55 isolated Chrome tests.
- Offline PyInstaller build completed for 0.4.23 after Tcl initialization passed.
- Packaged ZIP: 20 files, 29,301,960 bytes; archive CRCs and required files passed.
- ZIP SHA256: 75C470D83A54B2C5ED8D211E5C7AC6BE19E506F47D4FE016499863C130E0CDA8.
- Executable SHA256: 872B4E460C34531C7F4DF38DE52EE5C1A63414C20E3784AAB8C8DAA084718D94;
  it matches the packaged SHA256SUMS.txt.
- The extracted executable passed `--smoke-test` with version 0.4.23 and an
  isolated runtime, plus `--cli --help`. The package contains no user configuration,
  profiles, collected products or draft data.
- Machine-readable result: `.local/package-verification-0.4.23.json`.
