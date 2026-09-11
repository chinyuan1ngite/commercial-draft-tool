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

Full browser-suite and package evidence will follow.
