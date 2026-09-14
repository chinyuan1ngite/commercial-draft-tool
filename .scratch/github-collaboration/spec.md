# Private GitHub collaboration and release verification

Status: claimed

Baseline: `8b7c7b1`

## Goal

Prepare this repository for private GitHub collaboration with reviewable issue and pull-request workflows, Windows CI, and a repeatable package validation process. Keep real profiles, credentials, runtime data, reports, and collected products outside Git.

## Scope

- Add GitHub issue forms, a pull-request template, and least-privilege Windows workflows.
- Make version consistency and release archive validation reusable from a clean clone.
- Make install, test, and build scripts propagate native command failures.
- Prevent accidental replacement of a same-version local release archive.
- Document maintenance, triage, release, rollback, and the transition from local specs to GitHub Issues.
- Audit the Git history and refs that will be pushed before creating the private remote.
- Create the private GitHub repository, push `main`, and configure available branch rules after local verification.

## Acceptance criteria

- Non-browser CI installs the project, checks dependencies and versions, compiles source/tests/examples, and runs the default test suite on Windows.
- Browser regression and release packaging are explicit manual workflows and do not use real account profiles.
- A tracked verifier checks archive paths, required files, version, executable hash, smoke test, and CLI help; its structural checks have synthetic-archive tests.
- Build dependencies and packaged documentation are explicit, and the build refuses an existing same-version output unless the maintainer opts in.
- Issue and PR forms collect platform, environment, acceptance, compatibility, validation, and sanitization information.
- Collaboration and maintenance docs identify GitHub Issues as the task-status source after the remote is established, while repository specs and ADRs remain durable design records.
- Tests pass, documentation links resolve, and the existing 0.4.24 ZIP hash is unchanged.
- The remote repository remains private. Collaborator invitations and public licensing wait for concrete accounts and an owner decision.

## Verification

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`: 182 tests discovered, 126 executed and passed, 56 browser tests skipped by design.
- `python scripts/check_version.py`: passed for `0.4.24`.
- `python -m unittest tests.test_documentation tests.test_project_automation -v`: 7 passed.
- `scripts/verify_release.py` against the existing 0.4.24 ZIP: CRC, required files, safe paths, version, executable SHA256, `--smoke-test`, and `--cli --help` passed.
- Existing ZIP SHA256 remains `BA2242BDE8F27F1C319C1B74284071985F1476F66110363EEB584BE10811705A`.
- History audit: only `main` is reachable; 54 commits scanned with no high-signal credential hits, browser/runtime data paths, local absolute paths, or oversized blobs reported.
- Local build was intentionally not performed: the existing same-version output is protected, and this machine's Tcl/Tk installation cannot initialize. CI's clean Windows runner is the build environment.

## External follow-up

The local GitHub preparation is complete in commit `7ef3a03`. Creating the private remote and pushing `main` still requires an authenticated GitHub account and final repository owner/name. No remote, collaborator invitation, branch rule, or public release was created in this environment.
